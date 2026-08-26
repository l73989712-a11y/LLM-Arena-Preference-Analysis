# Phase 2C Final Closeout

Status: **CLOSED / FROZEN**

This document is the durable record of the Phase 2C formal analysis. It
supersedes the earlier implementation-readiness status for formal empirical
execution, while preserving the historical contracts and run identities.

## Scope and Research Boundary

Phase 2C estimates latent relative human preference in the pinned historical
LLM Arena pairwise-comparison population. The estimands are observational and
model-based. They are not objective capability measurements, universal user
preferences, current leaderboards, causal effects, or externally generalized
claims.

Phase 2A research framing is closed and frozen. Phase 2B canonical/data
contracts are closed and frozen. Phase 3 is not started.

## Pinned Source

```text
dataset: lmsys/chatbot_arena_conversations
revision: 1b6335d42a1d2c7e34870c905d03ab964f7f2bd8
split: train
file: data/train-00000-of-00001-cced8514c7ed782a.parquet
SHA-256: 3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e
source_snapshot_id: 2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4
rows: 33000
models: 20
unordered pairs: 190
```

Outcome counts are 11,744 A wins, 11,550 B wins, 3,443 ordinary ties, and
6,263 `tie_bothbad` outcomes. The raw Parquet remains external/cache-only and
is not committed to Git.

## Primary / Baseline Formal Contract

```text
estimator: Davidson (version 1)
primary outcome policy: ordinary_tie_only
gauge: sum(theta) = 0
optimizer: L-BFGS-B
regularization: None
bootstrap unit: judge_cluster
replicates: 2000 fixed attempts
RNG: PCG64
redraw: false
CI: 95% equal-tailed percentile
quantile method: linear
failure gate: attempted >= target and failed == 0
parallelism: serial
```

`quantile_method=linear` is fixed by the published bootstrap implementation
and the frozen bootstrap-contract documentation. It is not a separately
editable result field; formal execution uses the published implementation.

This is the Primary/Baseline contract. The preregistered sensitivity runs make
the following single-axis exceptions: S1 changes the tie policy and therefore
the tie estimand; S2 changes the estimator and decisive-outcome policy to
Bradley-Terry; and S3 changes only the bootstrap resampling unit to
`battle_row`. S4, S5, and S6 retain the Primary Davidson,
`ordinary_tie_only`, and `judge_cluster` estimator/uncertainty mechanics and
change only the named population view. All formal mechanics not changed by a
specific sensitivity continue to follow this frozen baseline contract.

## Formal Run Registry

Every run below is finalized, verified, and inference-valid (`2000/2000`, zero
failed replicates). Each run has its own manifest, seed, run ID, and artifact
directory.

| Analysis | Git SHA | Population | Seed | Run ID |
|---|---|---|---:|---|
| Primary | `2dad21a4816931b0dddf4ae77282ffde1c713512` | `base_research` | 15832207067816131242 | `9c1fd5abbe8681db45b535e5368c806caad8d8297914c7b86a598112900f2689` |
| S1 coalesced ties | `2d268c753478bc695b4f516fd70c738460c683b9` | `base_research` | 15918316334149081368 | `fa59994fb1f9de6a093162858bda584f6241c4a42314f0b027e57e2ff04d33e7` |
| S2 decisive BT | `2d268c753478bc695b4f516fd70c738460c683b9` | `base_research` | 17623742310410676408 | `3babe007af583d3f8a6b4e25731828a77dd6e91d1f1110c618f82aee531d49d3` |
| S3 battle-row bootstrap | `2d268c753478bc695b4f516fd70c738460c683b9` | `base_research` | 2232815072757272902 | `3c62408ca810a5aaa34a3c237333156b8f62ebeb7e1d94f4316264f898b3e2cf` |
| S4 repeated-question exclusion | `241a6db67686def7a777c00704d997e281eab1a9` | `base_research_no_repeated_qid` | 10795549338136829013 | `33b992df5e34b50d69218931bbcbadeee9db8658bd0b697d785cc909e3bb7d1f` |
| S5 support >=10 | `241a6db67686def7a777c00704d997e281eab1a9` | `base_research_pair_support_ge10` | 22049035408235882 | `60c314ba7c6453b8227db0be16a73963df0bda1e8321cd1085ae698549d6a466` |
| S5 support >=20 | `241a6db67686def7a777c00704d997e281eab1a9` | `base_research_pair_support_ge20` | 5611320067224646494 | `29a6ad3a3e401210de5a0ac1ad915e92d86bdcd6d954223dbb73fcf2e6f5ab7f` |
| S5 support >=50 | `241a6db67686def7a777c00704d997e281eab1a9` | `base_research_pair_support_ge50` | 6822823098261160380 | `da1dbcf8f4a55403f1df8e8cd4ada2b903b93431486ce337849f116f2aadc7e2` |
| S6 English | `241a6db67686def7a777c00704d997e281eab1a9` | `base_research_language_en` | 3148167322047722507 | `8dba0d09c93abafe6c448a3ddb8ee22671792208e85b378f5c1b2328ee52624d` |

The finalized artifact directories are under `outputs/research/<run_id>/` and
were verified with the default finalized-directory verifier.

## Population Evidence

| View | Effective rows | Davidson-effective rows | Models | Pairs | Judge clusters |
|---|---:|---:|---:|---:|---:|
| S4 no repeated question | 32961 | 26706 | 20 | 190 | 13373 |
| S5 support >=10 | 32982 | 26725 | 20 | 187 | 13376 |
| S5 support >=20 | 32840 | 26614 | 20 | 177 | 13333 |
| S5 support >=50 | 32517 | 26364 | 20 | 169 | 13207 |
| S6 English | 29206 | 23854 | 20 | 190 | 11676 |

S4 identified 19 repeated nonblank `question_id_raw` groups containing 39
rows. Nonblank identity is exact; trimming is used only for blank detection.
Missing and blank IDs are retained and never grouped together.

S5 support is an inclusive, unordered-pair count over all BASE_RESEARCH-eligible
rows before estimator outcome filtering. All four outcome classes contribute;
qualifying pairs are selected once and all their rows are retained. No
iterative pruning or outcome-based model selection is used.

S6 is the exact canonical filter `language_canonical == "English"`; no language
redetection or prompt inference is performed.

## Primary Point Ranking

The Primary Davidson point ordering is:

1. `gpt-4`
2. `claude-v1`
3. `claude-instant-v1`
4. `gpt-3.5-turbo`
5. `guanaco-33b`
6. `vicuna-13b`
7. `wizardlm-13b`
8. `palm-2`
9. `vicuna-7b`
10. `koala-13b`
11. `gpt4all-13b-snoozy`
12. `mpt-7b-chat`
13. `RWKV-4-Raven-14B`
14. `alpaca-13b`
15. `oasst-pythia-12b`
16. `fastchat-t5-3b`
17. `chatglm-6b`
18. `stablelm-tuned-alpha-7b`
19. `dolly-v2-12b`
20. `llama-13b`

This is a historical Arena estimated-preference ordering, not an objective
capability leaderboard.

## Comparative Findings

Primary, S1, S2, S3, S4, and all three S5 views have identical 20-model point
ordering, Spearman rho 1.0 versus Primary, maximum point-rank displacement 0,
and preserved top-four set and order. The `gpt-4` rank-1 bootstrap probability
is 1.0 in all nine reviewed analyses.

Local uncertainty remains despite stable point ordering. The reviewed
pairwise direction ranges were approximately 97.15%-99.45% for
`claude-v1` versus `claude-instant-v1`, 56.15%-75.95% for `vicuna-13b` versus
`wizardlm-13b`, 51.2%-68.9% for `gpt4all-13b-snoozy` versus `mpt-7b-chat`, and
34.8%-58.8% for `alpaca-13b` versus `oasst-pythia-12b`. Nearby positions must
not be presented as certain solely because the point ranking is deterministic.

S1 changes the tie estimand, so its Davidson tie parameter is not numerically
comparable with the Primary tie parameter. S2 uses decisive-only Bradley-Terry,
so its score scale is not interchangeable with Davidson theta. S3 changes only
the resampling unit and is an uncertainty/dependence sensitivity, not an
automatically superior bootstrap.

S4 is robust under repeated-question exclusion in this sample. S5 is robust
under the evaluated support restrictions; it is support-restriction robustness,
not data cleaning.

S6 English has Spearman rho 0.993985 versus Primary, maximum displacement 2,
mean absolute displacement 0.3, and preserved top-four set/order. Local changes
include `palm-2` 8->6, `vicuna-13b` 6->7, `wizardlm-13b` 7->8, and an
`alpaca`/`oasst-pythia` swap. This is classified as **PARTIALLY ROBUST /
HETEROGENEOUS**. It is not a causal language effect and does not identify why
the subgroup differs.

Overall classifications:

- Primary/core ordering: **ROBUST (C3)**
- Local middle/lower ordering: **UNCERTAIN, with uncertainty itself robust**
- English subgroup: **PARTIALLY ROBUST / HETEROGENEOUS (C3)**
- Davidson tie component: **robust to resampling, estimand-sensitive to tie definition**

## Claim Boundary

Supported claim levels are:

- **C0:** descriptive
- **C1:** associational
- **C2:** model-based inferential
- **C3:** robustness and heterogeneity

The following are not supported by Phase 2C:

- objective model capability ranking;
- universal user-preference claims;
- causal effects of language or other covariates;
- a current 2026 Arena leaderboard;
- external generalization beyond the pinned historical dataset.

## Comparative Review Provenance

The read-only T20 review artifact is:

```text
path: outputs/research/comparative_review/review.json
byte size: 89996
SHA-256: 452192dabbb8e8ad428a023ab8bb78052688965473a2736c5be352d021f26ffa
```

An earlier relay contained a 39-character incorrect/truncated digest. The
64-character SHA-256 above is the authoritative value.

## Deferred Exploratory Work

German, Spanish, French, Portuguese, and Russian L2 audits were intentionally
deferred and not executed. They are not required for Phase 2 validity and would
add subgroup support, multiplicity, and interpretation burden. Deferral does
not imply failure.

## Limitations and Residual Risks

1. The source is a historical observational dataset.
2. No causal identification is available.
3. The model universe is fixed to the historical Arena population.
4. Arena judge/user composition may not represent broader populations.
5. Subgroup composition and support can differ from the full population.
6. English subgroup association does not identify a language causal effect.
7. Pairwise ranking models simplify heterogeneous human preference behavior.
8. Local ranking uncertainty remains despite stable point ordering.
9. Results are not a current leaderboard.
10. The raw source is pinned externally and intentionally not committed to Git.

## Final Phase Status

```text
Phase 2A: CLOSED / FROZEN
Phase 2B: CLOSED / FROZEN
Phase 2C: CLOSED / FROZEN
Phase 3: NOT STARTED
```

Formal artifacts, seeds, manifests, and run IDs are immutable evidence. Any
future analysis with a changed source, code SHA, estimator, population, or
bootstrap contract requires a new explicitly reviewed run identity.
