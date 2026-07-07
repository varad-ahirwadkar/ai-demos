# TechMart Customer Service Demo - Quick Start

## 🚀 What This Demo Does

This demo shows an **intelligent customer service assistant** that combines:
- **RAG**: Retrieves return policy information from documents
- **MCP**: Fetches real-time order data from CSV
- **LLM**: Provides intelligent, context-aware responses

## 📦 What's Included

```
techmart-customer-service-demo/
├── README.md              # Detailed documentation
├── QUICKSTART.md          # This file
├── requirements.txt       # Python dependencies
├── orders_mcp_server.py       # MCP server with order tools
├── test_orders.py         # Test script
├── orders.csv             # Sample order data (10 orders)
└── return-policy.txt      # Return policy document
```

## ⚡ Quick Start (5 Minutes)

### Step 1: Install Dependencies

```bash
pip install fastmcp mcp
```

### Step 2: Start the MCP Server

```bash
fastmcp run orders_mcp_server.py --transport sse --host 0.0.0.0 --port 9001
```

You should see:
```
🚀 Orders MCP Server running on http://0.0.0.0:9001
📊 Loaded 10 orders from orders.csv
```

### Step 3: Test the Server (Optional)

Open a new terminal:
```bash
python test_orders.py
```

Expected output:
```
✓ Test 1: Getting order details for ORD-2024-001...
✓ Test 2: Checking return eligibility...
```

### Step 4: Use with Llama Stack Application

The MCP server is now ready to be used by the main Llama Stack application!

## 🎯 Example Questions

Once integrated with the main app, you can ask:

1. **"Can I return order ORD-2024-001?"**
   - System retrieves return policy (RAG)
   - System fetches order details (MCP)
   - System analyzes eligibility and provides answer

2. **"I want to return my laptop, order ORD-2024-001"**
   - System identifies product category
   - System checks delivery date
   - System calculates refund with restocking fee

3. **"Is order ORD-2024-007 eligible for return?"**
   - System checks if within return window
   - System provides eligibility status

## 📊 Sample Orders

| Order ID | Product | Category | Delivered | Opened | Status |
|----------|---------|----------|-----------|--------|--------|
| ORD-2024-001 | Laptop Pro 15 | Electronics | 2024-01-18 | Yes | Check |
| ORD-2024-002 | Wireless Mouse | Electronics | 2024-01-23 | No | Check |
| ORD-2024-005 | Smart Watch | Electronics | 2024-01-16 | Yes | Check |
| ORD-2024-007 | Headphones Pro | Electronics | 2024-01-09 | Yes | Expired? |

## 🔧 MCP Server Tools

### 1. get_order(order_id)
Retrieves order details from CSV:
```json
{
  "order_id": "ORD-2024-001",
  "product_name": "Laptop Pro 15",
  "category": "Electronics",
  "price": 1299.99,
  "delivery_date": "2024-01-18",
  "is_opened": "yes"
}
```

### 2. check_return_eligibility(order_id)
Calculates return eligibility:
```json
{
  "is_eligible": true,
  "days_since_delivery": 10,
  "return_window_days": 15,
  "restocking_fee_percent": 15,
  "estimated_refund": 1104.99,
  "message": "Order is eligible for return. 5 days remaining."
}
```

## 📝 Return Policy Rules

- **Electronics**: 15 days from delivery
- **Other items**: 30 days from delivery
- **Restocking fees**:
  - Opened electronics: 15%
  - Opened other items: 10%
  - Unopened items: No fee

## 🎓 How It Works

```
User Question
    ↓
┌─────────────────────────────────┐
│  Llama Stack Application        │
│  ┌───────────────────────────┐  │
│  │ 1. RAG: Query policy doc  │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │ 2. MCP: Get order data    │  │
│  └───────────────────────────┘  │
│  ┌───────────────────────────┐  │
│  │ 3. LLM: Analyze & respond │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
    ↓
Intelligent Response
```

## 🚧 Troubleshooting

### Port Already in Use
```bash
# Check what's using port 9001
lsof -i :9001

# Kill the process
kill -9 <PID>
```

### CSV File Not Found
Make sure you're running from the correct directory:
```bash
cd techmart-customer-service-demo
fastmcp run orders_mcp_server.py --transport sse --host 0.0.0.0 --port 9001
```

### Import Errors
Install dependencies:
```bash
pip install fastmcp mcp
```

## 📚 Next Steps

1. Read the full [README.md](README.md) for detailed documentation
2. Integrate with the main Llama Stack application
3. Try different order IDs and questions
4. Extend with more tools (shipping status, initiate return, etc.)

## 🎉 Success!

Your MCP server is now running and ready to provide real-time order data to the AI assistant!

---

**Made with Bob** 🤖