"""Deterministic Phase 6 publication bundle writer.

The writer persists only the accepted in-memory publication model.  It does
not acquire source data, run inference, or implement independent verification.
"""

from __future__ import annotations

import argparse
import ctypes
from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
from typing import Any, Mapping

from src.formal_figures import (
    render_heterogeneity_figure,
    render_primary_figure,
    render_rank_uncertainty_figure,
    render_robustness_figure,
)
from src.publication import (
    FIGURE_ROLES,
    PUBLICATION_CONTRACT_VERSION,
    PUBLICATION_SCHEMA_VERSION,
    PublicationError,
    PublicationModel,
    build_publication_model,
    canonical_json_bytes,
    render_report_markdown,
    serialize_tables,
    serialize_traceability,
    validate_publication_model_consistency,
)


_PRODUCER_SHA = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
NON_MANIFEST_PATHS = (
    "report.md",
    "tables.json",
    "traceability.json",
    "figures/primary_preference.png",
    "figures/rank_uncertainty.png",
    "figures/robustness_ranks.png",
    "figures/s6_heterogeneity.png",
)
ALL_BUNDLE_PATHS = ("manifest.json",) + NON_MANIFEST_PATHS


class PublicationArtifactError(PublicationError):
    """Raised when a publication bundle cannot be safely materialized."""


@dataclass(frozen=True)
class PublicationArtifactResult:
    publication_instance_id: str
    publication_spec_id: str
    producer_git_sha: str
    payload_inventory_sha256: str
    bundle_path: Path


def validate_producer_git_sha(value: str) -> str:
    if not isinstance(value, str) or _PRODUCER_SHA.fullmatch(value) is None:
        raise PublicationArtifactError("producer_git_sha must be exactly 40 lowercase hexadecimal characters")
    return value


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_reparse(path: Path) -> bool:
    """Detect links and Windows reparse points without following them."""
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction):
        try:
            if is_junction():
                return True
        except OSError:
            return True
    try:
        attributes = os.lstat(path).st_file_attributes
    except FileNotFoundError:
        return False
    except AttributeError:
        return False
    except OSError:
        return True
    return bool(attributes & 0x40000000)  # FILE_ATTRIBUTE_REPARSE_POINT


def _regular_files(root: Path) -> set[str]:
    if _is_reparse(root) or not root.is_dir():
        raise PublicationArtifactError("bundle root must be a regular directory")
    files: set[str] = set()
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if _is_reparse(path):
            raise PublicationArtifactError(f"symlink is not permitted in bundle: {relative}")
        if path.is_dir():
            if relative != "figures":
                raise PublicationArtifactError(f"unexpected bundle directory: {relative}")
        elif path.is_file():
            files.add(relative)
        else:
            raise PublicationArtifactError(f"non-regular bundle entry: {relative}")
    return files


def _validate_closed_world(root: Path, include_manifest: bool) -> None:
    expected = set(ALL_BUNDLE_PATHS if include_manifest else NON_MANIFEST_PATHS)
    actual = _regular_files(root)
    if actual != expected:
        raise PublicationArtifactError(f"bundle file set mismatch: expected {sorted(expected)}, got {sorted(actual)}")


def build_payload_inventory(root: str | Path) -> tuple[dict[str, Any], ...]:
    """Return the sorted inventory for the exact seven non-manifest files."""
    root_path = Path(root)
    actual = _regular_files(root_path)
    if actual not in (set(NON_MANIFEST_PATHS), set(ALL_BUNDLE_PATHS)):
        raise PublicationArtifactError("bundle file set is not a valid publication payload")
    inventory = []
    for relative in NON_MANIFEST_PATHS:
        path = root_path / Path(relative)
        data = path.read_bytes()
        inventory.append({"path": relative, "size_bytes": len(data), "sha256": _sha256(data)})
    inventory.sort(key=lambda item: item["path"])
    return tuple(inventory)


def payload_inventory_sha256(inventory: Any) -> str:
    if not isinstance(inventory, (list, tuple)) or len(inventory) != len(NON_MANIFEST_PATHS):
        raise PublicationArtifactError("payload inventory must contain exactly seven entries")
    normalized = []
    seen: set[str] = set()
    for entry in inventory:
        if not isinstance(entry, Mapping) or set(entry) != {"path", "size_bytes", "sha256"}:
            raise PublicationArtifactError("invalid payload inventory entry")
        path = entry["path"]
        if not isinstance(path, str) or path not in NON_MANIFEST_PATHS or path in seen or Path(path).is_absolute() or "\\" in path or any(part in {".", ".."} for part in Path(path).parts):
            raise PublicationArtifactError("invalid payload inventory path")
        if isinstance(entry["size_bytes"], bool) or not isinstance(entry["size_bytes"], int) or entry["size_bytes"] < 0:
            raise PublicationArtifactError("invalid payload inventory size")
        if not isinstance(entry["sha256"], str) or _SHA256.fullmatch(entry["sha256"]) is None:
            raise PublicationArtifactError("invalid payload inventory hash")
        seen.add(path)
        normalized.append({"path": path, "size_bytes": entry["size_bytes"], "sha256": entry["sha256"]})
    if tuple(item["path"] for item in normalized) != tuple(sorted(seen)):
        raise PublicationArtifactError("payload inventory paths must be lexicographically sorted")
    return _sha256(canonical_json_bytes(normalized))


def publication_instance_id(publication_spec_id: str, producer_git_sha: str, inventory_hash: str) -> str:
    if not isinstance(publication_spec_id, str) or _SHA256.fullmatch(publication_spec_id) is None:
        raise PublicationArtifactError("publication_spec_id must be a lowercase SHA-256")
    validate_producer_git_sha(producer_git_sha)
    if not isinstance(inventory_hash, str) or _SHA256.fullmatch(inventory_hash) is None:
        raise PublicationArtifactError("payload_inventory_sha256 must be a lowercase SHA-256")
    preimage = {
        "publication_schema_version": PUBLICATION_SCHEMA_VERSION,
        "publication_spec_id": publication_spec_id,
        "producer_git_sha": producer_git_sha,
        "payload_inventory_sha256": inventory_hash,
    }
    return _sha256(canonical_json_bytes(preimage))


def _write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _render_figures(model: PublicationModel, root: Path) -> None:
    (root / "figures").mkdir()
    specs = (
        ("primary_preference", model.figures["primary_preference"], render_primary_figure),
        ("rank_uncertainty", model.figures["rank_uncertainty"], render_rank_uncertainty_figure),
        ("robustness_ranks", model.figures["robustness_ranks"], render_robustness_figure),
        ("s6_heterogeneity", model.figures["s6_heterogeneity"], render_heterogeneity_figure),
    )
    for role, spec, renderer in specs:
        figure = renderer(spec)
        try:
            # Explicit metadata avoids renderer defaults becoming identity-bearing.
            figure.savefig(root / "figures" / f"{role}.png", format="png", metadata={"Software": "phase6-publication-v1"})
        finally:
            import matplotlib.pyplot as plt

            plt.close(figure)


def _validate_manifest(manifest: Mapping[str, Any], model: PublicationModel, inventory: tuple[dict[str, Any], ...], inventory_hash: str, producer_sha: str, instance_id: str) -> None:
    expected_keys = {"publication_schema_version", "publication_contract_version", "publication_spec_id", "publication_spec", "producer_git_sha", "publication_instance_id", "payload_inventory_sha256", "source_e0_identity", "source_e1_identity", "source_e2_identity", "non_manifest_payload_inventory"}
    if set(manifest) != expected_keys:
        raise PublicationArtifactError("manifest key set is not canonical")
    if manifest["publication_schema_version"] != PUBLICATION_SCHEMA_VERSION or manifest["publication_contract_version"] != PUBLICATION_CONTRACT_VERSION:
        raise PublicationArtifactError("manifest publication versions are not canonical")
    if manifest["publication_spec_id"] != model.specification.publication_spec_id or manifest["publication_spec"] != model.specification.to_dict():
        raise PublicationArtifactError("manifest publication specification mismatch")
    if manifest["producer_git_sha"] != producer_sha or manifest["publication_instance_id"] != instance_id or manifest["payload_inventory_sha256"] != inventory_hash:
        raise PublicationArtifactError("manifest identity mismatch")
    if manifest["source_e0_identity"] != model.specification.to_dict()["source_e0_identity"] or manifest["source_e1_identity"] != model.specification.to_dict()["source_e1_identity"] or manifest["source_e2_identity"] != model.specification.to_dict()["source_e2_identity"]:
        raise PublicationArtifactError("manifest source identity mismatch")
    if manifest["non_manifest_payload_inventory"] != list(inventory):
        raise PublicationArtifactError("manifest payload inventory mismatch")


def _materialize_temp(temporary: Path, final_path: Path) -> None:
    """Materialize a directory with an OS-level no-replace guarantee."""
    if os.name == "nt":
        try:
            os.rename(temporary, final_path)
        except FileExistsError as exc:
            raise PublicationArtifactError("publication instance destination appeared concurrently") from exc
        except OSError as exc:
            raise PublicationArtifactError(f"no-replace materialization failed: {exc}") from exc
        return
    if os.name != "posix" or not sys.platform.startswith("linux"):
        raise PublicationArtifactError("atomic no-replace materialization is unsupported on this platform")

    libc = ctypes.CDLL(None, use_errno=True)
    source = os.fsencode(temporary)
    destination = os.fsencode(final_path)
    at_fdcwd = -100
    rename_noreplace = 1
    try:
        renameat2 = libc.renameat2
    except AttributeError:
        renameat2 = None
    if renameat2 is not None:
        renameat2.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        renameat2.restype = ctypes.c_int
        result = renameat2(at_fdcwd, source, at_fdcwd, destination, rename_noreplace)
    else:
        machine = os.uname().machine.lower() if hasattr(os, "uname") else ""
        syscall_number = {"x86_64": 316, "amd64": 316, "aarch64": 276, "arm64": 276, "i386": 353, "i686": 353}.get(machine)
        if syscall_number is None or not hasattr(libc, "syscall"):
            raise PublicationArtifactError("atomic no-replace materialization is unsupported on this platform")
        libc.syscall.argtypes = [ctypes.c_long, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        libc.syscall.restype = ctypes.c_long
        result = libc.syscall(syscall_number, at_fdcwd, source, at_fdcwd, destination, rename_noreplace)
    if result != 0:
        error = ctypes.get_errno()
        if error == errno.EEXIST:
            raise PublicationArtifactError("publication instance destination appeared concurrently")
        raise PublicationArtifactError(f"no-replace materialization failed: {os.strerror(error)}")


def write_publication_bundle(model: PublicationModel, output_root: str | Path, producer_git_sha: str) -> PublicationArtifactResult:
    """Materialize one immutable publication instance below ``output_root``."""
    if not isinstance(model, PublicationModel):
        raise TypeError("write_publication_bundle expects PublicationModel")
    validate_publication_model_consistency(model)
    producer_sha = validate_producer_git_sha(producer_git_sha)
    root = Path(output_root)
    if _is_reparse(root):
        raise PublicationArtifactError("output_root must not be a symlink or reparse point")
    existed = root.exists()
    if existed and not root.is_dir():
        raise PublicationArtifactError("output_root must be a directory")
    root.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        temporary = Path(tempfile.mkdtemp(prefix=".publication-v1-", dir=root))
        report_bytes = render_report_markdown(model).encode("utf-8")
        if not report_bytes.endswith(b"\n") or report_bytes.endswith(b"\n\n") or b"publication_instance_id" in report_bytes:
            raise PublicationArtifactError("report bytes are not canonical")
        tables_bytes = serialize_tables(model)
        traceability_bytes = serialize_traceability(model)
        if b"publication_instance_id" in tables_bytes or b"publication_instance_id" in traceability_bytes:
            raise PublicationArtifactError("non-manifest payload contains publication_instance_id")
        _write_bytes(temporary / "report.md", report_bytes)
        _write_bytes(temporary / "tables.json", tables_bytes)
        _write_bytes(temporary / "traceability.json", traceability_bytes)
        _render_figures(model, temporary)
        _validate_closed_world(temporary, include_manifest=False)
        inventory = build_payload_inventory(temporary)
        inventory_hash = payload_inventory_sha256(inventory)
        instance_id = publication_instance_id(model.specification.publication_spec_id, producer_sha, inventory_hash)
        manifest = {
            "publication_schema_version": PUBLICATION_SCHEMA_VERSION,
            "publication_contract_version": PUBLICATION_CONTRACT_VERSION,
            "publication_spec_id": model.specification.publication_spec_id,
            "publication_spec": model.specification.to_dict(),
            "producer_git_sha": producer_sha,
            "publication_instance_id": instance_id,
            "payload_inventory_sha256": inventory_hash,
            "source_e0_identity": model.specification.to_dict()["source_e0_identity"],
            "source_e1_identity": model.specification.to_dict()["source_e1_identity"],
            "source_e2_identity": model.specification.to_dict()["source_e2_identity"],
            "non_manifest_payload_inventory": list(inventory),
        }
        _write_bytes(temporary / "manifest.json", canonical_json_bytes(manifest))
        _validate_closed_world(temporary, include_manifest=True)
        final_inventory = build_payload_inventory(temporary)
        if final_inventory != inventory or payload_inventory_sha256(final_inventory) != inventory_hash:
            raise PublicationArtifactError("payload changed after identity inventory was derived")
        manifest_raw = (temporary / "manifest.json").read_bytes()
        if not manifest_raw.endswith(b"\n") or manifest_raw.endswith(b"\n\n"):
            raise PublicationArtifactError("manifest must end with exactly one LF")
        try:
            manifest_parsed = json.loads(manifest_raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError) as exc:
            raise PublicationArtifactError("manifest is not valid UTF-8 JSON") from exc
        if manifest_raw != canonical_json_bytes(manifest_parsed):
            raise PublicationArtifactError("manifest bytes are not canonical JSON")
        _validate_manifest(manifest_parsed, model, final_inventory, inventory_hash, producer_sha, instance_id)
        if manifest_parsed["publication_spec_id"] != model.specification.publication_spec_id or publication_instance_id(manifest_parsed["publication_spec_id"], manifest_parsed["producer_git_sha"], manifest_parsed["payload_inventory_sha256"]) != manifest_parsed["publication_instance_id"]:
            raise PublicationArtifactError("manifest identity relation is not canonical")
        final_path = root / instance_id
        if _is_reparse(final_path) or final_path.exists():
            raise PublicationArtifactError("publication instance destination already exists")
        try:
            _materialize_temp(temporary, final_path)
        except FileExistsError as exc:
            raise PublicationArtifactError("publication instance destination appeared concurrently") from exc
        temporary = None
        return PublicationArtifactResult(instance_id, model.specification.publication_spec_id, producer_sha, inventory_hash, final_path)
    except PublicationError:
        raise
    except (OSError, ValueError) as exc:
        raise PublicationArtifactError(f"publication bundle write failed: {exc}") from exc
    except Exception as exc:
        raise PublicationArtifactError(f"publication bundle write failed: {exc}") from exc
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary, ignore_errors=True)
        if not existed and root.exists() and root.is_dir() and not any(root.iterdir()):
            root.rmdir()


write_publication_artifact = write_publication_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write a deterministic Phase 6 publication bundle")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--producer-git-sha", required=True)
    args = parser.parse_args(argv)
    try:
        result = write_publication_bundle(build_publication_model(), args.output_root, args.producer_git_sha)
    except (PublicationError, OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"publication_instance_id": result.publication_instance_id, "publication_spec_id": result.publication_spec_id, "producer_git_sha": result.producer_git_sha, "payload_inventory_sha256": result.payload_inventory_sha256}, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ALL_BUNDLE_PATHS", "NON_MANIFEST_PATHS", "PublicationArtifactError", "PublicationArtifactResult",
    "build_payload_inventory", "main", "payload_inventory_sha256", "publication_instance_id",
    "validate_producer_git_sha", "write_publication_artifact", "write_publication_bundle",
]
