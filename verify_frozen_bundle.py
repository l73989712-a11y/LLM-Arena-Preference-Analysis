"""Command-line adapter for the canonical frozen-bundle verifier."""

from __future__ import annotations

from src.formal_verifier import FrozenBundleVerificationError, verify_frozen_bundle


def main() -> int:
    try:
        result = verify_frozen_bundle()
    except FrozenBundleVerificationError as exc:
        print("Frozen Formal Research Bundle Verification")
        print("VERDICT: FAIL")
        print(f"stage: {exc.stage}")
        print(f"reason: {exc.reason}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print("Frozen Formal Research Bundle Verification")
        print("VERDICT: ERROR")
        print(f"reason: internal verifier error ({type(exc).__name__})")
        return 2

    print("Frozen Formal Research Bundle Verification")
    print(f"bundle: {result.bundle_name}")
    print(f"payload files: {result.payload_file_count}")
    print(f"payload bytes: {result.payload_total_bytes}")
    print(f"inventory SHA-256: {result.payload_inventory_sha256}")
    print(f"source snapshot: {result.source_snapshot_id}")
    print(f"runs: {result.verified_run_count}/9 verified")
    print("comparative review: verified")
    print("semantic validation: passed")
    print("\nVERDICT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
