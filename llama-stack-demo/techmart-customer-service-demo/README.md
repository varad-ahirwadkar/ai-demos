# TechMart Customer Service Assistant

## 🚀 Overview

An intelligent customer service assistant built with **Red Hat OpenShift Llama Stack** that demonstrates **RAG + MCP integration** for e-commerce support.

## 📂 Project Structure

```
techmart-customer-service-demo/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
│
├── src/                         # Source code
│   ├── app.py                   # Flask web application
│   ├── orders_mcp_server.py         # MCP server
│   └── templates/
│       └── index.html           # Web UI
│
├── data/                        # Data files
│   ├── orders.csv               # Sample order data
│   └── return-policy.txt        # Return policy document
│
├── docs/                        # Documentation
│   ├── QUICKSTART.md            # 5-minute setup guide
│   └── CONTAINER-DEPLOYMENT.md  # Container deployment guide
│
├── scripts/                     # Utility scripts
│   ├── build-containers.sh      # Build containers
│   ├── run-containers.sh        # Run containers
│   ├── stop-containers.sh       # Stop containers
│   └── test_orders.py           # Test MCP server
│
└── deployments/                 # Container & K8s files
    ├── Containerfile.mcp        # MCP server container
    ├── Containerfile.ui         # UI application container
    └── docker-compose.yaml      # Compose orchestration
```

## 🎯 Key Features

✅ **RAG**: Retrieves return policy information from documents  
✅ **MCP**: Fetches real-time order data from CSV  
✅ **Web UI**: Beautiful, responsive customer interface  
✅ **Containerized**: Ready to deploy with Docker/Podman  
✅ **Documented**: Comprehensive guides included  

## 🚀 Quick Start

### Option 1: Using Scripts (Recommended)

```bash
# Build containers
cd scripts
./build-containers.sh

# Run containers
./run-containers.sh

# Access UI at http://localhost:8000
```

### Option 2: Using Docker Compose

```bash
cd deployments
docker-compose up -d
```

### Option 3: Development Mode (No Containers)

```bash
# Terminal 1: Start MCP Server
cd src
fastmcp run orders_mcp_server.py --transport sse --host 0.0.0.0 --port 9001

# Terminal 2: Start Web App
cd src
python app.py

# Open browser: http://localhost:8000
```

## 💬 Example Questions

Once running, try these questions:

1. **"Can I return order ORD-2024-001?"**
   - Combines policy (RAG) + order data (MCP)
   - Response: Eligibility status and refund amount

2. **"What is the return policy for electronics?"**
   - Pure RAG query from policy document

3. **"Show me details for order ORD-2024-005"**
   - Pure MCP query from CSV data

## 📊 Sample Orders

| Order ID | Product | Category | Delivered | Status |
|----------|---------|----------|-----------|--------|
| ORD-2024-001 | Laptop Pro 15 | Electronics | 2024-01-18 | Check |
| ORD-2024-002 | Wireless Mouse | Electronics | 2024-01-23 | Check |
| ORD-2024-005 | Smart Watch | Electronics | 2024-01-16 | Check |
| ORD-2024-007 | Headphones Pro | Electronics | 2024-01-09 | Check |

## 🔧 Configuration

### Environment Variables

**UI Application** (`src/app.py`):
- `PORT`: Web server port (default: 8000)
- `LLAMA_STACK_URL`: Llama Stack endpoint (default: http://localhost:5001)
- `MCP_SERVER_URL`: MCP Server endpoint (default: http://localhost:9001/sse)

**MCP Server** (`src/orders_mcp_server.py`):
- No configuration needed (uses defaults)

## 📚 Documentation

- **[QUICKSTART.md](docs/QUICKSTART.md)** - 5-minute setup guide
- **[CONTAINER-DEPLOYMENT.md](docs/CONTAINER-DEPLOYMENT.md)** - Detailed container deployment
- **[README-RELOAD.md](README-RELOAD.md)** - How to reload order data dynamically
- **[README-CONTAINER.md](README-CONTAINER.md)** - Container deployment options

## 🧪 Testing

Test the MCP server:
```bash
cd scripts
python test_orders.py
```

## 🎓 What This Demonstrates

This demo showcases how to build intelligent assistants that combine:
- **Static knowledge** (RAG from documents)
- **Dynamic data** (MCP from databases/APIs)
- **AI reasoning** (intelligent analysis)
- **Container deployment** (Docker/Podman/OpenShift ready)

Perfect for customer service, support, and operational use cases!

## 🛠️ Development

### Adding More Tools

Edit `src/orders_mcp_server.py`:
```python
@mcp.tool()
def get_shipping_status(order_id: str) -> dict:
    """Get real-time shipping status"""
    # Implementation
    pass
```

### Adding More Documents

Add files to `data/` directory and update `src/app.py` to load them.

### Connecting to Real Database

Replace CSV loading in `src/orders_mcp_server.py` with database queries.

## 📝 License

See LICENSE file in repository root.

---

**Made with Bob** 🤖