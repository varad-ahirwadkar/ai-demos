"""Use case commands — rhoai usecase <name> <subcommand>.

    rhoai usecase deploy   <name>   deploy the named use case
    rhoai usecase verify  <name>   verify the deployment
    rhoai usecase cleanup <name>   remove use-case resources
    rhoai usecase list             show all registered use cases
"""

from pathlib import Path

import typer

from rhoai.config.loader import load_config
from rhoai.platform import inference, trustyai
from rhoai.usecases import registry
from rhoai.utils.errors import friendly_error
from rhoai.utils.logger import get_logger

app = typer.Typer(help="Deploy and manage AI use cases.")
log = get_logger(__name__)

_config_option = typer.Option(None, "--config", "-c", help="Path to config YAML.")
_name_argument = typer.Argument("fraud-detection", help="Use case name.")


@app.command()
def deploy(
    name: str = _name_argument,
    config_file: Path | None = _config_option,
) -> None:
    """Deploy the named use case."""
    config    = load_config(config_file)
    dep_cfg   = config.get("deployment", {})
    namespace = dep_cfg.get("namespace") or config["platform"]["namespace"]
    isvc_name = dep_cfg.get("inference_service_name", name)
    model_uri = dep_cfg.get("model_uri", "(from manifest)")

    typer.echo(f"\nDeploying : {name}")
    typer.echo(f"Namespace : {namespace}")
    typer.echo(f"Service   : {isvc_name}")
    typer.echo(f"Storage   : {model_uri}\n")

    try:
        registry.get(name).deploy(config)
    except Exception as exc:  # noqa: BLE001
        _exit_with_error(exc)
    _print_deploy_summary(name, config)


@app.command()
def verify(
    name: str = _name_argument,
    config_file: Path | None = _config_option,
) -> None:
    """Verify the named use case deployment."""
    config    = load_config(config_file)
    dep_cfg   = config.get("deployment", {})
    namespace = dep_cfg.get("namespace") or config["platform"]["namespace"]
    isvc_name = dep_cfg.get("inference_service_name", name)

    typer.echo(f"\nVerifying : {name}")
    typer.echo(f"Namespace : {namespace}\n")

    try:
        registry.get(name).verify(config)
    except Exception as exc:  # noqa: BLE001
        _exit_with_error(exc)
    _print_verify_summary(name, isvc_name, namespace, config)


@app.command()
def cleanup(
    name: str = _name_argument,
    config_file: Path | None = _config_option,
    delete_platform: bool = typer.Option(
        False,
        "--delete-platform",
        help="Also remove DSC and DSCI after use-case cleanup. Use with caution.",
    ),
) -> None:
    """Remove the named use case resources."""
    from rhoai.platform import dsc

    config    = load_config(config_file)
    dep_cfg   = config.get("deployment", {})
    namespace = dep_cfg.get("namespace") or config["platform"]["namespace"]

    typer.echo(f"\nRemoving  : {name}")
    typer.echo(f"Namespace : {namespace}\n")

    try:
        registry.get(name).cleanup(config)
        if delete_platform:
            log.warning("Deleting platform resources (DSC, DSCI)")
            dsc.delete_dsc(config["dsc"]["name"])
            dsc.delete_dsci(config["dsc"]["dsci_name"])
    except Exception as exc:  # noqa: BLE001
        _exit_with_error(exc)

    typer.echo(f"\n✔  {name}  removed.")


@app.command(name="list")
def list_cmd() -> None:
    """List all registered use case names."""
    for name in registry.list_available():
        typer.echo(f"  {name}")


def _print_deploy_summary(name: str, config: dict) -> None:
    """Print a concise post-deployment summary to stdout.

    Resolves the InferenceService and TrustyAI URLs from the cluster.
    URL lookups are best-effort — the summary is always printed even if
    the cluster is unreachable after a successful deploy.
    """
    dep_cfg       = config.get("deployment", {})
    namespace     = dep_cfg.get("namespace") or config["platform"]["namespace"]
    isvc_name     = dep_cfg.get("inference_service_name", name)
    trustyai_name = dep_cfg.get("trustyai_service_name", "trustyai-service")

    endpoint     = ""
    trustyai_url = ""
    try:
        endpoint = inference.get_inference_url(isvc_name, namespace)
    except Exception:  # noqa: BLE001
        pass
    try:
        trustyai_url = trustyai.get_trustyai_url(trustyai_name, namespace)
    except Exception:  # noqa: BLE001
        pass

    typer.echo("\nDeployment complete.\n")
    typer.echo(f"  Use case  : {name}")
    typer.echo(f"  Namespace : {namespace}")
    if endpoint:
        typer.echo(f"  Endpoint  : {endpoint}")
    if trustyai_url:
        typer.echo(f"  TrustyAI  : {trustyai_url}")
    typer.echo(f"\n  Next: rhoai usecase verify {name}")


def _print_verify_summary(name: str, isvc_name: str, namespace: str, config: dict) -> None:
    """Print a concise post-verification summary to stdout."""
    endpoint = ""
    try:
        endpoint = inference.get_inference_url(isvc_name, namespace)
    except Exception:  # noqa: BLE001
        pass

    typer.echo("\nVerification complete.\n")
    typer.echo(f"  Use case  : {name}")
    typer.echo(f"  Namespace : {namespace}")
    if endpoint:
        typer.echo(f"  Endpoint  : {endpoint}")
    typer.echo(f"\n✔  {name}  is healthy and serving inference requests.")


def _exit_with_error(exc: Exception) -> None:
    """Print a clean one-line error and exit 1. Never shows a traceback."""
    log.debug("Unhandled exception", exc_info=exc)
    typer.echo(f"\n✖  {friendly_error(exc)}", err=True)
    log.debug("Exception type: %s", type(exc).__name__)
    raise typer.Exit(code=1)
