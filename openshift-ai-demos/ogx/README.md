# OGX Demos

Demonstrations built on OGX, the Red Hat OpenShift AI component that provides a
unified, OpenAI-compatible API for models, tools, and data sources. OGX
orchestrates retrieval (RAG), tool calling (MCP), and model inference behind a
single endpoint.

## Prerequisites

Complete the setup steps in the [OpenShift AI README](/openshift-ai-demos/README.md#getting-started):
1. Configure DSCInitialization and DataScienceCluster — the DSC must have both
   **KServe** (model serving) and **OGX** enabled.
2. Create the S3 secret with your storage credentials *(only if the demo serves
   models from object storage)*.

## Available Demos

### TechMart Customer Service Assistant
A customer service assistant for a fictional electronics retailer, combining RAG
over policy documents with MCP tool calls against a PostgreSQL order database.
Serves Qwen3-4B-Instruct on vLLM behind a Flask UI.

[→ Explore TechMart Customer Service](techmart-customer-service/)

---

## Shared Resources

[`shared/`](shared/) contains resources used across OGX demos:
- [`ogx-metadata-postgres.yaml`](shared/ogx-metadata-postgres.yaml) — PostgreSQL instance backing the OGX
  server's internal state, plus the `postgres-credentials` secret the OGX server
  reads. Deploy this **before** the OGX server, or it will fail to start.

> **Note:** `ogx-metadata-postgres.yaml` hardcodes the `ogx-sandbox` namespace in
> `POSTGRES_HOST`. If you deploy to a different namespace, update that value to
> match.

## Resources

- [Red Hat OpenShift AI Docs](https://access.redhat.com/documentation/en-us/red_hat_openshift_ai_self-managed/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
</content>
