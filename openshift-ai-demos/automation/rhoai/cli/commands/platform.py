"""Platform commands — rhoai platform <subcommand>.

    rhoai platform init      validate cluster, install operator, initialize DSCI
    rhoai platform enable    enable one or more DSC components
    rhoai platform disable   disable one or more DSC components
    rhoai platform setup     full one-shot bootstrap (calls init then enable)
    rhoai platform uninstall remove all RHOAI platform resources
    rhoai platform status    report RHOAI platform health
    rhoai platform inspect   display factual cluster information (read-only)

Output verbosity
----------------
  Default (INFO log level):  Structured summary output only.
  --log-level DEBUG:          Full log stream + structured output.
"""

from pathlib import Path

import typer

from rhoai.config.loader import load_config
from rhoai.ocp import resources
from rhoai.platform import dsc, operators, prepare
from rhoai.platform import verify as platform_verify
from rhoai.utils.logger import get_logger
from rhoai.utils.progress import step as progress_step

app = typer.Typer(help="Manage the RHOAI platform.")
log = get_logger(__name__)

_config_option  = typer.Option(None, "--config", "-c", help="Path to config YAML.")
_components_arg = typer.Argument(..., help="Component names, e.g. kserve trustyai.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _step(msg: str) -> None:
    """Print an indented progress line."""
    typer.echo(f"    {msg}")


def _print_dashboard_url(config: dict) -> None:
    """Print the RHOAI dashboard URL if dashboard is currently Managed.

    Reads the URL from the ConsoleLink 'rhodslink' which the dashboard
    component creates — this is the exact URL Red Hat intends users to visit.
    Falls back to constructing the URL from the rhods-dashboard Route if the
    ConsoleLink is absent (older installs).

    Only prints when dashboard is confirmed Managed in the DSC.
    """
    dsc_name   = config["dsc"]["name"]
    cluster_ns = config["platform"]["namespace"]

    # Only show when dashboard component is Managed
    try:
        states = dsc.get_component_states(dsc_name)
        if states.get("dashboard") != "Managed":
            return
    except Exception:  # noqa: BLE001
        return

    url = ""

    # Primary: ConsoleLink created by the dashboard component
    try:
        cl  = resources.get("ConsoleLink", "rhodslink")
        url = cl.get("spec", {}).get("href", "").rstrip("/")
    except Exception:  # noqa: BLE001
        pass

    # Fallback: rhods-dashboard Route
    if not url:
        try:
            route = resources.get("Route", "rhods-dashboard", cluster_ns)
            host  = route.get("spec", {}).get("host", "")
            tls   = route.get("spec", {}).get("tls")
            if host:
                url = f"{'https' if tls else 'http'}://{host}"
        except Exception:  # noqa: BLE001
            pass

    if not url:
        return

    from urllib.parse import urlparse
    hostname = urlparse(url).hostname or url
    typer.echo(f"\n  \U0001f310  Dashboard")
    typer.echo(f"    URL    {url}")
    typer.echo(f"    Note   Add to /etc/hosts:  <ingress-ip>  {hostname}")


def _print_platform_summary(config: dict) -> None:
    """Print the RHOAI Platform status table (operator + DSCI + DSC + components)."""
    op_name   = config["operator"]["name"]
    op_ns     = config["operator"]["namespace"]
    dsc_name  = config["dsc"]["name"]
    dsci_name = config["dsc"]["dsci_name"]

    results     = platform_verify.verify_platform(config)
    op_result   = results[0]
    dsci_result = results[1]
    dsc_result  = results[2]
    op_failed   = not op_result.passed

    op_display = op_name
    if op_result.passed:
        try:
            csv = operators.get_csv_info(op_name, op_ns)
            op_display = f"{csv['name']}  {csv['version']}"
        except Exception:  # noqa: BLE001
            pass

    typer.echo("\nRHOAI Platform")
    typer.echo(_status_row("Operator",       op_display,  op_result))
    typer.echo(_status_row("Initialization", dsci_name,   dsci_result, skip=op_failed))
    typer.echo(_status_row("DataScienceCluster", dsc_name, dsc_result,  skip=op_failed))

    if dsc_result.passed:
        try:
            states  = dsc.get_component_states(dsc_name)
            managed = sorted(c for c, s in states.items() if s == "Managed")
            if managed:
                typer.echo("\n  Components")
                for comp in managed:
                    typer.echo(f"    \u2714  {comp}")
        except Exception:  # noqa: BLE001
            pass
        _print_dashboard_url(config)


def _status_row(
    label: str,
    name: str,
    result: platform_verify.CheckResult,
    skip: bool = False,
) -> str:
    if skip:
        mark   = "\u2013"
        detail = "(skipped)"
    elif result.passed:
        mark   = "\u2714"
        detail = "Ready" if label != "Operator" else "Succeeded"
    else:
        mark   = "\u2718"
        detail = result.message or "not installed"
    return f"  {label:<16}  {name:<36}  {mark}  {detail}"


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

@app.command(name="init")
def init_cmd(
    config_file: Path | None = _config_option,
    channel: str | None = typer.Option(
        None, "--channel",
        help=(
            "OLM channel, e.g. 'stable-3.x', 'stable-3.4', 'fast-3.x', 'beta'. "
            "Run: oc get packagemanifest rhods-operator "
            "-o jsonpath='{.status.channels[*].name}' to list available channels."
        ),
    ),
    version: str | None = typer.Option(
        None, "--version",
        help="Pin to a specific CSV, e.g. '3.4.2' or 'rhods-operator.3.4.2'.",
    ),
    source: str | None = typer.Option(
        None, "--source",
        help="CatalogSource name. Defaults to 'redhat-operators'.",
    ),
) -> None:
    """Validate prerequisites, install the operator, and initialize DSCI.

    Does not enable any DSC components — run 'enable' afterwards,
    or use 'setup' to do everything in one call.

    Examples:
        rhoai platform init --channel stable-3.x
        rhoai platform init --channel stable-3.4 --version 3.4.2
        rhoai platform init --channel beta --source cs-rhoai-fbc-fragment
    """
    config = load_config(config_file)

    if channel:
        config["operator"]["channel"] = channel
    if version:
        if version[0].isdigit():
            version = f"rhods-operator.{version}"
        config["operator"]["version"] = version
    if source:
        config["operator"]["source"] = source

    import rhoai.platform.operators as _ops
    import rhoai.platform.dsc as _dsc
    import rhoai.platform.prepare as _prep

    _orig_validate_login   = _prep.validate_login
    _orig_validate_storage = _prep.validate_storage
    _orig_install          = _ops.install
    _orig_verify           = _ops.verify
    _orig_apply_dsci       = _dsc.apply_dsci
    _orig_wait_dsci        = _dsc.wait_dsci_ready

    _spinners: dict = {}

    def _open_step(key: str, label: str) -> None:
        if key not in _spinners:
            ctx = progress_step(label)
            ctx.__enter__()
            _spinners[key] = ctx

    def _close_step(key: str) -> None:
        ctx = _spinners.pop(key, None)
        if ctx:
            ctx.__exit__(None, None, None)

    def _close_all() -> None:
        for key in list(_spinners):
            _close_step(key)

    ch  = config["operator"]["channel"]
    src = config["operator"].get("source", "redhat-operators")
    ver = config["operator"].get("version", "")
    op_label = f"channel: {ch}, source: {src}" + (f", version: {ver}" if ver else "")

    def _patched_validate_login():
        _open_step("prereq", "Prerequisites (login, RBAC, storage, namespaces)")
        _orig_validate_login()
        _close_step("prereq")

    def _patched_validate_storage(class_name):
        _orig_validate_storage(class_name)

    def _patched_install(name, ns, ch_, repo_root, timeout, **kwargs):
        _open_step("operator", f"Installing RHOAI operator ({op_label})")
        _orig_install(name, ns, ch_, repo_root, timeout, **kwargs)
        _close_step("operator")

    def _patched_verify(name, ns):
        _open_step("operator", "Operator already installed — skipping install")
        _orig_verify(name, ns)
        _close_step("operator")

    def _patched_apply_dsci(manifest_path):
        _open_step("dsci", "Applying DSCInitialization")
        _orig_apply_dsci(manifest_path)

    def _patched_wait_dsci(name, timeout):
        _orig_wait_dsci(name, timeout)
        _close_step("dsci")

    _prep.validate_login   = _patched_validate_login
    _prep.validate_storage = _patched_validate_storage
    _ops.install           = _patched_install
    _ops.verify            = _patched_verify
    _dsc.apply_dsci        = _patched_apply_dsci
    _dsc.wait_dsci_ready   = _patched_wait_dsci

    typer.echo("\nInitializing RHOAI platform...")

    try:
        prepare.init_platform(config)
    except Exception:
        _close_all()
        raise
    finally:
        _prep.validate_login   = _orig_validate_login
        _prep.validate_storage = _orig_validate_storage
        _ops.install           = _orig_install
        _ops.verify            = _orig_verify
        _dsc.apply_dsci        = _orig_apply_dsci
        _dsc.wait_dsci_ready   = _orig_wait_dsci

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

    typer.echo("\n  ✔  RHOAI Platform initialized")
    typer.echo(f"  Operator    {op_display}")
    typer.echo(f"  DSCI        {dsci_name}  {dsci_phase}")
    typer.echo("")


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
    comp_list = ", ".join(components)

    typer.echo(f"\nEnabling component(s): {comp_list}")
    _step("Setting component state(s) on DSC to Managed")

    prepare.install_component(config, components)

    typer.echo(f"\n  ✔  Enabled: {comp_list}")

    # Show all currently-managed components
    dsc_name = config["dsc"]["name"]
    try:
        states  = dsc.get_component_states(dsc_name)
        managed = sorted(c for c, s in states.items() if s == "Managed")
        if managed:
            typer.echo("\n  Components")
            for comp in managed:
                typer.echo(f"    \u2714  {comp}")
    except Exception:  # noqa: BLE001
        pass

    # If dashboard is enabled (just requested or already managed), print its URL
    _print_dashboard_url(config)
    typer.echo("")


@app.command(name="disable")
def disable_cmd(
    components: list[str] = _components_arg,
    config_file: Path | None = _config_option,
) -> None:
    """Disable one or more DSC components (set managementState to Removed).

    Idempotent — components already Removed stay Removed;
    unrelated components are left exactly as they are.

    Example:
        rhoai platform disable trustyai ray
    """
    config = load_config(config_file)
    comp_list = ", ".join(components)

    typer.echo(f"\nDisabling component(s): {comp_list}")
    _step("Setting component state(s) on DSC to Removed")

    prepare.remove_component(config, components)

    typer.echo(f"\n  ✔  Disabled: {comp_list}")

    dsc_name = config["dsc"]["name"]
    try:
        states  = dsc.get_component_states(dsc_name)
        managed = sorted(c for c, s in states.items() if s == "Managed")
        if managed:
            typer.echo("\n  Components still enabled")
            for comp in managed:
                typer.echo(f"    \u2714  {comp}")
        else:
            typer.echo("\n  No components currently enabled")
    except Exception:  # noqa: BLE001
        pass
    typer.echo("")


@app.command(name="uninstall")
def uninstall_cmd(
    config_file: Path | None = _config_option,
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    keep_workload_ns: bool = typer.Option(
        False, "--keep-workload-ns",
        help=(
            "Preserve workload namespaces (redhat-ods-applications, rhods-notebooks, "
            "rhoai-model-registries, redhat-ods-monitoring). "
            "By default they are deleted for a clean reinstall."
        ),
    ),
) -> None:
    """Remove all RHOAI platform resources for a clean cluster state.

    Workload namespaces are deleted by default. Pass --keep-workload-ns to
    preserve user notebooks and pipelines.
    """
    if not yes:
        typer.confirm(
            "This will remove all RHOAI platform resources. Continue?",
            abort=True,
        )
    config = load_config(config_file)

    import rhoai.platform.dsc as _dsc
    from rhoai.ocp import resources as _res

    D = "✔"  # ✔  fires after work completes

    _orig_delete_dsc      = _dsc.delete_dsc
    _orig_delete_dsci     = _dsc.delete_dsci
    _orig_delete_manifest = _res.delete_manifest
    _orig_exists          = _res.exists

    # Spinner for the slow DSC/DSCI phase — opened on first hook, closed after DSCI done
    _dsc_spinner = None

    def _open_dsc_spinner(label: str) -> None:
        nonlocal _dsc_spinner
        if _dsc_spinner is None:
            _dsc_spinner = progress_step(label)
            _dsc_spinner.__enter__()

    def _close_dsc_spinner() -> None:
        nonlocal _dsc_spinner
        if _dsc_spinner is not None:
            _dsc_spinner.__exit__(None, None, None)
            _dsc_spinner = None

    # Spinners for OLM and namespace phases
    _olm_spinner = None
    _ns_spinner  = None

    def _open_olm_spinner(label: str) -> None:
        nonlocal _olm_spinner
        if _olm_spinner is None:
            _olm_spinner = progress_step(label)
            _olm_spinner.__enter__()

    def _close_olm_spinner() -> None:
        nonlocal _olm_spinner
        if _olm_spinner is not None:
            _olm_spinner.__exit__(None, None, None)
            _olm_spinner = None

    def _open_ns_spinner(label: str) -> None:
        nonlocal _ns_spinner
        if _ns_spinner is None:
            _ns_spinner = progress_step(label)
            _ns_spinner.__enter__()

    def _close_ns_spinner() -> None:
        nonlocal _ns_spinner
        if _ns_spinner is not None:
            _ns_spinner.__exit__(None, None, None)
            _ns_spinner = None

    def _close_all_spinners() -> None:
        _close_dsc_spinner()
        _close_olm_spinner()
        _close_ns_spinner()

    # Hook 1: DSC deletion — opens spinner; work (delete + pod drain) runs inside
    def _patched_delete_dsc(name):
        _open_dsc_spinner("Removing DataScienceCluster and DSCInitialization")
        _orig_delete_dsc(name)

    # Hook 1b: DSCI-only path (when DSC was already absent)
    def _patched_delete_dsci(name):
        _open_dsc_spinner("Removing DSCInitialization")
        _orig_delete_dsci(name)
        _close_dsc_spinner()  # DSCI is the last dsc-phase call — close spinner here

    # Hook 2: OLM phase — first CSV delete opens the spinner;
    # stays open until namespace hook fires (next phase)
    def _patched_delete_manifest(kind, name, namespace=None):
        if kind == "ClusterServiceVersion":
            _close_dsc_spinner()  # safety — DSC spinner may still be open if DSCI was absent
            _open_olm_spinner("Removing operator (CSV, Subscription, OperatorGroup, InstallPlans)")
        _orig_delete_manifest(kind, name, namespace)

    # Hook 3: Namespace phase — first existing namespace closes the OLM spinner
    # and opens the namespace spinner
    def _patched_exists(kind, name, namespace=None):
        result = _orig_exists(kind, name, namespace)
        if kind == "Namespace" and result:
            _close_olm_spinner()
            if keep_workload_ns:
                _open_ns_spinner("Removing operator namespace (workload namespaces preserved)")
            else:
                _open_ns_spinner("Removing namespaces")
        return result

    _dsc.delete_dsc      = _patched_delete_dsc
    _dsc.delete_dsci     = _patched_delete_dsci
    _res.delete_manifest = _patched_delete_manifest
    _res.exists          = _patched_exists

    typer.echo("\nUninstalling RHOAI platform...")

    try:
        prepare.uninstall_platform(config, keep_workload_ns=keep_workload_ns)
    except Exception:
        _close_all_spinners()
        raise
    finally:
        _dsc.delete_dsc      = _orig_delete_dsc
        _dsc.delete_dsci     = _orig_delete_dsci
        _res.delete_manifest = _orig_delete_manifest
        _res.exists          = _orig_exists

    # Namespace deletions are done — close the spinner
    _close_ns_spinner()

    # CRDs / webhooks / RBAC ran as batch oc calls inside uninstall_platform.
    # Print as a plain completed line — consistent present-continuous tense.
    typer.echo("  ✔  Removing CRDs, webhooks and cluster-scoped RBAC  (done)")

    typer.echo("\n  ✔  RHOAI platform uninstalled.")


@app.command(name="setup")
def setup_cmd(
    config_file: Path | None = _config_option,
    channel: str | None = typer.Option(None, "--channel", help="OLM channel. Overrides config file."),
    version: str | None = typer.Option(None, "--version", help="Pin to a specific CSV version."),
    source:  str | None = typer.Option(None, "--source",  help="CatalogSource name."),
) -> None:
    """Full one-shot bootstrap: init + enable DSC components.

    Equivalent to 'init' followed by applying the base DSC manifest
    (or the components list in your config file).
    For fine-grained control use 'init' + 'enable' separately.
    """
    config = load_config(config_file)
    if channel:
        config["operator"]["channel"] = channel
    if version:
        if version[0].isdigit():
            version = f"rhods-operator.{version}"
        config["operator"]["version"] = version
    if source:
        config["operator"]["source"] = source

    import rhoai.platform.operators as _ops
    import rhoai.platform.dsc as _dsc
    import rhoai.platform.prepare as _prep

    _orig_validate_login   = _prep.validate_login
    _orig_validate_storage = _prep.validate_storage
    _orig_install          = _ops.install
    _orig_verify           = _ops.verify
    _orig_apply_dsci       = _dsc.apply_dsci
    _orig_wait_dsci        = _dsc.wait_dsci_ready
    _orig_apply_dsc        = _dsc.apply_dsc
    _orig_set_states       = _dsc.set_component_states
    _orig_wait_dsc         = _dsc.wait_until_ready

    _spinners: dict = {}

    def _open_step(key: str, label: str) -> None:
        if key not in _spinners:
            ctx = progress_step(label)
            ctx.__enter__()
            _spinners[key] = ctx

    def _close_step(key: str) -> None:
        ctx = _spinners.pop(key, None)
        if ctx:
            ctx.__exit__(None, None, None)

    def _close_all() -> None:
        for key in list(_spinners):
            _close_step(key)

    ch  = config["operator"]["channel"]
    src = config["operator"].get("source", "redhat-operators")
    ver = config["operator"].get("version", "")
    op_label = f"channel: {ch}, source: {src}" + (f", version: {ver}" if ver else "")

    def _patched_validate_login():
        _open_step("prereq", "Prerequisites (login, RBAC, storage, namespaces)")
        _orig_validate_login()
        _close_step("prereq")

    def _patched_validate_storage(class_name):
        _orig_validate_storage(class_name)

    def _patched_install(name, ns, ch_, repo_root, timeout, **kwargs):
        _open_step("operator", f"Installing RHOAI operator ({op_label})")
        _orig_install(name, ns, ch_, repo_root, timeout, **kwargs)
        _close_step("operator")

    def _patched_verify(name, ns):
        _open_step("operator", "Operator already installed — skipping install")
        _orig_verify(name, ns)
        _close_step("operator")

    def _patched_apply_dsci(manifest_path):
        _open_step("dsci", "Applying DSCInitialization")
        _orig_apply_dsci(manifest_path)

    def _patched_wait_dsci(name, timeout):
        _orig_wait_dsci(name, timeout)
        _close_step("dsci")

    def _patched_apply_dsc(manifest_path):
        _open_step("dsc", "Enabling components")
        _orig_apply_dsc(manifest_path)

    def _patched_set_states(name, states):
        _open_step("dsc", "Enabling components")
        _orig_set_states(name, states)

    def _patched_wait_dsc(name, timeout):
        _orig_wait_dsc(name, timeout)
        _close_step("dsc")

    _prep.validate_login      = _patched_validate_login
    _prep.validate_storage    = _patched_validate_storage
    _ops.install              = _patched_install
    _ops.verify               = _patched_verify
    _dsc.apply_dsci           = _patched_apply_dsci
    _dsc.wait_dsci_ready      = _patched_wait_dsci
    _dsc.apply_dsc            = _patched_apply_dsc
    _dsc.set_component_states = _patched_set_states
    _dsc.wait_until_ready     = _patched_wait_dsc

    typer.echo("\nSetting up RHOAI platform...")

    try:
        prepare.bootstrap_platform(config)
    except Exception:
        _close_all()
        raise
    finally:
        _prep.validate_login      = _orig_validate_login
        _prep.validate_storage    = _orig_validate_storage
        _ops.install              = _orig_install
        _ops.verify               = _orig_verify
        _dsc.apply_dsci           = _orig_apply_dsci
        _dsc.wait_dsci_ready      = _orig_wait_dsci
        _dsc.apply_dsc            = _orig_apply_dsc
        _dsc.set_component_states = _orig_set_states
        _dsc.wait_until_ready     = _orig_wait_dsc

    _print_platform_summary(config)
    typer.echo("")


@app.command()
def status(
    config_file: Path | None = _config_option,
) -> None:
    """Report the health of the installed RHOAI platform."""
    config = load_config(config_file)

    results     = platform_verify.verify_platform(config)
    op_result   = results[0]
    dsci_result = results[1]
    dsc_result  = results[2]
    op_failed   = not op_result.passed

    op_name   = config["operator"]["name"]
    op_ns     = config["operator"]["namespace"]
    dsc_name  = config["dsc"]["name"]
    dsci_name = config["dsc"]["dsci_name"]

    op_display = op_name
    if op_result.passed:
        try:
            csv = operators.get_csv_info(op_name, op_ns)
            op_display = f"{csv['name']}  {csv['version']}"
        except Exception:  # noqa: BLE001
            pass

    typer.echo("\nRHOAI Platform")
    typer.echo(_status_row("Operator",             op_display,  op_result))
    typer.echo(_status_row("Initialization",       dsci_name,   dsci_result, skip=op_failed))
    typer.echo(_status_row("DataScienceCluster",   dsc_name,    dsc_result,  skip=op_failed))

    if dsc_result.passed:
        try:
            states  = dsc.get_component_states(dsc_name)
            managed = sorted(c for c, s in states.items() if s == "Managed")
            if managed:
                typer.echo("\n  Components")
                for comp in managed:
                    typer.echo(f"    \u2714  {comp}")
        except Exception:  # noqa: BLE001
            pass

    failed = [r for r in results if not r.passed]
    typer.echo("")
    if not failed:
        typer.echo("Platform is healthy.")
        typer.echo("")
        return

    typer.echo("Platform is not healthy.", err=True)

    # Generic actionable hints — keeps the message correct regardless of
    # which combination of checks failed or what command was used to install.
    auth_failed = any(
        r.message and ("401" in r.message or "Unauthorized" in r.message)
        for r in failed
    )
    if auth_failed:
        typer.echo("  \u2139  Run 'oc login <cluster-url>' to authenticate.", err=True)
    else:
        typer.echo("  \u2139  Run 'rhoai platform setup' to reinstall.", err=True)
    typer.echo("  \u2139  For details run: rhoai --log-level DEBUG platform status", err=True)
    typer.echo("", err=True)

    raise typer.Exit(code=1)


@app.command()
def inspect(
    config_file: Path | None = _config_option,
) -> None:
    """Display factual cluster information. Read-only, no modifications."""
    typer.echo("\nDumping cluster info...")
    info         = prepare.get_cluster_info()
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

    typer.echo("\n\u2699  Cluster")
    typer.echo(f"  OpenShift    {info['openshift_version']}")
    typer.echo(f"  Topology     {info['topology']}  {topology_detail}")

    typer.echo("\n\u26f6  Worker Nodes")
    if has_gpu:
        typer.echo(f"  {'NAME':<48}  {'CPU':<10}  {'MEMORY':<10}  GPU")
        for node in worker_nodes:
            gpu_str = str(node["gpu"]) if node["gpu"] else "\u2014"
            typer.echo(f"  {node['name']:<48}  {node['cpu']:<10}  {node['memory']:<10}  {gpu_str}")
    else:
        typer.echo(f"  {'NAME':<48}  {'CPU':<10}  MEMORY")
        for node in worker_nodes:
            typer.echo(f"  {node['name']:<48}  {node['cpu']:<10}  {node['memory']}")

    typer.echo("\n💾  Storage Classes")
    storage = info["storage_summary"]
    if storage:
        typer.echo(f"  {'NAME':<40}  BOUND")
        for sc_name in sorted(storage):
            bound = storage[sc_name]["used"]
            typer.echo(f"  {sc_name:<40}  {bound}")
    else:
        typer.echo("  (none)")

    typer.echo("")
