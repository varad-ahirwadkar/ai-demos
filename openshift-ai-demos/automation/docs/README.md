# rhoai-automation

A CLI-first automation framework for deploying and configuring
[Red Hat OpenShift AI (RHOAI)](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)
use cases on OpenShift clusters.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Architecture](#2-architecture)
3. [Project Structure](#3-project-structure)
4. [Installation](#4-installation)
5. [Configuration](#5-configuration)
6. [CLI Usage](#6-cli-usage)
7. [Platform Capabilities](#7-platform-capabilities)
8. [OpenShift Operations](#8-openshift-operations)
9. [Use Cases](#9-use-cases)
10. [Adding a New Use Case](#10-adding-a-new-use-case)
11. [Logging](#11-logging)
12. [Testing](#12-testing)
13. [Development Guidelines](#13-development-guidelines)
14. [Current Status](#14-current-status)

---

## 1. Project Overview

### Purpose

`rhoai-automation` automates the end-to-end lifecycle of RHOAI use cases on
OpenShift: cluster validation, operator installation, platform configuration,
model serving setup, and observability.

The framework is designed to orchestrate the existing YAML manifests in the
[`openshift-ai-demos`](../) repository. It does not replace or modify those
manifests — it applies them in the right order, with the right dependencies,
and waits for each step to be healthy before continuing.

### Goals

- Reduce the time to deploy a working RHOAI use case from manual multi-step
  procedures to a single CLI command.
- Provide a reusable platform layer that any use case can build on, without
  duplicating cluster interaction code.
- Keep the framework simple enough to extend without deep framework knowledge.

### Current Capabilities

| Capability | Implemented |
|---|---|
| Cluster login and RBAC validation | ✔ |
| Namespace creation | ✔ |
| Storage class validation | ✔ |
| RHOAI operator install via OLM | ✔ |
| DataScienceCluster / DSCInitialization lifecycle | ✔ |
| KServe InferenceService and ServingRuntime management | ✔ |
| OpenShift Template processing (`oc process`) | ✔ |
| TrustyAI Service deployment and monitoring config | ✔ |
| S3 credentials secret management | ✔ |
| PVC creation and deletion | ✔ |
| Platform health verification | ✔ |
| Cluster info (topology, nodes, storage) | ✔ |
| Fraud Detection use case (end-to-end) | ✔ |

---

## 2. Architecture

### Layering

```
 CLI  (rhoai/cli)
┌─────────────────────────────────────────────┐
│  rhoai platform init / setup / status / …   │  User interface only.
│  rhoai usecase  deploy  / verify / cleanup  │  No business logic.
└────────────────┬──────────────┬─────────────┘
                 │              │
     platform/   │              │ usecases/
    ┌────────────▼──┐    ┌──────▼──────────────┐
    │  prepare.py   │    │  fraud_detection/   │
    │  operators.py │    │  deploy.py          │
    │  dsc.py       │◄───│  verify.py          │
    │  inference.py │    │  cleanup.py         │
    │  trustyai.py  │    │  assets.py          │
    │  storage.py   │    └─────────────────────┘
    │  verify.py    │    (use cases call platform/,
    └────────────┬──┘     never ocp/ directly)
                 │
     ocp/        │
    ┌────────────▼────────────────────────────┐
    │  resources.py   — OpenShift API         │  Only layer that
    │  wait.py        — polling helpers       │  talks to the cluster.
    └────────────┬────────────────────────────┘
                 │
     utils/      │
    ┌────────────▼────────────────────────────┐
    │  logger.py   yaml_io.py                 │
    └─────────────────────────────────────────┘
```

### Key design rules

- **`ocp/resources.py` is the only file that calls the Kubernetes API.**
  All other modules — platform and use cases alike — go through it.
- **Use cases never import `ocp/` directly.**
  They call `platform/` modules, which call `ocp/`.
- **Use cases never import each other.**
- **`ocp/wait.py` imports `ocp/resources.py`, never the reverse.**
- **The CLI is thin.** It loads config, calls one function, and prints output.
  All orchestration logic lives in `platform/` or `usecases/`.

---

## 3. Project Structure

```
automation/
├── pyproject.toml
├── README.md
└── rhoai/
    ├── cli/
    │   ├── main.py                  Entry point; registers command groups
    │   └── commands/
    │       ├── platform.py          rhoai platform subcommands
    │       └── usecase.py           rhoai usecase subcommands
    ├── config/
    │   ├── defaults.yaml            Bundled default configuration
    │   └── loader.py                Config merge logic (no env-var overrides)
    ├── ocp/
    │   ├── resources.py             All Kubernetes API calls
    │   └── wait.py                  Polling helpers (ready, deleted)
    ├── platform/
    │   ├── prepare.py               Cluster validation + platform bootstrap
    │   ├── operators.py             OLM operator lifecycle
    │   ├── dsc.py                   DataScienceCluster / DSCInitialization
    │   ├── inference.py             InferenceService + ServingRuntime
    │   ├── trustyai.py              TrustyAI Service lifecycle
    │   ├── storage.py               Secrets and PVCs
    │   ├── verify.py                Platform health checks
    │   ├── manifests.py             Shared manifest path resolver
    │   └── config_generator.py      ONNX model → Triton config.pbtxt
    ├── usecases/
    │   ├── registry.py              Maps CLI names to use-case modules
    │   └── fraud_detection/
    │       ├── assets.py            Manifest path resolver for this use case
    │       ├── deploy.py            Deployment orchestration
    │       ├── verify.py            Health checks
    │       └── cleanup.py           Resource teardown
    └── utils/
        ├── logger.py                Logging configuration
        └── yaml_io.py               YAML load, load_all, deep_merge

tests/
├── integration/
│   └── test_fraud_detection.py     Module-graph and smoke tests
└── unit/
    ├── config/
    ├── ocp/
    ├── platform/
    ├── usecases/
    └── utils/
```

### Package responsibilities

| Package | Responsibility |
|---|---|
| `rhoai/cli` | Parse arguments, load config, delegate to platform or use cases. No business logic. |
| `rhoai/config` | Load and deep-merge YAML config (defaults + user file). |
| `rhoai/platform` | Reusable capabilities: operator install, DSC, model serving, TrustyAI, storage, verification. |
| `rhoai/ocp` | The single integration point with the Kubernetes/OpenShift API. |
| `rhoai/usecases` | Customer-facing solutions. Each use case owns its deploy/verify/cleanup sequence. |
| `rhoai/utils` | Shared utilities with no dependencies on the rest of the framework. |
| `tests/` | Unit tests (all I/O mocked) and integration smoke tests (no live cluster). |

---

## 4. Installation

**Requirements:** Python 3.12 or later, `oc` CLI on `PATH`, and an active
`oc login` session before running any command that touches the cluster.

```bash
# 1. Create and activate a virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# 2. Install in editable mode
pip install -e ".[dev]"   # include [dev] when running tests

# 3. Verify the entry point is available
rhoai --help
```

---

## 5. Configuration

Configuration is assembled from two sources, deep-merged in priority order
(CLI flags are applied per-command after loading):

```
1. CLI flags              (highest — this run only)
       ↓
2. --config file          (user-supplied YAML)
       ↓
3. defaults.yaml          (bundled fallback)
```

### User configuration file

Create a YAML file with only the keys you want to override.  Everything
else is inherited from `rhoai/config/defaults.yaml`.

```yaml
# my-cluster.yaml
repo_root: /home/user/openshift-ai-demos

platform:
  namespace: redhat-ods-applications   # where RHOAI operands run

storage:
  class_name: gp3-csi
```

Pass it with `--config` on the subcommand:

```bash
rhoai usecase deploy fraud-detection --config my-cluster.yaml
```

### Default values

Key defaults from `rhoai/config/defaults.yaml`:

```yaml
log_level: INFO

platform:
  namespace: redhat-ods-applications

operator:
  name: rhods-operator
  namespace: redhat-ods-operator
  channel: stable
  source: redhat-operators
  source_namespace: openshift-marketplace

components: []   # used by 'setup' — empty applies the base DSC manifest as-is

dsc:
  name: default-dsc
  dsci_name: default-dsci

storage:
  class_name: ""        # empty = accept any available RWO class
  s3_secret_name: s3-credentials

deployment:
  namespace: ""                          # falls back to platform.namespace when empty
  trustyai_service_name:    trustyai-service
  trustyai_service_account: trustyai-user

timeouts:
  operator_ready:  300   # seconds
  dsc_ready:       600
  inference_ready: 120
  trustyai_ready:  300
  ingestion_ready: 300
```

---

## 6. CLI Usage

All commands accept `--config/-c` at the subcommand level to specify a config
file. Log verbosity is set with `--log-level/-l` on the root command.

```
rhoai --help
rhoai platform --help
rhoai usecase  --help
```

### `rhoai platform`

| Command | Description |
|---|---|
| `rhoai platform init` | Validate cluster prerequisites, install the RHOAI operator via OLM, and apply DSCInitialization. Blocks until everything is Ready. |
| `rhoai platform enable` | Enable one or more DSC components (e.g. `kserve`, `trustyai`). |
| `rhoai platform disable` | Disable one or more DSC components. |
| `rhoai platform setup` | One-shot bootstrap: init + enable components listed in config. |
| `rhoai platform status` | Check health of the operator CSV, DSCI, and DSC. Exits non-zero if any check fails. |
| `rhoai platform inspect` | Display cluster info (OpenShift version, topology, worker node CPU/memory/GPU, storage classes) without modifying anything. |
| `rhoai platform uninstall` | Remove all RHOAI platform resources. |

```bash
# Bootstrap the platform in one shot
rhoai platform setup --config my-cluster.yaml

# Or step by step
rhoai platform init   --config my-cluster.yaml --channel stable-3.x
rhoai platform enable kserve trustyai --config my-cluster.yaml
rhoai platform status --config my-cluster.yaml

# Inspect the cluster (read-only)
rhoai platform inspect
```

### `rhoai usecase`

| Command | Description |
|---|---|
| `rhoai usecase deploy <name>` | Deploy the named use case end-to-end, including platform bootstrap. |
| `rhoai usecase verify <name>` | Check that all use-case resources are healthy. |
| `rhoai usecase cleanup <name>` | Remove use-case resources. Add `--delete-platform` to also delete DSC and DSCI. |
| `rhoai usecase list` | List all registered use cases. |

```bash
# Deploy fraud detection
rhoai usecase deploy fraud-detection --config my-cluster.yaml

# Verify it
rhoai usecase verify fraud-detection

# Clean up (use-case resources only)
rhoai usecase cleanup fraud-detection

# Clean up everything including DSC/DSCI
rhoai usecase cleanup fraud-detection --delete-platform
```

---

## 7. Platform Capabilities

Platform modules live in `rhoai/platform/` and provide reusable building blocks.
Use cases and the CLI call these modules. Each platform module imports from
`rhoai.ocp.resources` and `rhoai.ocp.wait` to reach the cluster.

### `prepare.py`

Cluster validation and platform bootstrap.

| Function | Description |
|---|---|
| `validate_login()` | Confirm the cluster is reachable via the current kubeconfig. |
| `validate_permissions(namespace)` | Confirm `create` access on `Subscriptions` in the operator namespace. |
| `validate_storage(class_name)` | Confirm a named `StorageClass` exists, or that at least one exists when no name is given. |
| `validate_namespace(namespace)` | Ensure the namespace exists, creating it if absent. |
| `platform_needs_reconciliation(config)` | Return `True` if the platform state does not match the desired config. |
| `bootstrap_platform(config)` | Full bootstrap: validate cluster → operator install/wait → DSC/DSCI apply and wait. Shared by the CLI and all use-case deploy functions. |
| `get_cluster_info()` | Return OpenShift version, topology (SNO vs Multi-node), per-worker-node CPU/memory/GPU, and per-StorageClass PV usage. |

### `operators.py`

RHOAI operator lifecycle via OLM.

| Function | Description |
|---|---|
| `is_installed(name, namespace)` | Return `True` if the operator CSV is in `Succeeded` phase. |
| `install(name, namespace, channel, repo_root, timeout)` | Apply `OperatorGroup` + `Subscription` and wait for CSV to succeed. |
| `wait_until_ready(name, namespace, timeout)` | Block until the CSV reaches `Succeeded`. |
| `resolve_csv_name(package_name, namespace)` | Discover the versioned CSV name (e.g. `rhods-operator.3.5.0`) from the package name prefix. |
| `verify(name, namespace)` | Assert the CSV is `Succeeded`; raise `RuntimeError` otherwise. |
| `get_csv_info(name, namespace)` | Return display info: name, version, phase. |

### `dsc.py`

`DataScienceCluster` and `DSCInitialization` lifecycle.

| Function | Description |
|---|---|
| `apply_dsci(path)` | Apply the `DSCInitialization` manifest. Idempotent. |
| `apply_dsc(path)` | Apply the `DataScienceCluster` manifest. Idempotent. |
| `wait_until_ready(name, timeout)` | Block until the DSC reaches `Ready` phase. |
| `verify_dsci(name)` | Assert the DSCI is `Ready`; raise `RuntimeError` otherwise. |
| `verify(name)` | Assert the DSC is `Ready`; raise `RuntimeError` otherwise. |
| `delete_dsc(name)` | Delete the DSC and wait for removal. |
| `delete_dsci(name)` | Delete the DSCI and wait for removal. |
| `get_component_states(name)` | Return a `{component: managementState}` dict from the DSC spec. |

### `inference.py`

KServe `InferenceService` and `ServingRuntime` management.

| Function | Description |
|---|---|
| `apply_serving_runtime_from_template(path, namespace)` | Process an OpenShift Template (`oc process`) and apply the resulting `ServingRuntime`. |
| `wait_until_ready(name, namespace, timeout)` | Block until the `InferenceService` is `Ready`. |
| `verify(namespace, name=None)` | Assert one specific (or all) `InferenceService`(s) in the namespace are `Ready`. |
| `get_inference_url(name, namespace)` | Return the public inference URL from `.status.url` or the OpenShift `Route`. |
| `delete_inference_service(name, namespace)` | Delete an `InferenceService` and wait for removal. |
| `delete_serving_runtime(name, namespace)` | Delete a `ServingRuntime` and wait for removal. |

### `trustyai.py`

TrustyAI Service lifecycle for ML predictive model monitoring (bias detection,
data drift).

| Function | Description |
|---|---|
| `apply_monitoring_config(path)` | Apply the cluster-monitoring and user-workload-monitoring `ConfigMap`s. Reads the namespace from each document in the multi-doc YAML. |
| `patch_inferenceservice_config(namespace)` | Set `opendatahub.io/managed: "false"` on `inferenceservice-config`. Required in `RawDeployment` mode so TrustyAI can inject its payload-logging sidecar without RHOAI reverting the ConfigMap. |
| `apply_trustyai_service(path, namespace)` | Apply the `TrustyAIService` CR manifest. |
| `wait_until_ready(name, namespace, timeout)` | Block until the `TrustyAIService` is `Ready`. |
| `verify(name, namespace)` | Assert the `TrustyAIService` is `Ready`; raise `RuntimeError` otherwise. |
| `delete_trustyai_service(name, namespace)` | Delete the `TrustyAIService` CR and wait for removal. |

### `storage.py`

S3 credentials and PVC management.

| Function | Description |
|---|---|
| `apply_s3_secret(path, namespace)` | Apply an S3 credentials `Secret` manifest. |
| `create_secret(name, namespace, data, type)` | Create or update a `Secret` from a plain-string dict (base64 encoding applied internally). |
| `create_pvc(name, namespace, size, ...)` | Create a `PersistentVolumeClaim`. Skips if already exists. |
| `verify(secret_name, namespace)` | Assert the S3 credentials `Secret` exists. |
| `delete_pvc(name, namespace)` | Delete a PVC and wait for removal. |

### `verify.py`

Core platform health checks.

| Function | Description |
|---|---|
| `verify_platform(config)` | Run three checks — operator CSV, DSCI, DSC — and return a list of `CheckResult` objects. Raises `RuntimeError` if any check fails. |

---

## 8. OpenShift Operations

`rhoai/ocp/` is the **only package that communicates with the Kubernetes API**.
All other code reaches the cluster exclusively through it.

### `resources.py`

Wraps the `kubernetes` Python client's dynamic API with a thin, consistent
interface. Every resource kind that cannot be discovered by kind name alone is
pinned in `_API_HINTS` to avoid ambiguity with OpenShift's CRD overlaps.

| Function | Description |
|---|---|
| `apply_manifest(path, namespace)` | Load a YAML file and apply it via server-side apply. Idempotent. |
| `apply_dict(manifest, namespace)` | Apply a manifest dict via server-side apply. |
| `process_template(path, namespace)` | Run `oc process -n <namespace> -f <path>` then pipe the output to `oc apply`. |
| `delete_manifest(kind, name, namespace)` | Delete a resource by kind and name. Silent if already absent. |
| `exists(kind, name, namespace)` | Return `True` if the resource exists. |
| `get(kind, name, namespace)` | Return the full resource object dict. Raises `NotFoundError` if absent. |
| `patch(kind, name, body, namespace, strategy)` | Patch a resource (merge, json, or strategic). |
| `status(kind, name, namespace)` | Return the `.status` sub-object, or `{}` if absent. |
| `is_ready(kind, name, namespace)` | Return `True` if the resource meets its readiness condition. Dispatch varies by kind. |
| `list_resources(kind, namespace, label_selector)` | Return all matching resources as a list of dicts. |

### `wait.py`

Polling helpers that call back into `resources.py`.

| Function | Description |
|---|---|
| `wait_until_ready(kind, name, namespace, timeout)` | Poll `is_ready()` until `True` or timeout. |
| `wait_until_deleted(kind, name, namespace, timeout)` | Poll `exists()` until `False` or timeout. |
| `wait_until(condition_fn, description, timeout)` | General-purpose poller for custom conditions. |

---

## 9. Use Cases

Each use case lives in `rhoai/usecases/<name>/` and exposes exactly three
public functions: `deploy(config)`, `verify(config)`, and `cleanup(config)`.

### `assets.py`

The only file in a use case that knows where that use case's manifests live on
disk. All paths are resolved relative to `config["repo_root"]`.

Shared platform manifests (DSC, DSCI, S3 secret, Triton template) are delegated
to `platform/manifests.py` — `assets.py` only resolves use-case-specific paths.

### `deploy.py`

Orchestrates the full deployment in a documented, numbered sequence:

1–3. Call `prepare.bootstrap_platform(config)` — validates the cluster,
     installs the operator, and applies DSC/DSCI.
4.   Apply S3 credentials (skipped for `pvc://` URIs).
5.   For each model in `deployment.models`: apply Triton `ServingRuntime`
     (via OpenShift Template), apply `InferenceService`, wait for `Ready`,
     run smoke-test inference.
6.   If any model has `bias_monitoring` configured: enable user-workload
     monitoring, apply RBAC, apply `TrustyAIService`, wait for `Ready`.
7.   For each model with `bias_monitoring`: send observations, wait for
     ingestion, apply name mapping (optional), schedule SPD and identity
     monitors (optional).
8.   Print deployment summary.

`deploy.py` calls `platform/` modules only — never `ocp/` directly.

#### Inference input modes

Each model entry declares its inference input in exactly one of two mutually
exclusive modes, validated up front by `assets.validate_model_config` (both
`deploy` and `verify` run it before touching the cluster):

| | JSON mode | Dataset mode |
|---|---|---|
| Key | `inference_request` | `inference_dataset` |
| Smoke test | the file, used as-is (JSON) or converted (CSV) | first request from `iter_requests(..., batch_size=1)` — the first row/element, never the full batch |
| Observations | declared separately under `bias_monitoring.observations.path`/`.files` | derived from the dataset, batched by `bias_monitoring.observations.batch_size` (default 1) |
| Extra requirement | — | a Triton `config.pbtxt` via `inference_config_path`/`config_path`, or an ONNX `model_path` the framework generates one from |

Smoke test and observations share one generator (`request_generator.iter_requests`),
so in dataset mode the dataset is the single source of truth. Rejected as
ambiguous: both keys set; neither set; `inference_dataset` +
`observations.path`/`.files`; `inference_request` + `observations.batch_size`;
a dataset with no pbtxt and no `model_path` to generate one from.

When an ONNX `model_path` is supplied without a `config_path`, `deploy.py`
generates a Triton `config.pbtxt` via `platform/config_generator.py` (writing it
to `usecases/fraud_detection/inputs/<name>/config.pbtxt`) and records the path on
the model dict so staging, request generation, and name mapping all resolve the
same file.

### `verify.py`

Runs platform checks (`verify_platform`) then for each model:
confirms `InferenceService` is `Ready`, runs live inference, and (when
`bias_monitoring` is configured) checks TrustyAI observation count > 0.

### `cleanup.py`

Deletes use-case resources in reverse deploy order: TrustyAI Service (if
present), then each `InferenceService` and `ServingRuntime`. Does not touch
platform resources (DSC, DSCI) — that is the CLI's responsibility via
`--delete-platform`.

---

## 10. Adding a New Use Case

Follow these steps to add a new use case. No existing file outside the use case
directory needs to change except `registry.py`.

**Step 1 — Create the use case package.**

```
rhoai/usecases/<name>/
    __init__.py
    assets.py
    deploy.py
    verify.py
    cleanup.py
```

**Step 2 — Implement `assets.py`.**

Return `Path` objects for each manifest this use case needs:

```python
from pathlib import Path

def get_model_manifest(repo_root) -> Path:
    return Path(repo_root) / "model-serving" / "my-model" / "isvc.yaml"
```

**Step 3 — Implement `deploy.py`.**

Start with `prepare.deploy_platform(config)`, then call platform modules in
order for your use case:

```python
from rhoai.platform import inference, prepare, storage
from rhoai.usecases.my_use_case import assets
from rhoai.utils.logger import get_logger

log = get_logger(__name__)

def deploy(config):
    prepare.deploy_platform(config)
    storage.apply_s3_secret(...)
    inference.apply_serving_runtime_from_template(
        assets.get_serving_runtime_template(config["repo_root"]),
        config["platform"]["namespace"],
        config["deployment"]["namespace"],
        model_name="my-model",
        runtime_name="my-model-runtime",
    )
    inference.wait_until_ready(...)
```

**Step 4 — Implement `verify.py`.**

```python
from rhoai.platform import inference
from rhoai.platform import verify as platform_verify

def verify(config):
    platform_verify.verify_platform(config)
    inference.verify(config["cluster"]["namespace"], name="my-model")
```

**Step 5 — Implement `cleanup.py`.**

Delete in reverse deploy order. Do not delete platform resources here.

```python
from rhoai.platform import inference

def cleanup(config):
    inference.delete_inference_service("my-model", config["cluster"]["namespace"])
```

**Step 6 — Register the use case.**

Add one entry to `rhoai/usecases/registry.py`:

```python
from types import ModuleType
from rhoai.usecases import fraud_detection, my_use_case   # add import

REGISTRY: dict[str, ModuleType] = {
    "fraud-detection": fraud_detection,
    "my-use-case":     my_use_case,                        # add entry
}
```

The new use case is now available on the CLI:

```bash
rhoai usecase deploy my-use-case
```

---

## 11. Logging

Logging is configured once at startup by `utils/logger.py`. All modules obtain
their logger with `get_logger(__name__)`.

Log level is set by the `--log-level` CLI option (default: `INFO`).

```bash
# Verbose output during deployment
rhoai --log-level DEBUG usecase deploy fraud-detection

# Suppress everything except errors
rhoai --log-level ERROR platform status
```

Log format:

```
HH:MM:SS  LEVEL     module.name                    message
09:14:32  INFO      rhoai.platform.prepare         Validating cluster login
09:14:33  INFO      rhoai.platform.prepare         Cluster login confirmed
09:14:35  INFO      rhoai.platform.operators       Waiting for operator 'rhods-operator.3.5.0'
```

---

## 12. Testing

The test suite requires no live cluster. All Kubernetes API calls are mocked.

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/unit/platform/test_prepare.py

# Run a specific test class
pytest tests/unit/platform/test_prepare.py::TestDeployPlatform
```

### Test layout

| Directory | Contents |
|---|---|
| `tests/unit/` | Unit tests. Each module under `rhoai/` has a corresponding test file. All external I/O is mocked with `monkeypatch` or `unittest.mock`. |
| `tests/integration/` | Smoke tests. Verify that the module import graph is correct, config defaults are present, asset paths resolve to expected values, and deploy/verify/cleanup orchestration calls the right platform functions. No live cluster required. |

### Linting

```bash
ruff check rhoai/
```

The project targets Python 3.12 with `ruff` rules `E`, `F`, `I`, `UP`, `B`.

---

## 13. Development Guidelines

### Keep the CLI thin

CLI commands load config, call one function, and print output. All logic lives
in `platform/` or `usecases/`. A CLI command that is longer than ~10 lines is
doing too much.

### Platform modules manage platform capabilities

`platform/` modules own a single concern each (operators, DSC, inference,
storage, TrustyAI). They expose a clean function-level API that use cases and
the CLI can call without knowing anything about the Kubernetes API.

### Use cases orchestrate business workflows

A use case's `deploy.py` reads like a numbered procedure. It calls platform
functions in order and waits between steps. It does not contain resource
management logic — that belongs in `platform/`.

### All Kubernetes interactions belong in `ocp/`

`ocp/resources.py` is the only file that imports from `kubernetes`. If you need
to interact with the cluster, add a function there or in `platform/`. Never
import from `kubernetes` outside `ocp/`.

### Shared utilities belong in `utils/`

`utils/` modules have no dependencies on the rest of the framework. If a utility
needs to import from `platform/` or `ocp/`, it is not a utility — it belongs
somewhere else.

### Prefer simple functions over unnecessary abstractions

- Write plain functions, not classes, unless state is genuinely required.
- Do not add base classes, dataclasses, or protocols unless a concrete need
  exists today.
- Avoid `**kwargs` in public function signatures.
- Do not add error handling for conditions that cannot occur.

### Dependency direction

Imports must only flow in one direction:

```
cli  →  platform  →  ocp  →  utils
     ↘  usecases  ↗
```

Use cases import from `platform/` and `utils/`, never from `ocp/` or from each
other.

---

## 14. Current Status

The framework is fully implemented and in active use for the Fraud Detection
use case. The platform layer, OCP integration, CLI, configuration system,
and test suite are all production-ready.

Additional use cases will be added in subsequent iterations. Each new use case
requires only a new package under `rhoai/usecases/` and a single entry in
`registry.py` — the framework itself does not change.

### Implemented

- Full platform layer (`prepare`, `operators`, `dsc`, `inference`, `trustyai`,
  `storage`, `verify`)
- `fraud-detection` use case (end-to-end deploy, verify, cleanup)
- CLI with `platform` and `usecase` command groups
- Configuration system with YAML deep-merge (defaults + user file)
- 233-test suite (unit + integration), all passing

### Planned

- Additional use cases (to be added as separate work items)
- Live cluster integration tests

---

*Licensed under the [Apache License 2.0](https://www.apache.org/licenses/LICENSE-2.0).*
