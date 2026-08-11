# Quick Start Guide - Llama Stack Document Q&A Demo

This guide will help you quickly deploy and test the Intelligent Document Q&A system on CPU-only environments.

## 🎯 What This Demo Does

- **Upload Documents**: Process PDF/TXT files and store them in a vector database
- **Semantic Search**: Find relevant information using FAISS vector search
- **AI-Powered Q&A**: Get intelligent answers using Llama 3.2 3B model
- **Web Interface**: User-friendly interface for document management and queries

## ⚡ Quick Deploy (5 minutes)

### Prerequisites

- OpenShift/Kubernetes cluster (CPU-only is fine)
- `oc` or `kubectl` CLI installed
- 4GB RAM minimum for the stack

### Step 1: Create Namespace

```bash
oc new-project llama-demo
```

### Step 2: Deploy PostgreSQL

```bash
oc apply -f deployment/postgres.yaml
```

Wait for PostgreSQL to be ready:
```bash
oc wait --for=condition=ready pod -l app=postgres --timeout=300s
```

### Step 3: Deploy Llama Stack

```bash
oc apply -f deployment/llama-stack-distribution.yaml
```

This will deploy:
- Llama 3.2 3B Instruct model (via VLLM)
- IBM Granite embeddings (125M parameters)
- FAISS vector store (in-memory)
- PostgreSQL metadata store

Wait for it to be ready (may take 2-3 minutes):
```bash
oc get pods -w
```

### Step 4: Build & Deploy Application

**Option A: Use pre-built image (if available)**
```bash
# Update image in deployment/document-qa-app.yaml
oc apply -f deployment/document-qa-app.yaml
```

**Option B: Build from source**
```bash
# Build image
podman build -t document-qa-app:latest -f Containerfile .

# Tag for your registry
podman tag document-qa-app:latest quay.io/your-org/document-qa-app:latest

# Push to registry
podman push quay.io/your-org/document-qa-app:latest

# Update deployment/document-qa-app.yaml with your image
# Then apply
oc apply -f deployment/document-qa-app.yaml
```

### Step 5: Expose the Application

```bash
oc expose svc/document-qa-app
```

Get the URL:
```bash
oc get route document-qa-app
```

## 🧪 Test the Application

### 1. Access Web Interface

Open the route URL in your browser. You should see the Document Q&A interface.

### 2. Upload Sample Document

Upload the provided sample document:
```bash
# From the web UI, click "Upload" and select:
sample-docs/company-handbook.txt
```

### 3. Ask Questions

Try these example questions:
- "What is the remote work policy?"
- "How many vacation days do employees get?"
- "What are the company's core values?"
- "What is the parental leave policy?"
- "How much is the training budget per employee?"

## 🔧 Configuration for CPU-Only

The deployment is already optimized for CPU:

**Llama Stack Configuration:**
- Model: Llama 3.2 3B (small, efficient)
- Embeddings: Granite 125M (lightweight)
- Max tokens: 2048 (reduced for CPU)
- Resources: 4Gi RAM, 2 CPU cores

**Application Configuration:**
- Chunk size: 1000 characters
- Max chunks per query: 5
- Workers: 2 (for gunicorn)

## 📊 Monitoring

### Check System Health

```bash
# Via web UI
curl https://your-route-url/health

# Check logs
oc logs -f deployment/llama-stack
oc logs -f deployment/document-qa-app
```

### View Metrics

```bash
# Port forward to access metrics
oc port-forward svc/techmart-ogx-service 8321:8321

# Access metrics
curl http://localhost:8321/metrics
```

## 🐛 Troubleshooting

### Llama Stack Not Starting

```bash
# Check pod status
oc describe pod -l app=llama-stack

# Check PostgreSQL connection
oc exec -it deployment/postgres -- psql -U llamastack -d llamastack -c '\l'

# View logs
oc logs deployment/llama-stack --tail=100
```

### Application Can't Connect to Llama Stack

```bash
# Test connectivity
oc run test --rm -it --image=curlimages/curl -- \
  curl http://techmart-ogx-service.llama-demo.svc.cluster.local:8321/v1/models

# Check service
oc get svc techmart-ogx-service
```

### Out of Memory

If you see OOM errors:

```bash
# Reduce max tokens in llama-stack-distribution.yaml
# Change VLLM_MAX_TOKENS from 2048 to 512

# Reduce workers in document-qa-app.yaml
# Change gunicorn workers from 2 to 1

# Apply changes
oc apply -f deployment/llama-stack-distribution.yaml
oc apply -f deployment/document-qa-app.yaml
```

### Slow Response Times

For CPU-only deployments, expect:
- Document upload: 10-30 seconds
- Question answering: 5-15 seconds

To improve performance:
- Reduce chunk size (CHUNK_SIZE=500)
- Reduce max chunks (MAX_CHUNKS=3)
- Use smaller documents

## 🧹 Cleanup

Remove everything:
```bash
oc delete project llama-demo
```

Or remove individual components:
```bash
oc delete -f deployment/document-qa-app.yaml
oc delete -f deployment/llama-stack-distribution.yaml
oc delete -f deployment/postgres.yaml
```

## 📚 Next Steps

1. **Try More Documents**: Upload your own PDFs or text files
2. **Customize Prompts**: Edit `app.py` to modify the Q&A prompt
3. **Add Guardrails**: Enable FMS guardrails for content safety
4. **Scale Up**: Add GPU nodes for faster inference
5. **Production Setup**: Add persistent storage, monitoring, and backups

## 🆘 Getting Help

- Check logs: `oc logs -f deployment/document-qa-app`
- View health: `curl https://your-route/health`
- GitHub Issues: [Report issues here]
- Documentation: See main README.md

## 💡 Tips for CPU-Only Demos

1. **Use Small Documents**: Keep documents under 10 pages
2. **Limit Concurrent Users**: CPU inference is slower
3. **Pre-upload Documents**: Upload before the demo starts
4. **Prepare Questions**: Have example questions ready
5. **Set Expectations**: Explain CPU vs GPU performance differences

## ✅ Success Checklist

- [ ] All pods are running
- [ ] Health endpoint returns healthy status
- [ ] Can access web interface
- [ ] Successfully uploaded sample document
- [ ] Received answer to test question
- [ ] Response time is acceptable (< 30 seconds)

Congratulations! Your Llama Stack Document Q&A system is ready! 🎉