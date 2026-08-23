# Phase 2 Research Contract

Status: Phase 2B foundation and pinned-snapshot parameter policy implemented. Final GPT closeout remains pending.

This document is the authoritative contract reference for subsequent research implementation. Snapshot-specific policies are bound to the exact source revision and hash recorded below; a source change requires a new support audit.

## 1. Research Scope

The project studies historical LLM Arena pairwise human preference evidence. It does not estimate objective model capability, define a current leaderboard, or make claims about current 2026 models from historical data.

The unit of evidence is a pairwise battle with two model responses and a human preference outcome. A battle is not treated as an independent natural person, and a judge cluster is not treated as a deanonymized user.

## 2. Research Questions

Primary questions:

- RQ1: pairwise preference ranking.
- RQ2: ranking uncertainty and stability.
- RQ3: preference heterogeneity, including language-conditioned views and topic-conditioned views only after the topic taxonomy is validated.

Secondary audit questions:

- RQ4: position association.
- RQ5: response length/style association.
- RQ6: judge and sampling structure sensitivity.

Associations are not causal claims. Position, length, language, topic, and judge-cluster associations must not be described as causes without a separately justified causal design.

## 3. Claim Levels

- C0: descriptive counts, distributions, and audit summaries.
- C1: associational comparisons.
- C2: model-based inferential claims with uncertainty.
- C3: robustness and heterogeneity claims.
- C4: causal claims; not permitted by default.
- C5: external generalization; not permitted by default.

The following claims are prohibited: an objectively best-LLM claim; a general claim about what all users prefer; a causal claim that longer responses cause higher ratings; a causal claim that A-side position causes votes; a claim that synthetic results describe Arena users; and a claim that historical Arena data establishes current model quality.

## 4. Canonical Battle Contract

The canonical representation is versioned by `CANONICAL_BATTLE_SCHEMA_VERSION = 2`.

### Source provenance and identity

Canonical rows carry `source_dataset`, `source_revision`, `source_split`, `source_file`, `source_file_sha256`, `source_snapshot_id`, `source_row_index`, and `battle_id`.

`source_snapshot_id` is a deterministic SHA-256 of the canonical serialized source provenance fields. `battle_id` is a deterministic SHA-256 of `source_snapshot_id`, a canonical separator, and `source_row_index`. Neither identity depends on cleaned row order, model normalization, winner normalization, or Python's randomized `hash()`.

`question_id_raw` is retained as a source field but is not battle identity. A missing question ID is not fabricated.

### Outcomes

The canonical taxonomy is `model_a_win`, `model_b_win`, `tie`, `tie_bothbad`, and `invalid_unknown`.

`winner_raw` is retained. Unknown, null, empty, and unrecognized values map to `invalid_unknown` and are never silently converted to `tie`. `tie` and `tie_bothbad` remain distinct.

For the pinned train snapshot, the observed raw source taxonomy is confirmed as exactly `model_a`, `model_b`, `tie`, and `tie (bothbad)` with no null or unrecognized labels. Counts are 11,744, 11,550, 3,443, and 6,263 respectively. The `tie_bothbad` category is substantial and must remain explicit.

### Validity

Canonical rows expose separate flags for model fields, distinct models, outcome validity, both conversation parse results, user and assistant presence on each side, prompt-pair consistency, timestamp validity, judge presence, language presence, exact duplicates, and `source_record_valid`.

Parseability is not research usability. An empty list may parse structurally, but without user and assistant turns it cannot be a valid source record. A parse failure is not relabeled as a missing turn.

### Timestamp

Numeric `tstamp` values are Unix seconds. Timezone-aware text is converted to UTC. Timezone-naive text is interpreted as UTC. Canonical fields are `timestamp_utc`, `battle_date_utc`, `battle_hour_utc`, and `battle_month_utc`; conversion does not depend on the host machine's local timezone.

### Model, language, and judge

Model identity is exact trimmed identity only. The contract does not fuzzy-match models, collapse version suffixes, merge vendors, or infer aliases. Raw and trimmed model fields are retained.

Language fields are `language_raw`, `language_canonical`, `language_source`, and `language_present`. The current contract does not redetect language.

Judge fields are `judge_cluster_id` and `judge_present`. The source identifier is treated as an anonymized judge/voter cluster, not a natural-person user ID. Deanonymization and profiling are prohibited.

Anonymous-source fields are `anony_raw`, `anony_valid`, and `anonymous_battle`. Native booleans are parsed strictly; the explicit string forms `true`, `false`, `1`, and `0` are supported for CSV round trips. Missing or unsupported values are invalid and mean `anonymous_battle = False`. Anonymous status is a population policy, not part of `source_record_valid`.

### Length

`prompt_chars`, `response_a_chars`, `response_b_chars`, `response_char_diff`, and `response_abs_char_diff` are Python string character counts. They are not token counts, semantic information measures, or causal verbosity measures.

### Duplicates

Canonicalization never silently drops rows. `exact_duplicate` is an audit flag. The base and legacy populations retain duplicates by default. `exclude_exact_duplicates=True` is an infrastructure capability for explicitly named sensitivity populations; the final real-data duplicate policy is not frozen.

## 5. Population Contract

Population policy is independently versioned by `POPULATION_SPEC_SCHEMA_VERSION = 2`. Every application returns an eligible view, one audit row per input battle, and a summary. Input order and battle identity are preserved.

### `base_research`

Requires `source_record_valid` and `anonymous_battle = True`. Allows `model_a_win`, `model_b_win`, `tie`, and `tie_bothbad`. Judge and language are optional. `invalid_unknown` is never eligible.

### `legacy_score`

Requires `source_record_valid` and `anonymous_battle = True`, and allows only `model_a_win`, `model_b_win`, and ordinary `tie`. Excluding `tie_bothbad` is a legacy descriptive score policy, not a permanent research-level exclusion.

### `judge_cluster_research`

Requires the base conditions plus `judge_present`. It is intended for judge-cluster uncertainty and concentration audits.

### `language_research`

Requires the base conditions plus `language_present`. It supports future language-conditioned analysis but does not itself choose language subgroups or thresholds.

## 6. Exclusion Audit Contract

Stable exclusion reason codes are `SOURCE_RECORD_INVALID`, `INVALID_MODEL_FIELDS`, `SAME_MODEL`, `INVALID_OUTCOME`, `INVALID_CONVERSATION_A`, `INVALID_CONVERSATION_B`, `MISSING_USER_TURN_A`, `MISSING_USER_TURN_B`, `MISSING_ASSISTANT_TURN_A`, `MISSING_ASSISTANT_TURN_B`, `PROMPT_PAIR_MISMATCH`, `INVALID_TIMESTAMP`, `MISSING_JUDGE`, `MISSING_LANGUAGE`, `INVALID_ANONY_FLAG`, `NON_ANONYMOUS_BATTLE`, `OUTCOME_NOT_ALLOWED`, and `EXACT_DUPLICATE_EXCLUDED`.

A battle may have multiple reasons, and reason counts may overlap. Reason derivation is hierarchical: invalid model fields do not also claim `SAME_MODEL`; parse failure does not claim missing user/assistant turns; prompt mismatch is reported only when both conversations are valid and both user sequences are assessable; invalid anonymous flags do not also claim `NON_ANONYMOUS_BATTLE`.

## 7. Run Manifest Contract

Run manifests are versioned by `RUN_MANIFEST_SCHEMA_VERSION = 1`. They bind `run_id`, `created_by`, `git_commit`, `git_branch`, source provenance and `source_snapshot_id`, `canonical_schema_version`, `population_id`, `population_spec_version`, `analysis_config`, `python_version`, and `package_versions`.

The deterministic `run_id` is derived from `source_snapshot_id`, canonical schema version, population ID/version, Git commit, and canonicalized analysis configuration. It does not use timestamps, hostnames, user paths, environment variables, API keys, or judge identifiers.

Manifest integrity is two-layered: `source provenance fields -> source_snapshot_id -> run_id`. Deserialization validates both links. Package versions are execution provenance and do not alter research-definition identity.

## 8. Statistical Protocol Status

The primary descriptive baseline includes pair counts and win/loss/tie distributions. Legacy score-rate is a descriptive compatibility baseline, not the formal estimator.

The required model-based baseline is the Bradley-Terry family. Explicit tie policy and tie-aware sensitivity are required, but the final tie-aware estimator has not been frozen or implemented.

The primary uncertainty design is judge-cluster bootstrap. Battle-row bootstrap is a sensitivity analysis. The target confidence level is 95%, and formal research runs target at least 2,000 bootstrap replicates. Tests and CI may use smaller deterministic replicate counts. No bootstrap or estimator is implemented in the current foundation.

## 9. Comparison Graph Contract

Formal ranking may only be interpreted within sufficiently connected comparison components. Disconnected components must not be forcibly ranked against one another. Comparison graph construction and connectivity analysis are not yet implemented.

## 10. Snapshot-Specific Real-Data Policy

The following policy is bound to revision `1b6335d42a1d2c7e34870c905d03ab964f7f2bd8` and SHA-256 `3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e`. A different source snapshot requires a new outcome-blind support audit.

The pinned snapshot contains 20 models, all 190 possible unordered pairs, and one complete connected comparison component. Every model has 19 observed opponents and at least 1,034 appearances. The overall primary policy therefore retains all 20 observed models without an arbitrary numeric model-support cutoff and restricts inference to the largest sufficiently connected component.

All observed eligible pair edges are retained for the primary analysis. Pair-support robustness specifications are `pair_count >= 10`, `>= 20`, and `>= 50`, retaining 99.9455%, 99.5152%, and 98.5364% of battles respectively; each sensitivity graph remains connected. These are robustness specifications, not model-strength filters.

Repeated `question_id` rows are retained as distinct battles because `question_id` is not battle identity. The sensitivity specification excludes all rows belonging to repeated-question groups; it does not keep an arbitrary first row. Exact duplicates are retained, and the pinned snapshot has zero exact-duplicate groups. `exclude_exact_duplicates=True` remains available for future snapshots and sensitivity runs.

High-activity judge clusters are not removed from the primary population. Their activity is not itself evidence of invalidity. Primary uncertainty remains judge-cluster bootstrap, with battle-row bootstrap as sensitivity, 95% confidence, and a formal target of at least 2,000 replicates. No high-activity removal cutoff is frozen.

Language policy is tiered. English is the formal primary language subgroup (29,206 battles, 20 models, 190 pairs, connected graph). German, Spanish, French, Portuguese, and Russian are structured exploratory/secondary tiers. Chinese, Italian, Dutch, `unknown`, and lower-support labels are descriptive-only. No single numeric language-count threshold is frozen; promotion requires per-model, per-pair, and uncertainty diagnostics.

## 11. Remaining Not Yet Frozen

The final tie-aware estimator choice remains unfrozen and is deferred to Phase 2C. Any future high-activity-judge exclusion sensitivity cutoff also requires a separately registered decision. These are not primary exclusions for the pinned snapshot.

## 12. Real Dataset Access Status

The current source reference is a provisional metadata-pinned reference:

`dataset: lmsys/chatbot_arena_conversations`; `metadata revision: 1b6335d42a1d2c7e34870c905d03ab964f7f2bd8`; `split: train`; `metadata row count: 33,000`; `source file: data/train-00000-of-00001-cced8514c7ed782a.parquet`; `metadata/LFS SHA-256: 3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e`.

T6/T7 verified authenticated row-level access, the pinned Parquet file, its exact SHA-256, and 33,000 rows. Outcome taxonomy, question-ID structure, duplicate structure, model/pair support, language labels, judge concentration, UTC timestamps, conversation structure, `anony`, and graph connectivity were audited without ranking or outcome-driven threshold selection.

## 13. Synthetic vs Real Boundary

Synthetic data is permitted for tests, CI, integration, examples, pipeline reproduction, and algorithm unit tests. Synthetic data cannot support substantive model-preference claims, real ranking, user-preference conclusions, or Arena population conclusions.

## 14. Legacy Modules

The repository still contains historical or exploratory score-rate analysis, rule/KMeans topic labeling, a RandomForest preference demo, visualizations/dashboard code, notebooks, and MySQL export code. These are not automatically approved Phase 2 formal methodology. RandomForest demo accuracy is not validated real-world preference-prediction performance.
