# OGX Demonstration Notebooks

This directory contains interactive Jupyter Notebooks designed to guide you through testing and executing different capabilities of the OGX (Open GenAI Stack) server.

## Overview of Notebooks

The notebooks are grouped by functional areas so you can easily target specific features:

### 1. Core OGX & Client APIs
These notebooks demonstrate standard request patterns using either the OpenAI python library or the native `OgxClient` SDK wrapper.

- **[ogx-responses-api.ipynb](./ogx-responses-api.ipynb)**
  - *Description*: Demonstrates how to use the custom OGX `responses` endpoint using `OgxClient`. Includes creating responses, retrieving specific responses, listing all saved responses, deleting responses, and testing background execution with cancellation requests.
- **[ogx-messages-api-rh.ipynb](./ogx-messages-api-rh.ipynb)**
  - *Description*: Demonstrates the Anthropic-compatible Messages API (`/v1/messages`). Shows how OGX handles multi-turn chats and translates formats under the hood.
- **[ogx-batches-api.ipynb](./ogx-batches-api.ipynb)**
  - *Description*: Showcases how to dispatch batch offline inference tasks using files via the OpenAI SDK, including tracking progress, canceling jobs, and parsing final outputs.

### 2. Files & Processing APIs
These notebooks cover file uploads, storage options, and server-side text processors.

- **[ogx-file.ipynb](./ogx-file.ipynb)**
  - *Description*: Demonstrates standard file upload, retrieval, and deletion operations utilizing different storage backends (`localfs` vs `s3`).
- **[ogx-file-processors-api.ipynb](./ogx-file-processors-api.ipynb)**
  - *Description*: Demonstrates document chunking and processing for text (`return-policy.txt`) and PDF (`sample.pdf`) documents using various inline file processors (auto-detect, MarkItDown, pypdf, and docling). Describes how to configure and switch processors in the ConfigMap.

### 3. Vector DBs and RAG (Retrieval-Augmented Generation)
These notebooks walk through creating vector stores, uploading document files (`return-policy.txt`), indexing them with embeddings, and running context-grounded queries.

| Notebook | Vector Engine Type | Key Technologies Used |
| :--- | :--- | :--- |
| **[ogx-inline-faiss-vector-files.ipynb](./ogx-inline-faiss-vector-files.ipynb)** | **Inline** (In-process) | FAISS index, inline sentence-transformers |
| **[ogx-inline-milvus.ipynb](./ogx-inline-milvus.ipynb)** | **Inline** (In-process) | Milvus-Lite, local SQLite db path |
| **[ogx-remote-milvus.ipynb](./ogx-remote-milvus.ipynb)** | **Remote** (Standalone Pod) | Standalone Milvus Service, gRPC |
| **[ogx-remote-pgvector.ipynb](./ogx-remote-pgvector.ipynb)** | **Remote** (StatefulSet) | PostgreSQL with pgvector extension |
| **[ogx-remote-qdrant.ipynb](./ogx-remote-qdrant.ipynb)** | **Remote** (External Service) | Qdrant vector engine |

---

## Running the Notebooks

1. Ensure the OGX Server has been successfully deployed and its route/service is reachable.
2. Launch a Jupyter Workspace in your OpenShift AI dashboard.
3. Upload this `notebooks/` directory and the `data/` folder containing the `return-policy.txt` and `sample.pdf` assets.
4. Verify the `OGX_CONNECTION_URL` variable in the first cells corresponds to your cluster-internal service (e.g., `http://ogxserver-service.llama.svc.cluster.local:8321/v1`).
5. Run the cells sequentially to observe model completions, vector uploads, and chunking outputs.
