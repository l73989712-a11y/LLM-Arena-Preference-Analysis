# Frozen Formal Research Bundle Notice

This directory contains the reviewed, frozen aggregate research-output bundle
for the historical Phase 2-3 LLM Arena preference analysis. The `payload/`
directory is the exact byte-preserved E1 payload. `bundle_manifest.json` is
Phase 4 reproducibility metadata and is not itself E1 evidence.

## Upstream source identity

- Dataset: `lmsys/chatbot_arena_conversations`
- Pinned revision: `1b6335d42a1d2c7e34870c905d03ab964f7f2bd8`
- Split: `train`
- Parquet file: `data/train-00000-of-00001-cced8514c7ed782a.parquet`
- Source file SHA-256: `3726a6352e9bfc34e206460646f6e5e99bb837751966a671ddd30c7f64e5b06e`
- Source snapshot ID: `2f8937a5f46ea4c3ed4ac7d59a5e51a6b3fb9bae79918b1050c6420b34ce1fa4`

The upstream dataset card identifies user prompts as CC BY 4.0 and model
outputs as CC BY-NC 4.0. See:

- https://huggingface.co/datasets/lmsys/chatbot_arena_conversations
- https://creativecommons.org/licenses/by/4.0/
- https://creativecommons.org/licenses/by-nc/4.0/

The associated citation is:

Zheng, Lianmin, Wei-Lin Chiang, Ying Sheng, Siyuan Zhuang, Zhanghao Wu,
Yonghao Zhuang, Zi Lin, Zhuohan Li, Dacheng Li, Eric P. Xing, Hao Zhang,
Joseph E. Gonzalez, and Ion Stoica. "Judging LLM-as-a-judge with MT-Bench and
Chatbot Arena." arXiv:2306.05685, 2023.

## Rights and contents boundary

The payload contains aggregate/statistical research derivatives only. The
reviewed payload contains no raw prompts, raw model responses, conversations,
source rows, user identifiers, credentials, or machine-local private data.

Upstream attribution, license terms, model-specific terms of use, privacy
requirements, and other third-party rights remain applicable to any underlying
material. The repository MIT license applies to original repository code and
does not supersede or relicense third-party material. This notice does not
make a novel legal conclusion about copyright or database rights.

No endorsement by LMSYS, Chatbot Arena, or any model provider is implied.
