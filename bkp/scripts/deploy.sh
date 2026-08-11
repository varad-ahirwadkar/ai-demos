#!/bin/bash
set -e

# Deployment script for Llama Stack Document Q&A Demo
# Usage: ./scripts/deploy.sh [namespace]

NAMESPACE=${1:-llama-demo}
REGISTRY=${REGISTRY:-quay.io/your-org}
IMAGE_NAME=${IMAGE_NAME:-document-qa-app}
IMAGE_TAG=${IMAGE_TAG:-latest}

echo "🚀 Deploying Llama Stack Document Q&A Demo"
echo "Namespace: $NAMESPACE"
echo "Image: $REGISTRY/$IMAGE_NAME:$IMAGE_TAG"
echo ""

# Check if oc/kubectl is available
if command -v oc &> /dev/null; then
    CLI="oc"
    echo "✓ Using OpenShift CLI (oc)"
elif command -v kubectl &> /dev/null; then
    CLI="kubectl"
    echo "✓ Using Kubernetes CLI (kubectl)"
else
    echo "❌ Error: Neither oc nor kubectl found. Please install one."
    exit 1
fi

# Create namespace if it doesn't exist
echo ""
echo "📦 Creating namespace..."
$CLI create namespace $NAMESPACE --dry-run=client -o yaml | $CLI apply -f -

# Deploy PostgreSQL
echo ""
echo "🐘 Deploying PostgreSQL..."
$CLI apply -f deployment/postgres.yaml -n $NAMESPACE

# Wait for PostgreSQL to be ready
echo "⏳ Waiting for PostgreSQL to be ready..."
$CLI wait --for=condition=ready pod -l app=postgres -n $NAMESPACE --timeout=300s

# Deploy Llama Stack Distribution
echo ""
echo "🦙 Deploying Llama Stack Distribution..."
$CLI apply -f deployment/llama-stack-distribution.yaml -n $NAMESPACE

# Wait for Llama Stack to be ready
echo "⏳ Waiting for Llama Stack to be ready..."
sleep 30  # Give it time to start
$CLI wait --for=condition=ready pod -l app=llama-stack -n $NAMESPACE --timeout=600s || true

# Build and push application image (if needed)
if [ "$BUILD_IMAGE" = "true" ]; then
    echo ""
    echo "🔨 Building application image..."
    podman build -t $REGISTRY/$IMAGE_NAME:$IMAGE_TAG -f Containerfile .
    
    echo "📤 Pushing image to registry..."
    podman push $REGISTRY/$IMAGE_NAME:$IMAGE_TAG
fi

# Update deployment with correct image
echo ""
echo "📝 Updating deployment manifest with image..."
sed "s|quay.io/your-org/document-qa-app:latest|$REGISTRY/$IMAGE_NAME:$IMAGE_TAG|g" \
    deployment/document-qa-app.yaml > /tmp/document-qa-app-updated.yaml

# Deploy application
echo ""
echo "🚀 Deploying Document Q&A Application..."
$CLI apply -f /tmp/document-qa-app-updated.yaml -n $NAMESPACE

# Wait for application to be ready
echo "⏳ Waiting for application to be ready..."
$CLI wait --for=condition=ready pod -l app=document-qa-app -n $NAMESPACE --timeout=300s

# Get route/ingress URL
echo ""
echo "🌐 Getting application URL..."
if [ "$CLI" = "oc" ]; then
    ROUTE_URL=$($CLI get route document-qa-app -n $NAMESPACE -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
    if [ -n "$ROUTE_URL" ]; then
        echo "✅ Application deployed successfully!"
        echo ""
        echo "🔗 Access the application at: https://$ROUTE_URL"
    else
        echo "⚠️  Route not found. Creating route..."
        $CLI expose svc/document-qa-app -n $NAMESPACE
        ROUTE_URL=$($CLI get route document-qa-app -n $NAMESPACE -o jsonpath='{.spec.host}')
        echo "✅ Application deployed successfully!"
        echo ""
        echo "🔗 Access the application at: https://$ROUTE_URL"
    fi
else
    SERVICE_IP=$($CLI get svc document-qa-app -n $NAMESPACE -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "")
    if [ -n "$SERVICE_IP" ]; then
        echo "✅ Application deployed successfully!"
        echo ""
        echo "🔗 Access the application at: http://$SERVICE_IP"
    else
        echo "✅ Application deployed successfully!"
        echo ""
        echo "🔗 Access via port-forward: kubectl port-forward -n $NAMESPACE svc/document-qa-app 8080:80"
        echo "   Then open: http://localhost:8080"
    fi
fi

# Show pod status
echo ""
echo "📊 Deployment Status:"
$CLI get pods -n $NAMESPACE

echo ""
echo "✨ Deployment complete!"
echo ""
echo "📚 Next steps:"
echo "1. Access the web interface at the URL above"
echo "2. Upload sample documents from sample-docs/ directory"
echo "3. Ask questions about the uploaded documents"
echo ""
echo "🔍 Useful commands:"
echo "  View logs: $CLI logs -f deployment/document-qa-app -n $NAMESPACE"
echo "  Check health: curl https://$ROUTE_URL/health"
echo "  Delete deployment: $CLI delete namespace $NAMESPACE"

# Made with Bob
