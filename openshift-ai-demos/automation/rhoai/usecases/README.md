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

## Workflow

Every use case follows the same lifecycle. Steps 3–4 apply only when
TrustyAI bias monitoring is configured.

| Step | Command / Action | Required |
|---|---|---|
| 1. Deploy | `rhoai usecase deploy <name> -c config.yaml` | ✔ |
| 2. Verify | `rhoai usecase verify <name> -c config.yaml` | ✔ |
| 3. Observe TrustyAI metrics | OpenShift Console → Observe → Metrics → `trustyai_spd` | TrustyAI only |
| 4. Clean up | `rhoai usecase cleanup <name> -c config.yaml` | ✔ |

**Observations** (training data sent to TrustyAI for baseline fairness) are
sent automatically during `deploy` when `bias_monitoring.observations` is
configured — no separate script is needed.

---

## Available use cases

| Name | Description |
|---|---|
| `fraud-detection` | Triton-served fraud detection model with optional TrustyAI bias monitoring |

---

## Fraud Detection

Deploys a fraud-detection model on the Triton serving runtime, with a
KServe `InferenceService` in front of it.

Two ready-to-use config files are provided:

| Config file | When to use |
|---|---|
| [`config-fraud-detection.yaml`](../../config-fraud-detection.yaml) | Model serving only — no TrustyAI |
| [`config-fraud-detection-trustyai.yaml`](../../config-fraud-detection-trustyai.yaml) | Model serving **+** TrustyAI bias monitoring |

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
    - name: demo-loan-nn-onnx-alpha
      model_uri: pvc://fraud-model-pvc/bias-monitoring/unbiased_model
      inference_request: automation/rhoai/usecases/fraud_detection/inputs/demo-loan.json

    - name: demo-loan-nn-onnx-beta
      model_uri: pvc://fraud-model-pvc/bias-monitoring/biased_model
      inference_request: automation/rhoai/usecases/fraud_detection/inputs/demo-loan.json
```

#### `models`

Each entry under `deployment.models` defines one independent model deployment:

| Field | Required | Description |
|---|---|---|
| `name` | ✔ | Kubernetes resource name for the `InferenceService` and `ServingRuntime` |
| `model_uri` | ✔ | Where the model is loaded from (see formats below) |
| `inference_request` | ✔ | Path to a KServe v2 JSON payload used for post-deploy validation, relative to `repo_root` |
| `bias_monitoring` | | TrustyAI bias monitoring config — see [TrustyAI section](#fraud-detection--trustyai-bias-monitoring) |

Multiple entries deploy multiple models in sequence, each with its own `ServingRuntime` and `InferenceService`.
This is used for bias monitoring workflows where a baseline and a candidate model run side by side.

#### `model_uri` formats

Currently supported:

| Format | Example | Notes |
|---|---|---|
| `pvc://<claim>/<path>` | `pvc://fraud-model-pvc/bias-monitoring/unbiased_model` | Model pre-loaded on a PersistentVolumeClaim |

> Additional URI schemes (`hf://`, `oci://`, S3) are listed in
> [`rhoai/config/defaults.yaml`](../config/defaults.yaml) but are not yet
> validated end-to-end. Use `pvc://` for all current deployments.

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
Checking RHOAI platform...

  ✔  Operator ready
  ✔  DSCI 'default-dsci' ready
  ✔  DSC 'default-dsc' ready
  ✔  Components enabled: Dashboard, Workbenches, KServe

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

Deployment complete.  Total: 1m 2s

  Use case   : fraud-detection
  Namespace  : test-fraud

Models

✔  demo-loan-nn-onnx-alpha

  Source      : pvc://fraud-model-pvc/bias-monitoring/unbiased_model
  Endpoint    : https://demo-loan-nn-onnx-alpha-test-fraud.apps.<cluster>
  Status      : Ready
  Validation  : Passed

✔  demo-loan-nn-onnx-beta

  Source      : pvc://fraud-model-pvc/bias-monitoring/biased_model
  Endpoint    : https://demo-loan-nn-onnx-beta-test-fraud.apps.<cluster>
  Status      : Ready
  Validation  : Passed

Next

  rhoai usecase verify fraud-detection \
      -c /absolute/path/to/config-fraud-detection.yaml
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
    https://demo-loan-nn-onnx-alpha-test-fraud.apps.<cluster>/v2/models/demo-loan-nn-onnx-alpha/infer

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

---

### Verify

```bash
rhoai usecase verify fraud-detection -c /absolute/path/to/config-fraud-detection.yaml
```

Checks the platform, confirms each `InferenceService` is Ready, and runs a live inference
request for each configured model using its `inference_request` payload.

**Sample output:**
```
Verifying 'demo-loan-nn-onnx-alpha' (1/2)...

  ✔  Checking inference service  (1s)
  ✔  Checking model inference  (1s)

✔  'demo-loan-nn-onnx-alpha' healthy  (2s)

Verifying 'demo-loan-nn-onnx-beta' (2/2)...

  ✔  Checking inference service  (1s)
  ✔  Checking model inference  (1s)

✔  'demo-loan-nn-onnx-beta' healthy  (2s)

Verification complete.  Total: 7s

  Use case   : fraud-detection
  Namespace  : test-fraud

Models

✔  demo-loan-nn-onnx-alpha

  Endpoint    : https://demo-loan-nn-onnx-alpha-test-fraud.apps.<cluster>
  Validation  : Passed

✔  demo-loan-nn-onnx-beta

  Endpoint    : https://demo-loan-nn-onnx-beta-test-fraud.apps.<cluster>
  Validation  : Passed

Next steps

  Test a model endpoint

    # demo-loan-nn-onnx-alpha
    curl -sk -X POST https://demo-loan-nn-onnx-alpha-test-fraud.apps.<cluster>/v2/models/demo-loan-nn-onnx-alpha/infer \
      -H 'Content-Type: application/json' \
      -d @<path-to-request.json>
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
Removing model serving...

  ✔  Removing inference service 'demo-loan-nn-onnx-alpha'  (1s)
  ✔  Removing inference service 'demo-loan-nn-onnx-beta'  (1s)
  ✔  Waiting for inference service pods to terminate  (18s)
  ✔  Removing serving runtime 'demo-loan-nn-onnx-alpha-runtime'  (1s)
  ✔  Removing serving runtime 'demo-loan-nn-onnx-beta-runtime'  (1s)
  ✔  Waiting for serving runtime pods to terminate  (5s)

✔  Model serving removed  (26s)

Cleanup complete.  Total: 26s

  Use case   : fraud-detection
  Namespace  : test-fraud

Removed

  ✔  demo-loan-nn-onnx-alpha
  ✔  demo-loan-nn-onnx-beta
```

---

## Fraud Detection + TrustyAI Bias Monitoring

TrustyAI monitors deployed models for fairness metrics (Statistical Parity
Difference) and tracks column-average values over time (identity metrics).
The framework automates the full setup: TrustyAI Service deployment,
observation ingestion, name mapping, and metric scheduling.

Use [`config-fraud-detection-trustyai.yaml`](../../config-fraud-detection-trustyai.yaml)
to enable this workflow. It extends the base config with:

- `trustyai` added to the `components` list
- A `bias_monitoring` block for each model

### Configuration

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

### Deploy with TrustyAI

```bash
rhoai usecase deploy fraud-detection -c /absolute/path/to/config-fraud-detection-trustyai.yaml
```

The deploy sequence is extended when any model has `bias_monitoring` configured:

1. Platform bootstrap (same as the base deploy, with `trustyai` in the components list)
2. Deploy each model (`ServingRuntime` + `InferenceService`)
3. Enable user-workload monitoring
4. Deploy `TrustyAIService`, wait for `Ready`
5. Send observations from `bias_monitoring.observations.path` to TrustyAI, wait for ingestion
6. Apply name mapping (if configured)
7. Schedule SPD and identity monitors (if configured)

Observations are sent automatically from the files on disk — no separate manual
script step is needed.

### Verify with TrustyAI

```bash
rhoai usecase verify fraud-detection -c /absolute/path/to/config-fraud-detection-trustyai.yaml
```

In addition to the standard model checks, verify also confirms that TrustyAI
has observations recorded (count > 0) for each model that has `bias_monitoring`
configured.

### Observe fairness metrics

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

For background on what SPD values mean and how to interpret fairness results,
see [`docs/bias-readme.md`](../../docs/bias-readme.md).

### Cleanup with TrustyAI

```bash
rhoai usecase cleanup fraud-detection -c /absolute/path/to/config-fraud-detection-trustyai.yaml
```

When TrustyAI was deployed, cleanup removes it in a dedicated phase after the
models are gone:

**Sample output:**
```
Removing model serving...

  ✔  Removing inference service 'demo-loan-nn-onnx-alpha'  (1s)
  ✔  Removing inference service 'demo-loan-nn-onnx-beta'  (1s)
  ✔  Waiting for inference service pods to terminate  (18s)
  ✔  Removing serving runtime 'demo-loan-nn-onnx-alpha-runtime'  (1s)
  ✔  Removing serving runtime 'demo-loan-nn-onnx-beta-runtime'  (1s)
  ✔  Waiting for serving runtime pods to terminate  (5s)

✔  Model serving removed  (26s)

Removing TrustyAI...

  ✔  Removing TrustyAI service  (8s)
  ✔  Restoring KServe logger configuration  (1s)
  ✔  Removing logger CA bundle  (1s)
  ✔  Removing RBAC  (1s)

✔  TrustyAI removed  (11s)

Cleanup complete.  Total: 37s

  Use case   : fraud-detection
  Namespace  : test-fraud

Removed

  ✔  demo-loan-nn-onnx-alpha
  ✔  demo-loan-nn-onnx-beta
  ✔  TrustyAI
```

---

## Logging

Same as every other command — quiet by default, full trace with
`--log-level DEBUG` before the subcommand:

```bash
rhoai --log-level DEBUG usecase deploy fraud-detection -c /absolute/path/to/config-fraud-detection.yaml
```

See the [top-level README](../../README.md#logging) for details.
