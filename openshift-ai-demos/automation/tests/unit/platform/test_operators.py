"""Unit tests for rhoai.platform.operators."""

from unittest.mock import MagicMock

import pytest

from rhoai.platform import operators


@pytest.fixture(autouse=True)
def patch_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rhoai.platform.operators.resources", MagicMock())
    monkeypatch.setattr("rhoai.platform.operators.wait", MagicMock())
    monkeypatch.setattr("rhoai.platform.operators.manifests", MagicMock())


class TestIsInstalled:
    def test_true_when_succeeded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rhoai.platform.operators._csv_phase",
            lambda name, ns: "Succeeded",
        )
        assert operators.is_installed("rhods-operator", "redhat-ods-operator") is True

    def test_false_when_not_succeeded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rhoai.platform.operators._csv_phase",
            lambda name, ns: "Installing",
        )
        assert operators.is_installed("rhods-operator", "redhat-ods-operator") is False


class TestVerify:
    def test_passes_when_succeeded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rhoai.platform.operators._csv_phase",
            lambda name, ns: "Succeeded",
        )
        operators.verify("rhods-operator", "redhat-ods-operator")  # should not raise

    def test_raises_when_not_succeeded(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "rhoai.platform.operators._csv_phase",
            lambda name, ns: "Failed",
        )
        with pytest.raises(RuntimeError, match="not ready"):
            operators.verify("rhods-operator", "redhat-ods-operator")


class TestCsvPhase:
    def test_returns_phase_from_status(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.status.return_value = {"phase": "Succeeded"}
        monkeypatch.setattr("rhoai.platform.operators.resources", mock_resources)
        assert operators._csv_phase("my-csv", "ns") == "Succeeded"

    def test_returns_unknown_when_status_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.status.return_value = {}
        monkeypatch.setattr("rhoai.platform.operators.resources", mock_resources)
        assert operators._csv_phase("my-csv", "ns") == "Unknown"
