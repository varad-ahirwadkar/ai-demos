# OGX Server and Helper Deployments

This directory contains manifests for deploying the OGX (Open GenAI Stack) server and auxiliary microservices (like Model Context Protocol servers) on OpenShift.

## Manifests Overview

| File | Resource Type | Description |
| :--- | :--- | :--- |
| **[math-mcp.yaml](./math-mcp.yaml)** | `Deployment`, `Service`, `Route` | Deploys a **Model Context Protocol (MCP)** server providing basic mathematical calculations tools to LLMs. |
| **[ogx-server.yaml](./ogx-server.yaml)** | `OGXServer` (Custom Resource) | Configures and deploys the default OGX Server with **remote** backend database engines (e.g., external pgvector, remote Milvus). |
| **[ogx-server-custom-config.yaml](./ogx-server-custom-config.yaml)** | `ConfigMap`, `OGXServer` (Custom Resource) | Configures and deploys OGX Server with a comprehensive custom configuration, including **inline** vector DBs (FAISS, Milvus-Lite), inline sentence-transformers, and various third-party remote providers. |

---

## Deployment & Details

### 1. Simple Math MCP Server (`math-mcp.yaml`)
Model Context Protocol (MCP) allows AI servers or clients to safely delegate capability tasks (like executing calculations, reading DBs, or doing web searches) to local/remote tools. This YAML deploys a math tool server running on container port `9000` exposed as an SSE endpoint.

**Apply deployment:**
```bash
oc create -f math-mcp.yaml
```

**Route Information:**
Once deployed, the router will expose an external URL. You can locate it with:
```bash
oc get route math-mcp-server
```

---

### 2. Default OGX Server (`ogx-server.yaml`)
This deploys the OGX server with environment variable overrides that connect to external or remote services (Postgres, vLLM inference engine, remote Milvus, remote Qdrant, etc.). It assumes the OGX operator or controller is active in the cluster to manage the `OGXServer` CR.

**Key Environment Variables Defined:**
- `VLLM_URL` / `VLLM_EMBEDDING_URL`: Downstream LLM serving routes.
- `ENABLE_PGVECTOR` & `PGVECTOR_HOST`: Connection settings for remote pgvector.
- `MILVUS_ENDPOINT` & `MILVUS_TOKEN`: Connection settings for remote Milvus service.

**Apply deployment:**
```bash
oc create -f ogx-server.yaml
```

---

### 3. Custom OGX Server with ConfigMap (`ogx-server-custom-config.yaml`)
If you require custom provider configurations (such as embedding models running in-process via `inline::sentence-transformers`, local folder-based indexing via `inline::faiss`, or Milvus-Lite), you can provide a config file in a ConfigMap and mount it to the `OGXServer` Custom Resource.

**Structure of `config.yaml` inside the ConfigMap:**
1. **APIs Enabled**: `responses`, `messages`, `batches`, `inference`, `tool_runtime`, `vector_io`, `files`, `file_processors`.
2. **Inference Providers**: Remote vLLM, inline sentence-transformers, Bedrock, WatsonX, Azure, VertexAI, OpenAI, Gemini, Anthropic.
3. **Vector IO Providers**: Inline FAISS, Inline Milvus (Lite), Remote Milvus, Remote pgvector, Remote Qdrant.
4. **Tool Runtime**: Brave Search, Tavily Search, File Search, Model Context Protocol (MCP).
5. **Storage Backends**: PostgreSQL for key-value stores (`kv_postgres`) and SQL database tables (`sql_postgres`).

**Apply deployment:**
```bash
oc create -f ogx-server-custom-config.yaml
```

---

## Verifying Server Status

For either deployment, check the pods and service status to confirm execution:

```bash
# Check if pods are running
oc get pods | grep ogxserver

# View container logs
oc logs -f ogxserver-<pod-id>
```
