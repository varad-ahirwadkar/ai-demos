"""Unit tests for rhoai.config.loader."""

from pathlib import Path

import pytest

from rhoai.config.loader import load_config


@pytest.fixture
def minimal_config(tmp_path: Path) -> Path:
    p = tmp_path / "config.yaml"
    p.write_text("platform:\n  namespace: my-namespace\n")
    return p


@pytest.fixture
def defaults_only_config(tmp_path: Path) -> Path:
    """A config file that specifies nothing — all defaults apply."""
    p = tmp_path / "empty.yaml"
    p.write_text("{}\n")
    return p


class TestLoadConfig:
    def test_returns_dict(self) -> None:
        config = load_config()
        assert isinstance(config, dict)

    def test_defaults_present(self) -> None:
        config = load_config()
        assert config["log_level"] == "INFO"
        assert config["operator"]["name"] == "rhods-operator"
        assert config["dsc"]["name"] == "default-dsc"

    def test_user_file_overrides_defaults(self, minimal_config: Path) -> None:
        config = load_config(minimal_config)
        assert config["platform"]["namespace"] == "my-namespace"

    def test_user_file_preserves_unset_defaults(self, minimal_config: Path) -> None:
        config = load_config(minimal_config)
        assert config["operator"]["name"] == "rhods-operator"

    def test_env_override_namespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RHOAI_NAMESPACE", "env-namespace")
        config = load_config()
        assert config["platform"]["namespace"] == "env-namespace"

    def test_env_override_log_level(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RHOAI_LOG_LEVEL", "DEBUG")
        config = load_config()
        assert config["log_level"] == "DEBUG"

    def test_env_override_repo_root(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv("RHOAI_REPO_ROOT", str(tmp_path))
        config = load_config()
        assert config["repo_root"] == str(tmp_path)

    def test_rhoai_config_env_var(
        self, monkeypatch: pytest.MonkeyPatch, minimal_config: Path
    ) -> None:
        monkeypatch.setenv("RHOAI_CONFIG", str(minimal_config))
        config = load_config()
        assert config["platform"]["namespace"] == "my-namespace"

    def test_explicit_path_takes_priority_over_env(
        self, monkeypatch: pytest.MonkeyPatch, minimal_config: Path, tmp_path: Path
    ) -> None:
        other = tmp_path / "other.yaml"
        other.write_text("platform:\n  namespace: from-env-config\n")
        monkeypatch.setenv("RHOAI_CONFIG", str(other))
        config = load_config(minimal_config)
        assert config["platform"]["namespace"] == "my-namespace"
