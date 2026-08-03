"""Platform commands — rhoai platform <subcommand>.

    rhoai platform prepare   validate cluster, install operator, configure DSC
    rhoai platform verify    check platform health
    rhoai platform analyze   display cluster info without modifying anything
"""

from pathlib import Path

import typer

from rhoai.config.loader import load_config
from rhoai.platform import dsc, manifests, operators, prepare
from rhoai.platform import verify as platform_verify
from rhoai.utils.logger import get_logger

_MANAGED_MARKER = "✔"

app = typer.Typer(help="Manage the RHOAI platform.")
log = get_logger(__name__)

_config_option = typer.Option(None, "--config", "-c", help="Path to config YAML.")


@app.command(name="prepare")
def prepare_cmd(
    config_file: Path | None = _config_option,
) -> None:
    """Validate prerequisites, install the operator, and configure DSC."""
    config = load_config(config_file)
    repo_root = config["repo_root"]
    op_name    = config["operator"]["name"]
    op_ns      = config["operator"]["namespace"]
    op_timeout = config["timeouts"]["operator_ready"]
    prepare.prepare_platform(config)
    if not operators.is_installed(op_name, op_ns):
        operators.install(op_name, op_ns, config["operator"]["channel"], repo_root, op_timeout)
    else:
        operators.wait_until_ready(op_name, op_ns, op_timeout)
    dsc.apply_dsci(manifests.get_dsci(repo_root))
    dsc.apply_dsc(manifests.get_dsc(repo_root))
    dsc.wait_until_ready(config["dsc"]["name"], config["timeouts"]["dsc_ready"])
    typer.echo("Platform is ready.")


@app.command()
def verify(
    config_file: Path | None = _config_option,
) -> None:
    """Check the health of the RHOAI platform and print a component summary."""
    config  = load_config(config_file)
    op_name = config["operator"]["name"]
    op_ns   = config["operator"]["namespace"]
    results = platform_verify.verify_platform(config)

    # --- Operator summary ---
    try:
        csv = operators.get_csv_info(op_name, op_ns)
        typer.echo(f"\nOperator  : {csv['name']}  (version {csv['version']}, {csv['phase']})")
    except Exception:  # noqa: BLE001
        typer.echo(f"\nOperator  : {op_name}  (info unavailable)")

    # --- DSC component summary (enabled only) ---
    try:
        states  = dsc.get_component_states(config["dsc"]["name"])
        enabled = {c: s for c, s in states.items() if s not in ("Removed", "Unknown")}
        typer.echo("\nDSC Components (enabled):")
        if enabled:
            for comp, state in sorted(enabled.items()):
                typer.echo(f"  {_MANAGED_MARKER} {comp:<22} {state}")
        else:
            typer.echo("  (none)")
    except Exception:  # noqa: BLE001
        typer.echo("\nDSC Components: (info unavailable)")

    # --- Check results ---
    typer.echo("\nChecks:")
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        line = f"  [{status}] {r.name}"
        if r.message:
            line += f" — {r.message}"
        typer.echo(line)

    if any(not r.passed for r in results):
        raise typer.Exit(code=1)


@app.command()
def analyze(
    config_file: Path | None = _config_option,
) -> None:
    """Display cluster information without modifying anything."""
    info = prepare.get_cluster_info()
    typer.echo(f"OpenShift version : {info['openshift_version']}")
    typer.echo(f"Topology          : {info['topology']}")
    typer.echo(f"Nodes (total)     : {info['node_count']}")
    typer.echo(f"Nodes (worker)    : {info['worker_count']}")

    typer.echo("\nWorker nodes:")
    for node in info["worker_nodes"]:
        gpu_str = f"  GPU {node['gpu']}" if node["gpu"] else ""
        typer.echo(f"  {node['name']:<45} CPU {node['cpu']:<12} Mem {node['memory']}{gpu_str}")

    typer.echo("\nStorage classes:")
    if info["storage_summary"]:
        for sc, s in sorted(info["storage_summary"].items()):
            typer.echo(f"  {sc:<40} used {s['used']}")
    else:
        typer.echo("  (none)")
