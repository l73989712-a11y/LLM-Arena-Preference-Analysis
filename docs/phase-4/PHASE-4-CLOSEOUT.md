# Phase 4 Closeout - Public Reproducibility & Verification Hardening

Status: **CLOSED / PUBLICLY FROZEN**

This document is the final Phase 4 closeout record. It records the accepted
public implementation and hosted verification evidence; it does not reopen
scientific inference or add a new evidence layer.

The implementation publication head recorded below is already public. This
closeout record is prepared for the final closeout commit; that commit becomes
public only when it is pushed.

## Objective and Architecture

Phase 4 made the frozen Phase 2-3 research product independently verifiable
and reproducible from the public repository without reopening statistical
inference, altering frozen evidence, or expanding scientific claims.

The work added an orthogonal public reproducibility and verification plane:

```text
public delivery -> canonical verification -> environment contract
                 -> clean checkout / hosted CI -> documented provenance

E0 -> E1 -> E2 -> E3
```

No E4 scientific layer was created. Phase 4 tooling is delivery and
verification infrastructure, not new scientific evidence.

## Public Baseline and Lineage

Phase 4 started from the Phase 3 public baseline:

```text
1c44edc2658e5c8a6586d6f63436197029f47f67
```

The five implementation commits form an ordinary linear chain:

| Task | Commit | Subject |
|---|---|---|
| P4-T1 | `ba208ee66f4052c7b366806bc294231a19608de7` | `feat: publish frozen formal research bundle` |
| P4-T2 | `dc0c8bfab80d9bf2deca2b6670d976fba2d92498` | `feat: add frozen bundle verifier` |
| P4-T3 | `fb524afab3a367f7eeb6c6dca3fdbef8c02151ff` | `chore: freeze reproducible environment` |
| P4-T4 | `9d48604e557a98dbeff114edea7fbeb98f7077f4` | `ci: add frozen reproducibility workflow` |
| P4-T5 | `15ac5f2ef98a3c95a5b21727d181d594b16e1f0a` | `docs: publish frozen research reproducibility guide` |

These commits were published by ordinary fast-forward:

```text
old origin/main: 1c44edc2658e5c8a6586d6f63436197029f47f67
implementation publication head: 15ac5f2ef98a3c95a5b21727d181d594b16e1f0a
```

No force push, tag, or release was used.

## Frozen Public Bundle

The tracked public E1 payload is:

```text
bundle: formal-research-v1
payload root: artifacts/frozen/formal-research-v1/payload
payload files: 73
payload bytes: 3,626,761
payload_inventory_sha256: 392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6
source snapshot: 2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4
formal runs: 9
```

The comparative review is:

```text
path: artifacts/frozen/formal-research-v1/payload/comparative_review/review.json
bytes: 89,996
SHA-256: 452192dabbb8e8ad428a023ab8bb78052688965473a2736c5be352d021f26ffa
```

The payload is byte-frozen E1 scientific evidence. The bundle manifest,
NOTICE, workflow, and other Phase 4 files are reproducibility and publication
metadata, not a new scientific evidence layer.

## Canonical Verifier

The public command is:

```text
python verify_frozen_bundle.py
```

It verifies bundle structure, closed-world payload inventory, path/size/SHA
identity, frozen run manifests and registry, semantic frozen-loader checks,
and complete bundle consumption. It is read-only and performs no network
access, Arena download, inference, bootstrap generation, or artifact
regeneration.

Exit codes are:

```text
0  verification passed
1  expected verification failure
2  unexpected/internal verifier error
```

## Environment Contract

The supported Python policy is `>=3.12,<3.13`. The accepted reference
environment is CPython 3.12.5 on Windows AMD64. The canonical environment is
declared by `requirements.txt`, `requirements-dev.txt`, and the 58-pin
`requirements-constraints.txt` resolution. `requirements_optional.txt`
remains outside the Phase 4 verification environment.

Accepted Windows fresh-environment evidence:

```text
canonical install: PASS
58/58 resolution: PASS
pip check: PASS
verifier: PASS
fresh full safe: 260 passed, 3 skipped
current accepted suite: 261 passed, 3 skipped
```

The two Windows counts are separate recorded validation moments and are not
intended to be conflated.

## Local Clean-Checkout Evidence

An independent `git clone --no-local` from the committed Phase 4 tree was
validated on Windows AMD64:

```text
source committed HEAD: fb524afab3a367f7eeb6c6dca3fdbef8c02151ff
Python: 3.12.5
canonical install: PASS
pip check: PASS
verifier: PASS
outside-CWD verifier: PASS
full safe: 261 passed, 3 skipped
hidden local dependency: none found
```

The clone did not require `outputs/research`, raw Arena data, an existing
`.venv`, or untracked files.

## Hosted Ubuntu Evidence

The public workflow is `.github/workflows/frozen-reproducibility.yml`. The
independently accepted hosted run was:

```text
workflow: Frozen Reproducibility
run ID: 33095049526
run number: 1
attempt: 1
event: push
head SHA: 15ac5f2ef98a3c95a5b21727d181d594b16e1f0a
status: completed
conclusion: success
URL: https://github.com/l73989712-a11y/LLM-Arena-Preference-Analysis/actions/runs/33095049526
```

The `verify` job was `98597645889` on Ubuntu 24.04.4 LTS (`ubuntu-24.04`,
image `20260823.283.1`) with CPython 3.12.14 and pip 26.2.1. Observed
permissions were `Contents: read` and `Metadata: read`.

Hosted checks all passed:

```text
checkout exact head: PASS
canonical constrained installation: PASS
pip check: PASS
frozen verifier: PASS
payload: 73 files / 3,626,761 bytes
inventory SHA-256: 392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6
runs: 9/9 verified
comparative review: verified
semantic validation: passed
VERDICT: PASS
full safe suite: 264 passed, 0 skipped, 15.11s
tracked checkout diff gate: PASS
final job conclusion: success
```

This proves the canonical Python 3.12 and pinned dependency contract on the
accepted Windows and hosted Ubuntu environments. It does not claim support
for every operating system or Python version, nor bit-identical rendered
Matplotlib images.

## Scientific and Legal Boundaries

The project remains historical Arena pairwise preference research. The
preferred interpretation is estimated preference under the frozen historical
Arena population. Phase 4 does not establish a current leaderboard, best
model, objective capability ranking, universal model ranking, causal effects,
or external generalization.

See the [reproducibility guide](../reproducibility/FROZEN-RESEARCH-REPRODUCIBILITY.md)
and [NOTICE](../../artifacts/frozen/formal-research-v1/NOTICE.md) for durable
workflow, provenance, citation, and license details. The public payload
contains aggregate/statistical derivatives and no raw prompts, model
responses, conversation rows, or user identifiers. The repository MIT
license applies to original project material and does not supersede upstream
rights.

## Residual Limitations and Non-Goals

Phase 4 does not:

- regenerate or alter E1 inference;
- refresh Arena data;
- analyze arbitrary uploaded datasets;
- lock package wheel hashes;
- promise cross-platform rendered-image binary identity;
- make legacy/demo outputs formal evidence.

Optional acquisition, database, notebook, and spreadsheet dependencies remain
outside the canonical verification environment.

## Final Phase Status

```text
P4-T1: CLOSED
P4-T2: CLOSED
P4-T3: CLOSED
P4-T4: CLOSED / HOSTED ACCEPTED
P4-T5: CLOSED
P4-T6: CLOSED

Phase 4: CLOSED / PUBLICLY FROZEN
```
