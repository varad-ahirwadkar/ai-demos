"""Unit tests for rhoai.platform.inference."""

from unittest.mock import MagicMock

import pytest

from rhoai.platform import inference


@pytest.fixture(autouse=True)
def patch_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rhoai.platform.inference.resources", MagicMock())
    monkeypatch.setattr("rhoai.platform.inference.wait", MagicMock())


class TestGetInferenceUrl:
    def test_returns_status_url_when_present(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.status.return_value = {"url": "https://model.example.com"}
        monkeypatch.setattr("rhoai.platform.inference.resources", mock_resources)
        assert inference.get_inference_url("qwen", "ns") == "https://model.example.com"

    def test_falls_back_to_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.status.return_value = {}
        mock_resources.exists.return_value = True
        mock_resources.get.return_value = {
            "spec": {"host": "qwen.apps.example.com", "tls": {"termination": "edge"}}
        }
        monkeypatch.setattr("rhoai.platform.inference.resources", mock_resources)
        url = inference.get_inference_url("qwen", "ns")
        assert url == "https://qwen.apps.example.com"

    def test_raises_when_no_url_and_no_route(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.status.return_value = {}
        mock_resources.exists.return_value = False
        monkeypatch.setattr("rhoai.platform.inference.resources", mock_resources)
        with pytest.raises(RuntimeError, match="no URL"):
            inference.get_inference_url("qwen", "ns")


class TestVerify:
    # --- namespace-wide (name=None) ---
    def test_passes_when_all_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.list_resources.return_value = [{"metadata": {"name": "qwen"}}]
        mock_resources.is_ready.return_value = True
        monkeypatch.setattr("rhoai.platform.inference.resources", mock_resources)
        inference.verify("ns")  # should not raise

    def test_raises_when_service_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.list_resources.return_value = [{"metadata": {"name": "qwen"}}]
        mock_resources.is_ready.return_value = False
        monkeypatch.setattr("rhoai.platform.inference.resources", mock_resources)
        with pytest.raises(RuntimeError, match="not ready"):
            inference.verify("ns")

    def test_passes_with_no_services(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.list_resources.return_value = []
        monkeypatch.setattr("rhoai.platform.inference.resources", mock_resources)
        inference.verify("ns")  # no services = nothing to fail

    # --- named ISVC path ---
    def test_named_passes_when_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.is_ready.return_value = True
        monkeypatch.setattr("rhoai.platform.inference.resources", mock_resources)
        inference.verify("ns", name="qwen")  # should not raise
        mock_resources.is_ready.assert_called_once_with("InferenceService", "qwen", "ns")

    def test_named_raises_when_not_ready(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.is_ready.return_value = False
        monkeypatch.setattr("rhoai.platform.inference.resources", mock_resources)
        with pytest.raises(RuntimeError, match="'qwen' is not ready"):
            inference.verify("ns", name="qwen")

    def test_named_does_not_call_list_resources(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.is_ready.return_value = True
        monkeypatch.setattr("rhoai.platform.inference.resources", mock_resources)
        inference.verify("ns", name="qwen")
        mock_resources.list_resources.assert_not_called()
