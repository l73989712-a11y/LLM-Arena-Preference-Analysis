"""Command-line adapter for independent Phase 5 E2 verification."""

from __future__ import annotations

import sys

from src.ranking_robustness_verifier import RankingRobustnessVerificationError, verify_ranking_robustness_artifact


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: python verify_ranking_robustness.py <artifact-instance-directory>")
        return 1
    try:
        result = verify_ranking_robustness_artifact(args[0])
    except RankingRobustnessVerificationError as exc:
        print("Ranking Robustness E2 Verification")
        print("VERDICT: FAIL")
        print(f"reason: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        print("Ranking Robustness E2 Verification")
        print("VERDICT: ERROR")
        print(f"reason: internal verifier error ({type(exc).__name__})")
        return 2
    print("Ranking Robustness E2 Verification")
    print(f"artifact_instance_id: {result.artifact_instance_id}")
    print(f"derivation_spec_id: {result.derivation_spec_id}")
    print(f"producer_git_sha: {result.producer_git_sha}")
    print(f"payload inventory SHA-256: {result.e2_payload_inventory_sha256}")
    print(f"artifacts: {result.artifact_count}")
    print(f"runs: {result.run_count}")
    print(f"models: {result.model_count}")
    print("\nVERDICT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
