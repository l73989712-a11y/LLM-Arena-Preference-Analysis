"""Deterministic, safe provenance records for reproducible research runs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import importlib.metadata
import json
import platform
from collections.abc import Mapping
from typing import Any

from src.battle_contract import (
    CANONICAL_BATTLE_SCHEMA_VERSION,
    SourceProvenance,
    source_snapshot_id,
)
from src.population import PopulationSpec


RUN_MANIFEST_SCHEMA_VERSION = 1
DEFAULT_PACKAGE_NAMES = ("pandas", "numpy", "scikit-learn", "pytest")


def _canonicalize(value: Any) -> Any:
    """Convert supported configuration values into deterministic JSON values."""
    if isinstance(value, Mapping):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"unsupported manifest value type: {type(value).__name__}")


def _canonical_json(value: Any) -> str:
    return json.dumps(
        _canonicalize(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def run_id_for(
    *,
    source_snapshot: str,
    canonical_schema_version: int,
    population_id: str,
    population_spec_version: int,
    git_commit: str,
    analysis_config: Mapping[str, Any],
) -> str:
    """Return the deterministic identity for a research run definition."""
    identity = {
        "analysis_config": analysis_config,
        "canonical_schema_version": canonical_schema_version,
        "git_commit": git_commit,
        "population_id": population_id,
        "population_spec_version": population_spec_version,
        "source_snapshot_id": source_snapshot,
    }
    return hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()


def _package_version(package_name: str) -> str | None:
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def capture_environment(package_names: tuple[str, ...] = DEFAULT_PACKAGE_NAMES) -> dict[str, Any]:
    """Capture only safe runtime metadata; missing packages become ``None``."""
    names = tuple(sorted({str(name) for name in package_names}))
    return {
        "python_version": platform.python_version(),
        "package_versions": {name: _package_version(name) for name in names},
    }


@dataclass(frozen=True)
class RunManifest:
    """Machine-readable execution provenance, excluding analysis results."""

    manifest_schema_version: int
    run_id: str
    created_by: str
    git_commit: str
    git_branch: str
    source_dataset: str | None
    source_revision: str | None
    source_split: str | None
    source_snapshot_id: str
    canonical_schema_version: int
    population_id: str
    population_spec_version: int
    analysis_config: dict[str, Any]
    python_version: str
    package_versions: dict[str, str | None]
    source_file: str | None = None
    source_file_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "analysis_config": _canonicalize(self.analysis_config),
            "canonical_schema_version": self.canonical_schema_version,
            "created_by": self.created_by,
            "git_branch": self.git_branch,
            "git_commit": self.git_commit,
            "manifest_schema_version": self.manifest_schema_version,
            "package_versions": _canonicalize(self.package_versions),
            "population_id": self.population_id,
            "population_spec_version": self.population_spec_version,
            "python_version": self.python_version,
            "run_id": self.run_id,
            "source_dataset": self.source_dataset,
            "source_file": self.source_file,
            "source_file_sha256": self.source_file_sha256,
            "source_revision": self.source_revision,
            "source_snapshot_id": self.source_snapshot_id,
            "source_split": self.source_split,
        }

    def to_json(self) -> str:
        return _canonical_json(self.to_dict())

    @classmethod
    def from_dict(cls, values: Mapping[str, Any]) -> "RunManifest":
        manifest = cls(
            manifest_schema_version=int(values["manifest_schema_version"]),
            run_id=str(values["run_id"]),
            created_by=str(values["created_by"]),
            git_commit=str(values["git_commit"]),
            git_branch=str(values["git_branch"]),
            source_dataset=values.get("source_dataset"),
            source_revision=values.get("source_revision"),
            source_split=values.get("source_split"),
            source_snapshot_id=str(values["source_snapshot_id"]),
            canonical_schema_version=int(values["canonical_schema_version"]),
            population_id=str(values["population_id"]),
            population_spec_version=int(values["population_spec_version"]),
            analysis_config=_canonicalize(values["analysis_config"]),
            python_version=str(values["python_version"]),
            package_versions=_canonicalize(values["package_versions"]),
            source_file=values.get("source_file"),
            source_file_sha256=values.get("source_file_sha256"),
        )
        expected_source_snapshot_id = source_snapshot_id(
            SourceProvenance(
                source_dataset=manifest.source_dataset,
                source_revision=manifest.source_revision,
                source_split=manifest.source_split,
                source_file=manifest.source_file,
                source_file_sha256=manifest.source_file_sha256,
            )
        )
        if manifest.source_snapshot_id != expected_source_snapshot_id:
            raise ValueError("source_snapshot_id does not match source provenance fields")
        expected = run_id_for(
            source_snapshot=manifest.source_snapshot_id,
            canonical_schema_version=manifest.canonical_schema_version,
            population_id=manifest.population_id,
            population_spec_version=manifest.population_spec_version,
            git_commit=manifest.git_commit,
            analysis_config=manifest.analysis_config,
        )
        if manifest.manifest_schema_version != RUN_MANIFEST_SCHEMA_VERSION:
            raise ValueError("unsupported run manifest schema version")
        if manifest.run_id != expected:
            raise ValueError("run_id does not match manifest identity fields")
        return manifest

    @classmethod
    def from_json(cls, text: str) -> "RunManifest":
        return cls.from_dict(json.loads(text))


def create_run_manifest(
    *,
    source_provenance: SourceProvenance,
    population_spec: PopulationSpec,
    git_commit: str,
    git_branch: str,
    analysis_config: Mapping[str, Any] | None = None,
    created_by: str = "research-runner",
    environment: Mapping[str, Any] | None = None,
) -> RunManifest:
    """Create a deterministic manifest without I/O or machine-specific identity."""
    config = _canonicalize(analysis_config or {})
    if not isinstance(config, dict):
        raise TypeError("analysis_config must be a mapping")
    runtime = dict(environment or capture_environment())
    python_version = runtime.get("python_version")
    package_versions = runtime.get("package_versions")
    if not isinstance(python_version, str) or not isinstance(package_versions, Mapping):
        raise ValueError("environment must provide python_version and package_versions")

    snapshot = source_snapshot_id(source_provenance)
    run_id = run_id_for(
        source_snapshot=snapshot,
        canonical_schema_version=CANONICAL_BATTLE_SCHEMA_VERSION,
        population_id=population_spec.population_id,
        population_spec_version=population_spec.population_spec_version,
        git_commit=git_commit,
        analysis_config=config,
    )
    return RunManifest(
        manifest_schema_version=RUN_MANIFEST_SCHEMA_VERSION,
        run_id=run_id,
        created_by=created_by,
        git_commit=git_commit,
        git_branch=git_branch,
        source_dataset=source_provenance.source_dataset,
        source_revision=source_provenance.source_revision,
        source_split=source_provenance.source_split,
        source_snapshot_id=snapshot,
        canonical_schema_version=CANONICAL_BATTLE_SCHEMA_VERSION,
        population_id=population_spec.population_id,
        population_spec_version=population_spec.population_spec_version,
        analysis_config=config,
        python_version=python_version,
        package_versions=dict(sorted((str(key), value) for key, value in package_versions.items())),
        source_file=source_provenance.source_file,
        source_file_sha256=source_provenance.source_file_sha256,
    )
