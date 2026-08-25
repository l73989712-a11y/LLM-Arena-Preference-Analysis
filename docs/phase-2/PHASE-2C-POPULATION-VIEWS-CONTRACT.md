# Phase 2C Population Views Contract

## Scope

This document freezes the manifest-addressable population views introduced for
S4, S5, and S6. It does not authorize a formal sensitivity execution, seed
selection, or result generation.

The historical population remains immutable:

```text
population_id: base_research
population_spec_version: 2
```

Derived sensitivity populations use a separate `population_view_schema_version`
of `1`. The view schema describes a deterministic single-axis transformation
of `base_research` v2; it does not redefine or upgrade the base population.

## Registered View IDs

The registry accepts exactly these effective IDs:

```text
base_research_no_repeated_qid
base_research_pair_support_ge10
base_research_pair_support_ge20
base_research_pair_support_ge50
base_research_language_en
```

Unknown IDs are rejected. There is no fallback to `base_research`.

Every view definition serializes the following identity:

```json
{
  "population_id": "<effective-id>",
  "population_view_schema_version": 1,
  "base_population": {
    "population_id": "base_research",
    "population_spec_version": 2
  },
  "view": {
    "view_type": "..."
  }
}
```

Observed row counts, discovered question IDs, support pair lists, and result
values are never part of this identity.

## Filtering Order

All views use the same order:

```text
raw pinned source
  -> canonicalize_battles()
  -> apply BASE_RESEARCH v2
  -> apply exactly one named population view
  -> effective PopulationResult
  -> estimator outcome filtering
  -> graph/existence checks
  -> fit/bootstrap
```

Views are not composable in this contract. S4+S5, S5+English, and other
combined filters require a later explicit contract.

## S4: Repeated Question Exclusion

View ID: `base_research_no_repeated_qid`

```json
{
  "view_type": "exclude_repeated_question_groups",
  "question_id_field": "question_id_raw",
  "missing_policy": "retain_not_grouped",
  "group_policy": "exclude_all_rows_when_count_gt_1"
}
```

Counts are computed only among BASE_RESEARCH-eligible rows. A nonmissing,
nonblank question ID occurring more than once excludes every row in that group.
No representative is retained. Missing and blank IDs are retained and do not
form one shared group. No IDs are fabricated, and repeat detection is
independent of outcome and input row order. Whitespace trimming is used only
to classify blank values; nonblank `question_id_raw` identity is not normalized
by trimming or stringification.

## S5: Unordered Pair Support

View IDs:

```text
base_research_pair_support_ge10
base_research_pair_support_ge20
base_research_pair_support_ge50
```

Each uses:

```json
{
  "view_type": "unordered_pair_support_threshold",
  "pair_definition": "canonical_unordered_model_pair",
  "support_population": "base_research",
  "support_measure": "eligible_battle_count",
  "support_count_stage": "before_estimator_outcome_filter",
  "threshold_operator": ">=",
  "threshold": 10
}
```

The threshold value is 10, 20, or 50 for the corresponding ID. Pair identity
is orientation invariant, conceptually `(min(model_a_id, model_b_id),
max(model_a_id, model_b_id))`. All BASE_RESEARCH-eligible outcomes contribute
to support, including ordinary ties and `tie_bothbad`.

Support is counted once on the complete base population. Every row belonging to
a qualifying pair is retained; nonqualifying pairs are removed completely.
There is no iterative recount, deduplication, representative selection, or
outcome-based model pruning. Estimator-effective graph connectivity is checked
later by the existing formal path; a disconnected graph is a blocker rather
than a reason to drop components.

## S6: English View

View ID: `base_research_language_en`

```json
{
  "view_type": "language_exact_match",
  "language_field": "language_canonical",
  "language_value": "English"
}
```

The exact canonical equality `language_canonical == "English"` is applied
after BASE_RESEARCH. The view does not redetect language, infer language from
prompts, case-fold values, use substring matching, or map neighboring labels.
L2 languages remain support-audit-only and are not registered formal views.

## Manifest and Run Identity

For a derived view, `RunManifest.population_id` is the effective view ID and
`RunManifest.population_spec_version` is `1`. The manifest's
`analysis_config.population_view` contains the full deterministic view
definition and its base v2 provenance. The existing `run_id_for` algorithm is
the sole identity algorithm; because population identity and analysis config
are included, different views produce different run IDs while identical view
definitions reproduce the same run ID.

Base runs continue to omit `population_view` from their analysis config and
retain their historical v2 identity.

## Downstream Compatibility and Privacy

`apply_population_view()` returns an effective `PopulationResult`, so the
accepted estimator and bootstrap APIs receive tracked population results and
do not operate on ad hoc filtered frames. View audits preserve aggregate
eligibility information without exposing question IDs, raw language rows,
support pair lists, prompts, responses, judge IDs, credentials, or cache paths
in manifests or research artifacts.

## Execution Boundary

T17 implements and audits the population layer only. It selects no S4/S5/S6
seeds, preregisters no formal run IDs, fits no real sensitivity estimator, runs
no bootstrap, and writes no sensitivity artifacts. A later preregistration
task must bind executions to the published T17 implementation commit.
