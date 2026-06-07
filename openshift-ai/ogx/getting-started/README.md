# OGX Getting Started Guide

This guide walks you through deploying OGX on OpenShift AI. OGX provides an OpenAI-compatible API interface for various AI models and services.

## Deployment Options

This guide covers two deployment approaches:

1. **User-Defined Config**: Includes inline vector providers for complete local deployment. Best for development and testing.
2. **Default Config**: Uses remote providers for vector storage. Suitable for production scenarios with external infrastructure.

---

## Option 1: With User-Defined Config

This configuration includes inline vector providers, allowing you to deploy everything within OpenShift without external dependencies.

### Step 1: Deploy the LLM Model

```bash
oc process -n redhat-ods-applications vllm-cpu-runtime-template | oc create -f -
oc create -f ../../model-serving/llama-32-3b-instruct-isvc.yaml
```

**Verify deployment:**
```bash
oc get isvc
oc get pods | grep llama
```

### Step 2: Deploy Postgres for OGX

```bash
oc create -f ../shared/postgres.yaml
```

**Verify deployment:**
```bash
oc get pods | grep postgres
```

### Step 3: Deploy OGX Distribution

```bash
oc create -f deployments/ogx-server-custom-config.yaml

# Wait for OGX to be ready
oc get pods -w
```

**Verify deployment:**
```bash
oc get pods | grep ogx
```

### Step 4: Deploy the Simple Math MCP Server

```bash
oc create -f deployments/math-mcp.yaml
```

**Verify deployment:**
```bash
oc get pods | grep math-mcp
```

### Step 5: Test with Jupyter Notebook

1. Open the Jupyter notebook in your browser.

2. Create a data directory and upload the `return-policy.txt` file from `../data/`.

3. Follow the steps in the notebook to test the OGX server.

**Notebook:** [ogx-custom-config.ipynb](./ogx-custom-config.ipynb)

---

## Option 2: With Default Config

This configuration uses remote providers for vector storage, suitable when you have external infrastructure available.

### Prerequisites for Default Config

- External VM or server for pgvector database
- Network connectivity between OpenShift and external VM

### Clean Up Previous Resources

If you deployed the user-defined config, remove those resources first:

```bash
oc delete -f deployments/ogx-server-custom-config.yaml
oc delete -f ../shared/postgres.yaml
```

### Step 1: Deploy the Embedding Model

```bash
oc create -f ../../model-serving/granite-embedding-125m-english.yaml
```

**Verify deployment:**
```bash
oc get isvc | grep granite
```

### Step 2: Create the Vector Store

Deploy pgvector on an external VM (replace with your VM details):

```bash
# Run on external VM
podman run -itd -u 0 --name pgvector \
  -e POSTGRES_USER=ogx_pgv \
  -e POSTGRES_PASSWORD=ogx_pgv \
  -e POSTGRES_DB=ogx_pgv \
  -p 5433:5432 \
  --replace \
  quay.io/vahirwad/pgvector:pg16-ocp
```

**Note:** Ensure the external VM is accessible from your OpenShift cluster. You may need to configure network policies or firewall rules.



### Step 3: Deploy the Postgres Database

```bash
oc create -f ../shared/postgres.yaml
```

**Verify deployment:**
```bash
oc get pods | grep postgres
```

### Step 4: Deploy the OGX Server

```bash
oc create -f deployments/ogx-server.yaml
```

**Verify deployment:**
```bash
oc get pods | grep ogx
```

### Step 5: Deploy the Simple Math MCP Server

```bash
oc create -f deployments/math-mcp.yaml
```

### Step 6: Test with Jupyter Notebook

1. Open the Jupyter notebook in your browser.

2. Create a data directory and upload the `return-policy.txt` file from `../data/` if not already uploaded.

3. Follow the steps in the notebook to test the OGX server.

**Notebook:** [ogx-server-default.ipynb](./ogx-server-default.ipynb)
