"""Integration smoke tests — no live cluster required.

Verifies that the full fraud-detection use-case module graph imports
cleanly and that config defaults wire up correctly.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import yaml

from rhoai.config.loader import load_config
from rhoai.usecases import registry
from rhoai.usecases.fraud_detection import assets

# Minimal InferenceService manifest that matches the structure deploy.py mutates.
_ISVC_MANIFEST: dict[str, Any] = {
    "apiVersion": "serving.kserve.io/v1beta1",
    "kind": "InferenceService",
    "metadata": {
        "name": "fraud-detection",
        "annotations": {
            "opendatahub.io/connection-type-ref": "s3",
        },
    },
    "spec": {
        "predictor": {
            "model": {
                "runtime": "triton-ppc64le-runtime",
                "storage": {"key": "s3-credentials", "path": "models/fraud"},
            }
        }
    },
}


def _write_manifest(tmp_path: Path) -> None:
    """Write the stub InferenceService manifest into the expected asset path."""
    dest = (
        tmp_path
        / "model-serving"
        / "predictive-models"
        / "triton"
        / "fraud-detection.yaml"
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.dump(_ISVC_MANIFEST))


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
    def test_deployment_defaults_present(self) -> None:
        config = load_config()
        dep = config.get("deployment", {})
        assert dep.get("inference_service_name") == "fraud-detection"
        assert dep.get("trustyai_service_name") == "trustyai-service"
        # serving_runtime_name is an internal constant, not user-facing config.
        assert assets.SERVING_RUNTIME_NAME == "triton-ppc64le-runtime"

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

    def test_trustyai_service_path(self, tmp_path: Path) -> None:
        p = assets.get_trustyai_service_manifest(tmp_path)
        assert p == tmp_path / "trustyai" / "service" / "trustyai-service.yaml"

    def test_sample_inference_request_path(self) -> None:
        p = assets.get_sample_inference_request()
        assert p.name == "sample-fraud.json"
        assert p.parent.name == "data"
        assert p.exists(), "sample-fraud.json must exist alongside the package"


class TestDeploySmoke:
    """Smoke-test deploy() wiring with all cluster I/O mocked.

    deploy() reads the InferenceService manifest from disk via yaml_io.load()
    and applies it via ocp_resources.apply_dict(). Both are patched here so the
    test never touches the real filesystem beyond the stub file we create in tmp_path.
    """

    def _make_config(self, tmp_path: Path, model_uri: str = "") -> dict:
        config = load_config()
        config["repo_root"] = str(tmp_path)
        config["platform"]["namespace"] = "test-ns"
        if model_uri:
            config.setdefault("deployment", {})["model_uri"] = model_uri
        return config

    def _patch_all(
        self, monkeypatch: pytest.MonkeyPatch, deploy_mod: Any, tmp_path: Path
    ) -> dict[str, MagicMock]:
        """Patch every external dependency of deploy_mod and return the mocks."""
        storage_mock       = MagicMock()
        inference_mock     = MagicMock()
        ocp_resources_mock = MagicMock()
        trustyai_mock      = MagicMock()
        prepare_mock       = MagicMock()

        monkeypatch.setattr(deploy_mod, "storage",       storage_mock)
        monkeypatch.setattr(deploy_mod, "inference",     inference_mock)
        monkeypatch.setattr(deploy_mod, "ocp_resources", ocp_resources_mock)
        monkeypatch.setattr(deploy_mod, "trustyai",      trustyai_mock)
        monkeypatch.setattr(deploy_mod, "prepare",       prepare_mock)

        return {
            "storage":       storage_mock,
            "inference":     inference_mock,
            "ocp_resources": ocp_resources_mock,
            "trustyai":      trustyai_mock,
            "prepare":       prepare_mock,
        }

    def _fresh_deploy_mod(self) -> Any:
        import importlib
        import sys

        sys.modules.pop("rhoai.usecases.fraud_detection.deploy", None)
        return importlib.import_module("rhoai.usecases.fraud_detection.deploy")

    # ------------------------------------------------------------------
    # Core wiring test (default config — pvc:// model_uri, S3 skipped)
    # ------------------------------------------------------------------

    def test_deploy_calls_platform_modules(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _write_manifest(tmp_path)
        deploy_mod = self._fresh_deploy_mod()
        mocks = self._patch_all(monkeypatch, deploy_mod, tmp_path)

        config = self._make_config(tmp_path)
        deploy_mod.deploy(config)

        # Step 4: default model_uri is pvc:// → S3 secret is skipped
        mocks["storage"].apply_s3_secret.assert_not_called()

        # Step 5: Triton Template → ServingRuntime; InferenceService via apply_dict
        mocks["inference"].apply_serving_runtime_from_template.assert_called_once()
        mocks["ocp_resources"].apply_dict.assert_called_once()
        mocks["inference"].wait_until_ready.assert_called_once_with(
            "fraud-detection", "test-ns", config["timeouts"]["inference_ready"]
        )

        # Step 5b: smoke test — verify_triton_inference called after ready
        mocks["inference"].verify_triton_inference.assert_called_once()
        call_args = mocks["inference"].verify_triton_inference.call_args[0]
        assert call_args[0] == "fraud-detection"   # isvc_name
        assert call_args[1] == "test-ns"           # namespace
        assert call_args[2] == "fraud-detection"   # model_name

    # ------------------------------------------------------------------
    # model_uri variant: PVC — S3 secret skipped, storageUri injected
    # ------------------------------------------------------------------

    def test_deploy_pvc_uri_skips_s3_and_sets_storage_uri(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _write_manifest(tmp_path)
        deploy_mod = self._fresh_deploy_mod()
        mocks = self._patch_all(monkeypatch, deploy_mod, tmp_path)

        config = self._make_config(tmp_path, model_uri="pvc://fraud-model-pvc/models")
        deploy_mod.deploy(config)

        mocks["storage"].apply_s3_secret.assert_not_called()

        mocks["ocp_resources"].apply_dict.assert_called_once()
        applied_dict = mocks["ocp_resources"].apply_dict.call_args[0][0]
        model_spec = applied_dict["spec"]["predictor"]["model"]
        assert model_spec["storageUri"] == "pvc://fraud-model-pvc/models"
        assert "storage" not in model_spec
        assert "opendatahub.io/connection-type-ref" not in applied_dict["metadata"]["annotations"]

    # ------------------------------------------------------------------
    # model_uri variant: plain S3 path — path updated, S3 secret applied
    # ------------------------------------------------------------------

    def test_deploy_s3_path_updates_storage_path(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        _write_manifest(tmp_path)
        deploy_mod = self._fresh_deploy_mod()
        mocks = self._patch_all(monkeypatch, deploy_mod, tmp_path)

        config = self._make_config(tmp_path, model_uri="models/my-fraud-model")
        deploy_mod.deploy(config)

        mocks["storage"].apply_s3_secret.assert_called_once()

        mocks["ocp_resources"].apply_dict.assert_called_once()
        applied_dict = mocks["ocp_resources"].apply_dict.call_args[0][0]
        model_spec = applied_dict["spec"]["predictor"]["model"]
        assert model_spec["storage"]["path"] == "models/my-fraud-model"
        assert "storageUri" not in model_spec
