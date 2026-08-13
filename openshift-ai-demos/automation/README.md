# rhoai-automation

CLI automation for deploying and managing Red Hat OpenShift AI (RHOAI) use cases.

For architecture and developer docs see [`docs/README.md`](docs/README.md).

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.12 | `python3 --version` |
| `oc` CLI | Must be logged in to the target cluster (`oc login`) |
| OpenShift cluster | OCP 4.20+, ppc64le or x86_64 |

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
repo_root: /Users/varad/Desktop/repos/ai-demos/openshift-ai-demos

operator:
  channel: stable-3.5

# DSC components to enable during platform setup.
components:
  - dashboard
  - workbenches
  - kserve
  - trustyai

storage:
  class_name: ""   # empty = accept any available ReadWriteOnce class

deployment:
  namespace: test-fraud
  trustyai_service_name: trustyai-service
  trustyai_service_account: trustyai-user

  models:
    - name: demo-loan-nn-onnx-alpha
      model_uri: pvc://fraud-model-pvc/bias-monitoring/unbiased_model
      inference_request: automation/rhoai/usecases/inputs/demo-loan.json

    - name: demo-loan-nn-onnx-beta
      model_uri: pvc://fraud-model-pvc/bias-monitoring/biased_model
      inference_request: automation/rhoai/usecases/inputs/demo-loan.json

```

### `models`

Each entry under `deployment.models` defines one independent model deployment:

| Field | Required | Description |
|---|---|---|
| `name` | ✔ | Kubernetes resource name for the `InferenceService` and `ServingRuntime` |
| `model_uri` | ✔ | Where the model is loaded from (see below) |
| `inference_request` | ✔ | Path to a KServe v2 JSON payload used for post-deploy validation, relative to `repo_root` |

Multiple entries deploy multiple models in sequence, each with its own `ServingRuntime` and `InferenceService`.
This is used for bias monitoring workflows where a baseline and a candidate model run side by side.

### `model_uri` formats

| Format | Example | Notes |
|---|---|---|
| `pvc://<claim>/<path>` | `pvc://fraud-model-pvc/models` | Model pre-loaded on a PersistentVolumeClaim |

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
rhoai usecase deploy fraud-detection -c openshift-ai-demos/automation/config-fraud-detection.yaml
```

Checks the RHOAI platform (configuring it if needed), then for each configured model:
deploys a dedicated Triton `ServingRuntime` and `InferenceService`, waits until Ready,
and validates that the model is serving inference requests.

```
Deploying : fraud-detection
Namespace : test-fraud
Models    : 2

Checking RHOAI platform...

  ✔  Operator ready
  ✔  DSCI 'default-dsci' ready
  ✔  DSC 'default-dsc' ready
  ✔  Components enabled: Dashboard, Workbenches, KServe, TrustyAI

✔  Platform ready  (5s)

Deploying 'demo-loan-nn-onnx-alpha'...

✔  Configuring Triton ServingRuntime  (6s)
✔  Deploying service 'demo-loan-nn-onnx-alpha'  (21s)
✔  Validating model inference  (1s)

✔  'demo-loan-nn-onnx-alpha' ready  (30s)

Deploying 'demo-loan-nn-onnx-beta'...

✔  Configuring Triton ServingRuntime  (6s)
✔  Deploying service 'demo-loan-nn-onnx-beta'  (10s)
✔  Validating model inference  (1s)

✔  'demo-loan-nn-onnx-beta' ready  (19s)

Deployment complete.

  Use case  : fraud-detection
  Namespace : test-fraud

Models

✔  demo-loan-nn-onnx-alpha

  Source      : pvc://fraud-model-pvc/bias-monitoring/unbiased_model
  Status      : Ready
  Validation  : Passed

✔  demo-loan-nn-onnx-beta

  Source      : pvc://fraud-model-pvc/bias-monitoring/biased_model
  Status      : Ready
  Validation  : Passed

Next

  rhoai usecase verify fraud-detection \
    -c openshift-ai-demos/automation/config-fraud-detection.yaml
```

If the endpoint is unreachable from the machine running the CLI (for example, a local
workstation that cannot resolve the cluster's `.apps` route), inference validation is
marked **Unavailable** and the deployment is still considered successful.
The `Follow-up actions` section lists the affected models and the exact command to rerun
once the endpoint is reachable:

```
Follow-up actions

⚠  demo-loan-nn-onnx-alpha

  Endpoint:
    https://demo-loan-nn-onnx-alpha-test-fraud.apps.rdr-varad-421.ocp-rhoai.com/v2/models/demo-loan-nn-onnx-alpha/infer

  Model inference could not be validated because the endpoint
  was not reachable from this machine.

  Verify the cluster route is reachable from your workstation.

  If hostname resolution fails, check your DNS or /etc/hosts configuration.

  Then rerun:

    rhoai usecase verify fraud-detection \
      -c openshift-ai-demos/automation/config-fraud-detection.yaml

Next

  rhoai usecase verify fraud-detection \
    -c openshift-ai-demos/automation/config-fraud-detection.yaml
```

### Verify

```bash
rhoai usecase verify fraud-detection -c openshift-ai-demos/automation/config-fraud-detection.yaml
```

Checks the platform, confirms each `InferenceService` is Ready, and runs a live inference
request for each configured model using its `inference_request` payload.

### Cleanup

```bash
rhoai usecase cleanup fraud-detection -c openshift-ai-demos/automation/config-fraud-detection.yaml
```

Removes each model's `InferenceService` and its dedicated `ServingRuntime`.
Pass `--delete-platform` to also remove the DSC and DSCI.

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
> Default is `INFO` (structured output only). Use `DEBUG` for full log output, including
> inference endpoint URLs and curl reproduction commands for failed validation.

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
