"""CLI adapter for the independent Phase 6 publication verifier."""

from __future__ import annotations

import sys

from src.publication_verifier import PublicationVerificationError, verify_publication_bundle


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python -B verify_publication_bundle.py <publication-instance-root>")
        return 1
    try:
        result = verify_publication_bundle(args[0])
    except PublicationVerificationError as exc:
        print("Phase 6 Publication Verification")
        print("VERDICT: FAIL")
        print(f"stage: {exc.stage}")
        print(f"reason: {exc.reason}")
        return 1
    except Exception as exc:  # pragma: no cover
        print("Phase 6 Publication Verification")
        print("VERDICT: ERROR")
        print(f"reason: internal verifier error ({type(exc).__name__})")
        return 2
    print("Phase 6 Publication Verification")
    print(f"publication_instance_id: {result.publication_instance_id}")
    print(f"publication_spec_id: {result.publication_spec_id}")
    print(f"producer_git_sha: {result.producer_git_sha}")
    print(f"payload_inventory_sha256: {result.payload_inventory_sha256}")
    print("\nVERDICT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
