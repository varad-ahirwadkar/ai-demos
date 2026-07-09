# vLLM Embedding Runtime

Deploy and serve embedding models using vLLM runtime on Red Hat OpenShift AI.

---

## Prerequisites

1. Create a data science project:
   ```bash
   oc new-project <your-project> || oc project <your-project>
   ```

2. Navigate to the OpenShift AI demos directory:
   ```bash
   cd ai-demos/openshift-ai-demos
   ```

3. Create the vLLM CPU runtime:
   ```bash
   oc process -n redhat-ods-applications vllm-cpu-runtime-template | oc apply -f -
   ```

4. Download the model into a PVC — see [PVC Model Storage](../../README.md#option-2-pvc-huggingface-download) in the shared README.

---

## Available Models

### Granite Embedding 125M English

**Model:** `ibm-granite/granite-embedding-125m-english`
**Dimensions:** 768 (Matryoshka — supports flexible dimensions)
**Max tokens:** 512
**Total size:** ~955MB

**Download:**
```bash
export NAMESPACE=<your-project>
export MODEL_REPO=ibm-granite/granite-embedding-125m-english
export MODEL_NAME=granite-embedding-125m-english
export STORAGE_SIZE=5Gi
export STORAGE_CLASS=<your-storage-class>

envsubst '${MODEL_NAME},${NAMESPACE},${STORAGE_SIZE},${STORAGE_CLASS},${MODEL_REPO},${HF_TOKEN}' \
  < model-serving/shared/model-download.yaml | oc apply -f -
```

**Deploy:**
```bash
oc apply -f model-serving/embedding-models/vllm/granite-125m-english.yaml
```

**Minimum Resource Requirements:**
| Resource | Allocation |
|---|---|
| Runtime | vLLM (CPU) |
| CPU | 8 cores |
| Memory | 16Gi |
| Storage | 5Gi PVC |

---

### BGE-M3

**Model:** `BAAI/bge-m3`
**Dimensions:** 1024 (fixed — no Matryoshka support)
**Max tokens:** 8192
**Total size:** ~2.2GB

**Download:**
```bash
export NAMESPACE=<your-project>
export MODEL_REPO=BAAI/bge-m3
export MODEL_NAME=bge-m3
export STORAGE_SIZE=5Gi
export STORAGE_CLASS=<your-storage-class>

envsubst '${MODEL_NAME},${NAMESPACE},${STORAGE_SIZE},${STORAGE_CLASS},${MODEL_REPO},${HF_TOKEN}' \
  < model-serving/shared/model-download.yaml | oc apply -f -
```

**Deploy:**
```bash
oc apply -f model-serving/embedding-models/vllm/bge-m3.yaml
```

**Minimum Resource Requirements:**
| Resource | Allocation |
|---|---|
| Runtime | vLLM (CPU) |
| CPU | 8 cores |
| Memory | 16Gi |
| Storage | 5Gi PVC |

> **Note:** BGE-M3 does not support `embedding_dimension` parameter. Always use 1024 dimensions. Passing any other value will cause a `BadRequestError`.

---

## Model Comparison

| | Granite 125M | BGE-M3 |
|---|---|---|
| **Total size** | ~955MB | ~2.2GB |
| **Dimensions** | 768 (flexible) | 1024 (fixed) |
| **Max tokens** | 512 | 8192 |
| **Languages** | English | 100+ |
| **Matryoshka** | ✅ Yes | ❌ No |
| **License** | Apache 2.0 | MIT |
| **Best for** | English RAG, CPU-constrained | Multilingual, long docs |

---

## vLLM Configuration Reference

### Args

| Argument | Description |
|---|---|
| `--served-model-name` | Name exposed via the API (`/v1/models`). Clients use this to call the model. |
| `--runner=pooling` | Use the pooling runner — required for embedding models that output vectors instead of tokens. |
| `--max-model-len` | Maximum input sequence length in tokens. Requests exceeding this are rejected. |
| `--max-num-seqs` | Maximum number of concurrent requests. Lower = less memory, higher = more throughput. |
| `--dtype=bfloat16` | Weight precision. Uses half the memory of `float32` with minimal accuracy loss. |
| `--disable-custom-all-reduce` | Disables custom CUDA all-reduce kernel — required when running on CPU. |
| `--trust-remote-code` | Allows loading custom model code from HuggingFace (needed for some models). |
| `--gpu-memory-utilization` | Fraction of GPU memory to use. Set low (e.g. `0.4`) on CPU to limit KV cache allocation. |
| `--hf-overrides` | JSON overrides for the model config. Used to enable Matryoshka dimensions. |

### Environment Variables

| Variable | Description |
|---|---|
| `VLLM_ENGINE_ITERATION_TIMEOUT_S` | Timeout in seconds for a single engine iteration. Set high for CPU inference (e.g. `1200`). |
| `VLLM_CPU_KVCACHE_SPACE` | KV cache size in GB allocated on CPU. Larger = more concurrent requests cached. |
| `VLLM_CPU_OMP_THREADS_BIND` | Binds OpenMP threads to CPU cores. Set to `auto` for optimal CPU performance. |
| `VLLM_LOGGING_LEVEL` | Log verbosity. Use `INFO` for production, `DEBUG` for troubleshooting. |

---

## Verify Deployment

```bash
# List InferenceServices
oc get inferenceservice

# Watch predictor pod
oc get pods -w | grep predictor

# Check logs
oc logs -f <predictor-pod-name> -c kserve-container
```

---

## Test the Model

```bash
ISVC=<inferenceservice-name>
MODEL_URL=$(oc get inferenceservice $ISVC -o jsonpath='{.status.url}')
MODEL_NAME=$(curl -sk $MODEL_URL/v1/models | jq -r '.data[0].id')
```

### List Models
Lists all models currently served by the runtime.

```bash
curl -sk $MODEL_URL/v1/models | jq .

{
  "object": "list",
  "data": [
    {
      "id": "bge-m3",
      "object": "model",
      "created": 1783575578,
      "owned_by": "vllm",
      "root": "/mnt/models",
      "parent": null,
      "max_model_len": 8192,
      "permission": [
        {
          "id": "modelperm-ad65d9624eb9de03",
          "object": "model_permission",
          "created": 1783575578,
          "allow_create_engine": false,
          "allow_sampling": true,
          "allow_logprobs": true,
          "allow_search_indices": false,
          "allow_view": true,
          "allow_fine_tuning": false,
          "organization": "*",
          "group": null,
          "is_blocking": false
        }
      ]
    }
  ]
}
```

### Single Input
Generate an embedding vector for a single text input.

```bash
curl -sk $MODEL_URL/v1/embeddings \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL_NAME\",\"input\":\"What is machine learning?\"}" | jq .

{
  "id": "embd-bf25400d42e0341b",
  "object": "list",
  "created": 1783575634,
  "model": "bge-m3",
  "data": [
    {
      "index": 0,
      "object": "embedding",
      "embedding": [
        -0.046485308557748795,
        -0.022186171263456345,
        -0.030788971111178398,
        -0.0025280159898102283,
        0.008489605970680714,
        0.011244012042880058,
        -0.04618345946073532,
        .
        .
        .
        0.0047919112257659435,
        0.02460099197924137,
        0.007169000804424286
      ]
    }
  ],
  "usage": {
    "prompt_tokens": 7,
    "total_tokens": 7,
    "completion_tokens": 0,
    "prompt_tokens_details": null
  }
}
```

### Batch Input
Embed multiple texts in one request and return the vector dimensions per input.

```bash
curl -sk $MODEL_URL/v1/embeddings \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL_NAME\",\"input\":[\"What is machine learning?\",\"How does RAG work?\",\"Explain vector search\"]}" \
  | jq '[.data[] | {index: .index, dimensions: (.embedding | length)}]'

[
  {
    "index": 0,
    "dimensions": 1024
  },
  {
    "index": 1,
    "dimensions": 1024
  },
  {
    "index": 2,
    "dimensions": 1024
  }
]
```

### Check Embedding Dimensions
Returns the number of dimensions in the embedding vector.

```bash
curl -sk $MODEL_URL/v1/embeddings \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL_NAME\",\"input\":\"test\"}" \
  | jq '.data[0].embedding | length'

1024
```

### Pooling API (vLLM native)
vLLM's native pooling endpoint — same vectors as `/v1/embeddings` but with a different response format.

```bash
curl -sk $MODEL_URL/pooling \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL_NAME\",\"input\":\"What is machine learning?\"}" | jq .

{
  "id": "pooling-9867716949c9d145",
  "object": "list",
  "created": 1783575818,
  "model": "bge-m3",
  "data": [
    {
      "index": 0,
      "object": "pooling",
      "data": [
        -0.046485308557748795,
        -0.022186171263456345,
        -0.030788971111178398,
        -0.0025280159898102283,
        .
        .
        .
        0.0047919112257659435,
        0.02460099197924137,
        0.007169000804424286
      ]
    }
  ],
  "usage": {
    "prompt_tokens": 7,
    "total_tokens": 7,
    "completion_tokens": 0,
    "prompt_tokens_details": null
  }
}
```


> **Security Note:** The `-k` flag disables SSL certificate verification. Only use in development/testing environments.
