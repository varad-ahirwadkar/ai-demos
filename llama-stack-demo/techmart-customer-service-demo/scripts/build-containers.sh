#!/bin/bash
# Build script for TechMart Customer Service Demo containers

set -e

echo "🏗️  Building TechMart Customer Service Demo Containers..."
echo ""

# Get the project root directory (parent of scripts/)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Build MCP Server container
echo "📦 Building MCP Server container..."
podman build -f deployments/Containerfile.mcp -t techmart-mcp-server:latest .
echo "✅ MCP Server container built successfully"
echo ""

# Build UI Application container
echo "🎨 Building UI Application container..."
podman build -f deployments/Containerfile.ui -t techmart-ui-app:latest .
echo "✅ UI Application container built successfully"
echo ""

echo "🎉 All containers built successfully!"
echo ""
echo "To run the containers:"
echo "  cd scripts && ./run-containers.sh"
echo ""
echo "Or use docker-compose:"
echo "  cd deployments && docker-compose up -d"

# Made with Bob
