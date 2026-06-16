# OGX (Open GenAI Stack) Overview

OGX (formerly known as Meta's Llama Stack) is an open-source, vendor-neutral GenAI application server. Rather than acting as just another code framework (like LangChain or LlamaIndex) that you import directly into an application script, OGX runs as a standalone network service or in-process server that unifies the entire generative AI lifecycle. It acts as an abstraction layer between your upstream user applications and your downstream AI infrastructure.

## The Architecture Shift

OGX moves GenAI logic out of your application scripts and pushes it into standard cloud-native infrastructure, making it ideal for enterprise platforms like Red Hat OpenShift AI (RHOAI).

```
[ Application Layer ]      -->  Uses standard OpenAI, Anthropic, or Google SDKs
         │
         ▼
 ┌───────────────┐
 │   OGX API     │         -->  Unified API Gateway (/v1/responses, /v1/vector_stores)
 │  Server Layer │         -->  Server-side orchestration, safety checks, & RAG execution
 └───────┬───────┘
         │
         ▼
 [ Provider Layer ]         -->  Swappable infrastructure: vLLM/Ollama (LLMs) + Milvus (DB)
```

---

## Directory Structure

Here is a recursive map of the `openshift-ai/ogx` workspace structure:

```
openshift-ai/ogx/
├── README.md                              # Main overview and entry point (this file)
├── data/
│   ├── README.md                          # Ingestion & sample data documentation
│   └── return-policy.txt                  # Sample corporate policy document for RAG tests
├── shared/
│   ├── README.md                          # Shared DB & vector store configuration guide
│   ├── milvus.yaml                        # Standalone Milvus DB manifest
│   ├── pgvector.yaml                      # PostgreSQL with pgvector StatefulSet manifest
│   └── postgres.yaml                      # Core PostgreSQL state database manifest
└── getting-started/
    ├── README.md                          # Option 1 vs Option 2 deployment steps
    ├── ogx-custom-config.ipynb            # Option 1 testing Jupyter Notebook
    ├── ogx-server-default.ipynb           # Option 2 testing Jupyter Notebook
    ├── deployments/
    │   ├── README.md                      # Deployments details and commands
    │   ├── math-mcp.yaml                  # Model Context Protocol math server deployment
    │   ├── ogx-server.yaml                # Standard OGX server Custom Resource (CR)
    │   └── ogx-server-custom-config.yaml  # ConfigMap & OGX server custom distribution
    └── notebooks/
        ├── README.md                      # Index of all 10 API verification notebooks
        ├── ogx-batches-api.ipynb          # Batch jobs creation and tracking API demo
        ├── ogx-file.ipynb                 # File upload & retrieval API (localfs vs s3)
        ├── ogx-file-processors-api.ipynb  # File chunking & processing API demo
        ├── ogx-inline-faiss-vector-files.ipynb # Inline FAISS local RAG testing
        ├── ogx-inline-milvus.ipynb        # Inline Milvus-Lite local RAG testing
        ├── ogx-messages-api-rh.ipynb      # Anthropic Messages compatible API demo
        ├── ogx-remote-milvus.ipynb        # Remote standalone Milvus RAG testing
        ├── ogx-remote-pgvector.ipynb      # Remote pgvector StatefulSet RAG testing
        ├── ogx-remote-qdrant.ipynb        # Remote Qdrant database RAG testing
        └── ogx-responses-api.ipynb        # Custom responses workflow client-side demo
```

---

## Available Subdirectory Guides

Get started by navigating to the relevant component guides:

- **[Getting Started Guide](./getting-started/README.md)** - Step-by-step instructions for deploying OGX with inline or remote databases.
- **[Shared Infrastructure Guide](./shared/README.md)** - Instructions for deploying shared databases (Postgres, pgvector, Milvus).
- **[Deployments Resource Guide](./getting-started/deployments/README.md)** - Reference sheet for custom server overrides and math helper MCP services.
- **[Demonstration Notebooks Guide](./getting-started/notebooks/README.md)** - Explanations for all 10 Jupyter validation notebooks.
- **[Sample Data Documentation](./data/README.md)** - Details on the format and ingestion flow of the grounding text.

---

## Prerequisites

Before starting, ensure you have:
- An OpenShift cluster with the Red Hat OpenShift AI operator installed.
- Access to the cluster namespace (e.g. `redhat-ods-applications` or a user project namespace).
- The `oc` CLI tool configured and authenticated to your cluster.
- Sufficient cluster permissions to create deployments, statefulsets, services, configmaps, routes, and custom resource definitions (CRDs).

---

## Additional Resources

- [OGX / Llama Stack Official Documentation](https://github.com/meta-llama/llama-stack)
