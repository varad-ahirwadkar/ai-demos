#!/bin/bash
# Stop script for TechMart Customer Service Demo containers

echo "🛑 Stopping TechMart Customer Service Demo containers..."
echo ""

# Stop and remove containers
echo "Stopping UI Application..."
podman stop techmart-ui-app 2>/dev/null || echo "UI App not running"
podman rm techmart-ui-app 2>/dev/null || echo "UI App already removed"

echo "Stopping MCP Server..."
podman stop techmart-mcp-server 2>/dev/null || echo "MCP Server not running"
podman rm techmart-mcp-server 2>/dev/null || echo "MCP Server already removed"

echo ""
echo "✅ All containers stopped and removed"
echo ""
echo "To start again:"
echo "  cd scripts && ./run-containers.sh"

# Made with Bob
