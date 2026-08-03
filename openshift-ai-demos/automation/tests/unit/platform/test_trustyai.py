"""Unit tests for rhoai.platform.trustyai."""

from pathlib import Path
from unittest.mock import MagicMock, call

import pytest

from rhoai.platform import trustyai


@pytest.fixture(autouse=True)
def patch_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rhoai.platform.trustyai.resources", MagicMock())
    monkeypatch.setattr("rhoai.platform.trustyai.wait", MagicMock())


class TestApplyGuardrails:
    def test_applies_each_manifest(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        paths = [tmp_path / "a.yaml", tmp_path / "b.yaml"]
        for p in paths:
            p.write_text("kind: ConfigMap\n")
        trustyai.apply_guardrails(paths, "ns")
        assert mock_resources.apply_manifest.call_count == 2

    def test_applies_in_order(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        paths = [tmp_path / "first.yaml", tmp_path / "second.yaml"]
        for p in paths:
            p.write_text("kind: ConfigMap\n")
        trustyai.apply_guardrails(paths, "ns")
        calls = mock_resources.apply_manifest.call_args_list
        assert calls[0] == call(paths[0], "ns")
        assert calls[1] == call(paths[1], "ns")


class TestVerify:
    def test_passes_when_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.is_ready.return_value = True
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        trustyai.verify("ns")  # should not raise

    def test_raises_when_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.is_ready.return_value = False
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        with pytest.raises(RuntimeError, match="not ready"):
            trustyai.verify("ns")


class TestDeleteGuardrails:
    def test_deletes_orchestrator_and_configmaps(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.trustyai.resources", mock_resources)
        trustyai.delete_guardrails("guardrails-orchestrator", "ns")
        kinds_deleted = [c[0][0] for c in mock_resources.delete_manifest.call_args_list]
        assert "GuardrailsOrchestrator" in kinds_deleted
        assert kinds_deleted.count("ConfigMap") == 2
