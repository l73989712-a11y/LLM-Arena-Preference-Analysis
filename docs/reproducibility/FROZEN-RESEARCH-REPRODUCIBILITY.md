# Frozen Research Reproducibility

## 1. Purpose and Scope

This is the durable external protocol for inspecting, verifying, and boundedly
replaying the frozen research product from a clean repository checkout. It
does not define a new analysis or scientific evidence layer.

The project studies historical LLM Arena pairwise human-preference data. The
formal interpretation is:

> estimated preference under the frozen historical Arena population

This is not an objective model capability ranking, current model quality or
Arena leaderboard, universal ranking or recommendation, or causal effect.

## 2. Frozen Authority Chain

The formal authority chain is:

```text
E0  frozen source snapshot
 -> E1  frozen formal research evidence
 -> E2  frozen ranking-robustness evidence
 -> Phase 6 publication  derived publication bundle
```

E0 is the source authority. E1 is the immutable formal research bundle. E2
is deterministic robustness evidence derived from E1. The Phase 6 publication
is a derived, independently verifiable publication bundle. Level 2 replay is
scratch, NON-AUTHORITATIVE reproduction evidence; it is not E3 and never
replaces a frozen authority.

### E0 source identity

```text
dataset: lmsys/chatbot_arena_conversations
revision: 1b6335d42a1d2c7e34870c905d03ab964f7f2bd8
source file: data/train-00000-of-00001-cced8514c7ed782a.parquet
source SHA-256: 3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e
source_snapshot_id: 2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4
rows: 33000
models: 20
unordered pairs: 190
```

The raw source file is external and is not required for frozen verification.

### E1 formal evidence

```text
bundle: formal-research-v1
root: artifacts/frozen/formal-research-v1/
payload files: 73
payload bytes: 3626761
payload inventory SHA-256: 392066c7a23408e97f0f2bcd3e2a530b167e596c9b382d999d959ba49abb7eb6
```

### E2 robustness evidence

```text
root: artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e/
artifact_instance_id: 82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
derivation_spec_id: dc03cc925d2a85dc023542fc21f703abbb966dd4df5da36974c8ea061ece0be4
producer_git_sha: 766fd10a0a22c1266a70b11c1581e8f607f10c07
payload_inventory_sha256: a6a872a6737b5fd7e8d9836ff34ee895d5e99784bca4b5ef1ccb839f7f88857f
```

### Phase 6 publication

```text
root: artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467/
publication_instance_id: 1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467
publication_spec_id: 62503b0a94b7658c6c0b48b8b9d9b7e43df2e963039b999d9a87a2af760ba400
payload_inventory_sha256: dfd065cfc00d333f64c31e7481132954f2778e8b7a1b1f34875190d1e529f095
producer_git_sha: ae27c390524a3e9dd6524a7c131aa9d2c51485e6
```

The Phase 6 public repository freeze identity is
`18ba7f3989deb6d29dc485fcba62c0ecdc6c39e4`. It identifies the public Git
repository state at the Phase 6 freeze, not the current repository HEAD and
not a producer implementation. In particular, `producer_git_sha` and the
repository public-freeze SHA must never be substituted for one another.

## 3. Supported Environment

The supported Python policy is `>=3.12,<3.13`. The accepted reference
resolution is CPython 3.12.5 on Windows AMD64. Install from the repository
root with the constrained development requirements:

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt -c requirements-constraints.txt
.\.venv\Scripts\python -m pip check
```

POSIX shell:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt -c requirements-constraints.txt
.venv/bin/python -m pip check
```

Installation is network-dependent. The project does not require or promise
wheel hash locking, vendored dependencies, an offline wheelhouse, air-gapped
installation, or a fully hermetic supply-chain reconstruction.

## 4. Level 1 - Verification

Run these commands from the repository root:

```text
python -B verify_frozen_bundle.py
python -B verify_ranking_robustness.py artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
python -B verify_publication_bundle.py artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467
```

These three independent verifiers cover E1, E2, and the Phase 6 publication.
They are read-only: they do not acquire raw Arena data, run producers, rerun
inference, or write into accepted roots. Success reports `VERDICT: PASS` and
returns exit code 0. Expected verification or usage failures are non-zero;
an internal verifier error is also non-zero.

Level 1 is mandatory for the Phase 7 reproducibility contract.

### Clean-checkout procedure

Start from a clean checkout of the repository revision containing this
reproducibility guide:

```text
git clone <repository>
cd <repository>
```

Create the documented Python 3.12 environment, install
`requirements-dev.txt` with `requirements-constraints.txt`, and run:

```text
python -m pip check
```

Then run the three Level 1 authority verifiers from the repository root:

```text
python -B verify_frozen_bundle.py
python -B verify_ranking_robustness.py artifacts/phase-5/82239159eecc2067b7b89f9e13b9cf34d36497b8fdd7105e6babbcc2668e9a1e
python -B verify_publication_bundle.py artifacts/phase-6/publication-v1/1cd6f03c87ff4e909c5b97bd8727a4d5e6b04225ef32f9fc33303ee72f612467
```

These three verifiers are the minimum Level 1 authority checks. Raw Arena
data and E0 acquisition are not required; no producer execution or E1
regeneration occurs. `python -m pytest -q` and `git diff --exit-code` are
broader repository and CI-parity checks, not additional scientific authority
verifiers.

## 5. Level 2 - Bounded Downstream Replay

The supported external interface is:

```text
python -B replay_frozen_products.py e2 --output-root <NEW_PATH>
python -B replay_frozen_products.py publication --output-root <NEW_PATH>
```

`<NEW_PATH>` must be an explicit destination that does not already exist. The
wrapper protects accepted E1, E2, and Phase 6 roots, rejects unsafe aliases and
ancestor/child relationships, and never overwrites or merges an existing
destination. Outputs are scratch and NON-AUTHORITATIVE.

The two supported paths are independent:

```text
accepted E1 -> scratch E2
accepted E1 + accepted E2 -> scratch Phase 6 publication
```

Publication replay does not consume a scratch E2. Both paths verify their
accepted inputs before production and verify the scratch result afterward.
Replay does not acquire E0, regenerate E1, download source data, or create
E3. A successful replay demonstrates downstream reproduction only and does
not replace the accepted E2 or publication bundle.

## 6. Level 3 - Intentionally Unsupported

The following are intentionally outside the public reproducibility contract:

- remote E0 acquisition;
- E0-to-E1 formal regeneration;
- full source-to-publication reconstruction;
- offline or hermetic reconstruction of the scientific record.

This is a deliberate support boundary, not a temporary implementation defect
or a promise of future Phase 7 work.

## 7. Formal and Exploratory Interfaces

`formal_app.py` presents the tracked frozen evidence and does not regenerate
E1 or produce new estimates. `app.py`, `run_pipeline.py --mode sample`,
`run_pipeline.py --mode real`, notebooks, and related exploratory surfaces are
not formal E0 reproduction paths and do not carry E1/E2/publication authority.
In particular, a current-data or convenience path must not be interpreted as
source-to-publication reproduction.

## 8. Determinism and Equivalence

Level 2 inherits the existing producer, verifier, manifest, canonical JSON,
identity, and inventory rules. E2 structured outputs and publication
structured/text payloads follow their existing deterministic contracts under
the frozen inputs and producer identities. Cross-platform PNG byte identity
is not guaranteed. The publication verifier is the acceptance mechanism for
the declared inventory and semantic validity of a replay bundle.

## 9. CI and Hosted Evidence

The workflow definition is
[`.github/workflows/frozen-reproducibility.yml`](../../.github/workflows/frozen-reproducibility.yml).
Its current Phase 7 definition contains explicit gates for:

- the E1 frozen-bundle verifier;
- the E2 ranking-robustness verifier;
- the Phase 6 publication verifier;
- the constrained environment, `pip check`, and safe pytest suite;
- tracked-checkout cleanliness.

The historical Phase 4 hosted Ubuntu run remains historical evidence. The
Phase 7-expanded workflow completed hosted Level 1 acceptance on GitHub
Actions:

```text
workflow: Frozen Reproducibility
run: 33936320166
event: push
commit: c1dce0e235f6b0790e583668f4731fb8b33a7134
conclusion: success
job: verify
```

The successful `verify` job completed constrained environment setup, `pip
check`, the E1, E2, and Phase 6 publication verifiers, the safe pytest suite,
and tracked-checkout cleanliness. This is hosted Level 1 verification evidence
only: it does not create E3, replace a frozen authority, or extend the Level 3
support boundary. A local workflow definition and a hosted acceptance result
remain separate facts.

## 10. Attribution, Rights, and Contents

See the [frozen bundle notice](../../artifacts/frozen/formal-research-v1/NOTICE.md)
for the upstream dataset citation, revision, source hash, and terms links.
The upstream dataset identifies user prompts as CC BY 4.0 and model outputs as
CC BY-NC 4.0. The published payload contains aggregate and statistical
derivatives only; it contains no raw prompts, model responses, conversation
rows, or user identifiers.

The repository MIT license applies to original repository material. It does
not supersede or relicense upstream or other third-party material, and this
guide makes no new legal conclusion about rights or database status.

## 11. Limitations and Non-Goals

The frozen results concern only the historical Arena population, frozen
20-model universe, and committed E1/E2/publication authorities. They do not
establish current model quality, a current leaderboard, objective capability,
universal preference, recommendation, causal effects, or external
generalization. Sampling uncertainty does not exhaust all possible uncertainty.

Raw-data acquisition, E1 regeneration, arbitrary uploaded datasets, and
current-data exploratory paths are outside the supported levels above.
Generated paths such as `outputs/` are local outputs. Cross-platform rendered
image bytes are not promised to be identical.

## 12. Related Records

- [Phase 7 reproducibility contract](../phase-7/P7-REPRODUCIBILITY-CONTRACT.md)
- [Phase 6 closeout](../phase-6/PHASE-6-CLOSEOUT.md)
- [Phase 5 closeout](../phase-5/PHASE-5-CLOSEOUT.md)
- [Phase 2 research contract](../phase-2/RESEARCH-CONTRACT.md)
- [Frozen bundle notice](../../artifacts/frozen/formal-research-v1/NOTICE.md)
