"""CLI entry point — rhoai-automation.

Registers command groups:
    rhoai platform ...
    rhoai usecase  ...

Declared as the console script in pyproject.toml:
    [project.scripts]
    rhoai = "cli.main:app"
"""

import typer

from rhoai.cli.commands import platform as platform_cmd
from rhoai.cli.commands import usecase as usecase_cmd
from rhoai.utils import logger

app = typer.Typer(
    name="rhoai",
    help="rhoai-automation — deploy and manage Red Hat OpenShift AI use cases.",
    no_args_is_help=True,
)

app.add_typer(platform_cmd.app, name="platform")
app.add_typer(usecase_cmd.app,  name="usecase")


@app.callback()
def _callback(
    log_level: str = typer.Option("INFO", "--log-level", "-l", help="DEBUG, INFO, WARNING, ERROR."),
) -> None:
    logger.configure(level=log_level)


if __name__ == "__main__":
    app()
