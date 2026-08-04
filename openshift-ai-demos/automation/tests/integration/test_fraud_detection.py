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
        assert fd.get("inference_service_name") == "fraud-detection"
        assert fd.get("serving_runtime_name")   == "triton-ppc64le-runtime"
        assert fd.get("trustyai_service_name")  == "trustyai-service"

    def test_timeouts_present(self) -> None:
        config = load_config()
        assert "operator_ready"  in config["timeouts"]
        assert "dsc_ready"       in config["timeouts"]
        assert "inference_ready" in config["timeouts"]
        assert "trustyai_ready"  in config["timeouts"]


class TestAssetPaths:
    def test_serving_runtime_template_path(self, tmp_path: Path) -> None:
        p = assets.get_serving_runtime_template(tmp_path)
        assert p == (
            tmp_path
            / "model-serving"
            / "predictive-models"
            / "triton"
            / "triton-ppc64le-runtime-template.yaml"
        )

    def test_model_manifest_path(self, tmp_path: Path) -> None:
        p = assets.get_model_manifest(tmp_path)
        assert p == (
            tmp_path / "model-serving" / "predictive-models" / "triton" / "fraud-detection.yaml"
        )

    def test_trustyai_monitoring_path(self, tmp_path: Path) -> None:
        p = assets.get_trustyai_monitoring_manifest(tmp_path)
        assert p == tmp_path / "trustyai" / "service" / "monitoring-config.yaml"

    def test_trustyai_service_path(self, tmp_path: Path) -> None:
        p = assets.get_trustyai_service_manifest(tmp_path)
        assert p == tmp_path / "trustyai" / "service" / "trustyai-service.yaml"


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
        storage_mock   = MagicMock()
        inference_mock = MagicMock()
        trustyai_mock  = MagicMock()

        monkeypatch.setattr(deploy_mod, "prepare",   prepare_mock)
        monkeypatch.setattr(deploy_mod, "storage",   storage_mock)
        monkeypatch.setattr(deploy_mod, "inference", inference_mock)
        monkeypatch.setattr(deploy_mod, "trustyai",  trustyai_mock)

        config = self._make_config(tmp_path)
        deploy_mod.deploy(config)

        # Steps 1–3 collapsed into deploy_platform
        prepare_mock.deploy_platform.assert_called_once_with(config)

        # Step 4: S3 secret
        storage_mock.apply_s3_secret.assert_called_once()

        # Step 5: Triton Template → ServingRuntime, then InferenceService
        inference_mock.apply_serving_runtime_from_template.assert_called_once()
        inference_mock.apply_inference_service.assert_called_once()
        inference_mock.wait_until_ready.assert_called_once_with(
            "fraud-detection", "test-ns", config["timeouts"]["inference_ready"]
        )

        # Step 6: TrustyAI monitoring config + service
        trustyai_mock.apply_monitoring_config.assert_called_once()
        trustyai_mock.patch_inferenceservice_config.assert_called_once_with("test-ns")
        trustyai_mock.apply_trustyai_service.assert_called_once()
        trustyai_mock.wait_until_ready.assert_called_once_with(
            "trustyai-service", "test-ns", config["timeouts"]["trustyai_ready"]
        )
