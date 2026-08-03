"""Integration smoke tests — no live cluster required.

Verifies that the full fraud-detection use-case module graph imports
cleanly and that config defaults wire up correctly.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rhoai.config.loader import load_config
from rhoai.usecases import registry
from rhoai.usecases.fraud_detection import assets


class TestModuleGraph:
    def test_registry_imports_fraud_detection(self) -> None:
        mod = registry.get("fraud-detection")
        assert mod is not None

    def test_deploy_verify_cleanup_callable(self) -> None:
        mod = registry.get("fraud-detection")
        assert callable(mod.deploy)
        assert callable(mod.verify)
        assert callable(mod.cleanup)


class TestConfigDefaults:
    def test_fraud_detection_defaults_present(self) -> None:
        config = load_config()
        fd = config.get("fraud_detection", {})
        assert fd.get("model_name") == "qwen2.5-1.5b-instruct"
        assert fd.get("inference_service_name") == "qwen"
        assert fd.get("serving_runtime_name") == "vllm-cpu-runtime"

    def test_timeouts_present(self) -> None:
        config = load_config()
        assert "operator_ready" in config["timeouts"]
        assert "dsc_ready"       in config["timeouts"]
        assert "inference_ready" in config["timeouts"]


class TestAssetPaths:
    def test_model_manifest_path(self, tmp_path: Path) -> None:
        p = assets.get_model_manifest(tmp_path, "qwen2.5-1.5b-instruct")
        expected = (
            tmp_path / "model-serving" / "generative-models" / "vllm" / "qwen2.5-1.5b-instruct.yaml"
        )
        assert p == expected

    def test_serving_runtime_path(self, tmp_path: Path) -> None:
        p = assets.get_serving_runtime_manifest(tmp_path)
        assert p == tmp_path / "model-serving" / "shared" / "vllm-serving-runtime.yaml"

    def test_guardrails_manifest_paths(self, tmp_path: Path) -> None:
        paths = assets.get_trustyai_guardrails_manifests(tmp_path)
        assert len(paths) == 3
        names = [p.name for p in paths]
        assert "configmap_orchestrator.yaml" in names
        assert "configmap_vllm_gateway.yaml" in names
        assert "orchestrator_cr.yaml"        in names

    def test_guardrails_apply_order(self, tmp_path: Path) -> None:
        """ConfigMaps must come before the Orchestrator CR."""
        paths = assets.get_trustyai_guardrails_manifests(tmp_path)
        names = [p.name for p in paths]
        assert names.index("orchestrator_cr.yaml") > names.index("configmap_orchestrator.yaml")

    def test_prometheus_rules_path(self, tmp_path: Path) -> None:
        p = assets.get_prometheus_rules_manifest(tmp_path)
        assert p == tmp_path / "trustyai" / "monitoring" / "prometheus-rules.yaml"


class TestDeploySmoke:
    """Smoke-test deploy() wiring with all I/O mocked."""

    def _make_config(self, tmp_path: Path) -> dict:
        config = load_config()
        config["repo_root"] = str(tmp_path)
        config["cluster"]["namespace"] = "test-ns"
        return config

    def test_deploy_calls_platform_modules(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        import importlib
        import sys

        # Force a clean import of the deploy *module* (not the function)
        sys.modules.pop("rhoai.usecases.fraud_detection.deploy", None)
        deploy_mod = importlib.import_module("rhoai.usecases.fraud_detection.deploy")

        prepare_mock   = MagicMock()
        operators_mock = MagicMock()
        operators_mock.is_installed.return_value = True
        dsc_mock       = MagicMock()
        storage_mock   = MagicMock()
        inference_mock = MagicMock()
        trustyai_mock  = MagicMock()

        monkeypatch.setattr(deploy_mod, "prepare",   prepare_mock)
        monkeypatch.setattr(deploy_mod, "operators", operators_mock)
        monkeypatch.setattr(deploy_mod, "dsc",       dsc_mock)
        monkeypatch.setattr(deploy_mod, "storage",   storage_mock)
        monkeypatch.setattr(deploy_mod, "inference", inference_mock)
        monkeypatch.setattr(deploy_mod, "trustyai",  trustyai_mock)

        config = self._make_config(tmp_path)
        deploy_mod.deploy(config)

        prepare_mock.prepare_platform.assert_called_once()
        dsc_mock.apply_dsci.assert_called_once()
        dsc_mock.apply_dsc.assert_called_once()
        dsc_mock.wait_until_ready.assert_called_once()
        storage_mock.apply_s3_secret.assert_called_once()
        inference_mock.apply_serving_runtime.assert_called_once()
        inference_mock.apply_inference_service.assert_called_once()
        inference_mock.wait_until_ready.assert_called_once_with(
            "qwen", "test-ns", config["timeouts"]["inference_ready"]
        )
        trustyai_mock.apply_guardrails.assert_called_once()
        trustyai_mock.apply_prometheus_rules.assert_called_once()
