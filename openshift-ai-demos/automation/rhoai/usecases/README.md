# rhoai usecases

A **use case** is a self-contained, customer-facing solution built on top of
the [platform layer](../platform/README.md) — each one owns a `deploy` /
`verify` / `cleanup` sequence and is invoked through `rhoai usecase`.

`deploy` checks whether the RHOAI platform is already in the desired state and
bootstraps it if needed — running it against a completely fresh cluster is
expected to work end to end.

This page is an **index**. For how to configure and run a specific use case,
follow the link in [Available use cases](#available-use-cases).

---

## Lifecycle

Every use case follows the same three-step lifecycle:

| Step | Command |
|---|---|
| 1. Deploy | `rhoai usecase deploy <name> -c config.yaml` |
| 2. Verify | `rhoai usecase verify <name> -c config.yaml` |
| 3. Clean up | `rhoai usecase cleanup <name> -c config.yaml` |

Optional features such as TrustyAI bias monitoring extend the behavior of each
step through configuration — they do not introduce a separate workflow. Use
`rhoai usecase list` to see everything registered on your install.

---

## Available use cases

| Name | Description | Documentation |
|---|---|---|
| `fraud-detection` | Triton-served fraud-detection model with optional TrustyAI bias monitoring | [Fraud Detection guide](fraud_detection/README.md) |

---

## Common configuration concepts

Every use case is driven by a YAML config passed with `--config`/`-c`. Values
are deep-merged from CLI flags → `--config` file → bundled defaults; a config
file only needs the keys it overrides. Full details:
[Configuration](../../docs/README.md#5-configuration).

Config is split into two layers:

| Layer | Keys | Shared across use cases? |
|---|---|---|
| **Platform** | `repo_root`, `operator`, `components`, `storage`, `timeouts` | Yes — same meaning everywhere |
| **Deployment** | everything under `deployment:` (e.g. `namespace`, `models`) | No — each use case defines its own schema, documented in its own guide |

`repo_root` must be an **absolute** path to the `openshift-ai-demos` directory
(`~` is not expanded). Everything a use case applies is resolved relative to it.

---

## Adding a new use case

A use case is a package under `rhoai/usecases/<name>/` exposing `deploy` /
`verify` / `cleanup`, plus an `assets.py` and one entry in `registry.py`. For the
internal structure and a worked template, see
[Adding a New Use Case](../../docs/README.md#10-adding-a-new-use-case). When you
add one, give it a `README.md` in its directory and link it from the
[Available use cases](#available-use-cases) table above.
