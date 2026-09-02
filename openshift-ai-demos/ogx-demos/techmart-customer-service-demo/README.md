# TechMart Customer Service Assistant

An intelligent customer service assistant built on Red Hat OpenShift AI OGX, showcasing a hybrid RAG (Retrieval-Augmented Generation) + MCP (Model Context Protocol) architecture for e-commerce support.

OGX is an OpenAI-compatible platform that enables you to build and run AI applications anywhere, without changing your code. It provides a unified interface for models, tools and data. Ensures a consistent API layer across environments

In this demo, OGX acts as the core orchestration layer, seamlessly combining RAG, MCP and model inference.


## Demo Overview

This demo showcases an **e-commerce customer service scenario** for **TechMart**, a fictional electronics retailer, demonstrating how OGX can:

- **Answer policy questions** using RAG to retrieve information from company documents
- **Look up order details** using MCP tools that query a PostgreSQL database
- **Provide intelligent responses** by synthesizing both static and dynamic information

The configuration utilizes a [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) model deployed via vLLM, integrated with FAISS vector store for RAG and FastMCP server for database access.

## How It Works

```
User Question
    ↓
Flask UI (OGX Client)
    ↓
OGX Distribution
    ├─→ RAG (FAISS Vector Store)
    │   └─→ Policy Documents (return-policy.txt, shipping-policy.txt)
    ├─→ MCP (FastMCP Server)
    │   └─→ PostgreSQL Database (12 sample orders)
    └─→ LLM (vLLM - Qwen3 4B Instruct 2507)
    ↓
AI Response (combines policy info + order data)
```

---

## Prerequisites

#### Ensure the following are set up before deployment:

1. OpenShift Cluster with OpenShift AI
- KServe enabled via Data Science Cluster (DSC)
- OGX enabled via Data Science Cluster (DSC)

2. Container Registry
Access to a registry (for example, Quay.io) to push and pull images

### Project Setup
Create and switch to the demo project:
```bash
oc new-project ogx-sandbox || oc project ogx-sandbox
```

Reference base directory:
```
cd ai-demos/openshift-ai-demos
```
---

### Model Configuration

We will be deploying the [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) model and use it as self-hosted vLLM backend (with an OpenAI-compatible API).

Deploy the vLLM runtime and model:
```bash
oc process -n redhat-ods-applications vllm-cpu-runtime-template | oc apply -f -
oc create -f model-serving/generative-models/vllm/qwen3-4b-instruct-2507.yaml
```

Model arguments:
```
    model:
      args:
      - --max-model-len=8196
      - --enable-auto-tool-choice
      - --tool-call-parser=hermes
      - --gpu-memory-utilization=0.4
      env:
      - name: VLLM_CPU_KVCACHE_SPACE
        value: "12"
```
Resources:
```
      limits:
        cpu: "32"
        memory: 40Gi
      requests:
        cpu: "32"
        memory: 40Gi
```

## OGX Deployment Steps
#### Step 1: Deploy Postgres for OGX
```
oc create -f ogx-demos/shared/postgres.yaml
```

#### Step 2: Deploy OGX Distribution

```bash
oc create -f ogx-demos/techmart-customer-service-demo/deployments/ogx-server.yaml 

# Wait for OGX to be ready
oc wait --for=condition=ready pod -l app=ogx --timeout=300s
```

## MCP and UI Deployment Steps

#### Step 1: Build Container Images
Build and push all required images:
```bash
# Builds and pushes:
# - TechMart MCP server
# - TechMart UI application
# - PostgreSQL (for MCP)

sh ogx-demos/techmart-customer-service-demo/scripts/build-and-push-all.sh
```

**Quick Deployment Option**

For a simplified setup, you can use the automated script below. It performs Steps 2–5 (PostgreSQL, database initialization, MCP server and UI deployment) automatically:
```
sh scripts/deploy-with-postgresql.sh
```

#### Step 2: Deploy PostgreSQL Database
Deploy the database with persistent storage:
```bash
# Deploy PostgreSQL with persistent volume
% oc apply -f ogx-demos/techmart-customer-service-demo/deployments/postgresql-mcp.yaml
secret/techmart-db-secret created
persistentvolumeclaim/techmart-postgresql-pvc created
deployment.apps/techmart-postgresql created

# Wait for PostgreSQL to be ready
% oc wait --for=condition=ready pod -l app=techmart-postgresql --timeout=300s
pod/techmart-postgresql-58cccdd7f4-s6fdb condition met
```

#### Step 3: Initialize Database
Load schema and sample order data:

```bash
# Run database initialization Job
% oc apply -f ogx-demos/techmart-customer-service-demo/deployments/db-init-job.yaml 
job.batch/techmart-db-init created
configmap/techmart-db-scripts created
configmap/techmart-db-data created

# Check Job status
% oc logs job/techmart-db-init
🗄️  Creating database schema...
psql:/scripts/schema.sql:4: NOTICE:  table "orders" does not exist, skipping
DROP TABLE
CREATE TABLE
CREATE INDEX
CREATE INDEX
CREATE INDEX
CREATE INDEX
CREATE FUNCTION
CREATE TRIGGER
📊 Loading sample data...
📊 Loading orders from CSV...
   Found 10 orders
💾 Inserting orders into database...
✅ Inserted 10 orders
✅ Database initialization complete!
✅ Database initialization complete!

# Verify data was loaded
oc exec -it deployment/techmart-postgresql -- psql -U postgres -d techmart -c "SELECT COUNT(*) FROM orders;"
 count 
-------
    10
(1 row)
```

#### Step 4: Deploy MCP Server
Deploy the MCP server connected to PostgreSQL:
```bash
% oc apply -f  ogx-demos/techmart-customer-service-demo/deployments/techmart-mcp-server.yaml 
deployment.apps/techmart-mcp-server created
service/techmart-mcp-server created
route.route.openshift.io/techmart-mcp-server created

# Verify MCP server is running
% oc wait --for=condition=ready pod -l app=techmart-mcp-server --timeout=300s
pod/techmart-mcp-server-6b55b64f9b-tjj96 condition met
```


#### Step 5: Deploy UI Application

```bash
# Deploy Flask UI
% oc apply -f ogx-demos/techmart-customer-service-demo/deployments/techmart-ui.yaml 
deployment.apps/techmart-ui created
service/techmart-ui created
route.route.openshift.io/techmart-ui created
secret/techmart-ui-secret created

# Wait for TechMart UI to be ready
% oc wait --for=condition=ready pod -l app=techmart-ui --timeout=300s
pod/techmart-ui-86784bf7b8-np6rp condition met

# Get the route URL
UI_ROUTE=https://$(oc get route techmart-ui -o jsonpath='{.spec.host}')
echo "Access the demo at: $UI_ROUTE"
```


#### Step 6: Upload Policy Documents

Access the UI and upload policy documents for RAG:
- `data/return-policy.txt`

**Note**: 
- Sample Order data is already loaded in PostgreSQL via the init Job.

- All order details and the return policy document have been generated by the BOB Assistant.
---

## Configuration

### PostgreSQL Database

**Connection Details:**
- **Host**: `postgresql-mcp.llama.svc.cluster.local`
- **Port**: 5432
- **Database**: `techmart`
- **User**: `postgres`
- **Password**: `postgres123` (stored in Secret)
- **Storage**: 1Gi PersistentVolumeClaim

**Schema:**
```sql
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    order_id VARCHAR(50) UNIQUE NOT NULL,
    customer_name VARCHAR(255) NOT NULL,
    customer_email VARCHAR(255) NOT NULL,
    product_name VARCHAR(500) NOT NULL,
    product_category VARCHAR(100) NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    order_date DATE NOT NULL,
    delivery_date DATE NOT NULL,
    status VARCHAR(50) NOT NULL,
    is_opened VARCHAR(10) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### MCP Server Configuration

The MCP server provides three tools:

**1. `get_order(order_id: str)`**
- Retrieves complete order details from PostgreSQL database
- Returns: order_id, customer_email, product_name, category, order_date, delivery_date, price, status, is_opened

**2. `check_return_eligibility(order_id: str)`**
- Checks return eligibility and calculates refund based on delivery date and category
- Business rules:
  - Electronics: 15-day window, 15% restocking fee if opened
  - Home & Garden: 30-day window, 10% restocking fee if opened
  - Clothing: 30-day window, 10% restocking fee if opened
- Returns: is_eligible, days_since_delivery, return_window_days, days_remaining, restocking_fee_percent, restocking_fee_amount, estimated_refund

**3. `reload_orders()`**
- Reloads orders from database without restarting the server
- Useful for refreshing data after database updates

### OGX Configuration

Key settings in [`ogx-server.yaml`](deployments/ogx-server.yaml):

```yaml
env:
  # Inline FAISS vector store
  - name: ENABLE_FAISS
    value: "faiss"
  
  # Inline embeddings (sentence-transformers)
  - name: ENABLE_SENTENCE_TRANSFORMERS
    value: "true"
  - name: EMBEDDING_PROVIDER
    value: "sentence-transformers"
  
  # Remote LLM configuration
  - name: INFERENCE_MODEL
    value: "qwen3-4b"
  - name: VLLM_URL
    value: http://qwen3-4b-predictor.ogx-sandbox.svc.cluster.local:8080/v1
  - name: VLLM_TLS_VERIFY
    value:  "false"
  - name: VLLM_API_TOKEN
    value: "fake"
  - name: VLLM_MAX_TOKENS
    value: "80"
```

---

## Sample Orders

The demo includes 12 sample orders stored in PostgreSQL generated by BOB AI assistant (showing 5 examples):

| Order ID | Customer Email | Product | Category | Price | Order Date | Delivery Date | Status | Opened |
|----------|----------------|---------|----------|-------|------------|---------------|--------|--------|
| ORD-2024-001 | john.doe@email.com | Laptop Pro 15 | Electronics | $1,299.99 | Mar 15 | Mar 20 | Delivered | yes |
| ORD-2024-002 | jane.smith@email.com | Wireless Mouse | Electronics | $29.99 | Apr 1 | Apr 5 | Delivered | no |
| ORD-2024-003 | bob.wilson@email.com | Office Chair | Furniture | $249.99 | Mar 25 | Apr 2 | Delivered | yes |
| ORD-2024-004 | alice.brown@email.com | Desk Lamp | Home & Office | $45.99 | Apr 10 | Apr 15 | Delivered | no |
| ORD-2024-005 | charlie.davis@email.com | Mechanical Keyboard | Electronics | $89.99 | Apr 5 | Apr 12 | Delivered | yes |

**Demo Date**: April 21, 2024 (static reference for consistent eligibility calculations)

---

## Example Interactions

### 1. Policy Question (RAG Only)

**Question**: "what is your return policy in general ?"

**What happens**:
- RAG retrieves relevant sections from `return-policy.txt`
- LLM synthesizes the information into a natural response

**Expected Response**:
```
The return policy at TechMart allows customers to return standard items within 30 days of delivery, electronics within 15 days, and opened software and personalized items cannot be returned. Items must be in original condition with original packaging intact, and all accessories, manuals, and tags must be included. If an item is returned after the time limit, it may receive a partial refund or be rejected.
```

### 2. Order Lookup (MCP Only)

**Question**: "What's the status of order ORD-2024-001?"

**What happens**:
- MCP tool `get_order_by_id()` queries PostgreSQL database
- Returns order details

**Expected Response**:
```
The status of order ORD-2024-001 is "Delivered". The order was delivered on March 20, 2024, and the customer has opened the package. If you need any further assistance or have questions about your order, please don't hesitate to contact us.
```

### 3. Combined Query (RAG + MCP)

**Question**: "Can I return order ORD-2024-001?"

**What happens**:
1. RAG retrieves return policy rules
2. MCP fetches order details (delivery date, category, opened status)
3. MCP calculates eligibility using `check_return_eligibility()`
4. AI synthesizes both sources to provide complete answer

**Expected Response**:
```
Unfortunately, order ORD-2024-001 is not eligible for return. The return window expired 17 days ago, and you are outside the allowed timeframe.
```

### 4. Eligible Return (RAG + MCP)

**Question**: "Can I return order ORD-2024-005?"

**What happens**:
- MCP checks eligibility: delivered April 12, 6 days ago
- Electronics have 15-day window → eligible

**Expected Response**:
```
The order ORD-2024-005 is eligible for return. You have 6 days remaining in the return window, and the estimated refund amount is $76.49. Additionally, there is a restocking fee of 15% ($13.50) and you can return the item within 15 days of delivery.
```

### 5. Shipping Policy Question (RAG)

**Question**: "How long does shipping take?"

**What happens**:
- RAG retrieves information from `shipping-policy.txt`
- LLM provides natural response

**Expected Response**:
```
Standard shipping takes 3-5 business days. We also offer:
- Express shipping: 1-2 business days
- Free shipping on orders over $50

Orders are processed within 24 hours on business days.
```

---

## Update Order Database

#### Add data using CLI:
```bash
oc exec -it deployment/techmart-postgresql -- psql -U postgres -d techmart

INSERT INTO orders (order_id, customer_email, product_name, category, price, order_date, delivery_date, status, is_opened)
VALUES ('ORD-2024-011', 'customer@example.com', 'New Product', 'Electronics', 599.99, '2024-04-20', '2024-04-22', 'Delivered', 'No');
```

#### Add data using UI:

You can upload a CSV file with new orders using UI

#### Reload Orders in MCP Server:

After updating the database, ask the AI assistant (from UI) to reload the orders:
```
"Please reload the orders from the database"
```

The AI will call the `reload_orders()` MCP tool, which refreshes the in-memory cache without restarting the server.

####  Re-run Init Job:
```bash
oc delete job techmart-db-init
oc apply -f deployments/db-init-job.yaml
```

---

## References

- [OGX Documentation](https://ogx-ai.github.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [OpenShift AI Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed)
- [FAISS Vector Store](https://github.com/facebookresearch/faiss)
