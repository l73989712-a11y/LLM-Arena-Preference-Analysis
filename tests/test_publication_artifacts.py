from __future__ import annotations

import hashlib
import json
from dataclasses import replace
import os
from pathlib import Path

import pytest

import src.publication as publication
import src.publication_artifacts as artifacts


@pytest.fixture(scope="module")
def model() -> publication.PublicationModel:
    return publication.build_publication_model()


def _files(bundle: Path) -> dict[str, bytes]:
    return {relative: (bundle / relative).read_bytes() for relative in artifacts.ALL_BUNDLE_PATHS}


@pytest.mark.parametrize("value", ["a" * 39, "A" * 40, "g" * 40, "a" * 41, ""])
def test_producer_sha_is_explicit_and_strict(value: str) -> None:
    with pytest.raises(artifacts.PublicationArtifactError):
        artifacts.validate_producer_git_sha(value)
    assert artifacts.validate_producer_git_sha("a" * 40) == "a" * 40


def test_bundle_has_exact_files_and_inventory(model: publication.PublicationModel, tmp_path: Path) -> None:
    result = artifacts.write_publication_bundle(model, tmp_path, "a" * 40)
    assert {item.relative_to(result.bundle_path).as_posix() for item in result.bundle_path.rglob("*") if item.is_file()} == set(artifacts.ALL_BUNDLE_PATHS)
    inventory = artifacts.build_payload_inventory(result.bundle_path)
    assert tuple(item["path"] for item in inventory) == tuple(sorted(artifacts.NON_MANIFEST_PATHS))
    assert all("manifest.json" != item["path"] for item in inventory)
    assert artifacts.payload_inventory_sha256(inventory) == result.payload_inventory_sha256
    manifest = json.loads((result.bundle_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["non_manifest_payload_inventory"] == list(inventory)
    for entry in inventory:
        data = (result.bundle_path / entry["path"]).read_bytes()
        assert entry["size_bytes"] == len(data)
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()


def test_manifest_is_closed_and_identity_bound(model: publication.PublicationModel, tmp_path: Path) -> None:
    result = artifacts.write_publication_bundle(model, tmp_path, "b" * 40)
    raw = (result.bundle_path / "manifest.json").read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n")
    manifest = json.loads(raw)
    assert set(manifest) == {
        "publication_schema_version", "publication_contract_version", "publication_spec_id", "publication_spec",
        "producer_git_sha", "publication_instance_id", "payload_inventory_sha256", "source_e0_identity",
        "source_e1_identity", "source_e2_identity", "non_manifest_payload_inventory",
    }
    assert manifest["publication_spec"] == model.specification.to_dict()
    assert manifest["publication_spec_id"] == model.specification.publication_spec_id
    assert manifest["source_e0_identity"] == manifest["publication_spec"]["source_e0_identity"]
    assert manifest["source_e1_identity"] == manifest["publication_spec"]["source_e1_identity"]
    assert manifest["source_e2_identity"] == manifest["publication_spec"]["source_e2_identity"]
    preimage = {
        "publication_schema_version": 1,
        "publication_spec_id": result.publication_spec_id,
        "producer_git_sha": result.producer_git_sha,
        "payload_inventory_sha256": result.payload_inventory_sha256,
    }
    assert result.publication_instance_id == hashlib.sha256(publication.canonical_json_bytes(preimage)).hexdigest()
    assert manifest["publication_instance_id"] == result.publication_instance_id


def test_repeated_writes_are_byte_identical(model: publication.PublicationModel, tmp_path: Path) -> None:
    first = artifacts.write_publication_bundle(model, tmp_path / "one", "c" * 40)
    second = artifacts.write_publication_bundle(model, tmp_path / "two", "c" * 40)
    assert first.publication_instance_id == second.publication_instance_id
    assert first.payload_inventory_sha256 == second.payload_inventory_sha256
    first_files = _files(first.bundle_path)
    second_files = _files(second.bundle_path)
    assert first_files == second_files
    for role in publication.FIGURE_ROLES:
        relative = f"figures/{role}.png"
        assert hashlib.sha256(first_files[relative]).hexdigest() == hashlib.sha256(second_files[relative]).hexdigest()


def test_producer_sha_changes_instance_only(model: publication.PublicationModel, tmp_path: Path) -> None:
    first = artifacts.write_publication_bundle(model, tmp_path / "one", "d" * 40)
    second = artifacts.write_publication_bundle(model, tmp_path / "two", "e" * 40)
    assert first.payload_inventory_sha256 == second.payload_inventory_sha256
    assert all(_files(first.bundle_path)[path] == _files(second.bundle_path)[path] for path in artifacts.NON_MANIFEST_PATHS)
    assert first.publication_instance_id != second.publication_instance_id
    assert (first.bundle_path / "manifest.json").read_bytes() != (second.bundle_path / "manifest.json").read_bytes()


def test_existing_destination_is_refused_without_overwrite(model: publication.PublicationModel, tmp_path: Path) -> None:
    result = artifacts.write_publication_bundle(model, tmp_path, "f" * 40)
    before = _files(result.bundle_path)
    with pytest.raises(artifacts.PublicationArtifactError, match="already exists"):
        artifacts.write_publication_bundle(model, tmp_path, "f" * 40)
    assert _files(result.bundle_path) == before


def test_writer_cleans_temporary_output_on_render_failure(model: publication.PublicationModel, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise RuntimeError("render failure")

    monkeypatch.setattr(artifacts, "_render_figures", fail)
    with pytest.raises(artifacts.PublicationArtifactError, match="render failure"):
        artifacts.write_publication_bundle(model, tmp_path / "created", "1" * 40)
    assert not (tmp_path / "created").exists()


def test_closed_world_rejects_unexpected_payload(model: publication.PublicationModel, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = artifacts._render_figures

    def add_extra(model_arg: publication.PublicationModel, root: Path) -> None:
        original(model_arg, root)
        (root / "unexpected.txt").write_bytes(b"unexpected")

    monkeypatch.setattr(artifacts, "_render_figures", add_extra)
    with pytest.raises(artifacts.PublicationArtifactError, match="file set mismatch"):
        artifacts.write_publication_bundle(model, tmp_path, "2" * 40)
    assert not list(tmp_path.glob("*/manifest.json"))


def test_final_inventory_revalidation_rejects_payload_mutation(model: publication.PublicationModel, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = artifacts.build_payload_inventory
    calls = 0

    def mutate_after_first(root: Path) -> tuple[dict[str, object], ...]:
        nonlocal calls
        inventory = original(root)
        calls += 1
        if calls == 1:
            path = Path(root) / "report.md"
            path.write_bytes(path.read_bytes().replace(b"Frozen Historical", b"Altered Historical", 1))
        return inventory

    monkeypatch.setattr(artifacts, "build_payload_inventory", mutate_after_first)
    with pytest.raises(artifacts.PublicationArtifactError, match="payload changed"):
        artifacts.write_publication_bundle(model, tmp_path, "5" * 40)
    assert calls == 2
    assert not list(tmp_path.glob("*/manifest.json"))


def test_noncanonical_manifest_bytes_are_rejected(model: publication.PublicationModel, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = artifacts._write_bytes

    def alter_manifest(path: Path, data: bytes) -> None:
        altered = data[:-1] + b" \n" if path.name == "manifest.json" else data
        original(path, altered)

    monkeypatch.setattr(artifacts, "_write_bytes", alter_manifest)
    with pytest.raises(artifacts.PublicationArtifactError, match="canonical JSON"):
        artifacts.write_publication_bundle(model, tmp_path, "6" * 40)
    assert not list(tmp_path.glob("*/manifest.json"))


def test_reparse_entries_and_output_roots_fail_closed(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("target", encoding="utf-8")
    link = tmp_path / "link.txt"
    try:
        os.symlink(target, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable in this environment")
    with pytest.raises(artifacts.PublicationArtifactError, match="symlink"):
        artifacts._regular_files(tmp_path)
    with pytest.raises(artifacts.PublicationArtifactError, match="output_root"):
        artifacts.write_publication_bundle(publication.build_publication_model(), link, "7" * 40)


def test_reparse_helper_rejects_junction_like_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    entry = tmp_path / "junction"
    entry.mkdir()
    monkeypatch.setattr(artifacts, "_is_reparse", lambda path: path == entry)
    with pytest.raises(artifacts.PublicationArtifactError, match="symlink"):
        artifacts._regular_files(tmp_path)


def test_concurrent_destination_appearance_fails_without_replacement(model: publication.PublicationModel, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = artifacts._materialize_temp

    def race(temporary: Path, final_path: Path) -> None:
        final_path.mkdir()
        (final_path / "sentinel").write_bytes(b"untouched")
        raise FileExistsError("destination appeared")

    monkeypatch.setattr(artifacts, "_materialize_temp", race)
    with pytest.raises(artifacts.PublicationArtifactError, match="concurrently"):
        artifacts.write_publication_bundle(model, tmp_path, "8" * 40)
    destinations = [path for path in tmp_path.iterdir() if path.is_dir() and not path.name.startswith(".publication-v1-")]
    assert len(destinations) == 1
    assert (destinations[0] / "sentinel").read_bytes() == b"untouched"
    assert not list(tmp_path.glob(".publication-v1-*"))


def test_real_no_replace_materialization_rejects_existing_empty_directory(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "sentinel").write_bytes(b"source")
    destination.mkdir()
    with pytest.raises(artifacts.PublicationArtifactError, match="destination appeared concurrently"):
        artifacts._materialize_temp(source, destination)
    assert destination.is_dir() and not any(destination.iterdir())
    assert (source / "sentinel").read_bytes() == b"source"


def test_real_no_replace_materialization_moves_when_destination_absent(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "sentinel").write_bytes(b"source")
    artifacts._materialize_temp(source, destination)
    assert not source.exists()
    assert (destination / "sentinel").read_bytes() == b"source"


def test_unsupported_materialization_platform_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    monkeypatch.setattr(artifacts.os, "name", "unsupported")
    with pytest.raises(artifacts.PublicationArtifactError, match="unsupported"):
        artifacts._materialize_temp(source, destination)


@pytest.mark.parametrize("platform", ["darwin", "freebsd", "openbsd", "netbsd"])
def test_non_linux_posix_platforms_fail_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, platform: str) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    monkeypatch.setattr(artifacts.os, "name", "posix")
    monkeypatch.setattr(artifacts.sys, "platform", platform)
    with pytest.raises(artifacts.PublicationArtifactError, match="unsupported"):
        artifacts._materialize_temp(source, destination)
    assert source.exists() and not destination.exists()


class _FakeRename:
    def __init__(self, result: int) -> None:
        self.result = result
        self.argtypes = None
        self.restype = None
        self.called = False

    def __call__(self, *args: object) -> int:
        self.called = True
        return self.result


class _FakeLibc:
    def __init__(self, result: int) -> None:
        self.renameat2 = _FakeRename(result)


def test_linux_routing_is_unit_tested_without_linux_integration(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    fake = _FakeLibc(0)
    monkeypatch.setattr(artifacts.os, "name", "posix")
    monkeypatch.setattr(artifacts.sys, "platform", "linux")
    monkeypatch.setattr(artifacts.ctypes, "CDLL", lambda *args, **kwargs: fake)
    artifacts._materialize_temp(source, destination)
    assert fake.renameat2.called
    assert source.exists() and not destination.exists()


@pytest.mark.parametrize("error", [artifacts.errno.EEXIST, artifacts.errno.ENOSYS])
def test_linux_routing_translates_collision_and_unsupported_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: int) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    fake = _FakeLibc(-1)
    monkeypatch.setattr(artifacts.os, "name", "posix")
    monkeypatch.setattr(artifacts.sys, "platform", "linux")
    monkeypatch.setattr(artifacts.ctypes, "CDLL", lambda *args, **kwargs: fake)
    monkeypatch.setattr(artifacts.ctypes, "get_errno", lambda: error)
    with pytest.raises(artifacts.PublicationArtifactError):
        artifacts._materialize_temp(source, destination)
    assert source.exists() and not destination.exists()


def test_core_model_is_validated_before_materialization(model: publication.PublicationModel, tmp_path: Path) -> None:
    with pytest.raises(publication.PublicationError):
        broken = replace(model, report_markdown=model.report_markdown.replace("The first three", "The altered three", 1))
        artifacts.write_publication_bundle(broken, tmp_path, "3" * 40)
    assert not list(tmp_path.iterdir())


def test_cli_accepts_explicit_sha(model: publication.PublicationModel, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(artifacts, "build_publication_model", lambda: model)
    assert artifacts.main(["--output-root", str(tmp_path), "--producer-git-sha", "4" * 40]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["producer_git_sha"] == "4" * 40
    assert (tmp_path / output["publication_instance_id"] / "manifest.json").exists()
