# Phase 7 Closeout

Status: **CLOSED**

This document records the Phase 7 reproducibility closeout. Phase 7 completed
the public verification and bounded downstream replay contract for the frozen
research product. It added no scientific evidence layer, did not modify E0,
E1, E2, or the Phase 6 publication authority, and did not make source-to-
publication reconstruction a supported path.

## Accepted Baseline

The P7-T6d acceptance baseline is:

```text
c1dce0e235f6b0790e583668f4731fb8b33a7134
```

This identifies the implementation revision accepted by hosted Level 1 and
fresh-clone Level 2 verification. It is not this closeout document's final
public-freeze SHA. The final closeout commit and its hosted workflow result are
established by Git and GitHub Actions after the ordinary publication step; a
commit does not self-report its own future remote-publication identity.

## Scope and Task Closure

| Task | Status |
| --- | --- |
| P7-T0 | CLOSED |
| P7-T1 | CLOSED |
| P7-T2 reproducibility contract | CLOSED |
| P7-T3 Level 1 verification and CI hardening | CLOSED |
| P7-T4 bounded Level 2 replay hardening | CLOSED |
| P7-T5 external research communication hardening | CLOSED |
| P7-T6a | CLOSED |
| P7-T6b | CLOSED |
| P7-T6c | CLOSED |
| P7-T6d clean-environment external acceptance | CLOSED / ACCEPTED |
| P7-T7 closeout and public freeze record | CLOSED |

The closeout write scope is documentation only. It does not alter producer or
verifier logic, the Phase 7 reproducibility contract, requirements, workflows,
tests, or accepted artifacts.

## Frozen Authority Chain

```text
E0  frozen source snapshot
 -> E1  frozen formal research evidence
 -> E2  frozen ranking-robustness evidence
 -> Phase 6 publication  derived publication bundle
```

E0 remains the source authority. E1, E2, and the Phase 6 publication remain
immutable accepted authorities. A Level 2 output is scratch,
NON-AUTHORITATIVE reproduction evidence: it is not E3 and never replaces an
accepted root.

## Verification Evidence

### Hosted Level 1

The hosted Phase 7 acceptance result is:

```text
workflow: Frozen Reproducibility
run: 33936320166
event: push
commit: c1dce0e235f6b0790e583668f4731fb8b33a7134
conclusion: success
job: verify
```

The successful job completed constrained environment setup, `pip check`, the
E1 frozen-bundle verifier, the E2 ranking-robustness verifier, the Phase 6
publication verifier, the safe pytest suite, and tracked-checkout cleanliness.
This is hosted Level 1 evidence for the accepted baseline, not a new research
authority or a Level 3 claim.

### Fresh Windows Clone Level 2

An independent fresh public clone of the accepted baseline passed on Windows
with Python 3.12.10:

```text
pip check: PASS
E1 verifier: PASS
E2 verifier: PASS
Phase 6 publication verifier: PASS
E2 scratch replay: PASS
E2 scratch post-verification: PASS
publication scratch replay: PASS
publication scratch post-verification: PASS
clean clone after disposable-environment cleanup: PASS
```

Each replay destination was a new, repository-external scratch root. The
accepted E1, E2, and Phase 6 roots were not modified, no new authority was
created, and the two replay paths remained independent:

```text
accepted E1 -> scratch E2
accepted E1 + accepted E2 -> scratch Phase 6 publication
```

## Checkout Portability Resolution

The fresh Windows clone exposed an E2 byte-verification failure when a
checkout used `core.autocrlf=true`: the E2 frozen root had not been protected
from text conversion. The accepted baseline protects the exact E2 authority
root with this `.gitattributes` rule:

```text
artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e/** -text
```

The subsequent independent fresh public clone passed the E2 authority verifier
and both Level 2 replay paths. This is checkout-byte portability evidence for
the accepted frozen E2 authority; it does not change the E2 artifact or its
identity semantics.

## Supported Reproducibility Boundary

Phase 7 supports:

- Level 1 read-only verification of E1, E2, and the Phase 6 publication;
- Level 2 bounded downstream replay into a new scratch root.

Level 3 remains intentionally unsupported. The public contract does not
provide remote E0 acquisition, E0-to-E1 formal regeneration, full source-to-
publication reconstruction, raw Arena acquisition, or a hermetic offline
rebuild of the scientific record.

## Limitations and Distribution State

Dependency installation remains network-dependent. The project does not
promise wheel hash locking, vendored dependencies, an offline wheelhouse,
air-gapped installation, or a fully hermetic supply-chain reconstruction.
Cross-platform PNG byte identity is not guaranteed; the publication verifier
is the acceptance mechanism for the declared inventory and semantic validity
of a scratch publication replay.

Phase 7 creates no tag, GitHub release, archive, DOI, or new distribution
authority. The frozen research interpretation remains limited to preference
under the frozen historical Arena population; it is not a current leaderboard,
objective capability ranking, universal preference claim, recommendation, or
causal analysis.

## Public-Freeze Authority Procedure

After this closeout commit is published, public-freeze authority is established
by remote evidence, not by embedding the commit's own future SHA in this file:

```text
final HEAD == origin/main
ahead/behind == 0 / 0
worktree clean
final closeout commit has a successful Frozen Reproducibility hosted workflow
```

Those post-push facts identify the final Phase 7 public-freeze revision and
its hosted acceptance. They do not alter the P7-T6d acceptance baseline or
reopen any frozen authority.
