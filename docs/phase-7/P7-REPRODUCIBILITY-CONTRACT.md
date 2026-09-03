# Phase 7 Reproducibility Contract

Status: **ACCEPTED - P7-T2**

This document is the accepted contract for Phase 7 - External
Reproducibility & Research Communication Hardening. It defines the supported
external reproducibility boundary. It does not implement a replay command,
change the frozen research, or authorize a commit, tag, release, or archive.

## 1. Objective and Scientific Authority

Phase 7 makes the publicly frozen Phase 6 research independently
understandable, verifiable, and reproducible by an external user without
creating new scientific evidence or changing the frozen historical-population
interpretation.

The authoritative interpretation remains:

> estimated preference under the frozen historical Arena population

The scientific and publication authorities are immutable:

- E0: the pinned historical source snapshot;
- E1: the frozen formal research evidence;
- E2: the deterministic ranking-robustness evidence derived from E1;
- Phase 6 publication: the accepted formal publication derived from frozen
  E1/E2 evidence.

Phase 7 creates no E3 layer. It introduces no new data, estimand, estimator,
bootstrap method, ranking analysis, subgroup conclusion, temporal or language
analysis, robustness dimension, or causal/current-model claim. A newly found
scientific gap must stop the current scope and be reported for a separately
contracted methodology phase.

## 2. Reproduction Levels

Phase 7 uses three distinct reproduction levels. A higher level is not implied
by support for a lower level.

### Level 1 - Verification

Status: **SUPPORTED / MANDATORY FOR PHASE 7 CLOSEOUT**

An external user must be able to locate and run the existing independent
verifiers against the committed frozen authorities:

```text
E1                         verify_frozen_bundle.py
E2                         verify_ranking_robustness.py
Phase 6 publication        verify_publication_bundle.py
```

The verification chain must expose the relevant artifact inventories, source
identities, publication identities, and expected pass/failure semantics. It
must work in the documented supported environment without acquiring raw Arena
data or writing into the accepted frozen roots.

### Level 2 - Bounded Downstream Re-execution

Status: **SUPPORTED BY PHASE 7 AFTER BOUNDED HARDENING**

Level 2 is a scratch replay of downstream deterministic products from already
accepted frozen evidence. The allowed conceptual paths are:

```text
frozen E1
  -> E2 replay

frozen E1/E2 evidence
  -> Phase 6 publication replay
```

Level 2 does not regenerate E1 and does not acquire or reinterpret E0. The
public protocol must be a documented, stable CLI-oriented interface. Internal
Python APIs may remain implementation details and are not, by themselves, an
external reproduction contract.

Every replay must receive an explicit new or scratch destination. A successful
replay is engineering/reproduction evidence only; it does not create E3,
replace accepted E2, replace the accepted Phase 6 publication, or become a
new scientific authority, even when hashes are equal.

### Level 3 - Source-to-Publication Reproduction

Status: **INTENTIONALLY UNSUPPORTED**

Phase 7 does not promise:

- remote E0 acquisition;
- reconstruction of E0 from a current upstream endpoint;
- E0-to-E1 formal regeneration;
- full source-to-publication reconstruction;
- offline or hermetic reconstruction of the scientific record.

E0 remains an exact external dataset snapshot with a pinned revision, source
file and SHA-256 identity. The frozen E1 bundle is the formal scientific
authority used by supported verification and bounded downstream replay.
Level 3 is a deliberate scope boundary, not a claim that the repository is
damaged or temporarily incomplete.

## 3. Exploratory and Non-Authoritative Paths

Convenience and exploratory paths are not formal E0 reproduction paths:

```text
exploratory/current-data path != formal E0 reproduction path
```

In particular, `load_dataset()` and `run_pipeline.py --mode real` are legacy
or exploratory surfaces. They must not be presented as a way to recreate the
frozen E0/E1 scientific record. Phase 7 may later add documentation, help
text, warnings, naming, or bounded guards to prevent authority confusion.
Such hardening must not become a new formal E0 acquisition pipeline or expand
Phase 7 into Level 3.

## 4. Frozen Artifact Protection

Supported replay tooling must fail closed rather than overwrite any accepted
authority. At minimum, the following roots are protected:

```text
artifacts/frozen/formal-research-v1/...
artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e/...
artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467/...
```

Level 2 commands must require or construct an explicit scratch destination,
must not replace an existing destination, and must preserve accepted roots on
success, failure, collision, and interruption. A replay path that can mutate
an accepted E1, E2, or Phase 6 publication root violates this contract.

## 5. Authority and Identity Semantics

The following concepts remain separate:

```text
accepted scientific/publication authority
scratch reproduction output
verification evidence
repository public-freeze identity
producer implementation identity
artifact/publication instance identities
```

`producer_git_sha` identifies the committed implementation that produced an
artifact. The repository public-freeze SHA identifies the Git commit accepted
as the public repository state. They must never be substituted for one
another.

E2 identities remain distinct from Phase 6 publication identities. Publication
identities bind the publication specification, producer identity and actual
non-manifest payload inventory; they do not replace E0/E1/E2 source authority.

Verification confirms an accepted identity. Replay demonstrates downstream
re-execution. Neither action changes the identity or authority of the frozen
artifact.

## 6. Determinism and Output Equivalence

Phase 7 inherits the existing producer, verifier, manifest and canonical JSON
rules. It does not define a second determinism system.

Each replay contract must state which of the following applies to each output:

```text
EXACT IDENTITY
CONTRACT-EQUIVALENT
NOT GUARANTEED CROSS-PLATFORM
```

Canonical JSON, manifests, identity relations, inventory ordering and declared
hashes retain their existing exactness requirements. Cross-platform PNG byte
identity is not required where the existing publication contract excludes it;
semantic correctness and declared inventory rules still apply.

Environment-dependent paths, timestamps, locale formatting, random ordering,
and platform rendering effects must not silently alter an output that the
relevant existing contract declares exact.

## 7. Environment Contract

The supported external environment is:

```text
Python: >=3.12,<3.13
dependency versions: requirements-constraints.txt
installation: network-dependent package installation
validation: pip check and the applicable verifier/test gates
```

The contract does not require:

- wheel hash locking;
- vendored dependencies;
- an offline wheelhouse;
- air-gapped installation;
- a fully hermetic supply-chain reconstruction.

Package installation may require access to an external Python package source.
That limitation must be stated rather than silently treated as offline or
hermetic reproducibility.

## 8. CI Contract

Phase 7 CI hardening must explicitly verify all three frozen authority layers:

```text
verify_frozen_bundle.py
verify_ranking_robustness.py <accepted E2 root>
verify_publication_bundle.py <accepted publication root>
```

Existing appropriate dependency, `pip check`, test, and tracked-diff gates may
remain. This P7-T2 contract does not edit CI workflows or claim a new hosted
run. A later task must define the exact workflow change and acceptance
evidence.

## 9. Research Communication Contract

Later Phase 7 communication hardening must provide an external-reader entry
point that does not require reconstructing project history. It must make the
following discoverable:

- the historical-population interpretation and its limitations;
- the roles and locations of E0, E1 and E2;
- the Phase 6 formal publication;
- the authority chain `E0 -> E1 -> E2 -> Phase 6 publication`;
- the three verification commands and expected boundaries;
- the supported Level 2 scratch replay;
- the intentionally unsupported Level 3 path;
- dataset attribution and rights boundaries;
- the distinction between producer SHA and repository public-freeze SHA.

P7-T2 does not rewrite `README.md`, the formal report, or prior phase
documentation. It freezes the requirement for a later communication task.

## 10. Distribution Boundary

Phase 7 success does not require a distribution ceremony:

```text
tag:     NO
release: NO
archive: NO
DOI:     NO
```

P7-T6 may evaluate whether one of these adds genuine reproducibility value,
but no tag, release, archive, DOI, or equivalent publication is pre-authorized
by this contract.

## 11. Accepted P7-T1 Gap Mapping

The accepted P7-T1 gaps map into Phase 7 as follows:

| Audit ID | Contract disposition |
| --- | --- |
| P7-AUD-001 | Treat exploratory/current-data paths as an authority hazard. Use boundary hardening, not Level 3 implementation. |
| P7-AUD-002 | Keep the source-to-E1 path intentionally unsupported; do not create a formal acquisition or regeneration contract. |
| P7-AUD-003 | Require explicit E1, E2 and Phase 6 verifier gates in later CI hardening. |
| P7-AUD-004 | Define a stable external CLI requirement for bounded Level 2 replay; implement only in the later replay task. |
| P7-AUD-005 | Accept non-hermetic dependency installation as a documented limitation and non-goal. |
| P7-AUD-006 | Defer methods, limitations and external-reader exposition to communication hardening. |
| P7-AUD-007 | Defer a single external authority map covering all identities and Git freeze semantics to communication hardening. |

No gap is fixed, reclassified as new scientific evidence, or used to reopen
E0, E1, E2 or the Phase 6 publication in P7-T2.

## 12. Provisional Downstream Architecture

The provisional order after this contract is:

```text
P7-T3  Level 1 Verification & CI Hardening
P7-T4  Bounded Level 2 Replay Hardening
P7-T5  External Research Communication Hardening
P7-T6  Clean-Environment External Acceptance and distribution decision
P7-T7  Phase 7 Closeout / Public Freeze
```

Each later task requires its own Web GPT review and authorization. This
document does not authorize implementation, staging, commit, push, tag,
release, merge, rebase, reset, clean, stash, or artifact regeneration.
