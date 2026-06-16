# OGX Getting Started Guide

This guide walks you through deploying and configuring OGX (Open GenAI Stack) on Red Hat OpenShift AI (RHOAI). OGX provides a unified, API-compatible abstraction layer between your frontend applications and downstream AI models/services.

For more details on the individual files inside these subdirectories, refer to:
- **[Deployments README](./deployments/README.md)** - Details on deployment manifests and Custom Resources.
- **[Notebooks README](./notebooks/README.md)** - Breakdown of all 10 demonstration and test notebooks.

---

## Deployment Options

We cover two deployment configurations:

1. **Option 1: User-Defined Config (Custom)**: Uses an inline vector provider configuration (Milvus-Lite, FAISS, inline sentence-transformers) for a localized setup. Best for fast development and proof-of-concepts.
2. **Option 2: Default Config (Remote)**: Connects to remote standalone databases (external pgvector or remote Milvus) for production-grade setups.

---

## Option 1: User-Defined Config (Custom/Inline)

This configuration does not require spinning up heavy external standalone databases as it leverages in-memory and SQLite-based vector indexes inside the pod.

### Step 1: Deploy the LLM Model
Process the CPU runtime template and deploy your target large language model using OpenShift AI Serving:

```bash
oc process -n redhat-ods-applications vllm-cpu-runtime-template | oc create -f -
oc create -f ../../model-serving/llama-32-3b-instruct-isvc.yaml
```

**Verify model deployment:**
```bash
oc get isvc
oc get pods | grep llama
```

### Step 2: Deploy Postgres for Server State
Deploy the standard PostgreSQL database instance to store server state and metadata (conversations, telemetry, KV cache):

```bash
oc create -f ../shared/postgres.yaml
```

**Verify PostgreSQL health:**
```bash
oc get pods | grep postgres
```

### Step 3: Deploy Custom OGX Server
Create the Custom Config ConfigMap and apply the custom OGX server resource:

```bash
oc create -f deployments/ogx-server-custom-config.yaml
```

**Verify server health:**
```bash
oc get pods | grep ogx
oc logs -f ogxserver-<pod-hash>
```

### Step 4: Deploy the Math MCP Server (Optional)
MCP servers allow the model to query calculations and external tools:

```bash
oc create -f deployments/math-mcp.yaml
```

### Step 5: Run Ingestion and RAG Tests
1. Open a Jupyter Notebook workspace inside your OpenShift AI dashboard.
2. Upload the `ogx-custom-config.ipynb` notebook and upload `return-policy.txt` from the `../data/` directory.
3. Open and run the notebook:
   - **Notebook Link**: [ogx-custom-config.ipynb](./ogx-custom-config.ipynb)

---

## Option 2: Default Config (Remote DBs)

This configuration targets remote or external vector store engines, suitable for production clusters where data persistence must survive pod lifecycles.

### Vector Store Prerequisites for Notebooks

Depending on which notebook you want to run from the [notebooks/](./notebooks) directory, you must ensure the corresponding vector database is deployed and reachable by the OGX Server:

#### 1. Inline Vector Stores (No Deployment Needed)
- **FAISS**: Runs entirely in-process using local memory. No database deployment required. Verified via `ogx-inline-faiss-vector-files.ipynb`.
- **Milvus-Lite**: Runs inline in the OGX container using a local file-based SQLite database. No standalone service deployment required. Verified via `ogx-inline-milvus.ipynb`.

#### 2. Standalone/Remote Vector Stores (Deployment Required in OCP / External VM)
For standalone databases, you must deploy the services and ensure the OGX server's environment variables or custom ConfigMaps match their connection endpoints:

- **pgvector**:
  - Refer to the **[Shared Infrastructure Guide](../shared/README.md)** to deploy pgvector inside your OpenShift cluster (Option A) or set it up on an external VM/host container (Option B).
  - Verified via `ogx-remote-pgvector.ipynb`.
- **Milvus Standalone**:
  - Deploy standalone Milvus (along with etcd) inside your OpenShift project by following the instructions in the **[Shared Infrastructure Guide](../shared/README.md)**.
  - Verified via `ogx-remote-milvus.ipynb`.
- **Qdrant**:
  - Ensure you have a Qdrant deployment running and accessible inside OCP, with its endpoint and API key mapped (e.g. `http://qdrant-service.llama.svc.cluster.local:6333`).
  - Verified via `ogx-remote-qdrant.ipynb`.

---

### Clean Up Previous Resources
If you completed Option 1, clean up the custom configuration and local databases first:

```bash
oc delete -f deployments/ogx-server-custom-config.yaml
oc delete -f ../shared/postgres.yaml
```

### Step 1: Deploy the Embedding Model
Deploy the Granite embedding model:

```bash
oc create -f ../../model-serving/granite-embedding-125m-english.yaml
```

**Verify embedding model deployment:**
```bash
oc get isvc | grep granite
```

### Step 2: Deploy Postgres Database
Deploy Postgres inside the cluster to handle basic key-value data:

```bash
oc create -f ../shared/postgres.yaml
```

### Step 3: Deploy OGX Server
Deploy the default remote-configured OGX Server:

```bash
oc create -f deployments/ogx-server.yaml
```

**Verify deployment:**
```bash
oc get pods | grep ogx
```

### Step 4: Deploy Math MCP Server
```bash
oc create -f deployments/math-mcp.yaml
```

### Step 5: Test with Jupyter Notebook
Launch a Jupyter Workspace, upload `ogx-server-default.ipynb` along with `return-policy.txt` from `../data/`, and run the cells:
- **Notebook Link**: [ogx-server-default.ipynb](./ogx-server-default.ipynb)

---

## Deep Dive / Advanced Notebooks

For testing specific APIs recursively (such as Files, Batches, or alternative databases like Qdrant and standalone Milvus), we provide 10 additional notebooks in the `notebooks/` directory.

See [Notebooks README](./notebooks/README.md) for full descriptions and indexing guides.
