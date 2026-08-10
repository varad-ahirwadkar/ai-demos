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


# ---------------------------------------------------------------------------
# verify_triton_inference
# ---------------------------------------------------------------------------

class TestVerifyTritonInference:
    """Tests for verify_triton_inference and its private helpers.

    _http_post is patched at the module level so no real HTTP calls are made.
    get_inference_url is patched to return a fixed base URL.
    """

    _BASE_URL  = "https://fraud-detection.apps.example.com"
    _MODEL     = "fraud-detection"
    _GOOD_RESP = {"model_name": "fraud-detection", "outputs": [{"name": "output", "data": [0.1]}]}

    def _patch(self, monkeypatch: pytest.MonkeyPatch, post_return=None, post_side_effect=None):
        monkeypatch.setattr(
            "rhoai.platform.inference.get_inference_url",
            lambda *_: self._BASE_URL,
        )
        post_mock = MagicMock(return_value=post_return, side_effect=post_side_effect)
        monkeypatch.setattr("rhoai.platform.inference._http_post", post_mock)
        return post_mock

    def _sample_request(self, tmp_path):
        import json as _json
        p = tmp_path / "sample.json"
        p.write_text(_json.dumps({"inputs": [{"name": "dense_input", "data": [0.1] * 10}]}))
        return p

    # --- happy path ---

    def test_passes_on_valid_response(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        self._patch(monkeypatch, post_return=self._GOOD_RESP)
        inference.verify_triton_inference(
            "fraud-detection", "ns", self._MODEL, self._sample_request(tmp_path)
        )  # should not raise

    def test_posts_to_correct_url(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        post_mock = self._patch(monkeypatch, post_return=self._GOOD_RESP)
        inference.verify_triton_inference(
            "fraud-detection", "ns", self._MODEL, self._sample_request(tmp_path)
        )
        called_url = post_mock.call_args[0][0]
        assert called_url == f"{self._BASE_URL}/v2/models/{self._MODEL}/infer"

    # --- response validation ---

    def test_raises_on_wrong_model_name_in_response(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        bad_resp = {"model_name": "wrong-model", "outputs": [{}]}
        self._patch(monkeypatch, post_return=bad_resp)
        with pytest.raises(RuntimeError, match="Unexpected model_name"):
            inference.verify_triton_inference(
                "fraud-detection", "ns", self._MODEL, self._sample_request(tmp_path)
            )

    def test_raises_when_outputs_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        bad_resp = {"model_name": "fraud-detection", "outputs": []}
        self._patch(monkeypatch, post_return=bad_resp)
        with pytest.raises(RuntimeError, match="no outputs"):
            inference.verify_triton_inference(
                "fraud-detection", "ns", self._MODEL, self._sample_request(tmp_path)
            )

    def test_raises_when_outputs_key_absent(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        bad_resp = {"model_name": "fraud-detection"}
        self._patch(monkeypatch, post_return=bad_resp)
        with pytest.raises(RuntimeError, match="no outputs"):
            inference.verify_triton_inference(
                "fraud-detection", "ns", self._MODEL, self._sample_request(tmp_path)
            )

    # --- retry on connection error ---

    def test_retries_once_on_connection_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setattr("rhoai.platform.inference.time.sleep", MagicMock())
        monkeypatch.setattr(
            "rhoai.platform.inference.get_inference_url",
            lambda *_: self._BASE_URL,
        )
        # First call raises _ConnectionError; second call succeeds.
        post_mock = MagicMock(
            side_effect=[inference._ConnectionError("timeout"), self._GOOD_RESP]
        )
        monkeypatch.setattr("rhoai.platform.inference._http_post", post_mock)
        inference.verify_triton_inference(
            "fraud-detection", "ns", self._MODEL, self._sample_request(tmp_path)
        )
        assert post_mock.call_count == 2

    def test_raises_after_retry_also_fails(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path
    ) -> None:
        monkeypatch.setattr("rhoai.platform.inference.time.sleep", MagicMock())
        monkeypatch.setattr(
            "rhoai.platform.inference.get_inference_url",
            lambda *_: self._BASE_URL,
        )
        post_mock = MagicMock(
            side_effect=inference._ConnectionError("still down")
        )
        monkeypatch.setattr("rhoai.platform.inference._http_post", post_mock)
        with pytest.raises(inference._ConnectionError, match="still down"):
            inference.verify_triton_inference(
                "fraud-detection", "ns", self._MODEL, self._sample_request(tmp_path)
            )


# ---------------------------------------------------------------------------
# _http_post
# ---------------------------------------------------------------------------

class TestHttpPost:
    """Unit tests for the _http_post helper (urllib3 pool mocked)."""

    def _patch_pool(self, monkeypatch: pytest.MonkeyPatch, status: int, data: bytes):
        resp_mock = MagicMock()
        resp_mock.status = status
        resp_mock.data   = data
        pool_mock = MagicMock()
        pool_mock.request.return_value = resp_mock
        monkeypatch.setattr("rhoai.platform.inference.urllib3.PoolManager", lambda **_: pool_mock)
        return pool_mock

    def test_returns_decoded_json_on_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import json as _json
        body = _json.dumps({"model_name": "x", "outputs": []}).encode()
        self._patch_pool(monkeypatch, 200, body)
        result = inference._http_post("https://host/infer", {"inputs": []})
        assert result["model_name"] == "x"

    def test_raises_runtime_error_on_non_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_pool(monkeypatch, 503, b"Service Unavailable")
        with pytest.raises(RuntimeError, match="HTTP 503"):
            inference._http_post("https://host/infer", {})

    def test_raises_connection_error_on_urllib3_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import urllib3 as _urllib3
        pool_mock = MagicMock()
        pool_mock.request.side_effect = _urllib3.exceptions.HTTPError("connect failed")
        monkeypatch.setattr("rhoai.platform.inference.urllib3.PoolManager", lambda **_: pool_mock)
        with pytest.raises(inference._ConnectionError, match="connect failed"):
            inference._http_post("https://host/infer", {})

    def test_raises_on_invalid_json_response(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_pool(monkeypatch, 200, b"not-json{{")
        with pytest.raises(RuntimeError, match="not valid JSON"):
            inference._http_post("https://host/infer", {})
