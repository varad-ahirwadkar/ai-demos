#!/bin/bash
# Test script to verify MCP server runs on different ports

echo "Testing MCP Server Port Configuration"
echo "======================================"
echo ""

# Test 1: Default port (8000)
echo "Test 1: Starting server on default port 8000..."
echo "Command: python server.py"
echo ""
echo "Press Ctrl+C to stop and continue to next test"
echo ""
python server.py

echo ""
echo "======================================"
echo ""

# Test 2: Custom port (8333)
echo "Test 2: Starting server on custom port 8333..."
echo "Command: MCP_SERVER_PORT=8333 python server.py"
echo ""
echo "Press Ctrl+C to stop"
echo ""
MCP_SERVER_PORT=8333 python server.py

# Made with Bob
