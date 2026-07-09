# Embedding Models

Embedding models convert text into dense numerical vectors (embeddings) that capture semantic meaning. These vectors are used in Retrieval-Augmented Generation (RAG) pipelines, semantic search, and vector databases to find contextually similar content.

This demo demonstrates how to deploy and serve embedding models on Red Hat OpenShift AI. It provides production-ready examples of embedding model serving, enabling users to generate vector representations of text through a scalable and efficient deployment.

---

## Available Runtimes

### vLLM Runtime
High-performance inference engine supporting embedding models via the pooling runner.

**Available Models:**
- Granite Embedding 125M English
- BGE-M3

[→ View vLLM deployment guide](vllm/)
