"""vLLM generative — deployment.

Orchestrates platform capabilities in the correct order.
Does not call ocp/ directly — all cluster operations go through platform modules.

Deployment sequence:
    1-3. deploy_platform  — validate cluster, operator, DSC/DSCI
    4.   configure storage — S3 secret
    5.   deploy model      — vLLM CPU ServingRuntime + InferenceService
"""

from typing import Any

from rhoai.platform import inference, manifests, prepare, storage
from rhoai.usecases.vllm import assets
from rhoai.utils.logger import get_logger

log = get_logger(__name__)


def deploy(config: dict[str, Any]) -> None:
    """Deploy the vLLM generative model serving solution."""
    repo_root       = config["repo_root"]
    namespace       = config["cluster"]["namespace"]
    vllm_cfg        = config.get("vllm", {})
    model           = vllm_cfg.get("model", "qwen2.5-1.5b-instruct")
    isvc_name       = vllm_cfg.get("inference_service_name", "qwen")
    inference_timeout = config["timeouts"]["inference_ready"]

    log.info("=== Deploying vLLM (%s) ===", model)

    # 1–3 — platform bootstrap (cluster validation, operator, DSC/DSCI)
    prepare.deploy_platform(config)

    # 4 — S3 credentials
    storage.apply_s3_secret(manifests.get_s3_secret(repo_root), namespace)

    # 5 — vLLM CPU ServingRuntime + InferenceService
    inference.apply_serving_runtime(assets.get_serving_runtime(repo_root), namespace)
    inference.apply_inference_service(assets.get_model_manifest(repo_root, model), namespace)
    inference.wait_until_ready(isvc_name, namespace, inference_timeout)

    log.info("=== vLLM deployment complete ===")
