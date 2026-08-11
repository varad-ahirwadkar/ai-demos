# TechMart Customer Service Assistant - RAG + MCP Demo

## 🎯 Overview

This demo showcases an intelligent customer service assistant that combines:
- **RAG (Retrieval-Augmented Generation)**: Knowledge from return policy documents
- **MCP (Model Context Protocol)**: Real-time order data from CSV
- **LLM (Llama 3.2)**: Intelligent analysis and responses

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    User Question                             │
│  "Can I return my laptop? Order ORD-2024-001"               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Llama Stack Application                         │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. RAG: Query return policy (FAISS vector search)   │  │
│  │     → "Electronics: 15 days, opened: 15% fee"        │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  2. MCP: Get order details via orders_mcp_server.py      │  │
│  │     → Order date, category, opened status            │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  3. LLM: Combine both + analyze eligibility          │  │
│  │     → "Yes, eligible. Refund: $1104.99 (15% fee)"    │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Components

### 1. Return Policy Document (RAG)
**File**: `sample-docs/return-policy.txt`

Contains:
- Return time limits (30 days standard, 15 days electronics)
- Refund conditions and amounts
- Restocking fees
- Process steps

### 2. Orders MCP Server
**File**: `mcp-server/orders_mcp_server.py`

**Tools**:
- `get_order(order_id)` - Fetch order details from CSV
- `check_return_eligibility(order_id)` - Calculate eligibility and refund

**Data Source**: `sample-data/orders.csv`

### 3. Llama Stack Application
**File**: `app.py`

Integrates:
- FAISS vector store for RAG
- Llama 3.2 3B Instruct model
- MCP client to call order tools
- Web UI for interaction

## 🚀 Quick Start

### Step 1: Start Orders MCP Server

```bash
cd llama-stack-demo/mcp-server
fastmcp run orders_mcp_server.py --transport sse --host 0.0.0.0 --port 9001
```

### Step 2: Upload Return Policy

1. Start the main app: `python app.py`
2. Open browser: `http://localhost:8000`
3. Upload `sample-docs/return-policy.txt`
4. Wait for processing

### Step 3: Ask Questions

**Example Questions**:

1. **Policy Only (RAG)**:
   - "What is the return policy for electronics?"
   - "How long do I have to return an item?"
   - "What are the restocking fees?"

2. **Order Only (MCP)**:
   - "Show me details for order ORD-2024-001"
   - "When was order ORD-2024-005 delivered?"

3. **Combined (RAG + MCP)**:
   - "Can I return order ORD-2024-001?" 
     → RAG: Gets policy, MCP: Gets order, LLM: Analyzes eligibility
   
   - "I want to return my laptop, order ORD-2024-001"
     → RAG: Electronics policy, MCP: Order details, LLM: Calculates refund
   
   - "Is order ORD-2024-007 eligible for return?"
     → RAG: Time limits, MCP: Delivery date, LLM: Checks if within window

## 📊 Sample Orders

| Order ID | Product | Category | Delivery | Opened | Eligible? |
|----------|---------|----------|----------|--------|-----------|
| ORD-2024-001 | Laptop Pro 15 | Electronics | 2024-01-18 | Yes | Check date |
| ORD-2024-002 | Wireless Mouse | Electronics | 2024-01-23 | No | Check date |
| ORD-2024-005 | Smart Watch | Electronics | 2024-01-16 | Yes | Check date |
| ORD-2024-007 | Headphones Pro | Electronics | 2024-01-09 | Yes | Likely expired |

## 🧪 Testing

### Test MCP Server Only

```bash
cd llama-stack-demo/mcp-server
python test_orders.py
```

**Expected Output**:
```
Test 1: Getting order details for ORD-2024-001...
{
  "order_id": "ORD-2024-001",
  "product_name": "Laptop Pro 15",
  "category": "Electronics",
  "price": 1299.99,
  "is_opened": "yes"
}

Test 2: Checking return eligibility...
{
  "is_eligible": true,
  "restocking_fee_percent": 15,
  "estimated_refund": 1104.99,
  "message": "Order is eligible for return. 5 days remaining."
}
```

### Test Complete Flow

1. Start orders MCP server (port 9001)
2. Start main app (port 8000)
3. Upload return policy document
4. Ask: "Can I return order ORD-2024-001?"

**Expected Response**:
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

## 🎓 How It Works

### Scenario: User asks "Can I return order ORD-2024-001?"

**Step 1: RAG Retrieval**
```python
# Query FAISS vector store
query = "return policy electronics"
docs = vector_store.similarity_search(query)
# Returns: "Electronics: 15 days, opened: 15% restocking fee"
```

**Step 2: MCP Tool Call**
```python
# Call MCP server
result = mcp_client.call_tool("check_return_eligibility", {
    "order_id": "ORD-2024-001"
})
# Returns: {
#   "is_eligible": true,
#   "days_since_delivery": 10,
#   "restocking_fee_percent": 15,
#   "estimated_refund": 1104.99
# }
```

**Step 3: LLM Analysis**
```python
# Combine context
context = f"""
Policy: {rag_docs}
Order: {mcp_result}
"""

# Generate response
response = llm.generate(context + user_question)
# Returns: Intelligent analysis combining both sources
```

## 🔧 Configuration

### MCP Server Port
Edit `orders_mcp_server.py`:
```python
# Default: port 9001
# Change in logger.info and get_server_info()
```

### Orders Data
Edit `sample-data/orders.csv`:
```csv
order_id,customer_email,product_name,category,order_date,delivery_date,price,status,is_opened
ORD-2024-XXX,email@example.com,Product Name,Category,2024-01-01,2024-01-05,99.99,delivered,no
```

### Return Policy
Edit `sample-docs/return-policy.txt` to modify:
- Return windows
- Restocking fees
- Refund conditions

## 📝 Key Features

✅ **RAG**: Semantic search over policy documents
✅ **MCP**: Real-time data from CSV/database
✅ **LLM**: Intelligent reasoning and analysis
✅ **Combined**: Context-aware responses
✅ **CPU-Optimized**: Works on CPU-only systems
✅ **Extensible**: Easy to add more tools/documents

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

Replace CSV with PostgreSQL/MongoDB:
```python
import psycopg2

def load_orders():
    conn = psycopg2.connect(...)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders")
    return cursor.fetchall()
```

## 📚 Documentation

- **Main README**: `README.md`
- **Quick Start**: `QUICKSTART.md`
- **MCP Server**: `mcp-server/README.md`

## 🎉 Summary

This demo shows how to build intelligent assistants that combine:
- **Static knowledge** (RAG from documents)
- **Dynamic data** (MCP from databases/APIs)
- **AI reasoning** (LLM analysis)

Perfect for customer service, support, and operational use cases!

---

**Made with Bob** 🤖