# rhoai usecases

A **use case** is a self-contained, customer-facing solution built on top of
the [platform layer](../platform/README.md) — each one owns a `deploy` /
`verify` / `cleanup` sequence and is invoked through `rhoai usecase`.

```bash
rhoai usecase list
rhoai usecase deploy  <name> [-c CONFIG]
rhoai usecase verify  <name> [-c CONFIG]
rhoai usecase cleanup <name> [-c CONFIG] [--delete-platform]
```

`deploy` checks whether the RHOAI platform is already in the desired state
and bootstraps it if needed — running it against a completely fresh cluster
is expected to work end to end.

For the internal structure of a use case package (`assets.py` / `deploy.py`
/ `verify.py` / `cleanup.py`) and how to add a new one, see
[`docs/README.md`](../../docs/README.md#10-adding-a-new-use-case).

---

## Available use cases

| Name | Description |
|---|---|
| `fraud-detection` | Triton-served fraud detection model |

---

## Fraud Detection

Deploys a fraud-detection model on the Triton serving runtime, with a
KServe `InferenceService` in front of it.

A ready-to-use example is at [`config-fraud-detection.yaml`](../../config-fraud-detection.yaml).

### Configuration

Config keys for this use case live under `deployment:` in your YAML file.
The most common overrides:
```yaml
# config-fraud-detection.yaml
repo_root: /path/to/ai-demos/openshift-ai-demos

operator:
  channel: stable-3.x

components:
  - dashboard
  - workbenches
  - kserve
  - trustyai

deployment:
  namespace: test-fraud
  models:
    - name: demo-loan-nn-onnx-alpha
      model_uri: pvc://fraud-model-pvc/bias-monitoring/unbiased_model
      inference_request: automation/rhoai/usecases/inputs/demo-loan.json

    - name: demo-loan-nn-onnx-beta
      model_uri: pvc://fraud-model-pvc/bias-monitoring/biased_model
      inference_request: automation/rhoai/usecases/inputs/demo-loan.json
```

#### `models`

Each entry under `deployment.models` defines one independent model deployment:

| Field | Required | Description |
|---|---|---|
| `name` | ✔ | Kubernetes resource name for the `InferenceService` and `ServingRuntime` |
| `model_uri` | ✔ | Where the model is loaded from (see below) |
| `inference_request` | ✔ | Path to a KServe v2 JSON payload used for post-deploy validation, relative to `repo_root` |

Multiple entries deploy multiple models in sequence, each with its own `ServingRuntime` and `InferenceService`.
This is used for bias monitoring workflows where a baseline and a candidate model run side by side.

#### `model_uri` formats

| Format | Example | Notes |
|---|---|---|
| `pvc://<claim>/<path>` | `pvc://fraud-model-pvc/models` | Model pre-loaded on a PersistentVolumeClaim |


### Deploy

```bash
rhoai usecase deploy fraud-detection -c openshift-ai-demos/automation/config-fraud-detection.yaml
```

Checks the RHOAI platform (bootstrapping it if needed), deploys the Triton
`ServingRuntime` and `InferenceService`, applies TrustyAI monitoring, and
validates that the model is serving inference requests.

**Sample output:**
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
  Endpoint    : https://demo-loan-nn-onnx-alpha-test-fraud.apps.rdr-varad-421.ocp-rhoai.com
  Status      : Ready
  Validation  : Passed

✔  demo-loan-nn-onnx-beta

  Source      : pvc://fraud-model-pvc/bias-monitoring/biased_model
  Endpoint    : https://demo-loan-nn-onnx-beta-test-fraud.apps.rdr-varad-421.ocp-rhoai.com
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
# Remove use-case resources only
rhoai usecase cleanup fraud-detection -c openshift-ai-demos/automation/config-fraud-detection.yaml

# Remove use-case resources AND platform (DSC + DSCI)
rhoai usecase cleanup fraud-detection -c openshift-ai-demos/automation/config-fraud-detection.yaml --delete-platform
```
Removes the `InferenceService` and `ServingRuntime` in reverse deploy order.

---

## Logging

Same as every other command — quiet by default, full trace with
`--log-level DEBUG` before the subcommand:

```bash
rhoai --log-level DEBUG usecase deploy fraud-detection -c openshift-ai-demos/automation/config-fraud-detection.yaml
```

See the [top-level README](../../README.md#logging) for details.
