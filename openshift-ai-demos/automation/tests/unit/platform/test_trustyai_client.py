"""Unit tests for rhoai.platform.trustyai_client."""

from unittest.mock import MagicMock, patch

import pytest

from rhoai.platform import trustyai_client

_ROUTE = "https://trustyai.apps.example.com"
_TOKEN = "test-token"
_MODEL = "fraud-detection"


def _mock_response(json_data: object, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


# ---------------------------------------------------------------------------
# get_model_info
# ---------------------------------------------------------------------------

class TestGetModelInfo:
    def test_returns_model_entry(self) -> None:
        info_response = {_MODEL: {"name": _MODEL, "data": {}}, "other": {}}
        with patch("rhoai.platform.trustyai_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response(info_response)
            result = trustyai_client.get_model_info(_ROUTE, _TOKEN, _MODEL)
        assert result == {"name": _MODEL, "data": {}}

    def test_calls_correct_url(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response({_MODEL: {}})
            trustyai_client.get_model_info(_ROUTE, _TOKEN, _MODEL)
        url = mock_get.call_args[0][0]
        assert url == f"{_ROUTE}/info"

    def test_raises_key_error_when_model_not_found(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response({"other-model": {}})
            with pytest.raises(KeyError, match=_MODEL):
                trustyai_client.get_model_info(_ROUTE, _TOKEN, _MODEL)

    def test_sends_bearer_token(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.get") as mock_get:
            mock_get.return_value = _mock_response({_MODEL: {}})
            trustyai_client.get_model_info(_ROUTE, _TOKEN, _MODEL)
        headers = mock_get.call_args[1]["headers"]
        assert headers["Authorization"] == f"Bearer {_TOKEN}"


# ---------------------------------------------------------------------------
# apply_name_mapping
# ---------------------------------------------------------------------------

class TestApplyNameMapping:
    def test_posts_to_info_names(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response({})
            trustyai_client.apply_name_mapping(
                _ROUTE, _TOKEN, _MODEL,
                input_mapping={"input-0": "age"},
                output_mapping={"output-0": "fraud_score"},
            )
        url = mock_post.call_args[0][0]
        assert url.endswith("/info/names")

    def test_payload_shape(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response({})
            trustyai_client.apply_name_mapping(
                _ROUTE, _TOKEN, _MODEL,
                input_mapping={"input-0": "age"},
                output_mapping={"output-0": "score"},
            )
        body = mock_post.call_args[1]["json"]
        assert body["modelId"] == _MODEL
        assert body["inputMapping"] == {"input-0": "age"}
        assert body["outputMapping"] == {"output-0": "score"}


# ---------------------------------------------------------------------------
# compute_spd
# ---------------------------------------------------------------------------

class TestComputeSpd:
    _spd_response = {
        "value": 0.05,
        "id": "spd-123",
        "thresholds": {"lowerBound": -0.1, "upperBound": 0.1},
        "specificDefinition": "…",
    }

    def test_returns_response_dict(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(self._spd_response)
            result = trustyai_client.compute_spd(
                _ROUTE, _TOKEN, _MODEL,
                protected_attribute="gender", privileged_value=1.0,
                unprivileged_value=0.0, outcome_name="fraud_score",
                favorable_outcome=0.0,
            )
        assert result["value"] == 0.05

    def test_posts_to_spd_endpoint(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(self._spd_response)
            trustyai_client.compute_spd(
                _ROUTE, _TOKEN, _MODEL,
                protected_attribute="gender", privileged_value=1.0,
                unprivileged_value=0.0, outcome_name="fraud_score",
                favorable_outcome=0.0,
            )
        url = mock_post.call_args[0][0]
        assert url.endswith("/metrics/group/fairness/spd")

    def test_payload_contains_protected_attribute(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response(self._spd_response)
            trustyai_client.compute_spd(
                _ROUTE, _TOKEN, _MODEL,
                protected_attribute="gender", privileged_value=1.0,
                unprivileged_value=0.0, outcome_name="fraud_score",
                favorable_outcome=0.0, batch_size=1000,
            )
        body = mock_post.call_args[1]["json"]
        assert body["protectedAttribute"] == "gender"
        assert body["privilegedAttribute"] == {"type": "DOUBLE", "value": 1.0}
        assert body["batchSize"] == 1000


# ---------------------------------------------------------------------------
# schedule_spd
# ---------------------------------------------------------------------------

class TestScheduleSpd:
    def test_returns_request_id(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response({"id": "req-abc"})
            result = trustyai_client.schedule_spd(
                _ROUTE, _TOKEN, _MODEL,
                protected_attribute="gender", privileged_value=1.0,
                unprivileged_value=0.0, outcome_name="fraud_score",
                favorable_outcome=0.0,
            )
        assert result == "req-abc"

    def test_posts_to_spd_request_endpoint(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response({"id": "req-abc"})
            trustyai_client.schedule_spd(
                _ROUTE, _TOKEN, _MODEL,
                protected_attribute="gender", privileged_value=1.0,
                unprivileged_value=0.0, outcome_name="fraud_score",
                favorable_outcome=0.0,
            )
        url = mock_post.call_args[0][0]
        assert url.endswith("/metrics/group/fairness/spd/request")


# ---------------------------------------------------------------------------
# schedule_identity
# ---------------------------------------------------------------------------

class TestScheduleIdentity:
    def test_returns_request_id(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response({"id": "id-xyz"})
            result = trustyai_client.schedule_identity(
                _ROUTE, _TOKEN, _MODEL, column_name="gender"
            )
        assert result == "id-xyz"

    def test_posts_to_identity_request_endpoint(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response({"id": "id-xyz"})
            trustyai_client.schedule_identity(
                _ROUTE, _TOKEN, _MODEL, column_name="gender", batch_size=2000
            )
        url = mock_post.call_args[0][0]
        assert url.endswith("/metrics/identity/request")

    def test_payload_shape(self) -> None:
        with patch("rhoai.platform.trustyai_client.requests.post") as mock_post:
            mock_post.return_value = _mock_response({"id": "id-xyz"})
            trustyai_client.schedule_identity(
                _ROUTE, _TOKEN, _MODEL, column_name="gender", batch_size=2000
            )
        body = mock_post.call_args[1]["json"]
        assert body["modelId"] == _MODEL
        assert body["columnName"] == "gender"
        assert body["batchSize"] == 2000
