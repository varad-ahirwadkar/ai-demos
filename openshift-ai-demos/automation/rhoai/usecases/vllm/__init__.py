"""vLLM generative use case.

Deploys a generative LLM via KServe/vLLM on CPU:
    - Shared vLLM CPU ServingRuntime
    - Configurable InferenceService (qwen2.5, phi-3, qwen3, …)

Public interface (consumed by usecases/registry.py):
    deploy(config)
    verify(config)
    cleanup(config)
"""

from rhoai.usecases.vllm.cleanup import cleanup
from rhoai.usecases.vllm.deploy import deploy
from rhoai.usecases.vllm.verify import verify

__all__ = ["deploy", "verify", "cleanup"]
