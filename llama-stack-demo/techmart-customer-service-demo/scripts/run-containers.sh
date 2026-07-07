#!/bin/bash
# Run script for TechMart Customer Service Demo containers

set -e

echo "🚀 Starting TechMart Customer Service Demo..."
echo ""

# Create network if it doesn't exist
echo "🌐 Creating network..."
podman network create techmart-network 2>/dev/null || echo "Network already exists"
echo ""

# Run MCP Server
echo "📦 Starting MCP Server..."
podman run -d \
  --name techmart-mcp-server \
  --network techmart-network \
  -p 9001:9001 \
  techmart-mcp-server:latest

echo "✅ MCP Server started on port 9001"
echo ""

# Wait for MCP server to be ready
echo "⏳ Waiting for MCP Server to be ready..."
sleep 5
echo ""

# Run UI Application
echo "🎨 Starting UI Application..."
podman run -d \
  --name techmart-ui-app \
  --network techmart-network \
  -p 8000:8000 \
  -e LLAMA_STACK_URL=http://llama-stack:5001 \
  -e MCP_SERVER_URL=http://techmart-mcp-server:9001/sse \
  techmart-ui-app:latest

echo "✅ UI Application started on port 8000"
echo ""

echo "🎉 All containers are running!"
echo ""
echo "📊 Container Status:"
podman ps --filter "name=techmart-"
echo ""
echo "🌐 Access the application:"
echo "  UI Application: http://localhost:8000"
echo "  MCP Server: http://localhost:9001"
echo ""
echo "📝 View logs:"
echo "  MCP Server: podman logs -f techmart-mcp-server"
echo "  UI App: podman logs -f techmart-ui-app"
echo ""
echo "🛑 Stop containers:"
echo "  cd scripts && ./stop-containers.sh"

# Made with Bob
