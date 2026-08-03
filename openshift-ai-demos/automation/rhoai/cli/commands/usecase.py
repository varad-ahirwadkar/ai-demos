"""Use case commands — rhoai usecase <name> <subcommand>.

    rhoai usecase deploy   <name>   deploy the named use case
    rhoai usecase verify  <name>   verify the deployment
    rhoai usecase cleanup <name>   remove use-case resources
    rhoai usecase list             show all registered use cases
"""

from pathlib import Path

import typer

from rhoai.config.loader import load_config
from rhoai.usecases import registry
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
    registry.get(name).deploy(config)


@app.command()
def verify(
    name: str = typer.Argument(..., help="Use case name, e.g. 'fraud-detection'."),
    config_file: Path | None = _config_option,
) -> None:
    """Verify the named use case deployment."""
    config = load_config(config_file)
    registry.get(name).verify(config)


@app.command()
def cleanup(
    name: str = typer.Argument(..., help="Use case name, e.g. 'fraud-detection'."),
    config_file: Path | None = _config_option,
    delete_platform: bool = typer.Option(
        False,
        "--delete-platform",
        help="Also remove DSC and DSCI. Use with caution.",
    ),
) -> None:
    """Remove the named use case resources."""
    config = load_config(config_file)
    registry.get(name).cleanup(config, delete_platform=delete_platform)


@app.command(name="list")
def list_cmd() -> None:
    """List all registered use case names."""
    for name in registry.list_available():
        typer.echo(f"  {name}")
