# Phase 6 Closeout - Research Publication

Status: **CLOSED**

This document records the Phase 6 local closeout. The formal publication, its
producer, independent verifier, repository integration, and final validation
are complete locally. P6-T7 is the separate repository-publication operation
for this closed Phase 6 range; its completion is authoritative from remote Git
history and post-push identity rather than embedded as a self-referential state
in this payload.

## Objective and Final Verdict

Phase 6 produced a deterministic, independently verifiable research
publication package derived exclusively from frozen E0, E1, and E2 evidence.
It is a communication and publication layer, not a new scientific evidence
layer or estimand.

P6-T0 through P6-T6 are CLOSED. P6-T7 public publication and freeze authority
is established by remote Git history, not by a current-state claim in this
document.

## Scope and Task Closure

| Task | Scope | Status |
|---|---|---|
| P6-T0 | Strategic scope and gate | CLOSED |
| P6-T1 | Research publication contract | CLOSED |
| P6-T2 | Deterministic publication producer | CLOSED |
| P6-T3 | Independent publication verifier | CLOSED |
| P6-T4 | Formal publication generation and acceptance | CLOSED |
| P6-T5 | Repository integration and discoverability | CLOSED |
| P6-T6 | Final validation and closeout | CLOSED |
| P6-T7 | Public push and public freeze | REMOTE-STATE AUTHORITY / SEE GIT HISTORY |

## Scientific Interpretation

All reported ordering and uncertainty remain estimates of preference under the
frozen historical Arena population. The historical Primary top three are:

```text
1. gpt-4
2. claude-v1
3. claude-instant-v1
```

These are historical frozen Arena preference results only. They are not a
current leaderboard, objective capability ranking, universal preference claim,
best-model recommendation, current model-quality claim, or causal effect.

## No-New-Science Boundary

Phase 6 introduced no new estimand, source dataset or revision, estimator,
bootstrap inference, interval, sensitivity analysis, subgroup analysis,
ranking-robustness metric, causal analysis, or E3 scientific evidence. It did
not reacquire raw Arena data or create a new scientific evidence layer.

## Upstream Evidence Authority

The scientific authorities remain immutable E0, E1, and E2.

### E0

```text
dataset: lmsys/chatbot_arena_conversations
revision: 1b6335d42a1d2c7e34870c905d03ab964f7f2bd8
source file: data/train-00000-of-00001-cced8514c7ed782a.parquet
source file SHA-256: 3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e
source_snapshot_id: 2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4
rows: 33000
models: 20
unordered pairs: 190
```

### E1

```text
bundle: formal-research-v1
path: artifacts/frozen/formal-research-v1
payload files: 73
payload bytes: 3626761
payload inventory SHA-256: 392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6
formal runs: 9
primary_run_id: 9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689
S6-English run: 8dba0d09c93abafe6c448a3ddb8ee22671792208e85b378f5c1b2328ee52624d
```

E1 remains immutable.

### E2

```text
artifact_instance_id: 82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
derivation_spec_id: dc03cc925d2a85dc023542fc21f703abbb966dd4df5da36974c8ea061ece0be4
producer_git_sha: 766fd10a0a22c1266a70b11c1581e8f607f10c07
payload_inventory_sha256: a6a872a6737b5fd7e8d9836ff34ee895d5e99784bca4b5ef1ccb839f7f88857f
```

E2 remains immutable. Its producer identity is not the Phase 6 producer
identity.

## Publication Contract and Implementation

The frozen contract is
[`RESEARCH-PUBLICATION-CONTRACT.md`](RESEARCH-PUBLICATION-CONTRACT.md),
unchanged after P6-T1. The Phase 6 producer is the deterministic implementation
in P6-T2; the independent verifier is the separate P6-T3 implementation.

The canonical eight-file publication is:

```text
manifest.json
report.md
tables.json
traceability.json
figures/primary_preference.png
figures/rank_uncertainty.png
figures/robustness_ranks.png
figures/s6_heterogeneity.png
```

## Formal Publication Instance

The committed formal root is:

```text
artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467/
```

```text
publication_instance_id: 1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467
publication_spec_id: 62503b0a94b7658c6c0b48b8b9d9b7e43df2e963039b999d9a87a2af760ba400
payload_inventory_sha256: dfd065cfc00d333f64c31e7481132954f2778e8b7a1b1f34875190d1e529f095
producer_git_sha: ae27c390524a3e9dd6524a7c131aa9d2c51485e6
exact files: 8
total bytes: 560545
```

The `producer_git_sha` is the committed P6-T2 producer identity, not the
verifier, integration, or closeout commit. Same-environment reproduction
was 8/8 byte-identical; cross-platform PNG byte equality is not required.

### Formal File SHA-256

```text
manifest.json: 8ef7ea2721de7346c6fde4f47c4771be730e838889a4083a7fc2afe4e5397203
report.md: e9e32d82a0acb6a5e93c1855f9971c497c06de9ab9fd3974f8567aa8d4c0b6b9
tables.json: af8bc219da9a653fd4bfccbb0295c3a06c7dcc64cc81cb6331263ae46fff9868
traceability.json: 96b1704d2b0ea72da102d915a16886d7bee2a2ea0eb88e9c8d05fe5326003d8f
figures/primary_preference.png: 85d98a71d1f6552f769b10b121e221e029d11542e221fbaf1328854a37059881
figures/rank_uncertainty.png: 80a72416d56f10c1f6a546b3e559ce8e71914562eef1b03d3d8de96ca9729d5f
figures/robustness_ranks.png: e44d7a9c3e71c5f17a4db02548498aaecbb446eae379b4935aa797f375e975b1
figures/s6_heterogeneity.png: 87f32cd025fb0424e13d4a16d0055c1d0aa3db27c224b2c80d6f37a892bd7a69
```

## Independent Verification

The independent verifier is committed at `b78a2304ae9f44486094cd390268056c1ec3f4c3`.
Run:

```powershell
python -B verify_publication_bundle.py artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467
```

It independently checks the publication specification, source identities,
tables, claims, traceability, report bindings, inventory, instance identity,
figure semantics, and interpretation boundary. It does not regenerate E1/E2
or require cross-platform PNG byte equality.

## Repository Integration and Discoverability

P6-T5 made the formal instance ordinary tracked content through a single-
instance `.gitignore` allowlist and an instance-scoped `.gitattributes` `-text`
rule. With `core.autocrlf=true`, raw-vs-clean Git identity was equal for all
8/8 formal files. README links the report, manifest, four figures, verifier,
publication identities, and the verification/reproduction distinction.

## Validation Evidence

```text
publication verifier: PASS
E1 verifier: PASS — 73 payloads, 9/9 runs
E2 verifier: PASS — 7 artifacts, 9 runs, 20 models
full pytest: 452 passed, 6 skipped
pip check: PASS
compileall: PASS
git diff --check: PASS
warning-strict full-suite gate: NOT ADDED; no accepted repository precedent
```

## Commit Identities and Repository State

```text
Phase 5 public baseline: a3d93a8908e1797816048489821e59b90fbb5945
P6-T1 contract: 5cc29f7c3af0dc0a674a34c5e45eaed46de1b2c8
P6-T2 producer: ae27c390524a3e9dd6524a7c131aa9d2c51485e6
P6-T3 verifier: b78a2304ae9f44486094cd390268056c1ec3f4c3
P6-T5 integration: e7de904d57066d85c4e8874adf9d603a5a1fdd69
```

Historical pre-closeout documentation baseline:

```text
HEAD: e7de904d57066d85c4e8874adf9d603a5a1fdd69
origin/main: a3d93a8908e1797816048489821e59b90fbb5945
ahead/behind: 4 / 0
```

The P6-T6 closeout commit contains this document; its self-referential commit
identity is authoritative in Git history and is intentionally not embedded in
this payload. It is one ordinary child commit of the pre-closeout HEAD.

Accepted pre-P6-T7 durability-reconciliation baseline:

```text
HEAD: 684b3da1dc605a414e34998815dd56fe65c13738
origin/main: a3d93a8908e1797816048489821e59b90fbb5945
ahead/behind: 5 / 0
fast-forward ancestry: PASS
```

These are historical pre-publication values, not a claim about the permanent
current remote state. The exact commit that becomes the final public Phase 6
freeze cannot self-report its own remote-publication completion before it is
pushed. Final public authority is therefore established by Git history when an
ordinary P6-T7 push yields `HEAD == origin/main`.

## Non-Goals and Remaining Operation

Phase 6 does not refresh Arena data, alter E0/E1/E2, add a current leaderboard,
claim objective capability, establish current model quality, make a causal
claim, provide a universal recommendation, create a dashboard/API/backend, or
create a new E3 scientific layer.

P6-T7 is a repository-publication operation only: refresh the remote, confirm
the accepted pre-publication baseline and fast-forward ancestry, require a
clean worktree and empty index, perform ordinary `git push origin main`, then
verify `HEAD == origin/main` and ahead/behind `0 / 0`. No force push, tag, or
release is planned.

## Final Local Status

```text
local Phase 6: CLOSED
formal publication: FROZEN
public freeze authority: remote Git history after P6-T7
```

P6-T6 closeout commit subject:

```text
docs: close phase 6 research publication
```
