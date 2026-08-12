# rhoai-automation

CLI automation for deploying and managing Red Hat OpenShift AI (RHOAI) use cases.

For architecture and developer docs see [`docs/README.md`](docs/README.md).

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.12 | `python3 --version` |
| `oc` CLI | Must be logged in to the target cluster (`oc login`) |
| OpenShift cluster | OCP 4.14+, ppc64le or x86_64 |

---

## Installation

```bash
cd openshift-ai-demos/automation

python3 -m venv .venv
source .venv/bin/activate

pip install -e .

rhoai --help
```

---

## Configuration

Every command accepts `--config` / `-c` pointing to a YAML file.
Without it, the built-in defaults in [`rhoai/config/defaults.yaml`](rhoai/config/defaults.yaml) apply.

A ready-to-use example is at [`config-fraud-detection.yaml`](config-fraud-detection.yaml).

### Minimal config

```yaml
# Absolute path to the root of the openshift-ai-demos repository.
repo_root: /path/to/ai-demos/openshift-ai-demos

operator:
  channel: stable-3.5

# DSC components to enable.
components:
  - dashboard
  - workbenches
  - kserve
  - trustyai

deployment:
  namespace: test-fraud
  inference_service_name: fraud-detection
  model_uri: pvc://fraud-model-pvc/models
```
### `model_uri`

```yaml
model_uri: pvc://<claim-name>/<path>   # e.g. pvc://fraud-model-pvc/models
```

The model must be pre-loaded onto a PersistentVolumeClaim in the deployment namespace.


### Environment variable overrides

| Variable | Config key |
|---|---|
| `RHOAI_NAMESPACE` | `platform.namespace` |
| `RHOAI_REPO_ROOT` | `repo_root` |
| `RHOAI_KUBECONFIG` | `platform.kubeconfig` |
| `RHOAI_CONFIG` | Path to config YAML (replaces `--config`) |
| `RHOAI_LOG_LEVEL` | `log_level` |

---

## Fraud Detection use case

### Deploy

```bash
rhoai usecase deploy fraud-detection -c config-fraud-detection.yaml
```

Checks the RHOAI platform (configuring it if needed), deploys the Triton ServingRuntime
and InferenceService, and validates that the model is serving inference requests.

```
Deploying : fraud-detection
Namespace : test-fraud
Service   : fraud-detection
Storage   : pvc://fraud-model-pvc/models

Checking RHOAI platform...

  ✔  Operator ready
  ✔  DSCI 'default-dsci' ready
  ✔  DSC 'default-dsc' ready
  ✔  Components enabled: Dashboard, Workbenches, KServe, TrustyAI

✔  Platform ready  (6s)
✔  Configuring Triton ServingRuntime  (8s)
✔  Deploying model 'fraud-detection'  (21s)
✔  Validating model inference  (1s)

Deployment complete.

  Use case  : fraud-detection
  Namespace : test-fraud
  Endpoint  : https://fraud-detection-test-fraud.apps.<cluster>

  Next: rhoai usecase verify fraud-detection
```

### Verify

```bash
rhoai usecase verify fraud-detection -c config-fraud-detection.yaml
```

Checks the platform, confirms the InferenceService is Ready, and runs a live inference request.

### Cleanup

```bash
rhoai usecase cleanup fraud-detection -c config-fraud-detection.yaml
```

Removes the InferenceService and ServingRuntime. Pass `--delete-platform` to also remove the DSC and DSCI.

---

## Platform commands

```bash
# One-shot bootstrap: install operator + enable DSC components
rhoai platform setup -c config-fraud-detection.yaml

# Individual steps
rhoai platform init   -c config-fraud-detection.yaml --channel stable-3.5
rhoai platform enable kserve trustyai -c config-fraud-detection.yaml

# Inspect cluster and platform health
rhoai platform inspect -c config-fraud-detection.yaml
rhoai platform status  -c config-fraud-detection.yaml

# Full uninstall
rhoai platform uninstall -c config-fraud-detection.yaml --yes
```

---

## Command reference

```
rhoai [--log-level LEVEL] <command> [options]
```

> `--log-level` must come immediately after `rhoai`, before the subcommand.  
> Default is `INFO` (structured output only). Use `DEBUG` for full log output.

### `rhoai usecase`

| Command | Description |
|---|---|
| `deploy <name> [-c CONFIG]` | Deploy the named use case |
| `verify <name> [-c CONFIG]` | Verify the deployment is healthy |
| `cleanup <name> [-c CONFIG] [--delete-platform]` | Remove use-case resources |
| `list` | List available use cases |

### `rhoai platform`

| Command | Description |
|---|---|
| `init [-c CONFIG] [--channel CH] [--version VER]` | Install operator + initialize DSCI |
| `setup [-c CONFIG] [--channel CH]` | Full bootstrap (init + enable components) |
| `enable <components...> [-c CONFIG]` | Enable DSC components |
| `disable <components...> [-c CONFIG]` | Disable DSC components |
| `status [-c CONFIG]` | Report platform health |
| `inspect [-c CONFIG]` | Display cluster info (read-only) |
| `uninstall [-c CONFIG] [--yes] [--keep-workload-ns]` | Remove all RHOAI resources |

### Timeout defaults

| Operation | Default |
|---|---|
| Operator ready | 300 s |
| DSC ready | 600 s |
| InferenceService ready | 120 s |
| TrustyAI ready | 300 s |

Override under the `timeouts:` key in your config file.
