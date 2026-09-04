# LLM Arena User Preference Analysis

This repository studies historical LLM Arena pairwise human-preference data.
The formal research product estimates preference under a frozen historical
Arena population. It is not an objective capability ranking, a universal
user-preference claim, a current Arena leaderboard, or a causal analysis.

The scientific interpretation is defined in the [Phase 2 research contract](docs/phase-2/RESEARCH-CONTRACT.md).
The accepted formal evidence history is recorded in the [Phase 2C closeout](docs/phase-2/PHASE-2C-CLOSEOUT.md),
and the presentation/report history is recorded in the [Phase 3 closeout](docs/phase-3/PHASE-3-CLOSEOUT.md).

## Current Status

- Phase 3: **CLOSED / PUBLICLY FROZEN**
- Phase 4: **CLOSED / PUBLICLY FROZEN**
- Phase 5: **CLOSED / PUBLICLY FROZEN**
- Phase 6: **CLOSED / PUBLICLY FROZEN**
- Phase 7: **IN PROGRESS / NOT YET PUBLICLY FROZEN**

The Phase 6 public repository freeze identity is:

```text
18ba7f3989deb6d29dc485fcba62c0ecdc6c39e4
```

This is the Phase 6 freeze identity, not the current repository HEAD and not
the identity of either research producer. Later Phase 7 work must not be read
as a new scientific evidence layer.

The Phase 4 frozen bundle, canonical verifier, reproducible dependency
constraints, clean-checkout workflow, and hosted Ubuntu acceptance are
recorded in the [Phase 4 closeout](docs/phase-4/PHASE-4-CLOSEOUT.md).

Phase 5 adds deterministic ranking-robustness evidence derived from the
immutable frozen E1 bundle. Its formal artifact, four-layer identity, bounded
historical interpretation, and independent verification evidence are recorded
in the [Phase 5 closeout](docs/phase-5/PHASE-5-CLOSEOUT.md).

The committed formal E2 artifact is:

```text
artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e/
```

Verify it with:

```powershell
python -B verify_ranking_robustness.py artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
```

The formal identities are `derivation_spec_id`, `producer_git_sha`,
`artifact_instance_id`, and `e2_payload_inventory_sha256`; the closeout records
their exact values. The authoritative Phase 5 public freeze is:

```text
main / origin/main:
a3d93a8908e1797816048489821e59b90fbb5945
```

## Frozen Authority Chain

The formal authority chain is:

```text
E0  frozen source snapshot
 -> E1  frozen formal research evidence
 -> E2  frozen ranking-robustness evidence
 -> Phase 6 publication  derived publication bundle
```

Level 2 replay outputs are scratch, NON-AUTHORITATIVE reproduction evidence.
They do not create E3 or replace any frozen authority.

## Phase 6 Formal Publication

The [formal report](artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467/report.md)
reports estimated preference under the frozen historical Arena population. Its
historical Primary top three are `gpt-4`, `claude-v1`, and
`claude-instant-v1`; this is not a current leaderboard, objective capability
ranking, universal recommendation, or causal claim.

The publication instance includes a machine-readable
[manifest](artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467/manifest.json)
and four publication figures:
[primary preference](artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467/figures/primary_preference.png),
[rank uncertainty](artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467/figures/rank_uncertainty.png),
[robustness ranks](artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467/figures/robustness_ranks.png),
and [English-subgroup ranks](artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467/figures/s6_heterogeneity.png).

```text
publication_instance_id: 1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467
publication_spec_id: 62503b0a94b7658c6c0b48b8b9d9b7e43df2e963039b999d9a87a2af760ba400
payload_inventory_sha256: dfd065cfc00d333f64c31e7481132954f2778e8b7a1b1f34875190d1e529f095
producer_git_sha: ae27c390524a3e9dd6524a7c131aa9d2c51485e6
independent verifier commit: b78a2304ae9f44486094cd390268056c1ec3f4c3
repository public-freeze SHA: 18ba7f3989deb6d29dc485fcba62c0ecdc6c39e4
```

`producer_git_sha` identifies the implementation that produced a bundle. The
repository public-freeze SHA identifies a Git repository state; these values
must not be substituted for one another.

Verify the committed formal publication instance with:

```powershell
python -B verify_publication_bundle.py artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467
```

Verification checks the committed instance. The [Phase 6 closeout](docs/phase-6/PHASE-6-CLOSEOUT.md)
records the completed Phase 6 closeout. P6-T7 is the repository-publication
operation for the closed Phase 6 commit range; public publication/freeze status
is authoritative from remote Git history and post-push `HEAD`/`origin/main`
identity, rather than a self-referential README status claim. Same-environment
deterministic reproduction uses the frozen producer identity
`ae27c390524a3e9dd6524a7c131aa9d2c51485e6`; cross-platform PNG byte equality
is not required. Phase 6 formal publication: **FROZEN**.

## Quick Reproducibility

The canonical environment supports Python `>=3.12,<3.13`. The reference
resolution was CPython 3.12.5 on Windows AMD64. Use the explicit virtual
environment interpreter after creating the environment.

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt -c requirements-constraints.txt
.\.venv\Scripts\python -m pip check
.\.venv\Scripts\python -B verify_frozen_bundle.py
.\.venv\Scripts\python -B verify_ranking_robustness.py artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
.\.venv\Scripts\python -B verify_publication_bundle.py artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467
.\.venv\Scripts\python -m pytest -q
```

POSIX shell:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt -c requirements-constraints.txt
.venv/bin/python -m pip check
.venv/bin/python -B verify_frozen_bundle.py
.venv/bin/python -B verify_ranking_robustness.py artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
.venv/bin/python -B verify_publication_bundle.py artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467
.venv/bin/python -m pytest -q
```

Run the three verifier commands from the repository root. They are read-only,
do not acquire raw Arena data, and do not rerun formal inference. A successful
verifier reports `VERDICT: PASS`.

## Bounded Level 2 Replay

The public replay interface is:

```text
python -B replay_frozen_products.py e2 --output-root <NEW_PATH>
python -B replay_frozen_products.py publication --output-root <NEW_PATH>
```

`<NEW_PATH>` must not already exist. Each output is scratch and
NON-AUTHORITATIVE. E2 replay consumes accepted E1; publication replay consumes
accepted E1 and accepted E2, not a scratch E2. Replay does not acquire E0,
regenerate E1, or download source data. Accepted roots are never replaced and
successful output is independently post-verified. Detailed failure and
equivalence rules are in the [reproducibility guide](docs/reproducibility/FROZEN-RESEARCH-REPRODUCIBILITY.md).

## Level 3 - Intentionally Unsupported

The project does not provide a public contract for remote E0 acquisition,
E0-to-E1 regeneration, full source-to-publication reconstruction, or
offline/hermetic reconstruction. This is an intentional support boundary.

## Formal Application

The formal frozen-evidence interface is `formal_app.py`:

```powershell
.\.venv\Scripts\python -m streamlit run formal_app.py
```

```bash
.venv/bin/python -m streamlit run formal_app.py
```

It presents the tracked frozen evidence and does not require
`outputs/research`, regenerate E1, or produce new estimates.

The existing `app.py` and sample pipeline remain legacy synthetic/demo
surfaces. They are useful for demonstrations and exploration but do not have
the scientific authority of the formal frozen bundle.

## Data Boundary

- `data/sample/arena_sample.csv` is a deterministic synthetic fixture; it does not contain real Arena conversations or users.
- Raw Arena data is external and is not required for frozen verification.
- `requirements_optional.txt` is outside the canonical Phase 4 verification and test environment.
- Generated paths such as `outputs/` remain local/ignored outputs.

## Detailed Guide

See [Frozen Research Reproducibility](docs/reproducibility/FROZEN-RESEARCH-REPRODUCIBILITY.md)
for the public bundle identity, clean-checkout procedure, verifier contract,
formal/demo authority boundary, Level 1 and Level 2 protocols, CI contract,
provenance, licenses, and limitations.

For upstream rights and attribution, see the [frozen bundle notice](artifacts/frozen/formal-research-v1/NOTICE.md).

## Development Checks

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m compileall -q .
```

The repository also contains exploratory notebooks and SQL examples. They are
not part of the frozen formal verification contract.
