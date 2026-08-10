"""Unit tests for rhoai.usecases.vllm.assets and registry."""

from pathlib import Path

from rhoai.usecases import registry
from rhoai.usecases.vllm import assets


class TestRegistry:
    def test_vllm_registered(self) -> None:
        mod = registry.get("vllm")
        assert mod is not None

    def test_list_available_contains_vllm(self) -> None:
        assert "vllm" in registry.list_available()

    def test_list_available_still_contains_fraud_detection(self) -> None:
        assert "fraud-detection" in registry.list_available()

    def test_list_available_is_sorted(self) -> None:
        names = registry.list_available()
        assert names == sorted(names)


class TestAssets:
    def test_serving_runtime_returns_correct_path(self, tmp_path: Path) -> None:
        p = assets.get_serving_runtime(tmp_path)
        assert p == tmp_path / "model-serving" / "shared" / "vllm-serving-runtime.yaml"

    def test_model_manifest_appends_yaml_extension(self, tmp_path: Path) -> None:
        p = assets.get_model_manifest(tmp_path, "qwen2.5-1.5b-instruct")
        assert p.suffix == ".yaml"

    def test_model_manifest_embeds_model_name(self, tmp_path: Path) -> None:
        p = assets.get_model_manifest(tmp_path, "phi-3-mini-4k-instruct")
        assert "phi-3-mini-4k-instruct" in p.name

    def test_model_manifest_is_under_generative_vllm(self, tmp_path: Path) -> None:
        p = assets.get_model_manifest(tmp_path, "qwen2.5-1.5b-instruct")
        assert "generative-models" in str(p)
        assert "vllm" in str(p)

    def test_serving_runtime_is_under_shared(self, tmp_path: Path) -> None:
        p = assets.get_serving_runtime(tmp_path)
        assert "shared" in str(p)

    def test_different_models_produce_different_paths(self, tmp_path: Path) -> None:
        p1 = assets.get_model_manifest(tmp_path, "qwen2.5-1.5b-instruct")
        p2 = assets.get_model_manifest(tmp_path, "phi-3-mini-4k-instruct")
        assert p1 != p2
