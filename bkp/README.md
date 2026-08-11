# TechMart AI Assistant - Llama Stack Demo

## Now let me create a comprehensive main README:

<write_to_file>
<path>llama-stack-demo/README.md</path>
<content># TechMart AI Assistant - Llama Stack Demo

## 🚀 Overview

This project demonstrates an **intelligent customer service assistant** built using **Red Hat OpenShift Llama Stack** that combines:

- **RAG (Retrieval-Augmented Generation)**: Knowledge from documents
- **MCP (Model Context Protocol)**: Real-time data from systems
- **LLM (Llama 3.2)**: Intelligent analysis and responses

## 🎯 Key Features

✅ **RAG + MCP Integration**: Combines static knowledge with dynamic data
✅ **Customer Service Use Case**: Realistic e-commerce return scenarios
✅ **OpenShift Ready**: Containerized deployment manifests
✅ **CPU Optimized**: Works on standard hardware
✅ **Extensible Architecture**: Easy to add more tools/documents

## 📦 Project Structure

```
llama-stack-demo/
├── app.py                  # Main application with RAG + MCP integration
├── requirements.txt        # Python dependencies
├── QUICKSTART.md            # Quick start guide
├── RAG-MCP-DEMO.md         # Detailed demo documentation
├── sample-docs/             # Documents for RAG
│   └── return-policy.txt   # Return policy document
├── sample-data/             # Data for MCP
│   └── orders.csv           # Sample order data
├── mcp-server/              # MCP servers
│   ├── orders_mcp_server.py     # Orders MCP server
│   ├── test_orders.py       # Test script
│   └── README.md            # MCP server docs
├── deployment/              # OpenShift manifests
│   ├── llama-stack-distribution.yaml
│   └── document-qa-app.yaml
└── templates/               # Web UI
    └── index.html           # Customer service interface
```

## � Demo Scenarios

### 1. Return Policy Questions (RAG)
- "What is the return policy for electronics?"
- "How long do I have to return an item?"
- "What are the restocking fees?"

### 2. Order Status Questions (MCP)
- "Show me details for order ORD-2024-001"
- "When was order ORD-2024-005 delivered?"

### 3. Combined RAG + MCP Questions
- "Can I return order ORD-2024-001?"
- "I want to return my laptop, order ORD-2024-001"
- "Is order ORD-2024-007 eligible for return?"

## 🚀 Quick Start

### 1. Start Orders MCP Server
```bash
cd mcp-server
fastmcp run orders_mcp_server.py --transport sse --host 0.0.0.0 --port 9001
```

### 2. Start Main Application
```bash
python app.py
```

### 3. Open in Browser
Visit: `http://localhost:8000`

### 4. Upload Return Policy
Upload `sample-docs/return-policy.txt`

### 5. Ask Questions
Try the sample questions above!

## 📊 Sample Output

**Question**: "Can I return order ORD-2024-001?"

**Response**:
```
Based on the return policy and your order details:

Order ORD-2024-001 (Laptop Pro 15) was delivered on 2024-01-18.

✓ Eligible for return (within 15-day window for electronics)
✗ Item has been opened (15% restocking fee applies)

Estimated refund: $1,104.99
Original price: $1,299.99
Restocking fee: $195.00 (15%)

To proceed with the return:
1. Log into your TechMart account
2. Go to My Orders
3. Select order ORD-2024-001
4. Click "Return Item"
```

## 🔧 Technical Details

### RAG Implementation
- **FAISS Vector Store**: Efficient semantic search
- **Document Chunking**: 512 token chunks with 128 token overlap
- **Embeddings**: Sentence transformers for document representation

### MCP Implementation
- **FastMCP Framework**: Python decorators for tool definition
- **SSE Transport**: Real-time communication
- **CSV Data Source**: Simple file-based order storage

### LLM Integration
- **Llama 3.2 3B Instruct**: Local CPU-friendly model
- **Context Combination**: Merges RAG and MCP results
- **Response Generation**: Intelligent analysis

## 📚 Documentation

- [Quick Start Guide](QUICKSTART.md)
- [Detailed Demo Documentation](RAG-MCP-DEMO.md)
- [MCP Server Documentation](mcp-server/README.md)

## 🎯 Use Cases

1. **Customer Service**: Return/refund eligibility
2. **E-commerce**: Order status + policy queries
3. **Support**: Troubleshooting with live data
4. **SRE**: Runbooks + cluster state (K8s example)

## 🚧 Extending the Demo

### Add More MCP Tools
```python
@mcp.tool()
def get_shipping_status(order_id: str) -> dict:
    """Get real-time shipping status"""
    # Call shipping API
    pass

@mcp.tool()
def initiate_return(order_id: str) -> dict:
    """Start return process"""
    # Create return label
    pass
```

### Add More Documents
- Product manuals
- FAQ documents
- Warranty information
- Shipping policies

### Connect to Real Database
```python
import psycopg2

def load_orders():
    conn = psycopg2.connect(...)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders")
    return cursor.fetchall()
```

## 🎉 Summary

This demo shows how to build **intelligent assistants** that combine:
- **Static knowledge** (RAG from documents)
- **Dynamic data** (MCP from databases/APIs)
- **AI reasoning** (LLM analysis)

Perfect for **customer service, support, and operational use cases**!

---

**Made with Bob** 🤖