---
name: hermes-mnemosyne-ollama-local-setup
description: |
  Operational runbook/skill to configure Hermes with Mnemosyne using only local Ollama models:
  Nemotron for fact extraction/consolidation and multilingual local embeddings.
trigger: |
  Use when setting up or auditing a local-first Hermes+Mnemosyne stack on one machine.
---

# Hermes + Mnemosyne + Ollama (Local-First) Skill

## Purpose

Deliver a production-ready local memory stack that aligns with Mnemosyne practices:
- Hermes memory provider = Mnemosyne
- LLM via Ollama OpenAI-compatible endpoint
- multilingual embeddings via local Ollama embedding model
- boot-stable (autostart + warmup)
- explicit dimension migration hygiene for embeddings

## Inputs you must confirm

1. Exact Ollama model tag for Nemotron Q8
2. Exact Ollama embedding model tag
3. Whether existing Mnemosyne DB must be preserved
4. Target OS init system (systemd expected)

## Procedure

1. Set Hermes memory provider to Mnemosyne.
2. Configure Mnemosyne env for local Ollama endpoint (`MNEMOSYNE_LLM_BASE_URL`).
3. Set `MNEMOSYNE_LLM_MODEL` to Nemotron Q8 tag.
4. Set `MNEMOSYNE_EMBEDDING_MODEL=openai/<embedding-tag>` and OpenAI base URL to Ollama `/v1`.
5. Disable host adapter unless OAuth-hosted routing is intentionally desired.
6. Enable and start `ollama` system service.
7. Pull required models and verify with `ollama list`.
8. Add warmup unit to preload chat + embedding model after reboot.
9. Run Mnemosyne diagnostics and a save/recall/fact smoke test.
10. If embedding dimension changed, execute reindex/migration plan before go-live.

## Non-negotiable checks

- Mnemosyne LLM enabled.
- Ollama endpoint reachable at `/v1`.
- Model tags match exactly.
- Embedding dimension consistent with vec schema.
- DB backup taken before embedding migration.

## Failure handling

- If Ollama unavailable: keep Mnemosyne fallback behavior documented and alert.
- If model missing: pull again, then re-run warmup.
- If dim mismatch symptoms appear: stop writes, backup DB, rebuild vector stores, re-embed.

## Definition of Done

- Service survives reboot and serves both generation + embeddings.
- Hermes uses Mnemosyne provider consistently.
- Recall quality and fact extraction validated with deterministic repeat test.
