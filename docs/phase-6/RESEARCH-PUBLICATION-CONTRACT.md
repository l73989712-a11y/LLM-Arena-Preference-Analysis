# Phase 6 Research Communication & Publication Contract

Status: **ACCEPTED - Phase 6 Research Publication Contract v1**

Normative contract version: `publication_contract_version: 1`

This document defines the accepted Phase 6 publication contract. It is a
publication and research-communication contract, not a new statistical
analysis contract. Acceptance of this contract does not by itself authorize
implementation, artifact generation, staging, commit, or push; each remains
subject to the established task and Git gates.

## 1. Purpose and objective

Phase 6 produces a deterministic, independently verifiable research
publication package derived exclusively from the accepted frozen E0, E1, and
E2 authorities. Its purpose is to make the existing research inspectable and
reproducible for public readers without adding scientific conclusions.

The frozen Phase 6 objective is:

> Produce a deterministic, independently verifiable research publication
> package derived exclusively from frozen E0/E1/E2, without introducing new
> scientific estimands, analyses, evidence, or stronger interpretations.

The contract therefore fixes:

```text
new estimand: NO
new source: NO
new analysis: NO
new scientific evidence layer: NO
```

Phase 6 publication artifacts are communication derivatives. They are not a
replacement for the formal evidence chain and do not extend its scientific
scope.

## 2. Scientific authorities and non-authorities

The only scientific authorities remain:

```text
E0  frozen historical Arena source authority
E1  frozen formal inference evidence
E2  frozen deterministic ranking-robustness evidence
```

The exact source identities are:

```text
dataset: lmsys/chatbot_arena_conversations
revision: 1b6335d42a1d2c7e34870c905d03ab964f7f2bd8
source_file_sha256: 3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e
source_snapshot_id: 2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4

E1 bundle: artifacts/frozen/formal-research-v1/
E1 payload_inventory_sha256: 392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6
E1 primary_run_id: 9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689

E2 instance: artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e/
E2 derivation_spec_id: dc03cc925d2a85dc023542fc21f703abbb966dd4df5da36974c8ea061ece0be4
E2 artifact_instance_id: 82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
E2 payload_inventory_sha256: a6a872a6737b5fd7e8d9836ff34ee895d5e99784bca4b5ef1ccb839f7f88857f
```

Phase 3 presentation logic is an accepted non-authority transformation
surface. The existing `src/formal_presentation.py`, `src/formal_figures.py`,
`src/formal_report.py`, `src/formal_explorer.py`, and `formal_app.py` may be
reused. Their outputs do not become a new scientific evidence layer merely by
being persisted in Phase 6.

Publication artifacts cannot independently validate, supersede, or amend E1 or
E2. Existing E1 and E2 verifiers remain authoritative for their respective
frozen inputs.

## 3. Interpretation boundary

Every publication narrative, table, caption, and metadata record must preserve
the following interpretation:

> estimated preference under the frozen historical Arena population

The publication package must not describe the results as any of the following:

```text
objective model capability
contemporary model quality
current Arena leaderboard
universal model ordering
recommendation about which model to use
causal effect
external or current-population generalization
```

The historical Primary top three remain historical point-rank results only.
They must not be presented as a current ranking.

## 4. No E3 naming

Phase 3 historical records use E3-related terminology for a presentation layer.
To prevent collision with that history, Phase 6 publication outputs SHALL NOT
be named or described as:

```text
E3
E3 evidence
scientific E3
```

The required terms are `publication bundle`, `publication artifact`,
`publication instance`, and `research publication package`. E0/E1/E2 remain
the complete scientific authority hierarchy for this phase.

## 5. Publication bundle model

The canonical publication bundle is a small, file-based, diffable package. The
canonical future layout is:

```text
artifacts/phase-6/publication-v1/<publication_instance_id>/
|-- manifest.json
|-- report.md
|-- tables.json
|-- traceability.json
`-- figures/
    |-- primary_preference.png
    |-- rank_uncertainty.png
    |-- robustness_ranks.png
    `-- s6_heterogeneity.png
```

The seven non-manifest payload files are exactly:

```text
report.md
tables.json
traceability.json
figures/primary_preference.png
figures/rank_uncertainty.png
figures/robustness_ranks.png
figures/s6_heterogeneity.png
```

The four figure roles map to existing Phase 3 canonical figure
specifications as follows:

| Publication role | Existing specification | Existing canonical filename |
| --- | --- | --- |
| `primary_preference` | `PrimaryFigureSpec` from `build_formal_publication_package` | `formal_primary_preference.png` |
| `rank_uncertainty` | `RankUncertaintyFigureSpec` from `build_formal_publication_package` | `formal_rank_uncertainty.png` |
| `robustness_ranks` | `RobustnessFigureSpec` from `build_formal_publication_package` | `formal_robustness_ranks.png` |
| `s6_heterogeneity` | `HeterogeneityFigureSpec` from `build_formal_publication_package` | `formal_s6_heterogeneity.png` |

Phase 6 may choose publication filenames, but it must bind each role to the
corresponding accepted specification identity and semantics; it must not
invent a new figure analysis.

`report.md` is the canonical narrative form because it is diffable, testable,
and directly readable on GitHub. PDF is optional and non-authoritative; it must
not be required for scientific reproducibility.

`tables.json` contains only selected publication tables, not a dump of all E2
records. The initial table set is:

```text
primary results and uncertainty
accepted analysis rank comparison
English-subgroup rank movement
source and formal-run provenance
```

`traceability.json` contains the machine-readable mapping for substantive
claims and table fields. Figure pixels are presentation payloads; their source
specification and claim metadata must still be represented in traceability.

The exact JSON field schemas are implementation-gated by P6-T2, but the file
set and roles above are the canonical contract proposal. No extra payload file
may be added without a documented publication or verification role.

`manifest.json` is the eighth canonical bundle file and is part of the
closed-world bundle. It is explicitly excluded from the non-manifest payload
inventory that it declares. The inventory DAG is:

```text
non-manifest canonical payload bytes
        ->
sorted POSIX-relative path / size / SHA-256 inventory
        ->
payload_inventory_sha256
        ->
publication_instance_id
        ->
manifest.json
        ->
final canonical publication root
```

Thus the canonical bundle has seven non-manifest payload files and eight total
files. There is no manifest self-reference. The independent verifier must
reconstruct the non-manifest inventory from the filesystem and compare it with
the manifest declaration.

## 6. Namespace and visibility policy

The canonical publication namespace is:

```text
artifacts/phase-6/publication-v1/<publication_instance_id>/
```

It is disjoint from both frozen authorities:

```text
artifacts/frozen/formal-research-v1/**
artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e/**
```

The current `.gitignore` intentionally ignores `artifacts/*`. P6-T1 does not
modify it. Before a publication instance can be staged, a later authorized
task must add an explicit, narrow visibility allowlist for the accepted
namespace and verify the resulting tracked path set. `git add -f` is not an
acceptable substitute for that policy.

Transient build directories, temporary renderings, caches, logs, and unrelated
instances remain ignored and are never publication authority. A publication
instance becomes public only through the ordinary review, staging, commit,
and push gates.

## 7. Canonical inputs and determinism

The canonical publication input is the verified combination of:

```text
accepted E0 identity metadata
accepted E1 bundle identity and selected read-only records
accepted E2 instance identity and selected read-only records
this contract's publication schema/version
the fixed publication selection and transformation specification
producer code identity
```

Publication production must be offline after checkout. It must not download
Arena data, inspect current web content, use wall-clock values, use random
ordering, depend on locale-specific formatting, or embed machine-specific
absolute paths in canonical payloads. Any environment information is
provenance metadata and cannot affect scientific values or ordering.

Identical canonical inputs and producer identity must produce semantically
identical publication records, Markdown, traceability, and figure
specifications. Canonical JSON uses UTF-8, sorted object keys, compact separators,
and an explicit single final LF, consistent with repository precedent. Text
must use a fixed newline policy. Figure byte identity is required under the
accepted/reference rendering environment when practical; cross-platform image
bytes are not treated as scientific evidence and are not promised to be
identical. The byte and semantic verification responsibilities are separate:

```text
accepted-bundle byte integrity:
hash committed non-manifest files and compare path/size/SHA-256 to the manifest

figure semantic verification:
recompute or validate selected data series, ordering, labels, claims, source
identities, and accepted figure-specification identity from frozen E1/E2

cross-platform PNG regeneration byte equality: NOT REQUIRED
cross-platform semantic verification: REQUIRED
```

A producer-focused determinism test may require repeated figure generation to
produce identical bytes in the accepted/reference rendering environment. An
arbitrary-platform verifier must not be required to re-render PNGs for a
byte-equality comparison. Each produced bundle's declared inventory must still
bind the exact non-manifest bytes present in that bundle.

## 8. Publication identity model

Publication identity is separate from scientific E1/E2 identity. The future
manifest must carry at least:

```text
publication_schema_version
publication_contract_version
publication_spec_id
producer_git_sha
publication_instance_id
payload_inventory_sha256
source_e0_identity
source_e1_identity
source_e2_identity
```

The identity semantics are:

```text
publication_spec_id       = SHA-256 of canonical publication specification
producer_git_sha          = exact 40-character SHA of the already-committed producer implementation
payload_inventory_sha256  = SHA-256 of the ordered NON-MANIFEST payload path/size/SHA inventory
publication_instance_id   = SHA-256 of publication schema + publication spec + producer SHA + payload inventory
```

`publication_spec_id` identifies what publication is specified, while
`producer_git_sha` identifies the implementation. `publication_instance_id`
identifies one concrete produced instance of that specification and its actual
non-manifest bytes. The payload inventory binds the actual files and does not
replace the source E1/E2 identities.

The producer lifecycle is:

```text
producer implementation committed
        ->
producer_git_sha fixed to its full 40-character commit SHA
        ->
generate non-manifest payload in a temporary destination
        ->
derive non-manifest payload inventory and payload_inventory_sha256
        ->
derive publication_instance_id
        ->
write manifest.json
        ->
materialize/rename the final instance directory
```

The producer SHA is not the later publication-artifact commit and must not be
silently taken from a mutable or short current HEAD. No canonical
non-manifest payload may embed `publication_instance_id`; only the manifest
and final directory name may carry it.

The canonical publication specification must bind the exact E0 snapshot,
E1 bundle/inventory and primary run, E2 derivation and instance identities,
selected table/figure identifiers, report section schema, allowed transform
versions, and publication contract version. It must not bind a timestamp or
absolute filesystem path.

## 9. Traceability contract

Every substantive quantitative claim is a displayed number, rank, interval,
frequency, count, percentage, or comparison that could change a reader's
scientific understanding. Examples include the Primary top-three statement,
rank intervals, top-k frequencies, cross-specification counts, and S6 rank
movement summaries.

Each such claim must have a stable claim identifier and a traceability record
containing:

```text
claim_id
location (report section/table/figure)
source_authority (E0, E1, or E2, with exact pointer)
source_identity
source_record or field selector
allowed_transform_id
display formatting rule
```

Where a claim is directly restated from E1 or E2, the transform is an explicit
identity transform. Where it is selected, ordered, shaped, or rounded, the
transform must be one of the versioned allowed transformations in this
contract. Manual transcription of a headline value is not an acceptable
authority when a machine derivation is feasible.

E0 traceability is limited to accepted frozen identity/provenance metadata,
such as dataset identity, revision, source SHA-256, source snapshot ID, and
accepted row/model counts. It never authorizes reading raw source to compute a
new statistic. E1/E2 traceability covers scientific quantitative results and
accepted derived robustness claims.

The independent verifier must be able to recompute every traceable value from
the frozen source records and the declared transform without trusting the
producer's narrative text. It must also bind the recomputed value to its
actual rendered occurrence in `report.md`, `tables.json`, and figure
specification/metadata. Validating `traceability.json` in isolation is
insufficient: a traceability value of 1 and a rendered value of 2 must fail.
Canonical substantive values must be rendered from the structured
publication/claim model rather than independently hand-typed where machine
derivation is feasible.

## 10. Allowed and forbidden transformations

Allowed presentation-only operations are:

```text
selection of pre-specified records
stable ordering by an accepted key
fixed label and caption formatting
fixed decimal rounding for display
table shaping and column projection
figure rendering from an accepted Phase 3 figure specification
individually named, versioned, pre-specified aggregation that reproduces a
summary already represented by accepted E1/E2 or accepted Phase 3 semantics
```

Generic aggregation authorization is **NO**. Every aggregation-like
transformation must be individually named, versioned, pre-specified in the
canonical publication specification, mechanically reproducible, and
presentation-only. A transformation that creates a scientifically new
quantitative summary is forbidden and requires stop/re-scope. Selection and
other shaping rules must be specified before production. Rounding is
display-only and must not be used for verifier comparisons.

Forbidden operations include:

```text
new estimands or statistical tests
new bootstrap or estimator execution
new subgroup or language inference
pooling bootstrap draws or score scales
post-hoc metric or model selection
manual invention of headline statistics
current-data joins or live web lookups
reclassification of scientific claims
```

If a desired table, figure, or paragraph requires a forbidden operation, the
publication task must stop and the scope must be reconsidered as a separate
scientific phase.

## 11. Publication content boundary

The canonical report is selective and should contain these sections:

```text
research question and frozen population
method and evidence lineage
Primary historical result
uncertainty
pre-specified sensitivity and ranking robustness
English-subgroup heterogeneity boundary
limitations and non-goals
provenance and reproducibility
```

The report may reuse the accepted Phase 3 report content, but it must be
materialized through the Phase 6 deterministic package and traceability model.
It must not become an exhaustive E2 browser or an interactive product.

## 12. Independent verifier model

P6-T3 will provide an independent verifier that does not use the producer's
orchestration as its expected-value oracle. It must verify, at minimum:

```text
ordinary bundle root and exact schema
manifest identity and source E0/E1/E2 bindings
closed-world payload file set
payload paths, sizes, and SHA-256 values
publication specification and instance identities
canonical JSON and Markdown serialization
traceability record completeness
recomputation of every allowed publication transform
interpretation-critical metadata and forbidden-claim flags
absence of unexpected files, symlinks, and path traversal
```

It must invoke or require the existing E1 and E2 verifiers where appropriate,
remain read-only, and never regenerate or modify frozen evidence.

## 13. Frozen-path safety

No Phase 6 operation may write, replace, regenerate, or delete any path below:

```text
artifacts/frozen/formal-research-v1/**
artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e/**
```

The E1 command remains:

```text
python -B verify_frozen_bundle.py
```

The E2 command remains:

```text
python -B verify_ranking_robustness.py artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
```

## 14. Explicit non-goals

Phase 6 does not include:

```text
new dataset or raw source reacquisition
new E1 run or bootstrap
new subgroup or language inference
new estimator or ranking metric
external validation or current Arena comparison
current model-quality or recommendation claims
dashboard, API, database, backend, or live web integration
new scientific E3 layer
E1/E2 regeneration or mutation
```

## 15. Stop and re-scope conditions

Stop or reduce Phase 6 if any of the following occurs:

1. A headline claim cannot be derived from frozen E0/E1/E2 records.
2. A new statistical computation becomes necessary.
3. A displayed value cannot be mechanically traced where derivation is
   feasible.
4. The report requires contemporary, causal, universal, or capability claims.
5. The work expands into a dashboard, API, database, deployment, or live-data
   product.
6. A frozen E1/E2 path would need to be changed.
7. A namespace, identity, inventory, or source-binding collision appears.
8. A requested output exceeds the accepted evidence granularity.

## 16. Testing strategy

Future implementation tasks should cover, without assuming exact test counts:

```text
publication model and schema tests
determinism and canonical serialization tests
manifest, identity, and payload inventory tests
writer lifecycle and exact-file-set tests
traceability recomputation tests
negative verifier and tampering tests
frozen-path mutation protection tests
namespace and visibility allowlist tests
end-to-end producer/verifier tests
```

Tests must preserve the distinction between publication-package validity and
scientific E1/E2 validity.

## 17. Reproducibility contract

Phase 6 inherits the repository environment contract:

```text
Python >=3.12,<3.13
requirements-constraints.txt
existing E1 verifier
existing E2 verifier
existing CI baseline
```

Publication production and verification must work offline after checkout and
must not require raw Arena data, Hugging Face authentication, or acquisition of
a new source. The canonical report is Markdown. PDF and other rendered forms
are optional derivatives and cannot be prerequisites for acceptance.

## 18. Gate discipline and authorization

The phase retains the established workflow:

```text
candidate
-> Web GPT contract review
-> staging authorization
-> staged review
-> commit authorization
-> post-commit acceptance
-> implementation tasks
```

Acceptance of this contract does not by itself authorize P6-T2 implementation.
P6-T2 and later repository mutations require separate Web GPT authorization.
The `.gitignore` changes, publication generation, staging, commit, push, tag,
release, and any modification of E0/E1/E2 remain separately gate-dependent.

## 19. Planned task sequence

Following acceptance of this contract, the planned Phase 6 sequence is:

```text
P6-T1  publication contract and current-state documentation reconciliation
P6-T2  deterministic publication bundle serialization
P6-T3  independent publication traceability verifier
P6-T4  formal publication instance generation and acceptance
P6-T5  public-reader discoverability and reproducibility integration
P6-T6  final validation and Phase 6 closeout
P6-T7  controlled push and post-push public freeze
```

P6-T1 is not repository-complete until the accepted contract and README
reconciliation pass staging review, commit authorization, and post-commit
acceptance. P6-T2 remains separately gated.
