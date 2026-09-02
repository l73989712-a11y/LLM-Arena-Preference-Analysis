"""Adversarial and happy-path tests for the independent publication verifier."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
import shutil

import pytest

import src.publication as publication
import src.publication_artifacts as producer
from src.publication_verifier import PublicationVerificationError, verify_publication_bundle


@pytest.fixture(scope="module")
def model() -> publication.PublicationModel:
    return publication.build_publication_model()


def _bundle(model: publication.PublicationModel, root: Path, sha: str = "a" * 40) -> Path:
    return producer.write_publication_bundle(model, root, sha).bundle_path


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"


def _expect_fail(path: Path, stage: str | None = None) -> None:
    with pytest.raises(PublicationVerificationError) as exc:
        verify_publication_bundle(path)
    if stage is not None:
        assert exc.value.stage == stage


def _rebind_bundle(bundle: Path, *, spec: dict | None = None) -> Path:
    """Rebind a mutated fixture without using producer identity helpers."""
    manifest = _json(bundle / "manifest.json")
    if spec is not None:
        manifest["publication_spec"] = spec
        manifest["publication_spec_id"] = hashlib.sha256(_canonical(spec)).hexdigest()
        manifest["source_e0_identity"] = spec["source_e0_identity"]
        manifest["source_e1_identity"] = spec["source_e1_identity"]
        manifest["source_e2_identity"] = spec["source_e2_identity"]
    entries = []
    for relative in sorted(producer.NON_MANIFEST_PATHS):
        data = (bundle / relative).read_bytes()
        entries.append({"path": relative, "size_bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    manifest["non_manifest_payload_inventory"] = entries
    inventory_hash = hashlib.sha256(_canonical(entries)).hexdigest()
    manifest["payload_inventory_sha256"] = inventory_hash
    preimage = {
        "publication_schema_version": 1,
        "publication_spec_id": manifest["publication_spec_id"],
        "producer_git_sha": manifest["producer_git_sha"],
        "payload_inventory_sha256": inventory_hash,
    }
    instance_id = hashlib.sha256(_canonical(preimage)).hexdigest()
    manifest["publication_instance_id"] = instance_id
    (bundle / "manifest.json").write_bytes(_canonical(manifest))
    destination = bundle.with_name(instance_id)
    if destination != bundle:
        bundle.rename(destination)
    return destination


def _mutate_json(bundle: Path, name: str, mutate) -> Path:
    document = _json(bundle / name)
    mutate(document)
    (bundle / name).write_bytes(_canonical(document))
    return _rebind_bundle(bundle)


def test_valid_bundle_passes_independently(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    result = verify_publication_bundle(bundle)
    assert result.publication_spec_id == "62503b0a94b7658c6c0b48b8b9d9b7e43df2e963039b999d9a87a2af760ba400"
    assert result.producer_git_sha == "a" * 40


def test_verifier_source_does_not_call_producer_or_writer() -> None:
    source = Path("src/publication_verifier.py").read_text(encoding="utf-8")
    assert "from src.publication import" not in source
    assert "from src.publication_artifacts import" not in source
    assert "build_publication_model(" not in source
    assert "write_publication_bundle(" not in source


def test_payload_byte_tamper_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    path = bundle / "tables.json"
    path.write_bytes(path.read_bytes() + b" ")
    _expect_fail(bundle)


def test_manifest_forgery_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    manifest = _json(bundle / "manifest.json")
    manifest["publication_spec_id"] = "0" * 64
    (bundle / "manifest.json").write_bytes(_canonical(manifest))
    _expect_fail(bundle, "manifest")


def test_manifest_noncanonical_bytes_fail(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    raw = (bundle / "manifest.json").read_bytes()
    (bundle / "manifest.json").write_bytes(raw + b"\n")
    _expect_fail(bundle, "json")


def test_duplicate_manifest_key_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    raw = (bundle / "manifest.json").read_bytes()
    (bundle / "manifest.json").write_bytes(raw[:-2] + b',"publication_schema_version":1}\n')
    _expect_fail(bundle, "json")


def test_tables_json_noncanonical_bytes_fail(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    raw = (bundle / "tables.json").read_bytes()
    (bundle / "tables.json").write_bytes(b" " + raw)
    _expect_fail(bundle, "json")


@pytest.mark.parametrize("field", ["producer_git_sha", "publication_schema_version"])
def test_manifest_shape_forgery_fails(model: publication.PublicationModel, tmp_path: Path, field: str) -> None:
    bundle = _bundle(model, tmp_path)
    manifest = _json(bundle / "manifest.json")
    manifest[field] = "bad" if field == "producer_git_sha" else 2
    (bundle / "manifest.json").write_bytes(_canonical(manifest))
    _expect_fail(bundle, "manifest")


def test_manifest_extra_key_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    manifest = _json(bundle / "manifest.json")
    manifest["extra"] = True
    (bundle / "manifest.json").write_bytes(_canonical(manifest))
    _expect_fail(bundle, "manifest")


def test_self_consistent_forged_spec_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    spec = deepcopy(_json(bundle / "manifest.json")["publication_spec"])
    spec["source_e0_identity"]["dataset"] = "forged/dataset"
    bundle = _rebind_bundle(bundle, spec=spec)
    _expect_fail(bundle, "manifest")


@pytest.mark.parametrize(
    ("identity", "field", "value"),
    [
        ("source_e0_identity", "revision", "f" * 40),
        ("source_e1_identity", "primary_run_id", "f" * 64),
        ("source_e2_identity", "derivation_spec_id", "f" * 64),
    ],
)
def test_self_consistent_source_authority_forgery_fails(model: publication.PublicationModel, tmp_path: Path, identity: str, field: str, value: str) -> None:
    bundle = _bundle(model, tmp_path)
    spec = deepcopy(_json(bundle / "manifest.json")["publication_spec"])
    spec[identity][field] = value
    bundle = _rebind_bundle(bundle, spec=spec)
    _expect_fail(bundle, "manifest")


def test_wrong_source_identity_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    manifest = _json(bundle / "manifest.json")
    manifest["source_e2_identity"]["derivation_spec_id"] = "f" * 64
    (bundle / "manifest.json").write_bytes(_canonical(manifest))
    _expect_fail(bundle, "manifest")


def test_tables_value_tamper_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    tables = _json(bundle / "tables.json")
    tables["tables"][0]["rows"][0]["values"]["point_rank"] = 99
    (bundle / "tables.json").write_bytes(_canonical(tables))
    _expect_fail(bundle, "tables")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda doc: doc["tables"][1]["rows"].__setitem__(0, doc["tables"][1]["rows"][1]),
        lambda doc: doc["tables"][2]["rows"].__setitem__(0, {**doc["tables"][2]["rows"][0], "row_id": "model:forged"}),
        lambda doc: doc["tables"][3]["rows"].reverse(),
    ],
)
def test_self_consistent_nonprimary_table_shape_forgery_fails(model: publication.PublicationModel, tmp_path: Path, mutation) -> None:
    bundle = _bundle(model, tmp_path)
    bundle = _mutate_json(bundle, "tables.json", mutation)
    _expect_fail(bundle, "tables")


def test_self_consistent_primary_numeric_forgery_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    bundle = _mutate_json(bundle, "tables.json", lambda doc: doc["tables"][0]["rows"][0]["values"].__setitem__("point_score", 0.0))
    _expect_fail(bundle, "tables")


def test_self_consistent_row_claim_membership_forgery_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    bundle = _mutate_json(bundle, "tables.json", lambda doc: doc["tables"][0]["rows"][0]["claim_ids"].append("s6.rank_comparison"))
    _expect_fail(bundle, "tables")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda doc: doc["claims"][3]["source_pointers"][0].__setitem__("field", "latent_scores"),
        lambda doc: doc["claims"][3]["transform_chain"].__setitem__(0, "identity.v1"),
        lambda doc: doc["claims"][3]["scientific_values"][0].__setitem__("point_rank", 99),
        lambda doc: doc["claims"][3]["render_bindings"][0].__setitem__("expected_value", 99),
        lambda doc: doc["claims"][3]["render_bindings"][-1].__setitem__("section_id", "uncertainty"),
        lambda doc: doc["claims"][3]["render_bindings"].append({**doc["claims"][3]["render_bindings"][0]}),
    ],
)
def test_self_consistent_traceability_forgery_fails(model: publication.PublicationModel, tmp_path: Path, mutation) -> None:
    bundle = _bundle(model, tmp_path)
    bundle = _mutate_json(bundle, "traceability.json", mutation)
    _expect_fail(bundle, "traceability")


def test_traceability_value_tamper_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    trace = _json(bundle / "traceability.json")
    trace["claims"][0]["scientific_values"][0] = "tampered"
    (bundle / "traceability.json").write_bytes(_canonical(trace))
    _expect_fail(bundle, "traceability")


def test_report_interpretation_tamper_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    path = bundle / "report.md"
    path.write_text(path.read_text(encoding="utf-8").replace("estimated preference under", "objective capability under", 1), encoding="utf-8")
    _expect_fail(bundle, "report")


def test_self_consistent_report_top_three_forgery_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    path = bundle / "report.md"
    path.write_text(path.read_text(encoding="utf-8").replace("first three Primary", "first forged Primary", 1), encoding="utf-8")
    bundle = _rebind_bundle(bundle)
    _expect_fail(bundle, "report")


def test_self_consistent_report_table_forgery_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    path = bundle / "report.md"
    path.write_text(path.read_text(encoding="utf-8").replace("Point rank", "Forged rank", 1), encoding="utf-8")
    bundle = _rebind_bundle(bundle)
    _expect_fail(bundle, "report")


def test_self_consistent_report_anchor_forgery_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    path = bundle / "report.md"
    report = path.read_text(encoding="utf-8")
    anchor = "<!-- publication-claim:primary.top_three -->"
    report = report.replace(anchor, "", 1)
    limitation = report.index("<!-- publication-section:limitations -->")
    report = report[:limitation] + anchor + "\n\n" + report[limitation:]
    path.write_text(report, encoding="utf-8")
    bundle = _rebind_bundle(bundle)
    _expect_fail(bundle, "report")


@pytest.mark.parametrize("drift", [
    "The evidence establishes current model quality.",
    "The evidence supports a causal interpretation.",
])
def test_self_consistent_interpretation_drift_fails(model: publication.PublicationModel, tmp_path: Path, drift: str) -> None:
    bundle = _bundle(model, tmp_path)
    path = bundle / "report.md"
    report = path.read_text(encoding="utf-8")
    marker = "<!-- publication-section:limitations -->"
    position = report.index(marker)
    report = report[:position] + drift + "\n\n" + report[position:]
    path.write_text(report, encoding="utf-8")
    bundle = _rebind_bundle(bundle)
    _expect_fail(bundle, "report")


@pytest.mark.parametrize("field", ["phase3_spec_type", "transform_id", "source_claim_ids", "figure_role", "output_path"])
def test_self_consistent_figure_binding_forgery_fails(model: publication.PublicationModel, tmp_path: Path, field: str) -> None:
    bundle = _bundle(model, tmp_path)
    def mutate(doc):
        binding = doc["figure_bindings"][0]
        if field == "source_claim_ids":
            binding[field] = ["s6.rank_comparison"]
        elif field == "figure_role":
            binding[field] = "wrong"
        elif field == "output_path":
            binding[field] = "figures/wrong.png"
        else:
            binding[field] = "forged"
    bundle = _mutate_json(bundle, "traceability.json", mutate)
    _expect_fail(bundle, "figures")


def test_raw_png_corruption_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    path = bundle / "figures" / "primary_preference.png"
    data = bytearray(path.read_bytes())
    data[-1] ^= 1
    path.write_bytes(bytes(data))
    _expect_fail(bundle, "inventory")


def test_closed_world_extra_file_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    (bundle / "unexpected.txt").write_text("x", encoding="utf-8")
    _expect_fail(bundle, "filesystem")


def test_closed_world_missing_file_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    (bundle / "tables.json").unlink()
    _expect_fail(bundle, "filesystem")


def test_directory_name_identity_fails(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    renamed = bundle.with_name("0" * 64)
    bundle.rename(renamed)
    _expect_fail(renamed, "identity")


def test_symlink_entry_fails_when_supported(model: publication.PublicationModel, tmp_path: Path) -> None:
    bundle = _bundle(model, tmp_path)
    link = bundle / "link"
    try:
        link.symlink_to(bundle / "report.md")
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation unavailable")
    _expect_fail(bundle, "filesystem")


def test_cli_module_reports_pass(model: publication.PublicationModel, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    bundle = _bundle(model, tmp_path)
    import verify_publication_bundle as cli
    assert cli.main([str(bundle)]) == 0
    assert "VERDICT: PASS" in capsys.readouterr().out
