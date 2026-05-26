# Model Serving on Red Hat OpenShift AI

Deploy and serve Large Language Models (LLMs) on Red Hat OpenShift AI using KServe InferenceService and the vLLM runtime.

> Note: The current examples use the vLLM runtime. Additional runtimes may be added in future demos.

---

## Prerequisites

Before deploying models, complete the setup steps described in the [OpenShift AI README](../README.md#getting-started):

1. Configure `DSCInitialization` and `DataScienceCluster`
2. Create the S3 secret with your object storage credentials
3. Navigate to this directory:

```bash
cd ai-demos/openshift-ai/model-serving
```
4. Create a model serving runtime:
```
oc process -n redhat-ods-applications vllm-cpu-runtime-template | oc create -f -
```

## Available Models

### Phi-3-mini-4k-instruct

**Deploy:**
```bash
oc apply -f phi3.yaml
```

**Specifications:**
| Resource | Allocation    |
| -------- | ------------- |
| Runtime  | vLLM (CPU)    |
| CPU      | 6 to 10 cores |
| Memory   | 16Gi to 20Gi  |

### Qwen2.5-1.5B-Instruct

**Deploy:**
```bash
oc apply -f qwen.yaml
```

**Specifications:**
| Resource | Allocation    |
| -------- | ------------- |
| Runtime  | vLLM (CPU)    |
| CPU      | 32 cores      |
| Memory   | 40Gi          |

## Verify Deployment

```bash
# List InferenceServices
oc get inferenceservice

# Check status
oc describe inferenceservice <inferenceservice-name>
```

## Test the Model

```bash
# Get model URL
MODEL_URL=$(oc get inferenceservice <inferenceservice-name> -o jsonpath='{.status.url}')

# Get model name
MODEL_NAME=$(curl -sk "$MODEL_URL/v1/models" | jq -r '.data[0].id')

# Send test request
curl -sk -X POST "$MODEL_URL/v1/completions" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"$MODEL_NAME\",
    \"prompt\": \"What is machine learning?\",
    \"max_tokens\": 100
  }"
```

## Troubleshooting

**Model fails to load:**
- Verify S3 credentials in [`../shared/s3-secret.yaml`](../shared/s3-secret.yaml)
- Confirm model path exists in S3 bucket
- Check pod logs: `oc logs <predictor-pod-name>`

**Insufficient resources:**
- Adjust resource limits in YAML files
- Verify cluster capacity: `oc describe nodes`


## Resources

- [KServe Documentation](https://kserve.github.io/website/)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Red Hat OpenShift AI Docs](https://access.redhat.com/documentation/en-us/red_hat_openshift_ai_self-managed/)
