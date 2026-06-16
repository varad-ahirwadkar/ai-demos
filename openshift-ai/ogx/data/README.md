# Demo Data Files

This directory contains sample files used as data sources for demonstrating Retrieval-Augmented Generation (RAG) and other document processing capabilities in the OGX notebooks and servers.

## Files

### [return-policy.txt](./return-policy.txt)
A mock corporate document outlining the shipping, return, refund, and customer support policies for "TechMart". 

- **Purpose**: Acts as the grounding knowledge base for RAG validation.
- **Content Structure**: Includes shipping times, return time limits, return instructions, restocking fees, and answers to common customer service questions (FAQ).
- **Format**: Plain text (`UTF-8`).

### [sample.pdf](./sample.pdf)
A sample PDF file used for document parsing, extraction, and chunking operations.

- **Purpose**: Verified in the file processors notebook to demonstrate multi-format ingestion capabilities.
- **Format**: PDF binary.

## Ingestion Flow

In the vector store ingestion notebooks (e.g. `getting-started/notebooks/ogx-inline-faiss-vector-files.ipynb`, `ogx-remote-pgvector.ipynb`, etc.), this file is loaded, split/chunked (e.g., using static chunking), and embedded into the vector store:

```python
# Extract from notebooks:
POLICY_FILE = "data/return-policy.txt"

# 1. Upload file to OGX server via files API
file_info = client.files.create(
    file=open(POLICY_FILE, "rb"),
    purpose="assistants"
)

# 2. Bind the file to a Vector Store (e.g. with static chunking)
vector_store_file = client.vector_stores.files.create(
    vector_store_id=vector_store.id,
    file_id=file_info.id,
    chunking_strategy={
        "type": "static",
        "static": {
            "max_chunk_size_tokens": 128,
            "overlap_tokens": 20
        }
    }
)
```

After ingestion, queries like *"What is the standard shipping time?"* or *"What is the restocking fee for electronics?"* are asked to test semantic retrieval accuracy.
