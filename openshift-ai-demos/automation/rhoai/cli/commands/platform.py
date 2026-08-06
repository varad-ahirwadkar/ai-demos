"""Platform commands — rhoai platform <subcommand>.

    rhoai platform prepare   validate cluster, install operator, configure DSC
    rhoai platform status    report RHOAI platform health
    rhoai platform inspect   display factual cluster information (read-only)
"""

from pathlib import Path

import typer

from rhoai.config.loader import load_config
from rhoai.platform import dsc, operators, prepare
from rhoai.platform import verify as platform_verify
from rhoai.utils.logger import get_logger

app = typer.Typer(help="Manage the RHOAI platform.")
log = get_logger(__name__)

_config_option = typer.Option(None, "--config", "-c", help="Path to config YAML.")


@app.command(name="prepare")
def prepare_cmd(
    config_file: Path | None = _config_option,
) -> None:
    """Validate prerequisites, install the operator, and configure DSC."""
    config = load_config(config_file)
    prepare.deploy_platform(config)
    typer.echo("Platform is ready.")


@app.command()
def status(
    config_file: Path | None = _config_option,
) -> None:
    """Report the health of the installed RHOAI platform."""
    config  = load_config(config_file)
    op_name = config["operator"]["name"]
    op_ns   = config["operator"]["namespace"]
    dsc_name  = config["dsc"]["name"]
    dsci_name = config["dsc"]["dsci_name"]

    # Run all checks — never raises, always returns results
    results = platform_verify.verify_platform(config)
    op_result   = results[0]
    dsci_result = results[1]
    dsc_result  = results[2]

    # Determine whether downstream checks should be shown as skipped.
    # If the operator check failed, DSCI and DSC are not meaningful.
    op_failed = not op_result.passed

    # --- Resolve operator display string (name + version when available) ---
    op_display = op_name
    if op_result.passed:
        try:
            csv = operators.get_csv_info(op_name, op_ns)
            op_display = f"{csv['name']} {csv['version']}"
        except Exception:  # noqa: BLE001
            pass

    typer.echo("\nRHOAI Platform")
    typer.echo(_status_row("Operator",       op_display,  op_result))
    typer.echo(_status_row("Initialization", dsci_name,   dsci_result, skip=op_failed))
    typer.echo(_status_row("Cluster",        dsc_name,    dsc_result,  skip=op_failed))

    # --- DSC components (only when DSC is healthy) ---
    if dsc_result.passed:
        try:
            states  = dsc.get_component_states(dsc_name)
            managed = sorted(c for c, s in states.items() if s not in ("Removed", "Unknown"))
            if managed:
                typer.echo("\n  Components")
                for comp in managed:
                    typer.echo(f"    ✔  {comp}")
        except Exception:  # noqa: BLE001
            pass

    # --- Conclusion ---
    failed = [r for r in results if not r.passed]
    typer.echo("")
    if not failed:
        typer.echo("Platform is healthy.")
        return

    typer.echo("Platform is not healthy.", err=True)

    # Unique error reasons across failed checks
    reasons = dict.fromkeys(r.message for r in failed if r.message)
    if reasons:
        for reason in reasons:
            if "401" in reason or "Unauthorized" in reason:
                typer.echo(
                    f"Run 'oc login <cluster-url>' to authenticate.", err=True
                )
            else:
                typer.echo(
                    f"Run 'rhoai platform prepare' to install RHOAI.", err=True
                )
            break  # one actionable hint is enough

    raise typer.Exit(code=1)


@app.command()
def inspect(
    config_file: Path | None = _config_option,
) -> None:
    """Display factual cluster information. Read-only, no modifications."""
    info        = prepare.get_cluster_info()
    worker_nodes = info["worker_nodes"]
    has_gpu      = any(n["gpu"] for n in worker_nodes)

    node_count   = info["node_count"]
    worker_count = info["worker_count"]
    master_count = node_count - worker_count
    topology_detail = (
        f"({node_count} node)"
        if node_count == 1
        else f"({node_count} nodes: {master_count} master, {worker_count} workers)"
    )

    # --- Cluster section ---
    typer.echo("\nCluster")
    typer.echo(f"  OpenShift    {info['openshift_version']}")
    typer.echo(f"  Topology     {info['topology']}  {topology_detail}")

    # --- Worker Nodes section ---
    typer.echo("\nWorker Nodes")
    if has_gpu:
        typer.echo(f"  {'NAME':<48}  {'CPU':<10}  {'MEMORY':<10}  GPU")
        for node in worker_nodes:
            gpu_str = str(node["gpu"]) if node["gpu"] else "—"
            typer.echo(
                f"  {node['name']:<48}  {node['cpu']:<10}  {node['memory']:<10}  {gpu_str}"
            )
    else:
        typer.echo(f"  {'NAME':<48}  {'CPU':<10}  MEMORY")
        for node in worker_nodes:
            typer.echo(f"  {node['name']:<48}  {node['cpu']:<10}  {node['memory']}")

    # --- Storage Classes section ---
    typer.echo("\nStorage Classes")
    storage = info["storage_summary"]
    if storage:
        typer.echo(f"  {'NAME':<40}  BOUND")
        for sc_name in sorted(storage):
            bound = storage[sc_name]["used"]
            typer.echo(f"  {sc_name:<40}  {bound}")
    else:
        typer.echo("  (none)")


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _status_row(label: str, name: str, result: platform_verify.CheckResult, skip: bool = False) -> str:
    """Format a single platform status table row.

    Args:
        label:  Human-readable component label (e.g. "Operator").
        name:   Resource name or display string.
        result: CheckResult from verify_platform.
        skip:   When True the check is shown as skipped (–) regardless of result.
    """
    if skip:
        mark  = "–"
        detail = "(skipped)"
    elif result.passed:
        mark  = "✔"
        detail = "Ready" if label != "Operator" else "Succeeded"
    else:
        mark  = "✘"
        detail = result.message or "not installed"

    return f"  {label:<16}  {name:<28}  {mark}  {detail}"
