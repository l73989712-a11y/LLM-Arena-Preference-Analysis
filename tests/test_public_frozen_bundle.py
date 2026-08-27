from __future__ import annotations

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import formal_app
from src.formal_results import DEFAULT_FROZEN_ARTIFACT_ROOT, load_frozen_formal_research


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_ROOT = REPOSITORY_ROOT / DEFAULT_FROZEN_ARTIFACT_ROOT
BUNDLE_ROOT = PAYLOAD_ROOT.parent


def _payload_inventory(root: Path) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        data = path.read_bytes()
        entries.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "byte_size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    return entries


def test_manifest_matches_the_complete_tracked_payload() -> None:
    manifest = json.loads((BUNDLE_ROOT / "bundle_manifest.json").read_text(encoding="utf-8"))
    declared = manifest["files"]
    actual = _payload_inventory(PAYLOAD_ROOT)

    assert manifest["payload_file_count"] == 73
    assert manifest["payload_total_bytes"] == 3_626_761
    assert len(declared) == len(actual) == 73
    assert [entry["relative_path"] for entry in declared] == [entry["relative_path"] for entry in actual]
    assert sum(entry["byte_size"] for entry in actual) == 3_626_761
    for declared_entry, actual_entry in zip(declared, actual):
        assert declared_entry["relative_path"] == actual_entry["relative_path"]
        assert declared_entry["byte_size"] == actual_entry["byte_size"]
        assert declared_entry["sha256"] == actual_entry["sha256"]

    canonical = json.dumps(declared, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    assert hashlib.sha256(canonical).hexdigest() == manifest["payload_inventory_sha256"]

    review = PAYLOAD_ROOT / "comparative_review" / "review.json"
    assert review.stat().st_size == 89_996
    assert hashlib.sha256(review.read_bytes()).hexdigest() == "452192dabbb8e8ad428a023ab8bb78052688965473a2736c5be352d021f26ffa"


def test_default_loader_consumes_the_tracked_frozen_payload() -> None:
    bundle = load_frozen_formal_research()
    assert len(bundle.runs) == 9
    assert len(bundle.comparative_review["artifact_inventory"]) == 9


def test_default_loader_is_independent_of_current_working_directory(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    bundle = load_frozen_formal_research()

    assert Path.cwd() == tmp_path
    assert len(bundle.runs) == 9
    assert len(bundle.comparative_review["artifact_inventory"]) == 9


def test_default_formal_runtime_consumes_the_tracked_frozen_payload() -> None:
    runtime = formal_app.build_runtime_explorer()
    try:
        assert len(runtime.explorer.primary.rows) == 20
    finally:
        formal_app._close_runtime_figures(runtime)
