---
name: hermes-mnemosyne-ollama-local-setup
description: |
  Operational skill to configure Hermes with Mnemosyne using local Ollama for generation
  and (optionally) local API embeddings, with explicit migration/validation guardrails.
trigger: |
  Use when setting up or auditing a local-first Hermes+Mnemosyne stack on one machine.
---

# Hermes + Mnemosyne + Ollama (Local-First) Skill

## Critical accuracy notes

- Mnemosyne embeddings API path currently uses `OPENAI_BASE_URL + /embeddings`.
- There is no dedicated `MNEMOSYNE_EMBEDDING_BASE_URL` variable.
- There is no `MNEMOSYNE_LLM_PROVIDER` variable in current Mnemosyne config.
- Therefore, Ollama API embeddings require a verified `/v1/embeddings` path in your Ollama version.

## Inputs you must confirm

1. Exact Ollama chat model tag (Nemotron Q8 target)
2. Exact Ollama embedding model tag
3. Whether existing Mnemosyne DB must be preserved
4. Whether Ollama `/v1/embeddings` works in this environment
5. Target OS init system (systemd expected)

## Procedure

1. Set Hermes memory provider to Mnemosyne.
2. Configure `MNEMOSYNE_LLM_BASE_URL` to local Ollama `/v1`.
3. Set `MNEMOSYNE_LLM_MODEL` to exact Nemotron Q8 tag.
4. Pull and verify both models with `ollama list`.
5. Enable/start `ollama.service` and set `OLLAMA_HOST` only if non-localhost bind is required.
6. For API embeddings, set:
   - `OPENAI_BASE_URL=http://127.0.0.1:11434/v1`
   - `OPENAI_API_KEY=ollama` (dummy non-empty token)
   - `MNEMOSYNE_EMBEDDING_MODEL=openai/<embedding-tag>`
7. Validate `/v1/embeddings` with a real curl payload.
8. Install warmup unit to preload chat + embeddings after reboot.
9. Run `python -m mnemosyne.diagnose` and Hermes smoke tests.
10. If embedding dimension changes: perform backup + export + rebuild/reimport migration flow before go-live.

## Concrete migration flow (dimension change)

1. `mnemosyne backup`
2. `hermes mnemosyne export --output /tmp/pre-switch.json`
3. Set new embedding env (`MNEMOSYNE_EMBEDDING_MODEL`, optionally `MNEMOSYNE_EMBEDDING_DIM`)
4. Rebuild target DB (clean init)
5. `hermes mnemosyne import --input /tmp/pre-switch.json --force`
6. Validate recall quality and fact extraction determinism
7. Keep backup until acceptance is signed off

## Non-negotiable checks

- `ollama.service` is active and enabled.
- Model tags match exactly what `ollama list` reports.
- `/v1/embeddings` works before enabling API embeddings.
- Embedding dimension is consistent with vector schema.
- Backup and export exist before migration.

## Definition of Done

- Service survives reboot and serves generation + embeddings.
- Hermes consistently uses Mnemosyne provider.
- Recall quality and deterministic fact extraction pass acceptance smoke tests.
