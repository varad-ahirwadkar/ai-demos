# rhoai usecases

A use case is a self-contained solution built on top of the [platform layer](../platform/README.md). Each use case defines its own `deploy` /
`verify` / `cleanup` lifecycle and is managed through `rhoai usecase`.

`deploy` ensures the required RHOAI platform components are available, automatically bootstrapping the platform when needed. Deploying to a fresh cluster is therefore a supported workflow.

This page is an index. To prepare the required assets, configure, and deploy a specific use case, follow the corresponding guide in [Available use cases](#available-use-cases).

---

## Lifecycle

Every use case follows the same three-step lifecycle:

| Step | Command |
|---|---|
| 1. Deploy | `rhoai usecase deploy <name> -c config.yaml` |
| 2. Verify | `rhoai usecase verify <name> -c config.yaml` |
| 3. Clean up | `rhoai usecase cleanup <name> -c config.yaml` |

---

## Available use cases

| Name | Description | Documentation |
|---|---|---|
| `fraud-detection` | Triton-served fraud-detection model with optional TrustyAI bias monitoring | [Fraud Detection guide](fraud_detection/README.md) |

---

## Common configuration concepts

Every use case uses a YAML configuration file passed with --config (or -c). Settings from the command line override your config file, which overrides the built-in defaults.

Configuration is split into two layers:

| Layer | Purpose | Shared across use cases? |
|---|---|---|
| **Platform** | Platform settings such as `repo_root`, operator, components, storage, and timeouts | Yes |
| **Deployment** | Use case specific settings, such as namespaces, models, and other deployment options | No |

`repo_root` must be an **absolute** path to the `openshift-ai-demos` directory.
Each use case guide documents the deployment settings it supports.

---

## Adding a new use case

A use case is a package under `rhoai/usecases/<name>/` exposing `deploy` /
`verify` / `cleanup`, plus an `assets.py` and one entry in `registry.py`.
