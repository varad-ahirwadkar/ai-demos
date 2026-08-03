# rhoai-automation

A CLI-first automation framework for installing Red Hat OpenShift AI (RHOAI)
and deploying RHOAI use cases on OpenShift clusters — validate the cluster,
install the operator, configure the platform, and deploy a working use case
with a handful of commands instead of a manual, multi-step procedure.

- For architecture and developer docs, see [`docs/README.md`](docs/README.md).
- For platform commands (`rhoai platform ...`), see [`rhoai/platform/README.md`](rhoai/platform/README.md).
- For use cases (`rhoai usecase ...`), see [`rhoai/usecases/README.md`](rhoai/usecases/README.md).

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

Every command accepts `--config`/`-c` at the subcommand level, pointing to a
YAML file. Without it, the bundled defaults in
[`rhoai/config/defaults.yaml`](rhoai/config/defaults.yaml) apply.

Configuration is assembled from three sources, merged in priority order:

```
1. CLI flags                      (highest priority — this run only, never written to disk)
       ↓
2. --config file / RHOAI_ env vars
       ↓
3. rhoai/config/defaults.yaml     (bundled defaults)
```

### Environment variable overrides

| Variable | Config key | Description |
|---|---|---|
| `RHOAI_KUBECONFIG` | `platform.kubeconfig` | Path to kubeconfig (defaults to `~/.kube/config`) |
| `RHOAI_REPO_ROOT` | `repo_root` | Absolute path to the `openshift-ai-demos` repo root |
| `RHOAI_LOG_LEVEL` | `log_level` | `DEBUG`, `INFO` |
| `RHOAI_CONFIG` | — | Path to a config YAML file (replaces `--config`) |

### Minimal config file

```yaml
# my-cluster.yaml
repo_root: /path/to/ai-demos/openshift-ai-demos   # absolute path to the repo root

operator:
  channel: stable-3.x

components:              # DSC components 'rhoai platform setup' should enable
  - dashboard
  - workbenches
  - kserve
  - trustyai
```

See [`rhoai/platform/README.md`](rhoai/platform/README.md#configuration) for
the full set of defaults and every available config key.

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

## CLI usage

All commands accept `--config`/`-c` at the subcommand level to specify a
config file. Log verbosity is set with `--log-level`/`-l` on the root
command, **before** the subcommand.

```bash
rhoai --help
rhoai platform --help
rhoai usecase  --help
```

---

## Logging

Commands run in quiet mode by default — only the structured summary output
(the boxes and tables you see above) is printed.

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

