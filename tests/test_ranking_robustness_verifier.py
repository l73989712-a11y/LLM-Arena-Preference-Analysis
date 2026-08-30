from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from src.formal_results import FROZEN_RUNS
from src.formal_results import FrozenResultsError
from src.formal_verifier import FrozenBundleVerificationError
from src.ranking_robustness import canonical_json_bytes
from src.ranking_robustness_artifacts import FORMAL_ARTIFACT_FILENAMES
from src.ranking_robustness_producer import produce_ranking_robustness_artifact_instance
import src.ranking_robustness_verifier as verifier
from src.ranking_robustness_verifier import (
    FORMAL_ARTIFACT_INSTANCE_ID,
    FORMAL_DERIVATION_SPEC_ID,
    FORMAL_PRODUCER_GIT_SHA,
    RankingRobustnessVerificationError,
    verify_ranking_robustness_artifact,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPOSITORY_ROOT / "verify_ranking_robustness.py"


@pytest.fixture(scope="module")
def valid_instance(tmp_path_factory: pytest.TempPathFactory) -> Path:
    parent = tmp_path_factory.mktemp("valid-e2")
    return produce_ranking_robustness_artifact_instance(
        output_parent=parent,
        producer_git_sha=FORMAL_PRODUCER_GIT_SHA,
    ).instance_path


def _copy_instance(valid_instance: Path, tmp_path: Path, name: str = "instance") -> Path:
    target = tmp_path / name
    shutil.copytree(valid_instance, target)
    return target


def _read_json(root: Path, filename: str) -> dict[str, object]:
    return json.loads((root / filename).read_text(encoding="utf-8"))


def _write_json(root: Path, filename: str, value: object, *, newline: bytes = b"\n") -> None:
    (root / filename).write_bytes(canonical_json_bytes(value) + newline)


def _refresh_inventory(root: Path) -> None:
    manifest = _read_json(root, "manifest.json")
    entries = []
    for filename in sorted(name for name in FORMAL_ARTIFACT_FILENAMES if name != "manifest.json"):
        data = (root / filename).read_bytes()
        entries.append({"path": filename, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest["artifacts"] = entries
    manifest["e2_payload_inventory_sha256"] = hashlib.sha256(canonical_json_bytes(entries)).hexdigest()
    _write_json(root, "manifest.json", manifest)


def _tamper_record(root: Path, filename: str, mutate, *, refresh: bool = True) -> None:
    document = _read_json(root, filename)
    mutate(document["records"])
    _write_json(root, filename, document)
    if refresh:
        _refresh_inventory(root)


def test_valid_real_e2_instance_is_accepted(valid_instance: Path) -> None:
    result = verify_ranking_robustness_artifact(valid_instance)
    assert result.artifact_instance_id == FORMAL_ARTIFACT_INSTANCE_ID
    assert result.derivation_spec_id == FORMAL_DERIVATION_SPEC_ID
    assert result.producer_git_sha == FORMAL_PRODUCER_GIT_SHA
    assert result.artifact_count == 7
    assert result.run_count == 9
    assert result.model_count == 20


def test_verifier_does_not_import_or_call_t4c_producer() -> None:
    source = (REPOSITORY_ROOT / "src" / "ranking_robustness_verifier.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = [alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names]
    imported += [alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names]
    assert not any("ranking_robustness_producer" in name for name in imported)
    assert "derive_ranking_robustness_e2" not in source
    assert "produce_ranking_robustness_artifact_instance" not in source


def test_frozen_e1_expected_verification_failure_stops_before_loader(valid_instance: Path) -> None:
    called = False

    def fail_verifier() -> None:
        raise FrozenBundleVerificationError("payload_inventory", "tampered")

    def loader():
        nonlocal called
        called = True
        raise AssertionError("loader must not run")

    with pytest.raises(RankingRobustnessVerificationError, match="frozen E1 verification failed"):
        verify_ranking_robustness_artifact(valid_instance, _verifier=fail_verifier, _loader=loader)
    assert not called


def test_frozen_e1_loader_expected_failure_is_classified(valid_instance: Path) -> None:
    def loader():
        raise FrozenResultsError("frozen results are invalid")

    with pytest.raises(RankingRobustnessVerificationError, match="frozen E1 loading failed"):
        verify_ranking_robustness_artifact(valid_instance, _verifier=lambda: None, _loader=loader)


def test_unexpected_e1_verifier_failure_remains_unexpected(valid_instance: Path) -> None:
    with pytest.raises(RuntimeError, match="boom"):
        verify_ranking_robustness_artifact(
            valid_instance,
            _verifier=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
            _loader=lambda: pytest.fail("loader must not run"),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        lambda root: _tamper_record(root, "top_k.json", lambda records: records[0].update(frequency=0.123456)),
        lambda root: _tamper_record(root, "top_k.json", lambda records: records[0].update(run_id=FROZEN_RUNS[1].run_id)),
        lambda root: _tamper_record(root, "top_k.json", lambda records: records.pop()),
        lambda root: _tamper_record(root, "top_k.json", lambda records: records.append(dict(records[-1]))),
        lambda root: _tamper_record(root, "top_k.json", lambda records: records.reverse()),
        lambda root: _tamper_record(root, "top_k.json", lambda records: records[0].update(metric="rank_distributions")),
    ],
)
def test_metric_tampering_is_rejected(valid_instance: Path, tmp_path: Path, mutation) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    mutation(root)
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


@pytest.mark.parametrize(
    "manifest_mutation",
    [
        lambda manifest: manifest.update(producer_git_sha="a" * 40),
        lambda manifest: manifest.update(derivation_spec_id="a" * 64),
        lambda manifest: manifest.update(artifact_instance_id="b" * 64),
        lambda manifest: manifest.update(e2_payload_inventory_sha256="c" * 64),
        lambda manifest: manifest["artifacts"][0].update(size_bytes=1),
        lambda manifest: manifest.update(unexpected_field=True),
    ],
)
def test_manifest_tampering_is_rejected(valid_instance: Path, tmp_path: Path, manifest_mutation) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    manifest = _read_json(root, "manifest.json")
    manifest_mutation(manifest)
    _write_json(root, "manifest.json", manifest)
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


def test_metric_extra_field_is_rejected(valid_instance: Path, tmp_path: Path) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    document = _read_json(root, "top_k.json")
    document["records"][0]["unexpected"] = True
    _write_json(root, "top_k.json", document)
    _refresh_inventory(root)
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


def test_metric_envelope_identity_tamper_is_rejected(valid_instance: Path, tmp_path: Path) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    document = _read_json(root, "top_k.json")
    document["artifact_instance_id"] = "a" * 64
    _write_json(root, "top_k.json", document)
    _refresh_inventory(root)
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


def test_manifest_bool_int_coercion_is_rejected(valid_instance: Path, tmp_path: Path) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    manifest = _read_json(root, "manifest.json")
    manifest["artifact_schema_version"] = True
    _write_json(root, "manifest.json", manifest)
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


def test_metric_envelope_bool_int_coercion_is_rejected(valid_instance: Path, tmp_path: Path) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    document = _read_json(root, "top_k.json")
    document["metric_schema_version"] = True
    _write_json(root, "top_k.json", document)
    _refresh_inventory(root)
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


@pytest.mark.parametrize("replacement", [True, 1.0])
def test_record_integer_type_coercion_is_rejected(valid_instance: Path, tmp_path: Path, replacement: object) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    document = _read_json(root, "rank_distributions.json")
    document["records"][0]["rank"] = replacement
    _write_json(root, "rank_distributions.json", document)
    _refresh_inventory(root)
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


@pytest.mark.parametrize("operation", ["extra", "missing"])
def test_exact_seven_file_gate(valid_instance: Path, tmp_path: Path, operation: str) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    if operation == "extra":
        (root / "unexpected.json").write_bytes(b"{}\n")
    else:
        (root / "top_k.json").unlink()
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


@pytest.mark.parametrize("style", ["pretty", "crlf", "double_lf", "payload_byte"])
def test_noncanonical_or_byte_tampered_json_is_rejected(valid_instance: Path, tmp_path: Path, style: str) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    path = root / "top_k.json"
    if style == "pretty":
        value = json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8", newline="\n")
    elif style == "crlf":
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    elif style == "double_lf":
        path.write_bytes(path.read_bytes() + b"\n")
    else:
        data = bytearray(path.read_bytes())
        data[0] ^= 1
        path.write_bytes(data)
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


def test_inventory_hash_change_is_rejected(valid_instance: Path, tmp_path: Path) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    manifest = _read_json(root, "manifest.json")
    manifest["e2_payload_inventory_sha256"] = "a" * 64
    _write_json(root, "manifest.json", manifest)
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(root)


def test_cli_valid_instance_returns_zero(valid_instance: Path) -> None:
    completed = subprocess.run([sys.executable, str(SCRIPT), str(valid_instance)], cwd=Path.cwd(), capture_output=True, text=True, check=False)
    assert completed.returncode == 0
    assert "VERDICT: PASS" in completed.stdout
    assert completed.stderr == ""


def test_cli_expected_failure_returns_one(valid_instance: Path, tmp_path: Path) -> None:
    root = _copy_instance(valid_instance, tmp_path)
    (root / "top_k.json").unlink()
    completed = subprocess.run([sys.executable, str(SCRIPT), str(root)], cwd=Path.cwd(), capture_output=True, text=True, check=False)
    assert completed.returncode == 1
    assert "VERDICT: FAIL" in completed.stdout


def test_cli_expected_e1_failure_returns_one(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import verify_ranking_robustness as cli

    monkeypatch.setattr(
        cli,
        "verify_ranking_robustness_artifact",
        lambda _path: (_ for _ in ()).throw(RankingRobustnessVerificationError("frozen E1 verification failed")),
    )
    assert cli.main(["unused"]) == 1
    assert "VERDICT: FAIL" in capsys.readouterr().out


def test_symlinked_artifact_root_is_rejected_when_supported(valid_instance: Path, tmp_path: Path) -> None:
    link = tmp_path / "artifact-link"
    try:
        link.symlink_to(valid_instance, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    with pytest.raises(RankingRobustnessVerificationError):
        verify_ranking_robustness_artifact(link)


def test_cli_missing_path_returns_one(tmp_path: Path) -> None:
    completed = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "missing")], cwd=Path.cwd(), capture_output=True, text=True, check=False)
    assert completed.returncode == 1


def test_cli_unexpected_failure_returns_two(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import verify_ranking_robustness as cli

    monkeypatch.setattr(cli, "verify_ranking_robustness_artifact", lambda _path: (_ for _ in ()).throw(RuntimeError("boom")))
    assert cli.main(["unused"]) == 2
    assert "VERDICT: ERROR" in capsys.readouterr().out
