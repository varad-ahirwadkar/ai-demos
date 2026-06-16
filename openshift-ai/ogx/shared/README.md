# Shared Infrastructure Manifests

This directory contains Kubernetes/OpenShift manifests for databases and vector stores shared across different GenAI application servers and notebooks in the OGX (Open GenAI Stack) demos.

## Manifests Overview

| File | Description | Ports | Key Resources Created |
| :--- | :--- | :--- | :--- |
| **[postgres.yaml](./postgres.yaml)** | Standard PostgreSQL 16 database for KV/SQL store backups. | `5432` | `Pod`, `Service`, `Secret` (`postgres-credentials`) |
| **[pgvector.yaml](./pgvector.yaml)** | PostgreSQL 16 database with the pgvector extension enabled for vector stores. | `5432` | `StatefulSet`, `Service`, `Secret` (`pgvector-secret`), `PersistentVolumeClaim` |
| **[milvus.yaml](./milvus.yaml)** | Standalone Milvus vector database using etcd as its metadata engine. | `19530` (gRPC)<br>`9091` (HTTP) | `Deployment` (etcd), `Deployment` (milvus-standalone), `Service` (etcd-service), `Service` (milvus-service), `Secret` (`milvus-secret`), `PersistentVolumeClaim` |

---

## Deployment Steps

Before deploying these manifests, make sure you are logged in to your OpenShift cluster and have switched to the appropriate namespace (e.g., `redhat-ods-applications` or a custom user namespace):

```bash
oc project <your-namespace>
```

### 1. Deploy PostgreSQL (KV and Metadata Store)
PostgreSQL is used by the OGX Server to persist conversation logs, registry information, prompts, and tool configurations.

```bash
oc create -f postgres.yaml
```
*Verify pod health:*
```bash
oc get pods -l app=postgres
```

### 2. Deploy pgvector (Remote Vector Store Option)
You can deploy pgvector either directly inside your OpenShift cluster (Option A) or on an external VM/server (Option B):

#### Option A: In-Cluster (OpenShift)
Deploy pgvector as a StatefulSet inside your namespace:
```bash
oc create -f pgvector.yaml
```
*Verify pod health:*
```bash
oc get pods -l app=pgvector
```

#### Option B: External VM / Host Container
If you prefer running pgvector on an external server or VM:
```bash
podman run -itd -u 0 --name pgvector \
  -e POSTGRES_USER=ogx_pgv \
  -e POSTGRES_PASSWORD=ogx_pgv \
  -e POSTGRES_DB=ogx_pgv \
  -p 5433:5432 \
  --replace \
  quay.io/vahirwad/pgvector:pg16-ocp
```

> [!IMPORTANT]
> Ensure the external VM is accessible from your OpenShift cluster. You may need to configure network policies or firewall rules to allow traffic on port `5433`.

### 3. Deploy Milvus Standalone (Remote Vector Store Option)
Deploy this if you want to test remote Milvus integration. It will spin up both an etcd helper instance and the Milvus standalone engine.

```bash
oc create -f milvus.yaml
```
*Verify pod health:*
```bash
oc get pods | grep -E "milvus|etcd"
```

## Clean Up

To tear down any of the shared infrastructure databases:

```bash
oc delete -f postgres.yaml
oc delete -f pgvector.yaml
oc delete -f milvus.yaml
```
