# Phase 2C Formal Run Contract

Status: tooling implemented; formal empirical execution has not been run.

This document defines how the first Phase 2C empirical result may be created. It
does not select the formal seed and it does not authorize a real bootstrap run.

## Required Binding

A formal run is bound to all of the following:

- an exact published Git commit, clean tracked worktree, and matching
  `origin/main` reference;
- the declared source dataset, revision, split, filename, and SHA-256;
- canonical schema version and named population/spec version;
- estimator and bootstrap configuration;
- an explicitly preregistered integer seed using `PCG64`;
- a validated `RunManifest` and integrity-verified artifact directory.

The formal runner does not fetch source data or invent a seed. Source paths are
provided at execution time and are checked against the manifest provenance before
canonicalization.

## Execution Modes

`preflight` performs configuration, Git, source, environment, population,
manifest, and artifact-path checks, then stops before fitting. `development`
allows synthetic or explicitly non-formal runs with a positive replicate count.
`formal` requires at least 2,000 fixed attempts, an explicit seed, publication
verification, and the same zero-failure inference gate used by the bootstrap
contract.

Execution mode does not alter estimator or resampling semantics. T9 does not
choose the eventual formal seed and does not execute the formal run.

## Artifact Layout

Each run is written under `outputs/research/<run_id>/` (or an explicitly supplied
ignored artifact root) using these fixed files:

```text
manifest.json
point_estimate.json
bootstrap_summary.json
bootstrap_scores.npz
bootstrap_ranks.npz
bootstrap_tie_parameter.npz
replicate_status.json
artifact_manifest.json
```

The run ID comes from `RunManifest`; it is not a timestamp, model name, seed, or
random directory name. A temporary `.tmp-<run_id>` directory is populated first,
verified, and atomically renamed. Existing final run directories are rejected.
Incomplete temporary directories are never valid result directories.

`artifact_manifest.json` records artifact schema version 1, the run ID, each
other filename, byte size, and SHA-256. It intentionally does not hash itself.
JSON uses sorted keys and compact separators. Matrix artifacts use deterministic
ZIP/Numpy encoding with fixed ZIP timestamps and contain arrays named `scores`,
`ranks`, and `tie_parameter` respectively.

## Result and Failure Semantics

Point estimates are serialized with model IDs, scores, ranks, diagnostics, and
counts for local research use. Bootstrap summaries preserve attempted,
successful, failed, failure codes, fixed matrix shapes, intervals, rank
summaries, pairwise stability, and tie-parameter summaries. Failed replicates
remain represented by status entries and `NaN` matrix rows.

Formal inference is valid only when:

```text
replicate_count >= 2,000
and failed_replicates == 0
```

The artifact verifier recomputes this gate and checks manifest identity, file
hashes/sizes, matrix shapes, and status length. A failed formal run may be kept
as a complete diagnostic artifact marked `formal_ci_valid: false`; it must not be
reported as a valid confidence interval.

## Privacy Boundary

Local artifacts may contain model IDs and statistical result matrices. They must
not contain raw rows, prompts, responses, judge-cluster IDs, per-judge results,
cache paths, or credentials. Public reporting is a later task and is not implied
by writing local artifacts.

## Reproduction Sequence

1. Check out the exact published Git SHA and verify a clean worktree.
2. Verify the declared environment and pinned source SHA-256.
3. Build the canonical table and apply the named frozen population.
4. Construct and round-trip the `RunManifest` with the preregistered seed.
5. Fit the point estimator and run exactly the configured bootstrap attempts.
6. Write the temporary artifact directory, verify hashes/content, and atomically
   finalize it under the manifest run ID.
7. Run the artifact verifier before interpreting or publishing any result.

No formal seed, formal result, ranking, or confidence interval is selected or
produced by this tooling task.
