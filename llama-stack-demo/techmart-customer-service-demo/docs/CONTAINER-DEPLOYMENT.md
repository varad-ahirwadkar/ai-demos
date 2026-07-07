# TechMart Customer Service Demo - Container Deployment Guide

## 🐳 Container Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker/Podman Network                     │
│                                                              │
│  ┌──────────────────┐      ┌──────────────────┐            │
│  │  MCP Server      │      │  UI Application  │            │
│  │  Port: 9001      │◄─────│  Port: 8000      │            │
│  │                  │      │                  │            │
│  │  - Order Tools   │      │  - Flask Web     │            │
│  │  - CSV Data      │      │  - REST API      │            │
│  └──────────────────┘      └──────────────────┘            │
│                                     │                        │
│                                     ▼                        │
│                            ┌──────────────────┐             │
│                            │  Llama Stack     │             │
│                            │  Port: 5001      │             │
│                            │  (External)      │             │
│                            └──────────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

## 📦 Containers

### 1. MCP Server Container
- **Image**: `techmart-mcp-server:latest`
- **Port**: 9001
- **Purpose**: Provides order lookup and eligibility checking tools
- **Data**: Includes `orders.csv` with sample order data

### 2. UI Application Container
- **Image**: `techmart-ui-app:latest`
- **Port**: 8000
- **Purpose**: Web interface for customer service
- **Dependencies**: MCP Server, Llama Stack

## 🚀 Quick Start

### Option 1: Using Build Scripts (Recommended)

```bash
# Build containers
./build-containers.sh

# Run containers
./run-containers.sh

# Stop containers
./stop-containers.sh
```

### Option 2: Using Docker Compose

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

### Option 3: Manual Podman/Docker Commands

```bash
# Build MCP Server
podman build -f Containerfile.mcp -t techmart-mcp-server:latest .

# Build UI Application
podman build -f Containerfile.ui -t techmart-ui-app:latest .

# Create network
podman network create techmart-network

# Run MCP Server
podman run -d \
  --name techmart-mcp-server \
  --network techmart-network \
  -p 9001:9001 \
  techmart-mcp-server:latest

# Run UI Application
podman run -d \
  --name techmart-ui-app \
  --network techmart-network \
  -p 8000:8000 \
  -e LLAMA_STACK_URL=http://llama-stack:5001 \
  -e MCP_SERVER_URL=http://techmart-mcp-server:9001/sse \
  techmart-ui-app:latest
```

## 🔧 Configuration

### Environment Variables

#### UI Application
- `PORT`: Web server port (default: 8000)
- `LLAMA_STACK_URL`: Llama Stack endpoint (default: http://llama-stack:5001)
- `MCP_SERVER_URL`: MCP Server endpoint (default: http://mcp-server:9001/sse)

#### MCP Server
- No configuration needed (uses defaults)

### Ports

| Service | Port | Purpose |
|---------|------|---------|
| UI App | 8000 | Web interface |
| MCP Server | 9001 | MCP tools endpoint |
| Llama Stack | 5001 | LLM inference (external) |

## 🌐 Accessing the Application

Once containers are running:

- **Web UI**: http://localhost:8000
- **MCP Server**: http://localhost:9001
- **Health Check**: http://localhost:8000/api/health

## 📊 Container Management

### View Running Containers
```bash
podman ps --filter "name=techmart-"
```

### View Logs
```bash
# MCP Server logs
podman logs -f techmart-mcp-server

# UI Application logs
podman logs -f techmart-ui-app
```

### Restart Containers
```bash
# Restart MCP Server
podman restart techmart-mcp-server

# Restart UI Application
podman restart techmart-ui-app
```

### Stop and Remove
```bash
# Stop containers
podman stop techmart-mcp-server techmart-ui-app

# Remove containers
podman rm techmart-mcp-server techmart-ui-app

# Remove network
podman network rm techmart-network
```

## 🔍 Troubleshooting

### Container Won't Start

**Check logs**:
```bash
podman logs techmart-mcp-server
podman logs techmart-ui-app
```

**Common issues**:
- Port already in use: Change port mapping
- Network issues: Recreate network
- Missing dependencies: Rebuild containers

### MCP Server Connection Failed

**Check MCP server is running**:
```bash
curl http://localhost:9001/health
```

**Check network connectivity**:
```bash
podman exec techmart-ui-app ping techmart-mcp-server
```

### UI Application Can't Connect to Llama Stack

**Verify Llama Stack is running**:
```bash
curl http://localhost:5001/health
```

**Update environment variable**:
```bash
podman run -d \
  --name techmart-ui-app \
  -e LLAMA_STACK_URL=http://host.docker.internal:5001 \
  ...
```

## 🏗️ Building for Production

### Multi-stage Build (Optimized)

Create `Containerfile.mcp.prod`:
```dockerfile
FROM python:3.12-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY orders_mcp_server.py orders.csv ./
ENV PATH=/root/.local/bin:$PATH
EXPOSE 9001
CMD ["fastmcp", "run", "orders_mcp_server.py", "--transport", "sse", "--host", "0.0.0.0", "--port", "9001"]
```

### Security Hardening

1. **Run as non-root user**:
```dockerfile
RUN useradd -m -u 1000 appuser
USER appuser
```

2. **Read-only filesystem**:
```bash
podman run --read-only --tmpfs /tmp ...
```

3. **Resource limits**:
```bash
podman run --memory=512m --cpus=1 ...
```

## 🚢 Deploying to OpenShift

### Create ImageStreams
```bash
oc create imagestream techmart-mcp-server
oc create imagestream techmart-ui-app
```

### Build in OpenShift
```bash
oc new-build --name=techmart-mcp-server \
  --binary --strategy=docker

oc start-build techmart-mcp-server \
  --from-dir=. --follow
```

### Deploy
```bash
oc new-app techmart-mcp-server
oc new-app techmart-ui-app

oc expose svc/techmart-ui-app
```

## 📝 Container Registry

### Tag and Push
```bash
# Tag images
podman tag techmart-mcp-server:latest quay.io/yourorg/techmart-mcp-server:v1.0
podman tag techmart-ui-app:latest quay.io/yourorg/techmart-ui-app:v1.0

# Push to registry
podman push quay.io/yourorg/techmart-mcp-server:v1.0
podman push quay.io/yourorg/techmart-ui-app:v1.0
```

### Pull and Run
```bash
podman pull quay.io/yourorg/techmart-mcp-server:v1.0
podman pull quay.io/yourorg/techmart-ui-app:v1.0

podman run -d -p 9001:9001 quay.io/yourorg/techmart-mcp-server:v1.0
podman run -d -p 8000:8000 quay.io/yourorg/techmart-ui-app:v1.0
```

## 🎯 Next Steps

1. **Test the deployment**: Access http://localhost:8000
2. **Try example questions**: Use the sample questions in the UI
3. **Monitor logs**: Check container logs for any issues
4. **Scale if needed**: Run multiple UI containers behind a load balancer

## 📚 Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Podman Documentation](https://docs.podman.io/)
- [OpenShift Documentation](https://docs.openshift.com/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)

---

**Made with Bob** 🤖