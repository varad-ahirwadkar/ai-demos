# rhoai-automation

A CLI-first automation framework for installing Red Hat OpenShift AI (RHOAI)
and deploying RHOAI use cases on OpenShift clusters — validate the cluster,
install the operator, configure the platform, and deploy a working use case
with a handful of commands instead of a manual, multi-step procedure.

- For architecture and developer docs, see [`docs/README.md`](docs/README.md).
- For platform commands (`rhoai platform ...`), see [`rhoai/platform/README.md`](rhoai/platform/README.md).
- For use cases (`rhoai usecase ...`), see [`rhoai/usecases/README.md`](rhoai/usecases/README.md).

---

## Quick Start

> **Prerequisite:** Python ≥ 3.12, `oc` CLI, and an active `oc login` session.

```bash
# 1. Install
git clone https://github.com/IBM/ai-demos.git && cd ai-demos
git checkout rhoai-automation
python3 -m venv .venv && source .venv/bin/activate
pip install -e openshift-ai-demos/automation

# 2. Copy the example config and update my-config.yaml
cp openshift-ai-demos/automation/config-fraud-detection.yaml my-config.yaml

# 3. Deploy, verify, and clean up
rhoai usecase deploy  fraud-detection -c my-config.yaml
rhoai usecase verify  fraud-detection -c my-config.yaml
rhoai usecase cleanup fraud-detection -c my-config.yaml
```

For the full lifecycle including TrustyAI bias monitoring, use
[`config-fraud-detection-trustyai.yaml`](config-fraud-detection-trustyai.yaml) instead.
See [`rhoai/usecases/README.md`](rhoai/usecases/README.md) for the complete workflow.

---

## Prerequisites

| Requirement | Notes |
|---|---|
| Python ≥ 3.12 | `python3 --version` |
| `oc` CLI | Must be logged in to the target cluster (`oc login <cluster-url>`) |
| OpenShift cluster | OCP 4.20+, ppc64le or x86_64 |
| Cluster-admin permissions | Required to install the RHOAI operator |

---

## Installation

```bash
cd openshift-ai-demos/automation

python3 -m venv .venv
source .venv/bin/activate

pip install -e .          # add "[dev]" instead if you'll be running tests

rhoai --help
```

---

## Configuration

### The normal workflow — use a config file

Pass a YAML config file with `--config`/`-c` on any subcommand.
Only override what differs from the bundled defaults — everything else is
inherited from [`rhoai/config/defaults.yaml`](rhoai/config/defaults.yaml).

```bash
rhoai usecase deploy fraud-detection --config config-fraud-detection.yaml
```

A minimal config file looks like this:

```yaml
repo_root: /absolute/path/to/openshift-ai-demos   # must be absolute — ~ is not expanded

platform:
  namespace: redhat-ods-applications   # where RHOAI operands run

deployment:
  namespace: my-workload-namespace
```

### How configuration is resolved

Values are merged from three sources in priority order (highest → lowest):

| Priority | Source | When to use |
|---|---|---|
| 1 | CLI flags (e.g. `--channel`) | One-off overrides for a single run |
| 2 | `--config` file | Per-cluster or per-environment settings |
| 3 | `rhoai/config/defaults.yaml` | Bundled fallback — no action needed |

> **Tip:** For kubeconfig, use the standard `KUBECONFIG` environment variable
> or run `oc login` before invoking `rhoai`.

---

## CLI usage

Log verbosity is set with `--log-level`/`-l` on the root command, **before**
the subcommand. All other options are on the subcommand itself.

```bash
rhoai --help
rhoai platform --help
rhoai usecase  --help
```

---

## `rhoai platform`

Installs and manages the RHOAI platform itself: operator, DSCInitialization,
DataScienceCluster components, health, and uninstall.

| Command | Purpose |
|---|---|
| `rhoai platform init` | Install operator + initialize DSCI |
| `rhoai platform enable` / `disable` | Enable / disable DSC components |
| `rhoai platform setup` | One-shot bootstrap (init + components) |
| `rhoai platform status` | Report platform health |
| `rhoai platform inspect` | Display cluster info (read-only) |
| `rhoai platform uninstall` | Remove all RHOAI platform resources |

```bash
# One-shot bootstrap
rhoai platform setup --config my-cluster.yaml

# Or step by step
rhoai platform init   --config my-cluster.yaml --channel stable-3.x
rhoai platform enable kserve trustyai --config my-cluster.yaml
rhoai platform status --config my-cluster.yaml
```

Full command reference, channel/version discovery, component list, and
uninstall behavior: **[`rhoai/platform/README.md`](rhoai/platform/README.md)**.

---

## `rhoai usecase`

Deploys customer-facing solutions built on top of the platform layer — each
use case is a self-contained `deploy` / `verify` / `cleanup` sequence.

| Command | Description |
|---|---|
| `rhoai usecase list` | List all registered use cases |
| `rhoai usecase deploy <name>` | Deploy a use case end-to-end, bootstrapping the platform if needed |
| `rhoai usecase verify <name>` | Check that all use-case resources are healthy |
| `rhoai usecase cleanup <name>` | Remove use-case resources (`--delete-platform` to also remove DSC/DSCI) |

```bash
rhoai usecase deploy fraud-detection --config config-fraud-detection.yaml
rhoai usecase verify fraud-detection --config config-fraud-detection.yaml
```

Worked example, sample output, and config reference for the Fraud Detection
use case: **[`rhoai/usecases/README.md`](rhoai/usecases/README.md)**.

---

## Logging

Commands run in quiet mode by default — only the structured summary output
is printed.

```bash
# Normal output — structured summary only
rhoai platform init --channel stable-3.x

# Full log stream — useful when debugging a failure
rhoai --log-level DEBUG platform init --channel stable-3.x
```

`--log-level` accepts `DEBUG`, `INFO`, and must come
immediately after `rhoai`, before the subcommand.

---

## Timeout defaults

| Operation | Default |
|---|---|
| Operator ready | 300s |
| DSC ready | 600s |
| InferenceService ready | 120s |
| TrustyAI ready | 300s |

Override under the `timeouts:` key in your config file.

## Testing

The test suite requires no live cluster — all Kubernetes API calls are
mocked.

```bash
pytest                                       # full suite
pytest -v                                    # verbose
pytest tests/unit/platform/test_prepare.py   # a single file
ruff check rhoai/                            # lint
```

See [`docs/README.md`](docs/README.md) for test layout and
conventions.

---

## Troubleshooting

### `rhoai: command not found`

**Cause:** The virtual environment is not activated or the package is not installed.

**Fix:**
```bash
source openshift-ai-demos/automation/.venv/bin/activate
pip install -e openshift-ai-demos/automation
```

---

### `FileNotFoundError` or `No such file or directory` on a manifest path

**Cause:** `repo_root` in the config file is wrong, relative, or uses a `~` shortcut.

**Fix:** Set `repo_root` to the **absolute** path of the `openshift-ai-demos` directory.
The `~` shortcut is not expanded — use the full path:

```yaml
# Wrong
repo_root: ~/repos/openshift-ai-demos

# Correct
repo_root: /home/user/repos/openshift-ai-demos
```

---

### OLM error: `ConstraintsNotSatisfiable`

**Cause:** An invalid OLM channel name was passed to `rhoai platform init`.

**Fix:** List valid channels, then retry with a channel from that list:

```bash
oc get packagemanifest rhods-operator \
  -o jsonpath='{.status.channels[*].name}'

rhoai platform init --channel stable-3.x   # use a channel from the list above
```

---

### `InferenceService` stays `Unknown` after deploy

**Cause:** The model storage URI is unreachable, the PVC does not exist, or the
`kserve` DSC component is not enabled.

**Fix:**
```bash
rhoai platform status                     # confirm kserve is listed under Components
oc get pvc -n <namespace>                 # confirm the PVC exists and is Bound
rhoai --log-level DEBUG usecase deploy fraud-detection -c my-config.yaml
```

---

### TrustyAI pod stays `Pending`

**Cause:** The `trustyai` component is not enabled in the DataScienceCluster, or
no matching storage class is available.

**Fix:**
```bash
rhoai platform enable trustyai            # enable the component
rhoai platform status                     # confirm trustyai appears under Components
oc get pvc -n <namespace>                 # confirm PVC bound
```

---

### Inference endpoint returns `503` during `verify`

**Cause:** The pod is not yet ready, or the cluster route is not reachable from
this machine.

**Fix:** Wait for the pod, then re-run verify. If the hostname does not resolve,
add it to `/etc/hosts` as shown in the deploy output:

```bash
rhoai usecase verify fraud-detection -c my-config.yaml
```

---

### Namespace stuck in `Terminating` after `uninstall`

**Cause:** Stale finalizers prevent the namespace from completing deletion.

**Fix:** `rhoai platform uninstall` handles this automatically. If the namespace
was deleted by other means, run:

```bash
rhoai platform uninstall -y               # automated finalizer cleanup is built in
```

---

### Any command fails with no obvious error message

**Cause:** Default quiet mode suppresses log output.

**Fix:** Re-run with `--log-level DEBUG` immediately after `rhoai`:

```bash
rhoai --log-level DEBUG usecase deploy fraud-detection -c my-config.yaml
rhoai --log-level DEBUG platform status
```
---

