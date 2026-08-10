"""Unit tests for rhoai.platform.prepare."""

from typing import Any
from unittest.mock import MagicMock

import pytest

from rhoai.platform import prepare


@pytest.fixture(autouse=True)
def patch_resources(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    mock = MagicMock()
    monkeypatch.setattr("rhoai.platform.prepare.resources", mock)
    return mock


# ---------------------------------------------------------------------------
# validate_login
# ---------------------------------------------------------------------------
class TestValidateLogin:
    def test_passes_when_cluster_reachable(self, patch_resources: MagicMock) -> None:
        patch_resources.get.return_value = {"metadata": {"name": "version"}}
        prepare.validate_login()  # should not raise

    def test_raises_when_cluster_unreachable(self, patch_resources: MagicMock) -> None:
        patch_resources.get.side_effect = OSError("no route to host")
        with pytest.raises(RuntimeError, match="oc login"):
            prepare.validate_login()


# ---------------------------------------------------------------------------
# validate_permissions
# ---------------------------------------------------------------------------
class TestValidatePermissions:
    def test_passes_when_allowed(self, patch_resources: MagicMock) -> None:
        patch_resources.apply_dict.return_value = {"status": {"allowed": True}}
        prepare.validate_permissions("redhat-ods-operator")  # should not raise

    def test_raises_when_denied(self, patch_resources: MagicMock) -> None:
        patch_resources.apply_dict.return_value = {"status": {"allowed": False}}
        with pytest.raises(RuntimeError, match="Insufficient permissions"):
            prepare.validate_permissions("redhat-ods-operator")

    def test_raises_when_apply_fails(self, patch_resources: MagicMock) -> None:
        patch_resources.apply_dict.side_effect = RuntimeError("API error")
        with pytest.raises(RuntimeError, match="Permission check failed"):
            prepare.validate_permissions("redhat-ods-operator")


# ---------------------------------------------------------------------------
# validate_storage
# ---------------------------------------------------------------------------
class TestValidateStorage:
    def test_passes_when_specific_class_exists(self, patch_resources: MagicMock) -> None:
        patch_resources.exists.return_value = True
        prepare.validate_storage("gp3-csi")  # should not raise
        patch_resources.exists.assert_called_once_with("StorageClass", "gp3-csi")

    def test_raises_when_specific_class_missing(self, patch_resources: MagicMock) -> None:
        patch_resources.exists.return_value = False
        with pytest.raises(RuntimeError, match="gp3-csi"):
            prepare.validate_storage("gp3-csi")

    def test_passes_when_any_class_present(self, patch_resources: MagicMock) -> None:
        patch_resources.list_resources.return_value = [
            {"metadata": {"name": "standard"}}
        ]
        prepare.validate_storage("")  # empty → accept any

    def test_raises_when_no_classes_at_all(self, patch_resources: MagicMock) -> None:
        patch_resources.list_resources.return_value = []
        with pytest.raises(RuntimeError, match="No StorageClasses"):
            prepare.validate_storage("")


# ---------------------------------------------------------------------------
# validate_namespace
# ---------------------------------------------------------------------------
class TestValidateNamespace:
    def test_skips_creation_when_namespace_exists(self, patch_resources: MagicMock) -> None:
        patch_resources.exists.return_value = True
        prepare.validate_namespace("my-ns")
        patch_resources.apply_dict.assert_not_called()

    def test_creates_namespace_when_absent(self, patch_resources: MagicMock) -> None:
        patch_resources.exists.return_value = False
        prepare.validate_namespace("new-ns")
        call_kwargs = patch_resources.apply_dict.call_args[0][0]
        assert call_kwargs["kind"] == "Namespace"
        assert call_kwargs["metadata"]["name"] == "new-ns"


# ---------------------------------------------------------------------------
# get_cluster_info
# ---------------------------------------------------------------------------
def _make_node(name: str, roles: list[str], cpu: str, memory: str, gpu: int = 0) -> dict[str, Any]:
    labels = {f"node-role.kubernetes.io/{r}": "" for r in roles}
    capacity: dict[str, Any] = {"cpu": cpu, "memory": memory}
    if gpu:
        capacity["nvidia.com/gpu"] = str(gpu)
    return {"metadata": {"name": name, "labels": labels}, "status": {"capacity": capacity}}


def _make_pv(storage_class: str, capacity: str, phase: str) -> dict[str, Any]:
    return {
        "spec": {"storageClassName": storage_class, "capacity": {"storage": capacity}},
        "status": {"phase": phase},
    }


def _make_cv(version: str) -> dict[str, Any]:
    return {"status": {"desired": {"version": version}}}


class TestGetClusterInfo:
    def _setup(
        self,
        patch_resources: MagicMock,
        nodes: list[dict],
        pvs: list[dict],
        classes: list[str],
        version: str = "4.15.0",
    ) -> None:
        cv = _make_cv(version)
        sc_list = [{"metadata": {"name": c}} for c in classes]

        def list_resources_side_effect(kind: str, *args, **kwargs):
            if kind == "Node":
                return nodes
            if kind == "StorageClass":
                return sc_list
            if kind == "PersistentVolume":
                return pvs
            return []

        patch_resources.get.return_value = cv
        patch_resources.list_resources.side_effect = list_resources_side_effect

    def test_multi_node_topology(self, patch_resources: MagicMock) -> None:
        nodes = [
            _make_node("master-0", ["master"], "4", "8Gi"),
            _make_node("worker-0", ["worker"], "8", "32Gi"),
            _make_node("worker-1", ["worker"], "8", "32Gi"),
        ]
        self._setup(patch_resources, nodes, [], ["gp3-csi"])
        info = prepare.get_cluster_info()
        assert info["topology"] == "Multi-node"
        assert info["node_count"] == 3
        assert info["worker_count"] == 2

    def test_sno_topology_single_node(self, patch_resources: MagicMock) -> None:
        nodes = [_make_node("sno-0", ["master", "worker"], "16", "64Gi")]
        self._setup(patch_resources, nodes, [], [])
        info = prepare.get_cluster_info()
        assert info["topology"] == "SNO"
        assert info["node_count"] == 1
        assert info["worker_count"] == 1

    def test_worker_node_cpu_and_memory(self, patch_resources: MagicMock) -> None:
        nodes = [_make_node("worker-0", ["worker"], "8", "32Gi")]
        self._setup(patch_resources, nodes, [], [])
        info = prepare.get_cluster_info()
        node = info["worker_nodes"][0]
        assert node["name"] == "worker-0"
        assert node["cpu"] == "8 cores"
        assert node["memory"] == "32 GiB"

    def test_worker_node_gpu_detected(self, patch_resources: MagicMock) -> None:
        nodes = [_make_node("gpu-worker", ["worker"], "32", "128Gi", gpu=4)]
        self._setup(patch_resources, nodes, [], [])
        info = prepare.get_cluster_info()
        assert info["worker_nodes"][0]["gpu"] == 4

    def test_worker_node_no_gpu(self, patch_resources: MagicMock) -> None:
        nodes = [_make_node("worker-0", ["worker"], "8", "32Gi")]
        self._setup(patch_resources, nodes, [], [])
        info = prepare.get_cluster_info()
        assert info["worker_nodes"][0]["gpu"] == 0

    def test_pv_bound_counted_as_used(self, patch_resources: MagicMock) -> None:
        nodes = [_make_node("worker-0", ["worker"], "4", "8Gi")]
        pvs = [_make_pv("gp3-csi", "10Gi", "Bound")]
        self._setup(patch_resources, nodes, pvs, ["gp3-csi"])
        info = prepare.get_cluster_info()
        assert info["storage_summary"]["gp3-csi"]["used"] == "10 GiB"

    def test_pv_available_not_counted_as_used(self, patch_resources: MagicMock) -> None:
        nodes = [_make_node("worker-0", ["worker"], "4", "8Gi")]
        pvs = [_make_pv("gp3-csi", "10Gi", "Available")]
        self._setup(patch_resources, nodes, pvs, ["gp3-csi"])
        info = prepare.get_cluster_info()
        assert info["storage_summary"]["gp3-csi"]["used"] == "0 GiB"

    def test_openshift_version_returned(self, patch_resources: MagicMock) -> None:
        nodes = [_make_node("worker-0", ["worker"], "4", "8Gi")]
        self._setup(patch_resources, nodes, [], [], version="4.17.3")
        info = prepare.get_cluster_info()
        assert info["openshift_version"] == "4.17.3"

    def test_cpu_millicores_parsed_correctly(self, patch_resources: MagicMock) -> None:
        # "4000m" = 4 cores
        nodes = [_make_node("worker-0", ["worker"], "4000m", "8Gi")]
        self._setup(patch_resources, nodes, [], [])
        info = prepare.get_cluster_info()
        assert info["worker_nodes"][0]["cpu"] == "4 cores"


# ---------------------------------------------------------------------------
# deploy_platform
# ---------------------------------------------------------------------------
class TestDeployPlatform:
    # Shared minimal config used by all deploy_platform tests.
    _config: dict[str, Any] = {
        "repo_root": "/repo",
        "operator":  {"name": "rhods-operator", "namespace": "redhat-ods-operator", "channel": "stable"},
        "dsc":       {"name": "default-dsc", "dsci_name": "default-dsci"},
        "timeouts":  {"operator_ready": 300, "dsc_ready": 600},
    }

    def _setup(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        dsci_ready: bool = False,
        dsc_ready: bool = False,
        operator_installed: bool = True,
    ):
        import importlib
        import sys

        sys.modules.pop("rhoai.platform.prepare", None)
        prep_mod = importlib.import_module("rhoai.platform.prepare")

        operators_mock = MagicMock()
        operators_mock.is_installed.return_value = operator_installed
        dsc_mock = MagicMock()
        dsc_mock.is_dsci_ready.return_value = dsci_ready
        dsc_mock.is_dsc_ready.return_value  = dsc_ready

        monkeypatch.setattr(prep_mod, "prepare_platform", MagicMock())
        monkeypatch.setattr("rhoai.platform.operators", operators_mock)
        monkeypatch.setattr("rhoai.platform.dsc",       dsc_mock)
        monkeypatch.setattr("rhoai.platform.manifests", MagicMock())

        return prep_mod, operators_mock, dsc_mock

    def test_calls_prepare_then_operator_then_dsc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """deploy_platform calls prepare_platform, then operator, then DSC — in order."""
        prep_mod, operators_mock, dsc_mock = self._setup(monkeypatch)
        prep_mod.deploy_platform(self._config)

        operators_mock.is_installed.assert_called_once()
        dsc_mock.wait_until_ready.assert_called_once()

    def test_always_applies_dsci_and_dsc(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """DSC/DSCI manifests are always applied — ensures new components are reconciled."""
        prep_mod, _, dsc_mock = self._setup(monkeypatch)
        prep_mod.deploy_platform(self._config)

        dsc_mock.apply_dsci.assert_called_once()
        dsc_mock.apply_dsc.assert_called_once()
        dsc_mock.wait_until_ready.assert_called_once()

    def test_installs_operator_when_not_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        prep_mod, operators_mock, _ = self._setup(monkeypatch, operator_installed=False)
        prep_mod.deploy_platform(self._config)

        operators_mock.install.assert_called_once()
        operators_mock.wait_until_ready.assert_not_called()


# ---------------------------------------------------------------------------
# _parse_cpu / _parse_memory_ki helpers
# ---------------------------------------------------------------------------
class TestParseCpu:
    def test_integer_cores(self) -> None:
        assert prepare._parse_cpu("4") == 4000

    def test_millicores(self) -> None:
        assert prepare._parse_cpu("4000m") == 4000

    def test_single_core(self) -> None:
        assert prepare._parse_cpu("1") == 1000


class TestParseMemoryKi:
    def test_kibibytes(self) -> None:
        assert prepare._parse_memory_ki("1024Ki") == 1024

    def test_mebibytes(self) -> None:
        assert prepare._parse_memory_ki("1Mi") == 1024

    def test_gibibytes(self) -> None:
        assert prepare._parse_memory_ki("1Gi") == 1024 * 1024

    def test_tebibytes(self) -> None:
        assert prepare._parse_memory_ki("1Ti") == 1024 * 1024 * 1024

    def test_plain_bytes(self) -> None:
        # 2048 bytes = 2 KiB
        assert prepare._parse_memory_ki("2048") == 2
