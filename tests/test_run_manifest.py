from __future__ import annotations

import json

import pytest

import src.run_manifest as run_manifest_module
from src.battle_contract import SourceProvenance
from src.population import BASE_RESEARCH, LEGACY_SCORE
from src.run_manifest import (
    RUN_MANIFEST_SCHEMA_VERSION,
    create_run_manifest,
)


PROVENANCE = SourceProvenance(
    source_dataset="synthetic/manifest",
    source_revision="revision-1",
    source_split="train",
    source_file="synthetic.parquet",
    source_file_sha256="b" * 64,
)
ENVIRONMENT = {
    "python_version": "3.12.5",
    "package_versions": {"numpy": "2.5.2", "pandas": "3.0.5"},
}


def _manifest(**overrides: object):
    values: dict[str, object] = {
        "source_provenance": PROVENANCE,
        "population_spec": BASE_RESEARCH,
        "git_commit": "a" * 40,
        "git_branch": "main",
        "analysis_config": {"seed": 42, "estimator": None},
        "created_by": "synthetic-test",
        "environment": ENVIRONMENT,
    }
    values.update(overrides)
    return create_run_manifest(**values)


def test_run_id_is_deterministic_and_config_key_order_independent() -> None:
    first = _manifest(analysis_config={"seed": 42, "parameters": {"b": 2, "a": 1}})
    second = _manifest(analysis_config={"parameters": {"a": 1, "b": 2}, "seed": 42})

    assert first.run_id == second.run_id
    assert first.to_json() == second.to_json()


def test_config_and_population_changes_alter_run_id() -> None:
    assert _manifest(analysis_config={"seed": 1}).run_id != _manifest(analysis_config={"seed": 2}).run_id
    assert _manifest(population_spec=BASE_RESEARCH).run_id != _manifest(population_spec=LEGACY_SCORE).run_id


def test_manifest_schema_and_provenance_bindings_are_explicit() -> None:
    manifest = _manifest()
    payload = manifest.to_dict()

    assert payload["manifest_schema_version"] == RUN_MANIFEST_SCHEMA_VERSION
    assert payload["canonical_schema_version"] == 1
    assert payload["population_id"] == "base_research"
    assert payload["population_spec_version"] == BASE_RESEARCH.population_spec_version
    assert payload["source_snapshot_id"]
    assert payload["git_commit"] == "a" * 40


def test_json_round_trip_preserves_identity_and_payload() -> None:
    manifest = _manifest()
    restored = type(manifest).from_json(manifest.to_json())

    assert restored.run_id == manifest.run_id
    assert restored.to_json() == manifest.to_json()
    assert json.loads(restored.to_json()) == json.loads(manifest.to_json())


def test_environment_capture_excludes_secrets_paths_and_variables() -> None:
    manifest = _manifest()
    serialized = manifest.to_json()

    assert "TOKEN" not in serialized
    assert "fake-token" not in serialized
    assert "C:\\Users\\" not in serialized
    assert "environment_variables" not in serialized
    assert "hostname" not in serialized


def test_missing_package_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    original = run_manifest_module.importlib.metadata.version

    def fake_version(name: str) -> str:
        if name == "optional-not-installed":
            raise run_manifest_module.importlib.metadata.PackageNotFoundError(name)
        return original(name)

    monkeypatch.setattr(run_manifest_module.importlib.metadata, "version", fake_version)
    captured = run_manifest_module.capture_environment(("optional-not-installed",))

    assert captured["package_versions"] == {"optional-not-installed": None}
    manifest = _manifest(environment=captured)
    assert manifest.package_versions["optional-not-installed"] is None


def test_manifest_does_not_require_git_or_network_access() -> None:
    manifest = _manifest()

    assert manifest.git_branch == "main"
    assert manifest.git_commit == "a" * 40
