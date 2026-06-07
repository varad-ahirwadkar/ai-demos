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



## Available Guides

This directory contains guides and demos for deploying and using OGX on OpenShift AI:

- **[Getting Started Guide](./getting-started/README.md)** - Step-by-step instructions for deploying OGX with different configurations

## Prerequisites

Before starting, ensure you have:
- OpenShift cluster with OpenShift AI operator installed
- Access to the `redhat-ods-applications` namespace
- `oc` CLI tool configured and authenticated
- Sufficient permissions to create deployments, services, and routes


## Additional Resources

- [OGX Official Documentation](https://github.com/meta-llama/llama-stack)
