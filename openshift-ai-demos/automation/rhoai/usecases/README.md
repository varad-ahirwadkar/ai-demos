# rhoai usecases

A **use case** is a self-contained, customer-facing solution built on top of
the [platform layer](../platform/README.md) — each one owns a `deploy` /
`verify` / `cleanup` sequence and is invoked through `rhoai usecase`.

`deploy` checks whether the RHOAI platform is already in the desired state
and bootstraps it if needed — running it against a completely fresh cluster
is expected to work end to end.

For the internal structure of a use case package (`assets.py` / `deploy.py`
/ `verify.py` / `cleanup.py`) and how to add a new one, see
[`docs/README.md`](../../docs/README.md#10-adding-a-new-use-case).

---

## Workflow

Every use case follows the same three-step lifecycle:

| Step | Command |
|---|---|
| 1. Deploy | `rhoai usecase deploy <name> -c config.yaml` |
| 2. Verify | `rhoai usecase verify <name> -c config.yaml` |
| 3. Clean up | `rhoai usecase cleanup <name> -c config.yaml` |

Optional features such as TrustyAI bias monitoring extend the behavior of
each step through configuration — they do not introduce a separate workflow.

---

## Available use cases

| Name | Description |
|---|---|
| `fraud-detection` | Triton-served fraud detection model with optional TrustyAI bias monitoring |

---

## Fraud Detection

Deploys one or more fraud-detection models on the Triton serving runtime, with a
KServe `InferenceService` in front of each one.

Two ready-to-use config files are provided:

| Config file | When to use |
|---|---|
| [`config-fraud-detection.yaml`](../../config-fraud-detection.yaml) | Model serving only — no TrustyAI |
| [`config-fraud-detection-trustyai.yaml`](../../config-fraud-detection-trustyai.yaml) | Model serving **+** TrustyAI bias monitoring (biased and unbiased models side by side) |

---

### Configuration

Config keys for this use case live under `deployment:` in your YAML file.
The most common overrides:

```yaml
# config-fraud-detection.yaml
repo_root: /absolute/path/to/openshift-ai-demos   # must be absolute — ~ is not expanded

operator:
  channel: stable-3.x

components:
  - dashboard
  - workbenches
  - kserve

deployment:
  namespace: test-fraud
  models:
    - name: upi-fraud-detection
      model_uri: pvc://fraud-model-pvc/upi-fraud-detection
      inference_request: automation/rhoai/usecases/fraud_detection/inputs/upi-fraud-detection.json
```

#### `models`

Each entry under `deployment.models` defines one independent model deployment:

| Field | Required | Description |
|---|---|---|
| `name` | ✔ | Kubernetes resource name for the `InferenceService` and `ServingRuntime` |
| `model_uri` | ✔ | Where the model is loaded from (see formats below) |
| `inference_request` | ✱ | Path to a pre-built KServe v2 JSON payload used for post-deploy validation, relative to `repo_root` |
| `inference_dataset` | ✱ | Path to a raw CSV/JSON dataset the framework generates requests from, relative to `repo_root` |
| `bias_monitoring` | | TrustyAI bias monitoring config — see [`bias_monitoring`](#bias_monitoring) below |

> ✱ Supply **exactly one** of `inference_request` or `inference_dataset` — see
> [Inference input modes](#inference-input-modes).

Multiple entries deploy multiple models in sequence, each with its own `ServingRuntime`
and `InferenceService`. Use this when running biased and unbiased models side by side
for a comparative fairness demonstration.

#### `model_uri` formats

Currently supported:

| Format | Example | Notes |
|---|---|---|
| `pvc://<claim>/<path>` | `pvc://fraud-model-pvc/bias-monitoring/unbiased_model` | Model pre-loaded on a PersistentVolumeClaim |

> Additional URI schemes (`hf://`, `oci://`, S3) are listed in
> [`rhoai/config/defaults.yaml`](../config/defaults.yaml) but are not yet
> validated end-to-end. Use `pvc://` for all current deployments.

#### Inference input modes

Each model supplies its inference input in exactly one of two mutually exclusive
modes (validated before any cluster call):

| Mode | Key | Smoke test | Observations (TrustyAI) |
|---|---|---|---|
| **JSON** | `inference_request` | The file is used as-is | Declared explicitly under `bias_monitoring.observations.path`/`.files` |
| **Dataset** | `inference_dataset` | First request generated from the dataset | Generated from the same dataset, batched by `bias_monitoring.observations.batch_size` |

**JSON mode** — `inference_request` points at a pre-built KServe v2 JSON payload
(or a CSV converted with the model's schema). Use it when you already have a
request file and want to declare observation files separately.

**Dataset mode** — `inference_dataset` points at a raw CSV/JSON dataset that
becomes the single source of truth. The smoke-test request is the first
generated request, and TrustyAI observations are generated from the whole
dataset, batched by `bias_monitoring.observations.batch_size` (default `1`).
Dataset mode requires a Triton `config.pbtxt` via `inference_config_path` (or
`config_path`) for the request schema, and you must **not** also set
`bias_monitoring.observations.path`/`.files`.

```yaml
# Dataset mode (excerpt) — see config-fraud-detection-trustyai.yaml
deployment:
  models:
    - name: demo-loan-nn-onnx-alpha
      model_path:  /abs/path/model.onnx
      config_path: /abs/path/config.pbtxt      # also used as the request schema
      inference_dataset: automation/rhoai/usecases/fraud_detection/inputs/training/csv/batch_01.csv
      bias_monitoring:
        observations:
          batch_size: 250                        # observations per generated request
```

Rejected (fail-fast) combinations:

- `inference_request` **and** `inference_dataset` together (ambiguous mode).
- Neither set (no input source).
- `inference_dataset` **with** `observations.path`/`.files` (dataset already supplies observations).
- `inference_request` **with** `observations.batch_size` (batching applies only to dataset mode).
- `inference_dataset` without a `config.pbtxt` schema source.

#### `bias_monitoring`

`bias_monitoring` is an optional block on each model entry. When present on any
model, the deploy sequence is extended to set up TrustyAI for that model.

To enable bias monitoring:

- Add `trustyai` to the `components` list.
- Add a `bias_monitoring` block to each model you want monitored.
- Set `trustyai_service_name` and `trustyai_service_account` at the `deployment:`
  level (see [TrustyAI service settings](#trustyai-service-settings) below).

One TrustyAI service is shared across all models in the namespace; `bias_monitoring`
configuration is per model.

```yaml
# config-fraud-detection-trustyai.yaml (excerpt)
repo_root: /absolute/path/to/openshift-ai-demos   # must be absolute — ~ is not expanded

components:
  - dashboard
  - workbenches
  - kserve
  - trustyai          # required for bias monitoring

deployment:
  namespace: test-fraud

  models:
    - name: demo-loan-nn-onnx-alpha
      model_uri: pvc://fraud-model-pvc/bias-monitoring/unbiased_model
      inference_request: automation/rhoai/usecases/fraud_detection/inputs/demo-loan.json

      bias_monitoring:
        # Observation files sent to TrustyAI during deploy for baseline fairness.
        # Specify a directory (all *.json files in lexical order) or an explicit list.
        observations:
          path: automation/rhoai/usecases/fraud_detection/inputs/training/data

        # Rename opaque tensor column names to human-readable labels.
        name_mapping:
          inputs:
            customer_data_input-0:  "Number of Children"
            customer_data_input-3:  "Is Male-Identifying?"
            # ... see full example in config-fraud-detection-trustyai.yaml
          outputs:
            predict: "Will Default?"

        # SPD monitors — Statistical Parity Difference, computed at a recurring interval.
        spd_monitors:
          - protected_attribute:  "Is Male-Identifying?"
            privileged_value:     1.0
            unprivileged_value:   0.0
            outcome_name:         "Will Default?"
            favorable_outcome:    0.0
            batch_size:           5000

        # Identity monitors — track column-average values over time.
        identity_monitors:
          - column_name: "Is Male-Identifying?"
            batch_size:  250
          - column_name: "Will Default?"
            batch_size:  250
```

See [`config-fraud-detection-trustyai.yaml`](../../config-fraud-detection-trustyai.yaml)
for the complete example with both models fully configured.

**`observations`** — used in **JSON mode**: `path` relative to `repo_root` (a
directory loads all `*.json` files in lexical order; an explicit list of file
paths is also accepted). Each file must be a KServe v2 inference request. In
**dataset mode** observations are generated from `inference_dataset` instead —
set `observations.batch_size` rather than `path`/`files` (see
[Inference input modes](#inference-input-modes)). Observations (training data)
are sent automatically during `deploy` — no separate script is needed.

**`name_mapping`** — renames opaque tensor column names to human-readable labels
before monitors are scheduled, so that `spd_monitors` and `identity_monitors` can
reference the readable names.

**`spd_monitors`** — each entry schedules a recurring Statistical Parity Difference
computation for one protected attribute.

**`identity_monitors`** — each entry tracks the column-average value of one named
column over time.

#### TrustyAI service settings

These keys live at `deployment:` level (not per-model) because one TrustyAI service
is shared across all models in the namespace:

| Key | Default | Description |
|---|---|---|
| `trustyai_service_name` | `trustyai-service` | Name of the `TrustyAIService` resource |
| `trustyai_service_account` | `trustyai-user` | ServiceAccount created for TrustyAI RBAC |

```yaml
deployment:
  namespace: test-fraud
  trustyai_service_name:    trustyai-service
  trustyai_service_account: trustyai-user
```

---

### Prerequisites

**Compute:** Each model deployment requests 2 CPU and 8 GiB of memory on a worker
node. Confirm available capacity before deploying:

```bash
rhoai platform inspect   # shows worker node CPU and memory
```

**Model files on a PVC:** The model files must be present on a PersistentVolumeClaim
(PVC) in the workload namespace **before** running `deploy`. The CLI does not create
or populate the PVC.

The `model_uri` field in your config determines the PVC name and the path inside it.
For `pvc://<claim>/<path>`, KServe mounts the PVC at `/mnt/models` and Triton loads
the model at `<path>` within it. That directory must follow Triton's model repository
layout:

```
<claim> (PVC root)
└── <path>/           ← the path segment from model_uri
    ├── config.pbtxt  ← Triton model configuration
    └── 1/
        └── model.onnx
```

**Example** — for `model_uri: pvc://fraud-model-pvc/upi-fraud-detection`:

```bash
# 1. Create the PVC in the workload namespace
cat <<EOF | oc apply -f -
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: fraud-model-pvc
  namespace: test-fraud
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 5Gi
EOF

# 2. Attach a temporary pod to the PVC
oc run model-loader -n test-fraud --restart=Never \
  --image=registry.access.redhat.com/ubi9/python-312:latest \
  --overrides='{
    "spec":{
      "containers":[{"name":"model-loader",
        "image":"registry.access.redhat.com/ubi9/python-312:latest",
        "command":["sleep","3600"],
        "volumeMounts":[{"mountPath":"/mnt/models","name":"models"}]}],
      "volumes":[{"name":"models","persistentVolumeClaim":{"claimName":"fraud-model-pvc"}}]
    }}'

oc wait --for=condition=Ready pod/model-loader -n test-fraud --timeout=120s

# 3. Create the directory structure and copy the model files
oc exec model-loader -n test-fraud -- mkdir -p /mnt/models/upi-fraud-detection/1
oc cp config.pbtxt    test-fraud/model-loader:/mnt/models/upi-fraud-detection/config.pbtxt
oc cp model.onnx      test-fraud/model-loader:/mnt/models/upi-fraud-detection/1/model.onnx

# 4. Remove the loader pod
oc delete pod model-loader -n test-fraud
```

> The PVC name, path, and namespace must match what is in your config file.
> Run `oc get pvc -n test-fraud` and confirm `STATUS = Bound` before deploying.

**TrustyAI — additional permission required:** when `bias_monitoring` is configured
on any model, the deploy sequence writes to the `openshift-monitoring` namespace.
This requires cluster-admin or a role with write access to that namespace. The same
cluster-admin permission used to install the operator is sufficient.

---

### Deploy

```bash
rhoai usecase deploy fraud-detection -c /absolute/path/to/config-fraud-detection.yaml
```

Checks the RHOAI platform (bootstrapping it if needed), deploys the Triton
`ServingRuntime` and `InferenceService` for each configured model, then
validates that each model is serving inference requests.

**Sample output:**
```
Deploying  : fraud-detection
Namespace  : test-fraud


Checking RHOAI platform...

  ✔  Operator ready
  ✔  DSCInitialization ready
  ✔  DataScienceCluster ready
  ✔  Components enabled: Dashboard, Workbenches, KServe

✔  Platform ready  (3s)

Deploying 'upi-fraud-detection'...

✔  Ensuring serving runtime  (6s)
✔  Ensuring inference service  (0s)
✔  Smoke-testing model endpoint  (1s)

✔  'upi-fraud-detection' ready  (8s)

Deployment complete.  Total: 12s

  Use case   : fraud-detection
  Namespace  : test-fraud

Models

✔  upi-fraud-detection
  Endpoint    : https://upi-fraud-detection-test-fraud.apps.rdr-varad-421.ocp-rhoai.com
  Validation  : Passed

Next steps

  Test a model endpoint

    # upi-fraud-detection
    curl -sk -X POST https://upi-fraud-detection-test-fraud.apps.rdr-varad-421.ocp-rhoai.com/v2/models/upi-fraud-detection/infer \
      -H 'Content-Type: application/json' \
      -d @<path-to-request.json>

```

If the endpoint is unreachable from the machine running the CLI (for example, a local
workstation that cannot resolve the cluster's `.apps` route), inference validation is
marked **Unavailable** and the deployment is still considered successful.
The `Follow-up actions` section lists the affected models and the exact command to rerun
once the endpoint is reachable:

```
Follow-up actions

⚠  upi-fraud-detection

  Endpoint:
    https://upi-fraud-detection-test-fraud.apps.<cluster>/v2/models/upi-fraud-detection/infer

  Model inference could not be validated because the endpoint
  was not reachable from this machine.

  Verify the cluster route is reachable from your workstation.

  If hostname resolution fails, check your DNS or /etc/hosts configuration.

  Then rerun:

    rhoai usecase verify fraud-detection \
      -c /absolute/path/to/config-fraud-detection.yaml

Next

  rhoai usecase verify fraud-detection \
    -c /absolute/path/to/config-fraud-detection.yaml
```

#### With TrustyAI

When any model has `bias_monitoring` configured, the deploy sequence is extended
after all models are running:

1. Platform bootstrap (same as the base deploy, with `trustyai` in the components list)
2. Deploy each model (`ServingRuntime` + `InferenceService`)
3. Enable user-workload monitoring
4. Deploy `TrustyAIService`, wait for `Ready`
5. Send observations from `bias_monitoring.observations.path` to TrustyAI, wait for ingestion
6. Apply name mapping (if configured)
7. Schedule SPD and identity monitors (if configured)

Observations are sent automatically from the files on disk — no separate manual
script step is needed.

```bash
rhoai usecase deploy fraud-detection -c /absolute/path/to/config-fraud-detection-trustyai.yaml
```

---

### Verify

```bash
rhoai usecase verify fraud-detection -c /absolute/path/to/config-fraud-detection.yaml
```

Checks the platform, confirms each `InferenceService` is Ready, and runs a live inference
request for each configured model using its `inference_request` payload.

**Sample output:**
```
Verifying  : fraud-detection
Namespace  : test-fraud

✔  Checking RHOAI platform  (2s)

Verifying 'upi-fraud-detection'...

✔  Checking inference service  (0s)
✔  Checking model inference  (1s)

✔  'upi-fraud-detection' healthy  (1s)

Verification complete.  Total: 4s

  Use case   : fraud-detection
  Namespace  : test-fraud

Models

✔  upi-fraud-detection
  Endpoint    : https://upi-fraud-detection-test-fraud.apps.rdr-varad-421.ocp-rhoai.com
  Validation  : Passed

Next steps

  Test a model endpoint

    # upi-fraud-detection
    curl -sk -X POST https://upi-fraud-detection-test-fraud.apps.rdr-varad-421.ocp-rhoai.com/v2/models/upi-fraud-detection/infer \
      -H 'Content-Type: application/json' \
      -d @<path-to-request.json>
```

#### With TrustyAI

```bash
rhoai usecase verify fraud-detection -c /absolute/path/to/config-fraud-detection-trustyai.yaml
```

In addition to the standard model checks, `verify` also confirms that TrustyAI
has observations recorded (count > 0) for each model that has `bias_monitoring`
configured.

---

### Observe fairness metrics

> **TrustyAI only** — this section applies when `bias_monitoring` is configured
> and `rhoai usecase deploy` has completed successfully.

After deploy completes, the **Next steps** block of the summary prints direct
links to the OpenShift console metrics browser:

```
Next steps

  Check metrics in the OpenShift console

    https://console-openshift-console.apps.<cluster>/monitoring/query-browser

    Navigate to Observe → Metrics in the OpenShift console.
    If you just deployed, refresh the page before the new metrics appear.
    Set the time window to 5 minutes (top left)
    and the refresh interval to 15 seconds (top right).
    Enter one of the expressions below in the Expression field:

      trustyai_spd       — statistical parity difference
      trustyai_identity  — identity metrics
```

---

### Cleanup

```bash
# Remove use-case resources only
rhoai usecase cleanup fraud-detection -c /absolute/path/to/config-fraud-detection.yaml

# Remove use-case resources AND platform (DSC + DSCI)
rhoai usecase cleanup fraud-detection -c /absolute/path/to/config-fraud-detection.yaml --delete-platform
```

Removes the `InferenceService` and `ServingRuntime` for each model in reverse deploy order.
Pass `--delete-platform` to also remove the DataScienceCluster and DSCInitialization.

**Sample output:**
```

Removing   : fraud-detection
Namespace  : test-fraud


Removing model serving...

✔  Removing inference service 'upi-fraud-detection'  (1s)
✔  Waiting for inference service pods to terminate  (0s)
✔  Removing serving runtime 'triton-upi-fraud-detection'  (0s)
✔  Waiting for serving runtime pods to terminate  (0s)

✔  Model serving removed  (1s)

Cleanup complete.  Total: 1s

  Use case   : fraud-detection
  Namespace  : test-fraud

Removed

  ✔  upi-fraud-detection
```

#### With TrustyAI

```bash
rhoai usecase cleanup fraud-detection -c /absolute/path/to/config-fraud-detection-trustyai.yaml
```

When TrustyAI was deployed, cleanup adds a dedicated removal phase after the models
are gone:

```
Removing TrustyAI...

  ✔  Removing TrustyAI service  (8s)
  ✔  Restoring KServe logger configuration  (1s)
  ✔  Removing logger CA bundle  (1s)
  ✔  Removing RBAC  (1s)

✔  TrustyAI removed  (11s)

Cleanup complete.

  Use case   : fraud-detection
  Namespace  : test-fraud

Removed

  ✔  <model(s)>
  ✔  TrustyAI
```
