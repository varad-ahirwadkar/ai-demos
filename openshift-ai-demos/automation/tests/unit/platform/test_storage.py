"""Unit tests for rhoai.platform.storage."""

from unittest.mock import MagicMock

import pytest

from rhoai.platform import storage


@pytest.fixture(autouse=True)
def patch_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rhoai.platform.storage.resources", MagicMock())
    monkeypatch.setattr("rhoai.platform.storage.wait", MagicMock())


class TestCreateSecret:
    def test_base64_encodes_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import base64
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.storage.resources", mock_resources)

        storage.create_secret("my-secret", "ns", {"user": "admin", "pass": "secret"})

        call_args = mock_resources.apply_dict.call_args[0][0]
        assert call_args["kind"] == "Secret"
        assert call_args["data"]["user"] == base64.b64encode(b"admin").decode()
        assert call_args["data"]["pass"] == base64.b64encode(b"secret").decode()

    def test_default_type_is_opaque(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        monkeypatch.setattr("rhoai.platform.storage.resources", mock_resources)
        storage.create_secret("s", "ns", {})
        call_args = mock_resources.apply_dict.call_args[0][0]
        assert call_args["type"] == "Opaque"


class TestCreatePvc:
    def test_skips_if_already_exists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.exists.return_value = True
        monkeypatch.setattr("rhoai.platform.storage.resources", mock_resources)
        storage.create_pvc("my-pvc", "ns", "10Gi")
        mock_resources.apply_dict.assert_not_called()

    def test_creates_pvc_when_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.exists.return_value = False
        monkeypatch.setattr("rhoai.platform.storage.resources", mock_resources)
        storage.create_pvc("my-pvc", "ns", "10Gi")
        mock_resources.apply_dict.assert_called_once()

    def test_raises_if_storage_class_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        # PVC does not exist (so we proceed), StorageClass does not exist (should raise)
        mock_resources.exists.side_effect = lambda kind, name, *_: False
        monkeypatch.setattr("rhoai.platform.storage.resources", mock_resources)
        with pytest.raises(RuntimeError, match="StorageClass"):
            storage.create_pvc("pvc", "ns", "5Gi", storage_class="missing-class")


class TestVerify:
    def test_passes_when_secret_exists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.exists.return_value = True
        monkeypatch.setattr("rhoai.platform.storage.resources", mock_resources)
        storage.verify("s3-credentials", "ns")  # should not raise

    def test_raises_when_secret_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_resources = MagicMock()
        mock_resources.exists.return_value = False
        monkeypatch.setattr("rhoai.platform.storage.resources", mock_resources)
        with pytest.raises(RuntimeError, match="S3 credentials"):
            storage.verify("s3-credentials", "ns")
