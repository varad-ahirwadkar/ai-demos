"""Unit tests for rhoai.platform.dsc."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from rhoai.platform import dsc


@pytest.fixture(autouse=True)
def patch_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rhoai.platform.dsc.resources", MagicMock())
    monkeypatch.setattr("rhoai.platform.dsc.wait", MagicMock())


class TestApplyDsci:
    def test_calls_apply_manifest(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.dsc.resources", mock_resources)
        p = tmp_path / "dsci.yaml"
        p.write_text("apiVersion: v1\nkind: DSCInitialization\nmetadata:\n  name: x\n")
        dsc.apply_dsci(p)
        mock_resources.apply_manifest.assert_called_once_with(p)


class TestApplyDsc:
    def test_calls_apply_manifest(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.dsc.resources", mock_resources)
        p = tmp_path / "dsc.yaml"
        p.write_text("apiVersion: v1\nkind: DataScienceCluster\nmetadata:\n  name: x\n")
        dsc.apply_dsc(p)
        mock_resources.apply_manifest.assert_called_once_with(p)


class TestVerify:
    def test_passes_when_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rhoai.platform.dsc._is_ready", lambda name: True)
        dsc.verify("default-dsc")  # should not raise

    def test_raises_when_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("rhoai.platform.dsc._is_ready", lambda name: False)
        mock_resources = MagicMock()
        mock_resources.status.return_value = {"phase": "Progressing"}
        monkeypatch.setattr("rhoai.platform.dsc.resources", mock_resources)
        with pytest.raises(RuntimeError, match="not ready"):
            dsc.verify("default-dsc")


class TestSetComponentStates:
    def test_sends_merge_patch_for_named_components_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.dsc.resources", mock_resources)

        dsc.set_component_states("default-dsc", {"kserve": "Managed", "trustyai": "Removed"})

        mock_resources.patch.assert_called_once_with(
            "DataScienceCluster",
            "default-dsc",
            {
                "spec": {
                    "components": {
                        "kserve":   {"managementState": "Managed"},
                        "trustyai": {"managementState": "Removed"},
                    }
                }
            },
            strategy="merge",
        )

    def test_single_component(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.dsc.resources", mock_resources)

        dsc.set_component_states("default-dsc", {"dashboard": "Managed"})

        patch_body = mock_resources.patch.call_args[0][2]
        assert patch_body["spec"]["components"] == {"dashboard": {"managementState": "Managed"}}


class TestWaitDsciReady:
    def test_delegates_to_generic_wait_with_dsci_kind(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_wait = MagicMock()
        monkeypatch.setattr("rhoai.platform.dsc.wait", mock_wait)

        dsc.wait_dsci_ready("default-dsci", 120)

        mock_wait.wait_until_ready.assert_called_once_with(
            "DSCInitialization", "default-dsci", timeout=120
        )


class TestIsReady:
    def test_true_when_phase_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.status.return_value = {"phase": "Ready"}
        monkeypatch.setattr("rhoai.platform.dsc.resources", mock_resources)
        assert dsc._is_ready("default-dsc") is True

    def test_false_when_phase_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.status.return_value = {"phase": "Progressing"}
        monkeypatch.setattr("rhoai.platform.dsc.resources", mock_resources)
        assert dsc._is_ready("default-dsc") is False
