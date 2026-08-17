"""Fraud Detection — verification.

Checks that all resources deployed by this use case are healthy.
Runs platform checks first, then iterates over each configured model.
"""

from typing import Any

from rhoai.platform import inference, trustyai, trustyai_client
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


def _verify_bias_monitoring(
    model: dict[str, Any],
    route: str,
    token: str,
) -> None:
    """Check that TrustyAI has observations for a model.

    Reads ``model["bias_monitoring"]`` and returns immediately if absent or null.
    Confirms observation count > 0, indicating monitoring is active.

    Args:
        model: Model config dict (from deployment.models).
        route: TrustyAI service base URL.
        token: Bearer token for authentication.

    Raises:
        RuntimeError: If TrustyAI has no observations for the model.
    """
    if not model.get("bias_monitoring"):
        return

    model_id = model["name"]
    count    = trustyai_client.get_observation_count(route, token, model_id)
    if count == 0:
        raise RuntimeError(
            f"TrustyAI has no observations for model '{model_id}'. "
            "Re-run deployment to send observations."
        )
    log.info("TrustyAI observations for '%s': %d", model_id, count)


def verify(config: dict[str, Any]) -> None:
    """Verify the Fraud Detection deployment is healthy."""
    dep_cfg        = config.get("deployment", {})
    namespace      = dep_cfg.get("namespace") or config["platform"]["namespace"]
    repo_root      = config["repo_root"]
    models         = dep_cfg.get("models", [])
    trustyai_name  = dep_cfg.get("trustyai_service_name",    "trustyai-service")
    trustyai_sa    = dep_cfg.get("trustyai_service_account", "trustyai-user")

    log.info("Verifying Fraud Detection in '%s'", namespace)

    with step("Checking platform"):
        platform_verify.verify_platform(config)

    with step(f"Checking TrustyAI '{trustyai_name}'"):
        trustyai.verify(trustyai_name, namespace)

    route = trustyai.get_url(trustyai_name, namespace)
    token = trustyai.get_bearer_token(trustyai_sa, namespace)

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

            if model.get("bias_monitoring"):
                with step("Checking TrustyAI observations"):
                    _verify_bias_monitoring(model, route, token)

            results.append(result)

    _print_summary(
        results,
        use_case=config.get("_use_case", "fraud-detection"),
        namespace=namespace,
        config_file=config.get("_config_file", ""),
        trustyai_route=route,
    )
