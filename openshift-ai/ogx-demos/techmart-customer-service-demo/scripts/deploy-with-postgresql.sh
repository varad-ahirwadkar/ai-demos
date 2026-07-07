#!/bin/bash
set -e

echo "🚀 TechMart Customer Service Demo - PostgreSQL Deployment"
echo "=========================================================="
echo ""

# Check if oc is available
if ! command -v oc &> /dev/null; then
    echo "❌ Error: 'oc' command not found. Please install OpenShift CLI."
    exit 1
fi

# Check if logged in
if ! oc whoami &> /dev/null; then
    echo "❌ Error: Not logged in to OpenShift. Please run 'oc login' first."
    exit 1
fi

echo "✅ OpenShift CLI found and logged in"
echo "📍 Current project: $(oc project -q)"
echo ""

# Step 1: Deploy PostgreSQL
echo "📦 Step 1: Deploying PostgreSQL..."
oc apply -f deployments/postgresql-mcp.yaml
echo "✅ PostgreSQL deployment created"
echo ""

# Step 2: Wait for PostgreSQL to be ready
echo "⏳ Step 2: Waiting for PostgreSQL to be ready..."
oc wait --for=condition=ready pod -l app=techmart-postgresql --timeout=180s
echo "✅ PostgreSQL is ready"
echo ""

# Step 3: Initialize database using Job
echo "🗄️  Step 3: Initializing database schema and loading data..."

# Delete old job if it exists (Jobs are immutable)
if oc get job techmart-db-init &> /dev/null; then
    echo "   🗑️  Deleting existing job..."
    oc delete job techmart-db-init --wait=false
    sleep 2
fi

# Create ConfigMaps and Job
oc apply -f deployments/db-init-job.yaml
echo "   ✅ Database initialization job created"

# Wait for job to complete
echo "   ⏳ Waiting for database initialization to complete..."
oc wait --for=condition=complete job/techmart-db-init --timeout=180s
echo "   ✅ Database initialized successfully"

# Show job logs
echo "   📋 Initialization logs:"
oc logs job/techmart-db-init | sed 's/^/      /'
echo ""

# Step 5: Deploy MCP Server
echo "🔧 Step 5: Deploying MCP Server..."
oc apply -f deployments/techmart-mcp-server.yaml
echo "✅ MCP Server deployment created"
echo ""

# Step 6: Deploy UI
echo "🌐 Step 6: Deploying UI..."
oc apply -f deployments/techmart-ui.yaml
echo "✅ UI deployment created"
echo ""

# Step 7: Wait for deployments
echo "⏳ Step 7: Waiting for all deployments to be ready..."
oc wait --for=condition=available deployment/techmart-mcp-server --timeout=180s
oc wait --for=condition=available deployment/techmart-ui --timeout=180s
echo "✅ All deployments are ready"
echo ""

# Step 8: Get route
echo "🌍 Step 8: Getting application URL..."
ROUTE=$(oc get route techmart-ui -o jsonpath='{.spec.host}' 2>/dev/null || echo "Route not found")
if [ "$ROUTE" != "Route not found" ]; then
    echo "✅ Application URL: https://$ROUTE"
else
    echo "⚠️  Route not found. Creating route..."
    oc expose service techmart-ui
    ROUTE=$(oc get route techmart-ui -o jsonpath='{.spec.host}')
    echo "✅ Application URL: https://$ROUTE"
fi
echo ""

# Summary
echo "=========================================================="
echo "🎉 Deployment Complete!"
echo "=========================================================="
echo ""
echo "📋 Deployment Summary:"
echo "   • PostgreSQL: ✅ Running"
echo "   • MCP Server: ✅ Running"
echo "   • UI: ✅ Running"
echo ""
echo "🔗 Access the application:"
echo "   https://$ROUTE"
echo ""
echo "📊 Verify deployment:"
echo "   oc get pods"
echo "   oc logs deployment/techmart-mcp-server"
echo "   oc logs deployment/techmart-ui"
echo ""
echo "🗄️  Database access:"
echo "   oc exec deployment/techmart-postgresql -- psql -U techmart -d techmart"
echo ""

