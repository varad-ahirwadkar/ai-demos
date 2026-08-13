"""Fraud Detection — verification.

Checks that all resources deployed by this use case are healthy.
Runs platform checks first, then iterates over each configured model.
"""

from typing import Any

from rhoai.platform import inference
# from rhoai.platform import trustyai  # phase 2
from rhoai.platform import verify as platform_verify
from rhoai.platform.inference import EndpointUnreachable
from rhoai.usecases.fraud_detection.deploy import (
    _ModelResult,
    _print_summary,
    _resolve_inference_request,
)
from rhoai.utils.logger import get_logger
from rhoai.utils.progress import header_step, step

log = get_logger(__name__)


def verify(config: dict[str, Any]) -> None:
    """Verify the Fraud Detection deployment is healthy."""
    dep_cfg   = config.get("deployment", {})
    namespace = dep_cfg.get("namespace") or config["platform"]["namespace"]
    repo_root = config["repo_root"]
    models    = dep_cfg.get("models", [])
    # phase 2: trustyai_name = dep_cfg.get("trustyai_service_name", "trustyai-service")

    log.info("Verifying Fraud Detection in '%s'", namespace)

    with step("Checking platform"):
        platform_verify.verify_platform(config)

    results: list[_ModelResult] = []
    for model in models:
        name = model["name"]
        with header_step(f"Verifying '{name}'", outcome=f"'{name}' healthy"):
            with step(f"Checking InferenceService '{name}'"):
                inference.verify(namespace, name=name)
            result = _ModelResult(name=name)
            with step("Validating model inference") as s:
                try:
                    inference.verify_triton_inference(
                        name, namespace, name,
                        _resolve_inference_request(model, repo_root)
                    )
                except EndpointUnreachable as exc:
                    s.skip()
                    result.validation_skipped = True
                    result.unreachable        = exc
                    log.debug("Endpoint unreachable for '%s': %s", name, exc)
            results.append(result)

    _print_summary(
        results,
        use_case="fraud-detection",
        namespace=namespace,
        config_file=config.get("_config_file", ""),
    )

    # phase 2:
    # with step(f"Checking TrustyAI '{trustyai_name}'"):
    #     trustyai.verify(trustyai_name, namespace)
