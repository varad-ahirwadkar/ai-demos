"""Deployment configuration loader.

Loads the YAML config file, applies RHOAI_ environment variable overrides,
and returns a plain dict. Pydantic can be added later if config validation
becomes complex enough to justify it.

Priority (highest → lowest):
    1. RHOAI_ environment variables
    2. User-supplied YAML file  (--config flag or RHOAI_CONFIG env var)
    3. Bundled defaults         (config/defaults.yaml)

Environment variable mapping:
    RHOAI_CLUSTER_URL   → config["cluster"]["url"]
    RHOAI_NAMESPACE     → config["cluster"]["namespace"]
    RHOAI_KUBECONFIG    → config["cluster"]["kubeconfig"]
    RHOAI_REPO_ROOT     → config["repo_root"]
    RHOAI_LOG_LEVEL     → config["log_level"]

Depends on: utils.yaml_io, utils.logger, stdlib
"""

import os
from pathlib import Path
from typing import Any

import yaml

from rhoai.utils.logger import get_logger
from rhoai.utils.yaml_io import deep_merge, load

log = get_logger(__name__)

_DEFAULTS = Path(__file__).parent / "defaults.yaml"


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Load, merge, and return the deployment configuration.

    Args:
        path: Path to the user YAML config file. If None, falls back to
              the RHOAI_CONFIG environment variable, then defaults only.

    Returns:
        Merged configuration as a plain dict.
    """
    config = load(_DEFAULTS)

    user_path = path or _config_path_from_env()
    if user_path:
        log.debug("Loading config from %s", user_path)
        config = deep_merge(config, load(user_path))

    return _apply_env_overrides(config)


def _config_path_from_env() -> Path | None:
    value = os.environ.get("RHOAI_CONFIG")
    return Path(value) if value else None


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """Overwrite config keys from RHOAI_ environment variables."""
    mapping = {
        "RHOAI_CLUSTER_URL":  ["cluster", "url"],
        "RHOAI_NAMESPACE":    ["cluster", "namespace"],
        "RHOAI_KUBECONFIG":   ["cluster", "kubeconfig"],
        "RHOAI_REPO_ROOT":    ["repo_root"],
        "RHOAI_LOG_LEVEL":    ["log_level"],
    }
    for env_var, key_path in mapping.items():
        value = os.environ.get(env_var)
        if value is not None:
            _set_nested(config, key_path, value)
            log.debug("Env override: %s", env_var)
    return config


def _set_nested(d: dict[str, Any], keys: list[str], value: str) -> None:
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value


def save_defaults(updates: dict[str, Any]) -> None:
    """Persist key-value updates into defaults.yaml so future bare runs use them.

    Only the keys present in *updates* are changed — every other value in
    defaults.yaml is left exactly as-is.  The file is written atomically.

    Args:
        updates: Flat or nested dict matching the structure of defaults.yaml.
                 Example: ``{"operator": {"channel": "stable-3.5",
                                          "version": "rhods-operator.v3.5.0"}}``
    """
    current = load(_DEFAULTS)
    merged  = deep_merge(current, updates)
    with open(_DEFAULTS, "w") as fh:
        yaml.dump(merged, fh, default_flow_style=False, sort_keys=False)
    log.debug("defaults.yaml updated: %s", updates)
