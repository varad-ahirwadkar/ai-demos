"""Integration smoke tests for the vLLM use case — no live cluster required.

Verifies that the full vllm use-case module graph imports cleanly and that
config defaults wire up correctly.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rhoai.config.loader import load_config
from rhoai.usecases import registry
from rhoai.usecases.vllm import assets


class TestModuleGraph:
    def test_registry_imports_vllm(self) -> None:
        mod = registry.get("vllm")
        assert mod is not None

    def test_deploy_verify_cleanup_callable(self) -> None:
        mod = registry.get("vllm")
        assert callable(mod.deploy)
        assert callable(mod.verify)
        assert callable(mod.cleanup)


class TestConfigDefaults:
    def test_vllm_defaults_present(self) -> None:
        config = load_config()
        vllm = config.get("vllm", {})
        assert vllm.get("model")                == "qwen2.5-1.5b-instruct"
        assert vllm.get("serving_runtime_name") == "vllm-cpu-runtime"
        assert vllm.get("inference_service_name") == "qwen"

    def test_fraud_detection_defaults_still_present(self) -> None:
        """Adding vllm must not disturb existing fraud-detection defaults."""
        config = load_config()
        fd = config.get("fraud_detection", {})
        assert fd.get("inference_service_name") == "fraud-detection"


class TestAssetPaths:
    def test_serving_runtime_path(self, tmp_path: Path) -> None:
        p = assets.get_serving_runtime(tmp_path)
        assert p == tmp_path / "model-serving" / "shared" / "vllm-serving-runtime.yaml"

    def test_model_manifest_path_default(self, tmp_path: Path) -> None:
        p = assets.get_model_manifest(tmp_path, "qwen2.5-1.5b-instruct")
        assert p == (
            tmp_path
            / "model-serving"
            / "generative-models"
            / "vllm"
            / "qwen2.5-1.5b-instruct.yaml"
        )

    def test_model_manifest_path_phi3(self, tmp_path: Path) -> None:
        p = assets.get_model_manifest(tmp_path, "phi-3-mini-4k-instruct")
        assert p == (
            tmp_path
            / "model-serving"
            / "generative-models"
            / "vllm"
            / "phi-3-mini-4k-instruct.yaml"
        )

    def test_model_manifest_path_qwen3(self, tmp_path: Path) -> None:
        p = assets.get_model_manifest(tmp_path, "qwen3-4b-instruct-2507")
        assert p == (
            tmp_path
            / "model-serving"
            / "generative-models"
            / "vllm"
            / "qwen3-4b-instruct-2507.yaml"
        )


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

        sys.modules.pop("rhoai.usecases.vllm.deploy", None)
        deploy_mod = importlib.import_module("rhoai.usecases.vllm.deploy")

        prepare_mock   = MagicMock()
        storage_mock   = MagicMock()
        inference_mock = MagicMock()

        monkeypatch.setattr(deploy_mod, "prepare",   prepare_mock)
        monkeypatch.setattr(deploy_mod, "storage",   storage_mock)
        monkeypatch.setattr(deploy_mod, "inference", inference_mock)

        config = self._make_config(tmp_path)
        deploy_mod.deploy(config)

        # Steps 1–3 collapsed into deploy_platform
        prepare_mock.deploy_platform.assert_called_once_with(config)

        # Step 4: S3 secret
        storage_mock.apply_s3_secret.assert_called_once()

        # Step 5: vLLM ServingRuntime then InferenceService
        inference_mock.apply_serving_runtime.assert_called_once()
        inference_mock.apply_inference_service.assert_called_once()
        inference_mock.wait_until_ready.assert_called_once_with(
            "qwen", "test-ns", config["timeouts"]["inference_ready"]
        )

    def test_deploy_uses_model_from_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """When config.vllm.model is overridden, deploy() must use the overridden value."""
        import importlib
        import sys

        sys.modules.pop("rhoai.usecases.vllm.deploy", None)
        deploy_mod = importlib.import_module("rhoai.usecases.vllm.deploy")

        prepare_mock   = MagicMock()
        storage_mock   = MagicMock()
        inference_mock = MagicMock()
        assets_mock    = MagicMock()

        monkeypatch.setattr(deploy_mod, "prepare",   prepare_mock)
        monkeypatch.setattr(deploy_mod, "storage",   storage_mock)
        monkeypatch.setattr(deploy_mod, "inference", inference_mock)
        monkeypatch.setattr(deploy_mod, "assets",    assets_mock)

        config = self._make_config(tmp_path)
        config["vllm"]["model"] = "phi-3-mini-4k-instruct"
        config["vllm"]["inference_service_name"] = "phi3"
        deploy_mod.deploy(config)

        # assets.get_model_manifest must be called with the overridden model name
        assets_mock.get_model_manifest.assert_called_once_with(
            str(tmp_path), "phi-3-mini-4k-instruct"
        )
        inference_mock.wait_until_ready.assert_called_once_with(
            "phi3", "test-ns", config["timeouts"]["inference_ready"]
        )
