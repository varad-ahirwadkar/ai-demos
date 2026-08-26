# Fraud Detection

A use case that deploys one or more fraud-detection models on the **Triton**
serving runtime, each fronted by a KServe `InferenceService`, with **optional
TrustyAI bias monitoring**. For the generic use-case lifecycle and shared
concepts, see the [use-case index](../README.md).

## Contents

- [When should I use this?](#when-should-i-use-this)
- [Architecture](#architecture)
- [Configuration reference](#configuration-reference)
  - [Model configuration](#model-configuration)
  - [Providing the model](#providing-the-model)
  - [Inference input modes](#inference-input-modes)
  - [TrustyAI configuration](#trustyai-configuration)
- [Deployment walkthrough](#deployment-walkthrough)
- [Verification](#verification)
- [Cleanup](#cleanup)
- [Troubleshooting](#troubleshooting)

---

## When should I use this?

Use this to stand up a **predictive fraud-detection model** on OpenShift AI and,
optionally, demonstrate **fairness monitoring** — for example running a biased
and an unbiased model side by side and comparing their Statistical Parity
Difference (SPD) over time.

**Prerequisites**

- The framework installed and `oc` logged in to a cluster — see the
  [main README](../../../README.md#quick-start).
- Cluster-admin permissions (needed to install the operator, and — for TrustyAI
  — to write to the `openshift-monitoring` namespace).
- **Compute:** each model deployment requests **2 CPU / 8 GiB** on a worker
  node. Confirm capacity with `rhoai platform inspect`.
- A model, either as local files or already staged on a PVC — see
  [Providing the model](#providing-the-model).

**Typical workflow**

```bash
rhoai usecase deploy  fraud-detection -c config-fraud-detection.yaml   # deploy + smoke test
rhoai usecase verify  fraud-detection -c config-fraud-detection.yaml   # re-check health
rhoai usecase cleanup fraud-detection -c config-fraud-detection.yaml   # tear down
```

Two ready-to-use config files are provided:

| Config file | When to use |
|---|---|
| [`config-fraud-detection.yaml`](../../../config-fraud-detection.yaml) | Model serving only — no TrustyAI |
| [`config-fraud-detection-trustyai.yaml`](../../../config-fraud-detection-trustyai.yaml) | Model serving **+** TrustyAI bias monitoring (biased and unbiased models side by side) |

---

## Architecture

Each model in the config becomes an independent deployment: its own Triton
`ServingRuntime` and a KServe `InferenceService` in front of it. Multiple models
deploy in sequence, which is what enables the biased/unbiased side-by-side demo.

```
config.yaml (deployment.models[])
      │
      ▼
 per model:  ServingRuntime (triton-<name>)  ──►  InferenceService (<name>)  ──►  smoke test
      │
      └─ optional: TrustyAIService (one per namespace) ──► observations ──► SPD / identity monitors
```

Models are served from a PVC. KServe mounts the PVC at `/mnt/models` and Triton
loads the model from the standard repository layout:

```
<claim> (PVC root)
└── <name>/           ← the InferenceService / model name
    ├── config.pbtxt  ← Triton model configuration
    └── 1/
        └── model.onnx
```

---

## Configuration reference

Config keys for this use case live under `deployment:` in your YAML file.
Platform-level keys (`operator`, `components`, `storage`, `timeouts`) and how
config is merged are covered in
[Configuration](../../../docs/README.md#5-configuration). A minimal example:

```yaml
# config-fraud-detection.yaml
repo_root: /absolute/path/to/openshift-ai-demos   # must be absolute — ~ is not expanded

operator:
  channel: stable-3.5

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

### Model configuration

Each entry under `deployment.models` defines one independent model deployment:

| Field | Required | Description |
|---|---|---|
| `name` | ✔ | Kubernetes resource name for the `InferenceService` and `ServingRuntime` |
| `model_uri` | ✦ | Reference a model **already staged** on a PVC — see [`model_uri` formats](#model_uri-formats) |
| `model_path` + `config_path` | ✦ | Local model file + Triton `config.pbtxt`; the framework creates the PVC and stages the Triton layout for you |
| `pvc_name` | | Local-staging only — PVC to create/reuse (defaults to `<name>-pvc`) |
| `pvc_size` | | Local-staging only — PVC size (defaults to `1Gi`) |
| `inference_request` | ✱ | Path to a pre-built KServe v2 JSON payload used for post-deploy validation, relative to `repo_root` |
| `inference_dataset` | ✱ | Path to a raw CSV/JSON dataset the framework generates requests from, relative to `repo_root` |
| `bias_monitoring` | | TrustyAI bias monitoring config — see [TrustyAI configuration](#trustyai-configuration) |

> **✦ Model source** — supply **either** `model_uri` **or** both `model_path`
> and `config_path` (mutually exclusive) — see [Providing the model](#providing-the-model).
>
> **✱ Inference input** — supply **exactly one** of `inference_request` or
> `inference_dataset` — see [Inference input modes](#inference-input-modes).

Multiple entries deploy multiple models in sequence, each with its own
`ServingRuntime` and `InferenceService` — use this to run biased and unbiased
models side by side for a comparative fairness demonstration.

#### `model_uri` formats

| Format | Example | Notes |
|---|---|---|
| `pvc://<claim>/<path>` | `pvc://fraud-model-pvc/bias-monitoring/unbiased_model` | Model pre-loaded on a PersistentVolumeClaim |

> `pvc://` is the scheme used by the shipped configs. Other schemes are defined
> in [`rhoai/config/defaults.yaml`](../../config/defaults.yaml) but are not yet
> validated end-to-end — use `pvc://` for all current deployments.

### Providing the model

There are two ways to supply the model.

**Option A — local files (recommended): `model_path` + `config_path`.** Point at
a local model file and its `config.pbtxt`, and the framework does the rest — it
validates the artifacts, **creates the PVC** (`pvc_name`, default `<name>-pvc`;
`pvc_size`, default `1Gi`), and **stages the Triton layout** for you. No manual
PVC steps.

```yaml
deployment:
  models:
    - name: upi-fraud-detection
      model_path:  /abs/path/to/model.onnx
      config_path: /abs/path/to/config.pbtxt
      pvc_size:    5Gi                          # optional
```

**Option B — pre-staged PVC: `model_uri: pvc://<claim>/<path>`.** Use this when
the model already lives on a PVC in the workload namespace; the framework only
references it, so you must create and populate the PVC **before** `deploy`:

```bash
# 1. Create the PVC
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
oc cp config.pbtxt test-fraud/model-loader:/mnt/models/upi-fraud-detection/config.pbtxt
oc cp model.onnx   test-fraud/model-loader:/mnt/models/upi-fraud-detection/1/model.onnx

# 4. Remove the loader pod
oc delete pod model-loader -n test-fraud
```

> For Option B, the PVC name, path, and namespace must match your config. Run
> `oc get pvc -n test-fraud` and confirm `STATUS = Bound` before deploying.

### Inference input modes

Each model supplies its inference input in exactly one of two mutually exclusive
modes (validated before any cluster call):

| Mode | Key | Smoke test | Observations (TrustyAI) |
|---|---|---|---|
| **JSON** | `inference_request` | The file is used as-is | Declared explicitly under `bias_monitoring.observations.path`/`.files` |
| **Dataset** | `inference_dataset` | First request generated from the dataset | Generated from the same dataset, batched by `bias_monitoring.observations.batch_size` |

**JSON mode** — `inference_request` points at a pre-built KServe v2 JSON payload
(or a CSV converted with the model's schema). Use it when you already have a
request file and want to declare observation files separately.

#### Dataset-driven inference

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

### TrustyAI configuration

`bias_monitoring` is an optional block on each model entry. When present on any
model, the deploy sequence is extended to set up TrustyAI for that model. For the
underlying TrustyAI concepts and a manual walkthrough, see
[`docs/bias-readme.md`](../../../docs/bias-readme.md).

To enable bias monitoring:

- Add `trustyai` to the `components` list.
- Add a `bias_monitoring` block to each model you want monitored.
- Set `trustyai_service_name` / `trustyai_service_account` at the `deployment:`
  level (one TrustyAI service is shared across all models in the namespace).

```yaml
# config-fraud-detection-trustyai.yaml (excerpt) — see the file for the full example
deployment:
  namespace: test-fraud
  trustyai_service_name:    trustyai-service   # default
  trustyai_service_account: trustyai-user      # default

  models:
    - name: demo-loan-nn-onnx-alpha
      model_uri: pvc://fraud-model-pvc/bias-monitoring/unbiased_model
      inference_request: automation/rhoai/usecases/fraud_detection/inputs/demo-loan.json
      bias_monitoring:
        observations:
          path: automation/rhoai/usecases/fraud_detection/inputs/training/data
        name_mapping:
          inputs:  { customer_data_input-3: "Is Male-Identifying?" }
          outputs: { predict: "Will Default?" }
        spd_monitors:
          - protected_attribute: "Is Male-Identifying?"
            privileged_value:    1.0
            unprivileged_value:  0.0
            outcome_name:        "Will Default?"
            favorable_outcome:   0.0
            batch_size:          5000
```

| Key | Purpose |
|---|---|
| `observations` | Baseline data sent to TrustyAI during deploy. **JSON mode:** `path` (a directory of `*.json` in lexical order) or an explicit `files` list, each a KServe v2 request. **Dataset mode:** generated from `inference_dataset` — set `observations.batch_size` instead (see [Inference input modes](#inference-input-modes)). Sent automatically; no separate script. |
| `name_mapping` | Renames opaque tensor columns to human-readable labels before monitors are scheduled, so `spd_monitors`/`identity_monitors` can reference readable names. |
| `spd_monitors` | Each entry schedules a recurring Statistical Parity Difference computation for one protected attribute. |
| `identity_monitors` | Optional (not in the shipped configs). Each entry tracks the column-average value of one named column over time. |
| `trustyai_service_name` | `TrustyAIService` resource name (default `trustyai-service`). |
| `trustyai_service_account` | ServiceAccount created for TrustyAI RBAC (default `trustyai-user`). |

**Observing fairness metrics** — after a TrustyAI deploy, the summary's
**Next steps** block prints a link to the OpenShift console metrics browser
(*Observe → Metrics*). Query `trustyai_spd` (statistical parity difference); set
a 5-minute window and 15-second refresh, and refresh the page if metrics have
not appeared yet. (`trustyai_identity` is also available if you add
`identity_monitors`.)

---

## Deployment walkthrough

```bash
rhoai usecase deploy fraud-detection -c config-fraud-detection.yaml
```

Checks the RHOAI platform (bootstrapping it if needed), deploys the Triton
`ServingRuntime` and `InferenceService` for each configured model, then
smoke-tests each model.

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

Models
✔  upi-fraud-detection
  Endpoint    : https://upi-fraud-detection-test-fraud.apps.<cluster>
  Validation  : Passed
```

If the endpoint is unreachable from the machine running the CLI (for example, a
workstation that cannot resolve the cluster's `.apps` route), inference
validation is marked **Unavailable**, the deploy is still considered successful,
and a `Follow-up actions` block prints the exact `verify` command to rerun once
the endpoint is reachable. See [Troubleshooting](#troubleshooting).

### With TrustyAI

When any model has `bias_monitoring` configured, the deploy sequence is extended
after all models are running:

1. Deploy each model (`ServingRuntime` + `InferenceService`)
2. Enable user-workload monitoring
3. Deploy `TrustyAIService`, wait for `Ready`
4. Send observations (from the dataset or the declared files), wait for ingestion
5. Apply name mapping (if configured)
6. Schedule SPD and identity monitors (if configured)

```bash
rhoai usecase deploy fraud-detection -c config-fraud-detection-trustyai.yaml
```

---

## Verification

```bash
rhoai usecase verify fraud-detection -c config-fraud-detection.yaml
```

Checks the platform, confirms each `InferenceService` is Ready, and runs a live
inference request for each model. With a TrustyAI config, `verify` additionally
confirms that TrustyAI has observations recorded (count > 0) for each monitored
model.

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

Models
✔  upi-fraud-detection
  Endpoint    : https://upi-fraud-detection-test-fraud.apps.<cluster>
  Validation  : Passed
```

---

## Cleanup

```bash
# Remove use-case resources only
rhoai usecase cleanup fraud-detection -c config-fraud-detection.yaml

# Remove use-case resources AND platform (DSC + DSCI)
rhoai usecase cleanup fraud-detection -c config-fraud-detection.yaml --delete-platform
```

Removes the `InferenceService` and `ServingRuntime` for each model in reverse
deploy order. Pass `--delete-platform` to also remove the DataScienceCluster and
DSCInitialization. When TrustyAI was deployed, cleanup adds a dedicated removal
phase (TrustyAI service, KServe logger restore, CA bundle, RBAC) after the models
are gone.

**Sample output:**
```
Removing   : fraud-detection
Namespace  : test-fraud

Removing model serving...
✔  Removing inference service 'upi-fraud-detection'  (1s)
✔  Waiting for inference service pods to terminate  (0s)
✔  Removing serving runtime 'triton-upi-fraud-detection'  (0s)
✔  Model serving removed  (1s)

Cleanup complete.  Total: 1s

Removed
  ✔  upi-fraud-detection
```

---

## Troubleshooting

Common issues specific to this use case. For platform-wide problems (operator
install, timeouts, `rhoai: command not found`), see the
[framework troubleshooting guide](../../../docs/troubleshooting.md).

| Symptom | Cause / fix |
|---|---|
| Validation shows **Unavailable** after deploy | The endpoint isn't reachable from your machine. Add the ingress IP to `/etc/hosts` and rerun `rhoai usecase verify fraud-detection -c <config>` — see [troubleshooting guide](../../../docs/troubleshooting.md). |
| `InferenceService` stays `Unknown` | `model_uri` PVC not `Bound`, path wrong, or `kserve` not enabled. Check `oc get pvc -n <namespace>` and `rhoai platform status`. |
| Config rejected before any cluster call | An invalid input-mode combination — see the rejected combinations under [Inference input modes](#inference-input-modes). |
| TrustyAI pod stays `Pending` | `trustyai` component not enabled, or no matching storage class. Run `rhoai platform enable trustyai`. |
| Ingestion never reaches the expected count | Raise `timeouts.ingestion_ready` on slow clusters — see the [troubleshooting guide](../../../docs/troubleshooting.md). |
