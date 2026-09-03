"""Fail-closed Level 2 scratch replay orchestration for frozen evidence."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import shutil
from typing import Callable

from src.formal_verifier import verify_frozen_bundle
from src.publication import build_publication_model
from src.publication_artifacts import write_publication_bundle
from src.publication_verifier import verify_publication_bundle
from src.ranking_robustness_producer import produce_ranking_robustness_artifact_instance
from src.ranking_robustness_verifier import verify_ranking_robustness_artifact


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_E1_ROOT = REPOSITORY_ROOT / "artifacts" / "frozen" / "formal-research-v1"
ACCEPTED_E2_ROOT = REPOSITORY_ROOT / "artifacts" / "phase-5" / "82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e"
ACCEPTED_PUBLICATION_ROOT = REPOSITORY_ROOT / "artifacts" / "phase-6" / "publication-v1" / "1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467"

E2_PRODUCER_GIT_SHA = "766fd10a0a22c1266a70b11c1581e8f607f10c07"
PUBLICATION_PRODUCER_GIT_SHA = "ae27c390524a3e9dd6524a7c131aa9d2c51485e6"


class Level2ReplayError(RuntimeError):
    """Raised when a Level 2 replay cannot satisfy its frozen contract."""


@dataclass(frozen=True)
class ReplayResult:
    kind: str
    output_root: Path
    bundle_path: Path


def _is_reparse(path: Path) -> bool:
    """Reject links and Windows reparse points without following them."""
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = os.lstat(path).st_file_attributes
    except FileNotFoundError:
        return False
    except AttributeError:
        return False
    except OSError:
        return True
    return bool(attributes & 0x40000000)  # FILE_ATTRIBUTE_REPARSE_POINT


def _absolute_path(value: str | Path) -> Path:
    try:
        return Path(os.path.abspath(os.fspath(Path(value).expanduser())))
    except (OSError, TypeError, ValueError) as exc:
        raise Level2ReplayError(f"invalid output root: {exc}") from exc


def _has_reparse_ancestor(path: Path) -> bool:
    current = path
    while True:
        if _is_reparse(current):
            return True
        if current == current.parent:
            return False
        current = current.parent


def _related_to_protected_root(candidate: Path, protected: Path) -> bool:
    return candidate == protected or candidate.is_relative_to(protected) or protected.is_relative_to(candidate)


def validate_scratch_root(value: str | Path) -> Path:
    """Validate one new root owned exclusively by this replay invocation."""
    root = _absolute_path(value)
    protected_roots = tuple(path.resolve() for path in (ACCEPTED_E1_ROOT, ACCEPTED_E2_ROOT, ACCEPTED_PUBLICATION_ROOT))
    resolved = root.resolve(strict=False)
    if any(_related_to_protected_root(resolved, protected) for protected in protected_roots):
        raise Level2ReplayError("output root conflicts with an accepted frozen authority root")
    if root.exists() or root.is_symlink():
        raise Level2ReplayError("output root already exists")
    if not root.parent.is_dir() or _has_reparse_ancestor(root.parent):
        raise Level2ReplayError("output root parent must be an ordinary existing directory")
    return root


def _create_owned_root(root: Path) -> None:
    try:
        root.mkdir()
    except FileExistsError as exc:
        raise Level2ReplayError("output root already exists") from exc
    except OSError as exc:
        raise Level2ReplayError(f"unable to create output root: {exc}") from exc


def _cleanup_owned_root(root: Path) -> None:
    """Best-effort cleanup that never follows a replacement reparse point."""
    try:
        if root.exists() and not _is_reparse(root):
            shutil.rmtree(root, ignore_errors=True)
    except OSError:
        pass


def _owned_bundle_path(root: Path, value: str | Path) -> Path:
    """Require the producer result to be an ordinary child of ``root``."""
    try:
        candidate = _absolute_path(value)
        resolved_root = root.resolve(strict=True)
        resolved_candidate = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise Level2ReplayError(f"producer returned an unusable bundle path: {exc}") from exc
    if (
        candidate == root
        or not candidate.is_relative_to(root)
        or resolved_candidate == resolved_root
        or not resolved_candidate.is_relative_to(resolved_root)
        or not candidate.is_dir()
    ):
        raise Level2ReplayError("producer bundle path is not an owned scratch descendant")
    current = candidate
    while current != root:
        if _is_reparse(current):
            raise Level2ReplayError("producer bundle path contains a reparse point")
        current = current.parent
    return candidate


def _produce_in_owned_root(
    root: Path,
    produce: Callable[[Path], Path],
    verify: Callable[[Path], object],
) -> Path:
    _create_owned_root(root)
    try:
        bundle_path = _owned_bundle_path(root, produce(root))
        verify(bundle_path)
        return bundle_path
    except BaseException:
        _cleanup_owned_root(root)
        raise


def replay_e2(output_root: str | Path) -> ReplayResult:
    """Rebuild the formal E2 instance from accepted E1 into new scratch space."""
    root = validate_scratch_root(output_root)
    verify_frozen_bundle()

    def produce(destination: Path) -> Path:
        return produce_ranking_robustness_artifact_instance(
            output_parent=destination,
            producer_git_sha=E2_PRODUCER_GIT_SHA,
        ).instance_path

    bundle_path = _produce_in_owned_root(root, produce, verify_ranking_robustness_artifact)
    return ReplayResult("e2", root, bundle_path)


def replay_publication(output_root: str | Path) -> ReplayResult:
    """Rebuild the publication from accepted E1/E2 into new scratch space."""
    root = validate_scratch_root(output_root)
    verify_frozen_bundle()
    verify_ranking_robustness_artifact(ACCEPTED_E2_ROOT)

    def produce(destination: Path) -> Path:
        return write_publication_bundle(
            build_publication_model(),
            destination,
            PUBLICATION_PRODUCER_GIT_SHA,
        ).bundle_path

    bundle_path = _produce_in_owned_root(root, produce, verify_publication_bundle)
    return ReplayResult("publication", root, bundle_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a NON-AUTHORITATIVE Phase 7 Level 2 scratch replay."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("e2", "publication"):
        command_parser = commands.add_parser(command)
        command_parser.add_argument("--output-root", required=True)
    args = parser.parse_args(argv)
    runner = replay_e2 if args.command == "e2" else replay_publication
    try:
        result = runner(args.output_root)
    except KeyboardInterrupt:
        print("Level 2 scratch replay interrupted; any owned scratch output was cleaned best-effort.")
        return 130
    except Exception as exc:
        print("Level 2 Scratch Replay")
        print("VERDICT: FAIL")
        print(f"reason: {exc}")
        return 1
    print("Level 2 scratch replay completed.")
    print("This output is NON-AUTHORITATIVE and does not replace frozen project evidence.")
    print(f"kind: {result.kind}")
    print(f"bundle_path: {result.bundle_path}")
    print("VERDICT: PASS")
    return 0


__all__ = [
    "ACCEPTED_E1_ROOT",
    "ACCEPTED_E2_ROOT",
    "ACCEPTED_PUBLICATION_ROOT",
    "E2_PRODUCER_GIT_SHA",
    "Level2ReplayError",
    "PUBLICATION_PRODUCER_GIT_SHA",
    "ReplayResult",
    "main",
    "replay_e2",
    "replay_publication",
    "validate_scratch_root",
]
