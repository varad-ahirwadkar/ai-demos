"""Shared manifest path resolver for platform-level resources.

Maps logical names to file paths inside the openshift-ai-demos repo.
If the repo is reorganised, only this file needs to change.
Imports stdlib only.
"""

from pathlib import Path


def get_dsci(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "dsci.yaml"


def get_dsc(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "dsc.yaml"


def get_s3_secret(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "s3-secret.yaml"


def get_operator_group(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "operator-group.yaml"


def get_subscription(repo_root: str | Path) -> Path:
    return Path(repo_root) / "shared" / "subscription.yaml"


def get_vllm_serving_runtime(repo_root: str | Path) -> Path:
    return Path(repo_root) / "model-serving" / "shared" / "vllm-serving-runtime.yaml"
