from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

import src.formal_verifier as formal_verifier


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = REPOSITORY_ROOT / "artifacts" / "frozen" / "formal-research-v1"
SCRIPT = REPOSITORY_ROOT / "verify_frozen_bundle.py"


def _copy_bundle(tmp_path: Path) -> Path:
    target = tmp_path / "formal-research-v1"
    shutil.copytree(BUNDLE_ROOT, target)
    return target


def _write_manifest(bundle_root: Path, manifest: dict[str, object]) -> None:
    (bundle_root / "bundle_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def _refresh_inventory_entry(bundle_root: Path, relative_path: str) -> str:
    manifest_path = bundle_root / "bundle_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    path = bundle_root / "payload" / relative_path
    data = path.read_bytes()
    entry = next(item for item in manifest["files"] if item["relative_path"] == relative_path)
    entry["byte_size"] = len(data)
    entry["sha256"] = hashlib.sha256(data).hexdigest()
    canonical = json.dumps(manifest["files"], ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest["payload_inventory_sha256"] = hashlib.sha256(canonical).hexdigest()
    _write_manifest(bundle_root, manifest)
    return manifest["payload_inventory_sha256"]


def test_default_verification_passes() -> None:
    result = formal_verifier.verify_frozen_bundle()

    assert result.bundle_name == "formal-research-v1"
    assert result.payload_file_count == 73
    assert result.payload_total_bytes == 3_626_761
    assert result.payload_inventory_sha256 == "392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6"
    assert result.verified_run_count == 9
    assert result.comparative_review_verified is True
    assert result.semantic_validation_passed is True


def test_injected_bundle_root_passes(tmp_path: Path) -> None:
    assert formal_verifier.verify_frozen_bundle(_copy_bundle(tmp_path)).verified_run_count == 9


def test_whole_bundle_root_symlink_fails_when_supported(tmp_path: Path) -> None:
    bundle = _copy_bundle(tmp_path)
    link = tmp_path / "bundle-link"
    try:
        link.symlink_to(bundle, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="structure"):
        formal_verifier.verify_frozen_bundle(link)


def test_cli_passes_from_outside_repository(tmp_path: Path) -> None:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert completed.stderr == ""
    assert completed.stdout == (
        "Frozen Formal Research Bundle Verification\n"
        "bundle: formal-research-v1\n"
        "payload files: 73\n"
        "payload bytes: 3626761\n"
        "inventory SHA-256: 392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6\n"
        "source snapshot: 2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4\n"
        "runs: 9/9 verified\n"
        "comparative review: verified\n"
        "semantic validation: passed\n"
        "\n"
        "VERDICT: PASS\n"
    )


def test_verifier_does_not_import_ui_stack(tmp_path: Path) -> None:
    code = (
        "import sys; "
        "import src.formal_verifier; "
        "assert 'streamlit' not in sys.modules; "
        "assert 'matplotlib' not in sys.modules"
    )
    completed = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(REPOSITORY_ROOT)}, check=False)
    assert completed.returncode == 0


def test_one_byte_payload_tamper_fails_closed(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    path = root / "payload" / "comparative_review" / "review.json"
    data = bytearray(path.read_bytes())
    data[0] ^= 1
    path.write_bytes(data)

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="payload_inventory"):
        formal_verifier.verify_frozen_bundle(root)


def test_missing_payload_file_fails_closed(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    (root / "payload" / "comparative_review" / "review.json").unlink()

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="payload_inventory"):
        formal_verifier.verify_frozen_bundle(root)


def test_extra_payload_file_fails_closed(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    (root / "payload" / "unexpected.bin").write_bytes(b"unexpected")

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="payload_inventory"):
        formal_verifier.verify_frozen_bundle(root)


def test_manifest_metadata_tamper_fails_closed(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest = json.loads((root / "bundle_manifest.json").read_text(encoding="utf-8"))
    manifest["payload_total_bytes"] = 1
    _write_manifest(root, manifest)

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="bundle_manifest"):
        formal_verifier.verify_frozen_bundle(root)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("bundle_schema_version", True),
        ("bundle_schema_version", 1.0),
        ("payload_file_count", 73.0),
        ("payload_total_bytes", 3_626_761.0),
    ],
)
def test_manifest_scalar_types_are_strict(tmp_path: Path, key: str, value: object) -> None:
    root = _copy_bundle(tmp_path)
    manifest = json.loads((root / "bundle_manifest.json").read_text(encoding="utf-8"))
    manifest[key] = value
    _write_manifest(root, manifest)

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="bundle_manifest"):
        formal_verifier.verify_frozen_bundle(root)


def test_nested_manifest_types_are_strict(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    manifest = json.loads((root / "bundle_manifest.json").read_text(encoding="utf-8"))
    manifest["expected_analysis_inventory"][0]["valid"] = 1
    _write_manifest(root, manifest)

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="bundle_manifest"):
        formal_verifier.verify_frozen_bundle(root)


@pytest.mark.parametrize("field", ["repository", "formal_evidence_status", "frozen_run_git_shas"])
def test_producing_repository_identity_tamper_fails_closed(tmp_path: Path, field: str) -> None:
    root = _copy_bundle(tmp_path)
    manifest = json.loads((root / "bundle_manifest.json").read_text(encoding="utf-8"))
    provenance = manifest["producing_repository_identity"]
    if field == "frozen_run_git_shas":
        provenance[field] = list(reversed(provenance[field]))
    else:
        provenance[field] = "tampered"
    _write_manifest(root, manifest)

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="bundle_manifest"):
        formal_verifier.verify_frozen_bundle(root)


def test_malformed_bundle_manifest_fails_closed(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    (root / "bundle_manifest.json").write_text("{", encoding="utf-8")

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="bundle_manifest"):
        formal_verifier.verify_frozen_bundle(root)


def test_corrupt_artifact_reaches_existing_semantic_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _copy_bundle(tmp_path)
    relative = next(path for path in (root / "payload").rglob("bootstrap_scores.npz")).relative_to(root / "payload").as_posix()
    path = root / "payload" / relative
    data = bytearray(path.read_bytes())
    data[0] ^= 1
    path.write_bytes(data)
    digest = _refresh_inventory_entry(root, relative)
    monkeypatch.setattr(formal_verifier, "EXPECTED_PAYLOAD_INVENTORY_SHA256", digest)

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="semantic_validation"):
        formal_verifier.verify_frozen_bundle(root)


def test_source_identity_tamper_reaches_existing_semantic_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _copy_bundle(tmp_path)
    run_id = formal_verifier.FROZEN_RUNS[0].run_id
    run_root = root / "payload" / run_id
    manifest_path = run_root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_snapshot_id"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    artifact_path = run_root / "artifact_manifest.json"
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    data = manifest_path.read_bytes()
    artifact["files"]["manifest.json"] = {"size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    artifact_path.write_text(json.dumps(artifact, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    _refresh_inventory_entry(root, f"{run_id}/manifest.json")
    digest = _refresh_inventory_entry(root, f"{run_id}/artifact_manifest.json")
    monkeypatch.setattr(formal_verifier, "EXPECTED_PAYLOAD_INVENTORY_SHA256", digest)

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="semantic_validation"):
        formal_verifier.verify_frozen_bundle(root)


def test_comparative_review_mismatch_reaches_existing_semantic_authority(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _copy_bundle(tmp_path)
    path = root / "payload" / "comparative_review" / "review.json"
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(data)
    digest = _refresh_inventory_entry(root, "comparative_review/review.json")
    monkeypatch.setattr(formal_verifier, "EXPECTED_PAYLOAD_INVENTORY_SHA256", digest)

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="semantic_validation"):
        formal_verifier.verify_frozen_bundle(root)


def test_symlink_payload_substitution_fails_when_supported(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    target = root / "payload" / formal_verifier.FROZEN_RUNS[0].run_id / "point_estimate.json"
    replacement = root / "payload" / formal_verifier.FROZEN_RUNS[0].run_id / "replacement.json"
    target.unlink()
    try:
        replacement.symlink_to(root / "payload" / formal_verifier.FROZEN_RUNS[0].run_id / "manifest.json")
        target.symlink_to(replacement)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(formal_verifier.FrozenBundleVerificationError, match="payload_inventory"):
        formal_verifier.verify_frozen_bundle(root)


def test_verification_does_not_write_or_infer(tmp_path: Path) -> None:
    root = _copy_bundle(tmp_path)
    before = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}
    formal_verifier.verify_frozen_bundle(root)
    after = {path.relative_to(root): path.read_bytes() for path in root.rglob("*") if path.is_file()}

    assert before == after
    source = (REPOSITORY_ROOT / "src" / "formal_verifier.py").read_text(encoding="utf-8")
    assert "execute_formal_run" not in source
    assert "run_bootstrap" not in source
    assert "urlopen" not in source


def test_cli_maps_expected_failure_to_exit_one(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import verify_frozen_bundle as cli

    monkeypatch.setattr(cli, "verify_frozen_bundle", lambda: (_ for _ in ()).throw(formal_verifier.FrozenBundleVerificationError("payload_inventory", "tampered")))
    assert cli.main() == 1
    output = capsys.readouterr().out
    assert "VERDICT: FAIL" in output
    assert "stage: payload_inventory" in output


def test_cli_maps_unexpected_failure_to_exit_two(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import verify_frozen_bundle as cli

    monkeypatch.setattr(cli, "verify_frozen_bundle", lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cli.main() == 2
    output = capsys.readouterr().out
    assert "VERDICT: ERROR" in output
    assert "internal verifier error" in output
