# TechMart Customer Service Assistant

A customer service assistant for an e-commerce platform, built on Red Hat OpenShift AI. This demo showcases a hybrid **RAG** (Retrieval-Augmented Generation) and **MCP** (Model Context Protocol) architecture for answering customer queries using both enterprise knowledge and external tools.

**What is OGX?**   
OGX is a Red Hat OpenShift AI component that provides a unified, OpenAI-compatible API for models, tools, and data sources. In this demo, OGX orchestrates retrieval, tool calling, and model inference through a single API, allowing the assistant to combine RAG and MCP seamlessly.

## Demo Overview

This demo is based on **TechMart**, a fictional electronics retailer, and demonstrates three common customer support workflows:


The demo demonstrates how the assistant can:
- **Answer policy questions** by retrieving relevant information from company documents using RAG.
- **Look up order details** by invoking MCP tools that query a PostgreSQL database.
- **Combine policy and order information** to answer questions that require both sources.

The demo uses the [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507) model served with vLLM, a FAISS vector store for document retrieval, and a FastMCP server for database access.

## How It Works

```
User Question
    ↓
Flask UI (OGX Client)
    ↓
OGX Distribution
    ├─→ RAG (FAISS Vector Store)
    │   └─→ Policy Documents (return-policy.txt)
    ├─→ MCP (FastMCP Server)
    │   └─→ PostgreSQL Database (10 sample orders)
    └─→ LLM (vLLM - Qwen3 4B Instruct 2507)
    ↓
AI Response (combines policy info + order data)
```

---

## Prerequisites

Before you begin, make sure you have the following.

### Cluster

- An OpenShift cluster with **OpenShift AI** installed.
- A **DataScienceCluster (DSC)** configured with **KServe** (model serving) and **OGX** enabled.  
See the [openshift-ai-demos README](../../README.md#2-clone-and-configure-openshift-ai) for instructions on configuring the DSCInitialization and DataScienceCluster resources.


### Resource summary

Approximate resource requests for the demo components:

| Component | CPU | Memory | Storage |
|-----------|----:|-------:|---------|
| Model (`qwen3-4b`) | 32 | 40Gi | — |
| App PostgreSQL | 200m | 256Mi | 1Gi PVC |
| MCP server | 200m | 256Mi | — |
| UI | 200m | 256Mi | — |
| OGX Server | best-effort* | best-effort* | — |
| OGX PostgreSQL (shared) | best-effort* | best-effort* | — |
| Database initialization job | best-effort* | best-effort* | — |

\* No explicit resource requests are configured. These components run with best-effort scheduling and consume resources as available.

The model is the primary resource consumer. Plan for approximately **33 CPU cores** and **41 GiB of memory** to run the complete demo.

### Local tools

- [`oc`](https://docs.openshift.com/container-platform/latest/cli_reference/openshift_cli/getting-started-cli.html), logged in to your OpenShift cluster (`oc login ...`)
- [`podman`](https://podman.io/) to build and push container images
- Access to a container registry (for example, [Quay.io](https://quay.io)) where you can push images that your OpenShift cluster can pull
One

---

## Setup

Complete the first three steps, then choose one deployment method:  
a scripted **Quick start** or a **Manual walkthrough**.

### Step 1: Clone the repository and create the project

```bash
https://github.com/IBM/ai-demos.git
cd ai-demos/openshift-ai-demos

# Create (or switch to) the demo project
oc new-project ogx-sandbox || oc project ogx-sandbox
```

> **Note:** The manifests are configured for the `ogx-sandbox` namespace. If you use a different namespace, update the service hostnames in `deployments/ogx-server.yaml` and `deployments/techmart-ui.yaml` to match your project name.

> Unless otherwise noted, run all remaining commands from the `ai-demos/openshift-ai-demos` directory.

### Step 2: Deploy the model

Deploy the Qwen3-4B model using vLLM. The model exposes an OpenAI-compatible API that is used by both the Quick start and Manual deployment paths.

```bash
# Register the vLLM CPU serving runtime
oc process -n redhat-ods-applications vllm-cpu-runtime-template | oc apply -f -

# Deploy the Qwen3-4B model
oc create -f model-serving/generative-models/vllm/qwen3-4b-instruct-2507.yaml
```

The model may take several minutes to become ready. Wait until the inference service reports `READY=True`:

```bash
oc get inferenceservice qwen3-4b -w
```

### Step 3: Build and push the container images


Build and push the demo's three container images: the UI, MCP server, and database initialization job. The script verifies that you are authenticated with the container registry and prompts you to run `podman login` if needed.

```bash
# Registry namespace or username
export REGISTRY_USER=your-quay-username

# Optional: export CONTAINER_REGISTRY=quay.io (default)

sh ogx/techmart-customer-service/scripts/build-and-push-all.sh
```

> **Note:** If your images are stored in a private registry, configure an image pull secret in the `ogx-sandbox` namespace so OpenShift can pull them.

### Step 4: Deploy the demo

Choose one of the following deployment methods.

#### Option A: Quick start (recommended)


`manage-resources.sh` automates the deployment of all demo components, applying resources in the required order and waiting for each component to become ready.


```bash
# Deploy all demo components
bash ogx/techmart-customer-service/scripts/manage-resources.sh deploy --all
```

Additional commands:

```bash
# Interactively select which resources to deploy
bash ogx/techmart-customer-service/scripts/manage-resources.sh deploy

# Delete all deployed resources
bash ogx/techmart-customer-service/scripts/manage-resources.sh delete --all
```

> **Note:** `manage-resources.sh` assumes the model is already running. Complete [Step 2](#step-2--deploy-the-model) before using it.

After the deployment completes, continue to [Step 5](#step-5--open-the-ui-and-upload-the-policy-document).

#### Option B: Manual, step by step

Use this path to deploy each component individually and better understand how the demo is assembled. It performs the same deployment as the Quick start.

##### 4.1 Deploy the shared PostgreSQL instance
OGX uses this PostgreSQL instance to store its internal state, including vector store metadata, conversation history, and uploaded file records. It also creates the `postgres-credentials` Secret that the OGX server reads at startup.

```bash
oc create -f ogx/shared/ogx-metadata-postgres.yaml
oc wait --for=condition=ready pod -l app=postgres --timeout=300s
```

##### 4.2: Deploy the OGX Distribution
This is the OGX orchestration layer that coordinates RAG, MCP tools, and model inference.

```bash
oc create -f ogx/techmart-customer-service/deployments/ogx-server.yaml
# The OGX operator creates the pod asynchronously, so give it a moment to
# appear before waiting on readiness.
oc wait --for=condition=ready pod -l app.kubernetes.io/instance=techmart-ogx --timeout=300s
```

##### 4.3: Deploy the application database (PostgreSQL)
This PostgreSQL instance stores the sample order data that the MCP server exposes as tools.

```bash
oc apply -f ogx/techmart-customer-service/deployments/postgresql.yaml
oc wait --for=condition=ready pod -l app=techmart-postgresql --timeout=300s
```

##### 4.4: Initialize the database
This Job creates the schema and loads the sample orders. It reads both from
ConfigMaps generated from the files in `db-init/` and `data/`, so create those
first.

```bash
DEMO=ogx/techmart-customer-service

# Generate the ConfigMaps the Job mounts
oc create configmap techmart-db-scripts \
  --from-file=$DEMO/db-init/schema.sql \
  --from-file=$DEMO/db-init/init_db.py \
  --dry-run=client -o yaml | oc apply -f -

oc create configmap techmart-db-data \
  --from-file=$DEMO/data/orders.csv \
  --dry-run=client -o yaml | oc apply -f -

oc apply -f $DEMO/deployments/db-init-job.yaml
oc wait --for=condition=complete job/techmart-db-init --timeout=300s

# (Optional) confirm the data loaded
oc exec -it deployment/techmart-postgresql -- \
  psql -U postgres -d techmart -c "SELECT COUNT(*) FROM orders;"
```

##### 4.5: Deploy the MCP server 
This exposes the order database through MCP tools that OGX can invoke.

```bash
oc apply -f ogx/techmart-customer-service/deployments/techmart-mcp-server.yaml
oc wait --for=condition=ready pod -l app=techmart-mcp-server --timeout=300s
```

##### 4.6: Deploy the UI 
This is the Flask chat interface users interact with.

```bash
oc apply -f ogx/techmart-customer-service/deployments/techmart-ui.yaml
oc wait --for=condition=ready pod -l app=techmart-ui --timeout=300s
```

### Step 5: Open the UI and upload the policy document

Retrieve the UI URL and open it in your browser:

```bash
echo "Access the demo at: https://$(oc get route techmart-ui -o jsonpath='{.spec.host}')"
```

The **TechMart Customer Service** chat interface includes a file upload panel. Upload the policy document so the assistant can answer policy questions using RAG.


```text
ogx/techmart-customer-service/data/return-policy.txt
```
This document contains the sample return policy and shipping information.


> **Note:** The sample order data is loaded automatically by the database initialization job.

The demo is now ready. Try asking questions about the return policy or look up one of the sample orders.

---

## Try the Demo

The following examples demonstrate the assistant's capabilities, progressing from RAG, to MCP, and finally to hybrid queries that combine both.

### 1. Policy question (RAG only)

**Try:**
> What is your return policy in general?

**How it works**
- Retrieves relevant content from `return-policy.txt` using RAG.
- Generates a natural language response based on the retrieved context.

**Expected response:**
```
The return policy at TechMart allows customers to return standard items within 30 days of delivery, electronics within 15 days, and opened software and personalized items cannot be returned. Items must be in original condition with original packaging intact, and all accessories, manuals, and tags must be included. If an item is returned after the time limit, it may receive a partial refund or be rejected.
```

### 2. Order lookup (MCP)

**Try:**

> What's the status of order ORD-2024-001?

**How it works**
- Invokes the `get_order()` MCP tool.
- Retrieves the order details from the PostgreSQL database.
- Generates a response based on the returned order information.

**Expected response:**
```
The status of order ORD-2024-001 is "Delivered". The order was delivered on March 20, 2024, and the customer has opened the package. If you need any further assistance or have questions about your order, please don't hesitate to contact us.
```

### 3. Return eligibility (RAG + MCP), using a non-eligible order.

**Try:**

> Can I return order ORD-2024-001?

**How it works**
- Invokes the `check_return_eligibility()` MCP tool, which looks up the order and deterministically applies the return policy — computing the return deadline, whether the window is still open, the restocking fee, and the refund amount.
- Generates a natural-language response from the tool's computed values, so the dates and amounts are always exact.

**Expected response:**
```
Unfortunately, order ORD-2024-001 is not eligible for return. The return window expired 17 days ago, and you are outside the allowed timeframe.
```

### 4. Return eligibility (RAG + MCP), using an eligible order.

**Try:**

> Can I return order ORD-2024-005?

**How it works**

- Invokes the `check_return_eligibility()` MCP tool, which looks up the order and deterministically applies the return policy — computing the return deadline, days remaining, the restocking fee, and the refund amount.
- Generates a natural-language response from the tool's computed values, so the dates and amounts are always exact.

**Expected response:**
```
The order ORD-2024-005 is eligible for return. You have 6 days remaining in the return window, and the estimated refund amount is $76.49. Additionally, there is a restocking fee of 15% ($13.50) and you can return the item within 15 days of delivery.
```

### 5. Shipping policy (RAG)

**Try:**

> How long does shipping take?

**How it works**
- Retrieves the shipping information from `return-policy.txt` using RAG.
- Generates a natural language response based on the retrieved policy information.

**Expected response:**
```
Standard shipping takes 3-5 business days. We also offer:
- Express shipping: 1-2 business days
- Free shipping on orders over $50

Orders are processed within 24 hours on business days.
```

---

## Troubleshooting

| Symptom | Likely cause | What to check |
|---------|--------------|---------------|
| Model pod remains in `Pending` | Insufficient CPU or memory resources | Run `oc describe inferenceservice qwen3-4b` and verify node capacity. |
| `ImagePullBackOff` for the UI, MCP server, or DB-init pods | Images were not pushed, or the namespace cannot pull from a private registry | Verify [Step 3](#step-3--build-and-push-the-container-images) completed successfully. If using a private registry, configure an image pull secret for the `ogx-sandbox` namespace. |
| MCP server crashes or cannot retrieve orders | The database is unavailable or was not initialized | Verify the PostgreSQL pod is running and the database initialization job completed successfully (`oc get job techmart-db-init`). |
| Policy questions return no or incorrect information | The policy document has not been uploaded | Upload `return-policy.txt` through the UI (see [Step 5](#step-5-open-the-ui-and-upload-the-policy-document)). |
| OGX pod is not ready | The shared PostgreSQL instance or model is unavailable | Verify the shared PostgreSQL deployment is running and the model reports `READY=True`. |

To inspect a failing component, view its logs:

```bash
oc logs deployment/<name>
oc logs job/techmart-db-init
```

For example:

- `oc logs deployment/techmart-mcp-server`
- `oc logs deployment/techmart-ui`
---

## Reference

### Sample orders

The sample orders are stored in [`data/orders.csv`](data/orders.csv)  and loaded automatically by the database initialization job.

### Key OGX settings

The OGX deployment is configured in [`ogx-server.yaml`](deployments/ogx-server.yaml):

### Add a sample order

To test additional scenarios, connect to the PostgreSQL database and insert a new order:

```bash
oc exec -it deployment/techmart-postgresql -- psql -U postgres -d techmart
```

> **Use dates on or before 2024-04-21.** So the demo gives the same answers
> whenever it is run, `check_return_eligibility()` treats **2024-04-21** as
> "today" (`DEMO_TODAY` in [`mcp-server/server.py`](mcp-server/server.py)). A
> `delivery_date` after that is a package that has not arrived yet, and the
> assistant will report more days remaining than the return window allows.

```bash
INSERT INTO orders (
  order_id,
  customer_email,
  product_name,
  category,
  price,
  order_date,
  delivery_date,
  status,
  is_opened
)
VALUES (
  'ORD-2024-011',
  'customer@example.com',
  'New Product',
  'Electronics',
  599.99,
  '2024-04-10',
  '2024-04-15',
  'Delivered',
  'No'
);
```

New orders are available immediately. The MCP server reads directly from the database, so no restart is required.

Asking *"Can I return order ORD-2024-011?"* now returns a consistent result: an
unopened electronics item delivered on 2024-04-15 has a 15-day window closing
2024-04-30, so 9 days remain and the full $599.99 is refunded with no
restocking fee.


> **Reset the sample data:** To restore the original sample orders, recreate the database initialization job. This drops the `orders` table and reloads the default data, removing any orders you added.
>
> ```bash
> oc delete job techmart-db-init
> oc apply -f ogx/techmart-customer-service/deployments/db-init-job.yaml
> ```
>
> If you edited `data/orders.csv`, regenerate the `techmart-db-data` ConfigMap
> first (see [Step 4.4](#44-initialize-the-database)) — the Job loads what is in
> the ConfigMap, not what is on disk.

---

## References

- [OGX Documentation](https://ogx-ai.github.io/)
- [FastMCP Documentation](https://github.com/jlowin/fastmcp)
- [OpenShift AI Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed)
- [FAISS Vector Store](https://github.com/facebookresearch/faiss)
