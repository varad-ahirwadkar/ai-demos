# rhoai platform — CLI Reference

The `rhoai platform` command group manages the full lifecycle of a Red Hat OpenShift AI
(RHOAI) installation: operator install, platform initialisation, component management,
status reporting, and clean uninstall.

---

## Prerequisites

- `oc` CLI installed and logged in (`oc login <cluster-url>`)
- Cluster-admin permissions
- Python environment with the automation package installed (`pip install -e .` from the
  `automation/` directory)

---

## Command overview

| Command | Purpose |
|---|---|
| `rhoai platform init` | Install operator + initialise DSCI |
| `rhoai platform enable` | Enable one or more DSC components |
| `rhoai platform disable` | Disable one or more DSC components |
| `rhoai platform setup` | One-shot bootstrap (init + components from config) |
| `rhoai platform uninstall` | Remove all RHOAI platform resources (cluster-clean) |
| `rhoai platform status` | Report platform health |
| `rhoai platform inspect` | Display cluster info (read-only) |

---

## Configuration

All commands load configuration from (highest priority first):

1. **CLI flags** — override everything for that invocation only, never written to disk
2. **`--config` file** — user-supplied YAML merged on top of defaults
3. **`RHOAI_` environment variables** — `RHOAI_NAMESPACE`, `RHOAI_CLUSTER_URL`, etc.
4. **`config/defaults.yaml`** — bundled defaults

Key defaults (`config/defaults.yaml`):

```yaml
operator:
  name: rhods-operator
  namespace: redhat-ods-operator
  channel: stable
  source: redhat-operators
  source_namespace: openshift-marketplace

platform:
  namespace: redhat-ods-applications

dsc:
  name: default-dsc
  dsci_name: default-dsci

components: []   # used by 'setup' — empty = apply full dsc.yaml as-is
```

Pass `--config /path/to/my-config.yaml` to any command to override defaults without
modifying the bundled file.

---

## `rhoai platform init`

Validates cluster prerequisites, installs the RHOAI operator via OLM, and initialises
the DSCInitialization (DSCI). Does **not** enable any DSC components — run
`enable` or `setup` afterwards.

**Sequence:**
1. Validate cluster login
2. Validate RBAC permissions (SelfSubjectAccessReview)
3. Validate / confirm storage classes
4. Create operator namespace (`redhat-ods-operator`) if absent
5. Create workload namespace (`redhat-ods-applications`) if absent
6. Apply OperatorGroup + Subscription → wait for CSV `Succeeded`
7. Approve InstallPlan automatically if `--version` pin was requested (Manual approval)
8. Apply DSCI manifest → wait for `Ready`

### Flags

| Flag | Default | Description |
|---|---|---|
| `--channel` | `stable` | OLM channel. See available channels below. |
| `--version` | _(none)_ | Pin to a specific CSV. Accepts bare semver or full CSV name. |
| `--source` | `redhat-operators` | CatalogSource name. |
| `--config`, `-c` | _(none)_ | Path to a config YAML file. |

### Discovering channels and versions

```bash
# List all available channels for rhods-operator
oc get packagemanifest rhods-operator \
  -o jsonpath='{.status.channels[*].name}'

# Show which CSV a specific channel currently resolves to
oc get packagemanifest rhods-operator \
  -o jsonpath='{range .status.channels[?(@.name=="stable-3.x")]}{.currentCSV}{"\n"}{end}'
```

**Notable channels:**

| Channel | Description |
|---|---|
| `stable` | Latest 2.x release (long-term support line) |
| `stable-3.x` | Latest 3.x release (floating, auto-upgrades within 3.x) |
| `stable-3.4` | Pinned to the 3.4 minor line |
| `stable-3.3` | Pinned to the 3.3 minor line |
| `fast-3.x` | Latest 3.x fast lane (promoted ahead of stable) |
| `beta` | Pre-GA builds — **see note below** |
| `alpha` | Alpha builds |

### Examples

```bash
# Latest 3.x from the standard catalog
rhoai platform init --channel stable-3.x

# Pinned to a specific patch (bare semver — normalised automatically)
rhoai platform init --channel stable-3.4 --version 3.4.2

# Full CSV name also accepted
rhoai platform init --channel stable-3.4 --version rhods-operator.3.4.2

# With an explicit config file
rhoai platform init --config /path/to/my-config.yaml --channel stable-3.x
```

> **Version normalisation:** bare semver `3.4.2` is automatically expanded to
> `rhods-operator.3.4.2`. The `v` prefix (e.g. `v3.4.2`) is **not** used in RHOAI
> CSV names.

> **Manual approval:** when `--version` is supplied the Subscription is created with
> `installPlanApproval: Manual` and the pending InstallPlan is automatically approved
> by the CLI — OLM will not auto-upgrade beyond the pinned CSV.

---

### Pre-GA install (`--source` / `beta` channel)

> ⚠️ **Work in progress** — automated pre-GA install support is not yet complete.
> The steps below describe what the CLI will handle end-to-end once implemented.
> For now, perform these steps manually before running `rhoai platform init`.

Installing a pre-GA build (e.g. RHOAI 3.5 EA) requires three cluster-side
prerequisites that are not yet automated:

#### 1. Pull secret for `quay.io/rhoai`

```bash
oc registry login \
  --registry=quay.io/rhoai \
  --auth-basic='<robot-account>:<token>' \
  --to=/tmp/rhoai-pull.json

oc set data secret/pull-secret \
  -n openshift-config \
  --from-file=.dockerconfigjson=/tmp/rhoai-pull.json
```

#### 2. ImageContentSourcePolicy (ICSP)

Apply the ICSP manifest provided with the EA release to redirect pulls from the
public registry to the internal mirror.

#### 3. CatalogSource

```bash
cat <<EOF | oc apply -f -
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: cs-rhoai-fbc-fragment
  namespace: openshift-marketplace
spec:
  sourceType: grpc
  image: quay.io/rhoai/rhoai-fbc-fragment:<ea-tag>
  displayName: RHOAI Pre-GA
  publisher: Red Hat
EOF

oc get catalogsource cs-rhoai-fbc-fragment -n openshift-marketplace -w
```

Once all three prerequisites are in place:

```bash
rhoai platform init --channel beta --source cs-rhoai-fbc-fragment
```

---

## `rhoai platform enable`

Enables one or more DSC components on an already-initialised platform. Requires
`init` to have run first.

**Behaviour:**
- Additive and idempotent — only the named components are patched to `Managed`
- Components not named are left exactly as they are (no accidental disables)
- If no DataScienceCluster exists yet, one is created from the base manifest before patching

### Syntax

```bash
rhoai platform enable <component> [<component> ...]
```

### Available components

| Component | Description |
|---|---|
| `dashboard` | RHOAI web dashboard |
| `kserve` | Model serving (KServe) |
| `workbenches` | Jupyter notebooks |
| `modelregistry` | Model registry |
| `aipipelines` | AI/ML pipelines (Argo-based) |
| `trustyai` | TrustyAI bias / explainability |
| `ray` | Distributed compute (Ray) |
| `kueue` | Job queue management |
| `trainingoperator` | Kubeflow Training Operator |
| `trainer` | Training workflows |
| `mlflowoperator` | MLflow experiment tracking |
| `feastoperator` | Feature store (Feast) |
| `llamastackoperator` | LlamaStack operator |
| `ogx` | OpenShift AI Extensions |
| `sparkoperator` | Apache Spark operator |

### Examples

```bash
# Enable a single component
rhoai platform enable dashboard

# Enable multiple components in one call
rhoai platform enable dashboard kserve workbenches modelregistry

# Common production set
rhoai platform enable dashboard kserve workbenches modelregistry aipipelines trustyai

# With a config file
rhoai platform enable kserve --config /path/to/my-config.yaml
```

---

## `rhoai platform disable`

Disables one or more DSC components (sets `managementState` to `Removed`). Requires
`init` to have run first and a DataScienceCluster to already exist.

**Behaviour:**
- Idempotent — components already `Removed` stay `Removed`
- Components not named are left exactly as they are (no accidental enables)
- Raises an error immediately if the component name is unknown (typo guard)

### Syntax

```bash
rhoai platform disable <component> [<component> ...]
```

### Examples

```bash
# Disable a single component
rhoai platform disable trustyai

# Disable multiple components in one call
rhoai platform disable ray kueue trainingoperator

# With a config file
rhoai platform disable trustyai --config /path/to/my-config.yaml
```

> **Note:** `disable` requires the DataScienceCluster to already exist. If it does
> not (i.e. `enable` or `setup` was never run), the command will exit with an error.

---

## `rhoai platform setup`

Full one-shot bootstrap — runs `init` followed by enabling DSC components.

**Two modes:**

| Mode | When | Behaviour |
|---|---|---|
| **Full** | `components` not set in config (default) | Applies `shared/dsc.yaml` as-is — enables whatever is `Managed` in that file |
| **Selective** | `components` list set in config | Patches only the listed components to `Managed`; everything else is left `Removed` |

Use `setup` when you want a single command to go from zero to a running platform.
Use `init` + `enable`/`disable` when you need day-2 fine-grained control.

```bash
# Full install — applies dsc.yaml defaults
rhoai platform setup

# Selective install — only the listed components are enabled
rhoai platform setup --config my-config.yaml
```

**Config file for selective setup:**

```yaml
# my-config.yaml
operator:
  channel: stable-3.x
  source: redhat-operators
components:
  - dashboard
  - kserve
  - workbenches
  - modelregistry
```

```bash
rhoai platform setup --config my-config.yaml
```

---

## `rhoai platform uninstall`

Performs a **complete teardown** of all RHOAI platform resources, leaving the cluster
clean for a fresh reinstall. Workload namespaces are deleted by default.

**Deletion sequence:**
1. DataScienceCluster — operator deprovisions components gracefully first
2. DSCInitialization
3. ClusterServiceVersion (CSV), Subscription, OperatorGroup, InstallPlans
4. Cluster-wide sweep of any stale rhods/rhoai/odh CSVs
5. CRDs registered by the operator
6. Validating and mutating webhooks (rhoai/rhods/odh/kserve/trustyai) — prevents namespaces getting stuck Terminating
7. Cluster-scoped RBAC (ClusterRoles / ClusterRoleBindings)
8. Operator namespace (`redhat-ods-operator`)
9. Workload namespaces: `redhat-ods-applications`, `rhods-notebooks`,
   `rhoai-model-registries`, `redhat-ods-monitoring`
   — skipped automatically if never created (e.g. `rhoai-model-registries` only
   exists when `modelregistry` was enabled)

Every step is safe on a partially-installed cluster — missing resources are skipped
with an info log rather than raising an error.

**Stuck namespace handling:** if any namespace gets stuck in `Terminating` after
deletion, the CLI automatically strips its finalizers and waits for removal.

### Flags

| Flag | Default | Description |
|---|---|---|
| `--yes`, `-y` | `false` | Skip the confirmation prompt |
| `--keep-workload-ns` | `false` | Preserve workload namespaces instead of deleting them |
| `--config`, `-c` | _(none)_ | Path to a config YAML file |

### Examples

```bash
# Full clean wipe — cluster ready for fresh reinstall (default)
rhoai platform uninstall -y

# Interactive prompt
rhoai platform uninstall

# Preserve user workloads (notebooks, pipelines, models)
rhoai platform uninstall -y --keep-workload-ns

# With a config file (e.g. different namespace)
rhoai platform uninstall --config /path/to/my-config.yaml -y
```

> **Why are workload namespaces deleted by default?**
> The primary use case is testing and development where a clean cluster state is
> required for each reinstall. Pass `--keep-workload-ns` only when you want to
> preserve user notebooks, pipelines, inference services, and PVCs across
> a platform reinstall.

---

## `rhoai platform status`

Reports the health of the installed platform.

```bash
rhoai platform status
```

**Sample output:**

```
RHOAI Platform
  Operator          rhods-operator.3.4.2        ✔  Succeeded
  Initialization    default-dsci                ✔  Ready
  Cluster           default-dsc                 ✔  Ready

  Components
    ✔  aipipelines
    ✔  dashboard
    ✔  kserve
    ✔  modelregistry
    ✔  workbenches

Platform is healthy.
```

Exits with code `1` if any check fails.

---

## `rhoai platform inspect`

Displays factual cluster information. Read-only — makes no changes.

```bash
rhoai platform inspect
```

**Sample output:**

```
Cluster
  OpenShift    4.16.3
  Topology     Multi-node  (6 nodes: 3 master, 3 workers)

Worker Nodes
  NAME                                              CPU         MEMORY
  ip-10-0-110-158.us-west-1.compute.internal        4 cores     15 GiB
  ip-10-0-21-28.us-west-1.compute.internal          4 cores     15 GiB
  ip-10-0-65-202.us-west-1.compute.internal         4 cores     15 GiB

Storage Classes
  NAME                                      BOUND
  gp2-csi                                   0 GiB
  gp3-csi                                   40 GiB
```

---

## Typical workflows

### Fresh install — selective components

```bash
oc login <cluster-url>
rhoai platform init --channel stable-3.x
rhoai platform enable dashboard kserve workbenches modelregistry
rhoai platform status
```

### Fresh install — one-shot via config

```bash
# my-config.yaml: operator.channel + components list
rhoai platform setup --config my-config.yaml
rhoai platform status
```

### Day-2 component changes

```bash
# Add a component after initial setup
rhoai platform enable trustyai

# Remove a component that is no longer needed
rhoai platform disable ray kueue
```

### Teardown and reinstall (fresh cluster state)

```bash
# Full wipe — deletes all namespaces, CRDs, webhooks, RBAC
rhoai platform uninstall -y

# Reinstall
rhoai platform init --channel stable-3.x
rhoai platform enable dashboard kserve workbenches modelregistry
```

### Teardown preserving user workloads

```bash
# Removes the operator but keeps notebooks, pipelines, and models
rhoai platform uninstall -y --keep-workload-ns
```

### Using a config file (CI/CD)

```yaml
# rhoai-config.yaml
operator:
  channel: stable-3.x
  source: redhat-operators
components:
  - dashboard
  - kserve
  - workbenches
  - modelregistry
  - aipipelines
```

```bash
rhoai platform setup --config rhoai-config.yaml
```
