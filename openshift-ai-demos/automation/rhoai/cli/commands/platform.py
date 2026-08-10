"""Platform commands — rhoai platform <subcommand>.

    rhoai platform init      validate cluster, install operator, initialize DSCI
    rhoai platform enable    enable one or more DSC components
    rhoai platform setup     full one-shot bootstrap (calls init then enable)
    rhoai platform uninstall remove all RHOAI platform resources
    rhoai platform status    report RHOAI platform health
    rhoai platform inspect   display factual cluster information (read-only)
"""

from pathlib import Path

import typer

from rhoai.config.loader import load_config
from rhoai.ocp import resources
from rhoai.platform import dsc, operators, prepare
from rhoai.platform import verify as platform_verify
from rhoai.utils.logger import get_logger

app = typer.Typer(help="Manage the RHOAI platform.")
log = get_logger(__name__)

_config_option = typer.Option(None, "--config", "-c", help="Path to config YAML.")
_components_arg = typer.Argument(..., help="Component names, e.g. kserve trustyai.")


@app.command(name="init")
def init_cmd(
    config_file: Path | None = _config_option,
    channel: str | None = typer.Option(
        None, "--channel",
        help=(
            "OLM channel, e.g. 'stable-3.x', 'stable-3.4', 'fast-3.x', 'beta'. "
            "Run: oc get packagemanifest rhods-operator -o jsonpath='{.status.channels[*].name}' "
            "to see all available channels. Overrides config file."
        ),
    ),
    version: str | None = typer.Option(
        None, "--version",
        help=(
            "Pin to a specific CSV, e.g. '3.4.2' or 'rhods-operator.3.4.2'. "
            "Check available CSVs with: oc get packagemanifest rhods-operator "
            "-o jsonpath='{range .status.channels[?(@.name==\"<channel>\")]}{.currentCSV}{\"\\n\"}{end}'. "
            "Applied as startingCSV on the Subscription after install."
        ),
    ),
    source: str | None = typer.Option(
        None, "--source",
        help=(
            "CatalogSource name. Defaults to 'redhat-operators'. "
            "Use a custom CatalogSource for pre-GA builds, e.g. 'cs-rhoai-fbc-fragment'."
        ),
    ),
) -> None:
    """Validate prerequisites, install the operator, and initialize DSCI.

    Does not enable any DSC components. Run 'enable' afterwards,
    or use 'setup' to do everything in one call.

    Flag values override the config file. Priority: flags > config file > defaults.

    Examples:
        rhoai platform init --channel stable-3.x
        rhoai platform init --channel stable-3.4 --version 3.4.2
        rhoai platform init --channel beta --source cs-rhoai-fbc-fragment
    """
    config = load_config(config_file)

    # CLI flags take highest priority — overwrite in-memory config only.
    # These are never written back to defaults.yaml.
    if channel:
        config["operator"]["channel"] = channel
    if version:
        # Accept bare semver (3.4.2) and normalise to the full CSV name.
        # Real CSV names use no 'v' prefix: rhods-operator.3.4.2 (not .v3.4.2).
        if version[0].isdigit():
            version = f"rhods-operator.{version}"
        config["operator"]["version"] = version
    if source:
        config["operator"]["source"] = source

    prepare.init_platform(config)

    # --- Post-init status summary ---
    op_name   = config["operator"]["name"]
    op_ns     = config["operator"]["namespace"]
    dsci_name = config["dsc"]["dsci_name"]

    op_display = op_name
    try:
        csv = operators.get_csv_info(op_name, op_ns)
        op_display = f"{csv['name']}  {csv['version']}"
    except Exception:  # noqa: BLE001
        pass

    dsci_phase = resources.status("DSCInitialization", dsci_name).get("phase", "Unknown")

    typer.echo("\nPlatform initialized")
    typer.echo(f"  Operator    {op_display}")
    typer.echo(f"  DSCI        {dsci_name}  {dsci_phase}")


@app.command(name="enable")
def enable_cmd(
    components: list[str] = _components_arg,
    config_file: Path | None = _config_option,
) -> None:
    """Enable one or more DSC components. Requires 'init' to have run first.

    Additive and idempotent — only the named components are changed;
    existing Managed components stay Managed.

    Example:
        rhoai platform enable kserve trustyai
    """
    config = load_config(config_file)
    prepare.install_component(config, components)
    typer.echo(f"Enabled: {', '.join(components)}")


@app.command(name="uninstall")
def uninstall_cmd(
    config_file: Path | None = _config_option,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    delete_workload_ns: bool = typer.Option(
        False, "--delete-workload-ns",
        help=(
            "Also delete the workload namespace (redhat-ods-applications). "
            "Off by default — the namespace may contain user notebooks and pipelines."
        ),
    ),
) -> None:
    """Remove all RHOAI platform resources (DSC, DSCI, operator, namespaces).

    Deletes in reverse-install order: DSC → DSCI → CSV → Subscription →
    OperatorGroup → operator namespace.

    The workload namespace (redhat-ods-applications) is left intact unless
    --delete-workload-ns is passed.
    """
    if not yes:
        typer.confirm(
            "This will remove all RHOAI platform resources. Continue?",
            abort=True,
        )
    config = load_config(config_file)
    prepare.uninstall_platform(config, delete_workload_ns=delete_workload_ns)
    typer.echo("Platform uninstalled.")


@app.command(name="setup")
def setup_cmd(
    config_file: Path | None = _config_option,
) -> None:
    """Full one-shot bootstrap: calls 'init' then enables all base components.

    Equivalent to running 'init' followed by 'enable' for every component
    defined in the base DSC manifest. For fine-grained control use
    'init' + 'enable' separately.
    """
    config = load_config(config_file)
    prepare.bootstrap_platform(config)
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
                typer.echo("Run 'oc login <cluster-url>' to authenticate.", err=True)
            else:
                typer.echo("Run 'rhoai platform setup' to install RHOAI.", err=True)
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

def _status_row(
    label: str, name: str, result: platform_verify.CheckResult, skip: bool = False
) -> str:
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
