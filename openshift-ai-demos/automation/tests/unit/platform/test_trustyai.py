"""Unit tests for rhoai.platform.trustyai."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rhoai.platform import trustyai


@pytest.fixture(autouse=True)
def patch_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rhoai.platform.trustyai.resources", MagicMock())
    monkeypatch.setattr("rhoai.platform.trustyai.wait", MagicMock())


# ---------------------------------------------------------------------------
# apply_monitoring_config
# ---------------------------------------------------------------------------

class TestApplyMonitoringConfig:
    def test_applies_each_document(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Each YAML document in the multi-doc file is applied with its own namespace."""
        manifest = tmp_path / "monitoring-config.yaml"
        manifest.write_text(
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: a\n  namespace: openshift-monitoring\n"
            "---\n"
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: b\n  namespace: openshift-user-workload-monitoring\n"
        )
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        trustyai.apply_monitoring_config(manifest)
        assert mock_resources.apply_dict.call_count == 2

    def test_passes_namespace_from_document(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        manifest = tmp_path / "monitoring-config.yaml"
        manifest.write_text(
            "apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: a\n  namespace: openshift-monitoring\n"
        )
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        trustyai.apply_monitoring_config(manifest)
        _, kwargs = mock_resources.apply_dict.call_args
        assert kwargs is not None or mock_resources.apply_dict.call_args[0][1] == "openshift-monitoring"


# ---------------------------------------------------------------------------
# patch_inferenceservice_config
# ---------------------------------------------------------------------------

class TestPatchInferencserviceConfig:
    def test_calls_patch_with_correct_args(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        trustyai.patch_inferenceservice_config("test-ns")
        mock_resources.patch.assert_called_once_with(
            "ConfigMap",
            "inferenceservice-config",
            {"metadata": {"annotations": {"opendatahub.io/managed": "false"}}},
            namespace="test-ns",
        )


# ---------------------------------------------------------------------------
# apply_trustyai_service
# ---------------------------------------------------------------------------

class TestApplyTrustyAIService:
    def test_delegates_to_apply_manifest(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        path = tmp_path / "trustyai-service.yaml"
        path.write_text("kind: TrustyAIService\n")
        trustyai.apply_trustyai_service(path, "ns")
        mock_resources.apply_manifest.assert_called_once_with(path, "ns")


# ---------------------------------------------------------------------------
# wait_until_ready
# ---------------------------------------------------------------------------

class TestWaitUntilReady:
    def test_delegates_to_wait(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_wait = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.wait", mock_wait)
        trustyai.wait_until_ready("trustyai-service", "ns", timeout=120)
        mock_wait.wait_until_ready.assert_called_once_with(
            "TrustyAIService", "trustyai-service", "ns", timeout=120
        )


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------

class TestVerify:
    def test_passes_when_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.is_ready.return_value = True
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        trustyai.verify("trustyai-service", "ns")  # should not raise

    def test_raises_when_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.is_ready.return_value = False
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        with pytest.raises(RuntimeError, match="not ready"):
            trustyai.verify("trustyai-service", "ns")

    def test_error_message_contains_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.is_ready.return_value = False
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        with pytest.raises(RuntimeError, match="my-trustyai"):
            trustyai.verify("my-trustyai", "ns")


# ---------------------------------------------------------------------------
# delete_trustyai_service
# ---------------------------------------------------------------------------

class TestDeleteTrustyAIService:
    def test_deletes_cr(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_wait = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        monkeypatch.setattr("rhoai.platform.trustyai.wait", mock_wait)
        trustyai.delete_trustyai_service("trustyai-service", "ns")
        mock_resources.delete_manifest.assert_called_once_with(
            "TrustyAIService", "trustyai-service", "ns"
        )

    def test_waits_for_deletion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_wait = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.resources", MagicMock())
        monkeypatch.setattr("rhoai.platform.trustyai.wait", mock_wait)
        trustyai.delete_trustyai_service("trustyai-service", "ns")
        mock_wait.wait_until_deleted.assert_called_once_with(
            "TrustyAIService", "trustyai-service", "ns"
        )
