"""Use case commands — rhoai usecase <name> <subcommand>.

    rhoai usecase deploy   <name>   deploy the named use case
    rhoai usecase verify  <name>   verify the deployment
    rhoai usecase cleanup <name>   remove use-case resources
    rhoai usecase list             show all registered use cases
"""

from pathlib import Path

import typer

from rhoai.config.loader import load_config
from rhoai.platform import inference
from rhoai.usecases import registry
from rhoai.utils.errors import friendly_error
from rhoai.utils.logger import get_logger

app = typer.Typer(help="Deploy and manage AI use cases.")
log = get_logger(__name__)

_config_option = typer.Option(None, "--config", "-c", help="Path to config YAML.")


@app.command()
def deploy(
    name: str = typer.Argument(..., help="Use case name, e.g. 'fraud-detection'."),
    config_file: Path | None = _config_option,
) -> None:
    """Deploy the named use case."""
    config = load_config(config_file)
    try:
        registry.get(name).deploy(config)
    except Exception as exc:  # noqa: BLE001
        _exit_with_error(exc)
    _print_deploy_summary(name, config)


@app.command()
def verify(
    name: str = typer.Argument(..., help="Use case name, e.g. 'fraud-detection'."),
    config_file: Path | None = _config_option,
) -> None:
    """Verify the named use case deployment."""
    config = load_config(config_file)
    try:
        registry.get(name).verify(config)
    except Exception as exc:  # noqa: BLE001
        _exit_with_error(exc)
    typer.echo(f"\n  ✔  {name}  verification passed.")


@app.command()
def cleanup(
    name: str = typer.Argument(..., help="Use case name, e.g. 'fraud-detection'."),
    config_file: Path | None = _config_option,
    delete_platform: bool = typer.Option(
        False,
        "--delete-platform",
        help="Also remove DSC and DSCI after use-case cleanup. Use with caution.",
    ),
) -> None:
    """Remove the named use case resources."""
    from rhoai.platform import dsc

    config = load_config(config_file)
    try:
        registry.get(name).cleanup(config)
        if delete_platform:
            log.warning("Deleting platform resources (DSC, DSCI)")
            dsc.delete_dsc(config["dsc"]["name"])
            dsc.delete_dsci(config["dsc"]["dsci_name"])
    except Exception as exc:  # noqa: BLE001
        _exit_with_error(exc)


@app.command(name="list")
def list_cmd() -> None:
    """List all registered use case names."""
    for name in registry.list_available():
        typer.echo(f"  {name}")


def _print_deploy_summary(name: str, config: dict) -> None:
    """Print a concise post-deployment summary to stdout.

    Resolves the InferenceService endpoint from the cluster. If the URL
    lookup fails for any reason the summary is still printed without it —
    the deployment itself succeeded.
    """
    dep_cfg   = config.get("deployment", {})
    namespace = dep_cfg.get("namespace") or config["platform"]["namespace"]
    isvc_name = dep_cfg.get("inference_service_name", name)

    url = ""
    try:
        url = inference.get_inference_url(isvc_name, namespace)
    except Exception:  # noqa: BLE001
        pass  # URL unavailable — don't fail the summary

    typer.echo(f"\n  Use case:   {name}")
    typer.echo(f"  Namespace:  {namespace}")
    if url:
        typer.echo(f"  Endpoint:   {url}")
    typer.echo(f"  Next:       rhoai usecase verify {name}")


def _exit_with_error(exc: Exception) -> None:
    """Print a clean one-line error and exit 1. Never shows a traceback."""
    typer.echo(f"\nError: {friendly_error(exc)}", err=True)
    raise typer.Exit(code=1)
