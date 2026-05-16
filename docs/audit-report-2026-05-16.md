# Mnemosyne Security Audit Report (2026-05-16)

## Scope
- Source review for: `mnemosyne/`, `hermes_memory_provider/`, `hermes_plugin/`, and `scripts/`.
- Focus: exploitability, outgoing network behavior, auth controls, risky primitives, and consistency edge-cases.

## Method
- Pattern scan for dangerous primitives and network usage:
  - `rg -n "(subprocess|os\.system|eval\(|exec\(|pickle\.loads|yaml\.load\(|shell=True|urlopen\()" ...`
  - `rg -n "https?://" ...`
  - `rg -n "verify=False|ssl._create_unverified_context|yaml\.load\(|pickle\.loads|md5\(|sha1\(|subprocess\.run\(|shell=True|eval\(|exec\(" ...`
- Manual code inspection of critical surfaces:
  - MCP SSE auth gate.
  - Diagnostics/autofix execution paths.
  - External importer HTTP behavior.

## Findings

### 1) Outbound HTTP without explicit allowlist (Medium)
**What:** Multiple modules issue outbound HTTP requests via `urllib.request.urlopen` to configurable endpoints (OpenRouter, external importers, local services).

**Evidence (examples):**
- `mnemosyne/extraction/client.py` (OpenRouter calls).
- `mnemosyne/core/embeddings.py` (embedding API calls).
- `mnemosyne/core/importers/*` (Mem0/Letta/Zep/Honcho/Supermemory/Hindsight/Cognee import paths).

**Risk:**
- In high-security environments, unrestricted egress can leak metadata or interact with untrusted endpoints when configuration is mis-set.
- Several importers default to `http://localhost` (not TLS), which is acceptable for loopback, but dangerous if users point them to non-local HTTP hosts.

**Recommendation:**
- Add optional strict egress policy (`MNEMOSYNE_ALLOWED_HOSTS`) that rejects destinations not in an allowlist.
- Enforce HTTPS for non-loopback hosts by default; require explicit override env var to allow cleartext.

### 2) SSRF-style input surface via URL targets (Low/Medium, context-dependent)
**What:** CLI and importer paths can accept URL-like targets or configurable base URLs.

**Evidence:**
- `mnemosyne/cli.py` has URL target handling.
- `mnemosyne/core/importers/hindsight.py` fetches from provided URL.
- Importers support user-provided `base_url`.

**Risk:**
- If exposed through higher-privileged automation, attacker-controlled parameters could trigger internal network probing.

**Recommendation:**
- Validate/normalize URL schemes and optionally block RFC1918/link-local destinations unless explicitly enabled.
- Document trust boundaries for CLI and plugin usage.

### 3) Subprocess execution present but no obvious shell injection in reviewed paths (Info)
**What:** Subprocess is used in diagnostics and maintenance scripts.

**Evidence:**
- `mnemosyne/diagnose.py` and `scripts/heal_quality.py` use `subprocess.run([...])` argument lists (no `shell=True`).

**Risk:**
- Current usage appears safe from shell metacharacter injection.
- Operational risk remains if invoked in hostile environments with poisoned PATH/binaries.

**Recommendation:**
- Keep list-form invocations.
- Prefer absolute executable paths where practical in repair scripts.

### 4) MCP SSE auth posture is strong for non-loopback (Positive)
**What:** SSE mode requires bearer token when binding to non-loopback host; loopback can run without auth.

**Evidence:**
- `mnemosyne/mcp_server.py` enforces token requirement and uses `hmac.compare_digest`.

**Risk:**
- Low. Main residual risk is operator misconfiguration (accidentally exposing loopback proxy).

**Recommendation:**
- Keep current behavior; add startup warning when running unauthenticated even on loopback.

## Outgoing connection inventory (high-level)
- OpenRouter API (extraction/embeddings/local_llm remote adapters).
- External memory providers (Mem0, Letta, Zep, Supermemory).
- Local service defaults (`http://localhost:*`) for some importers (Mem0, Honcho, Cognee, Hindsight examples).

## Not observed in reviewed scope
- No obvious use of `eval`, `exec`, `pickle.loads`, `yaml.load` (unsafe loader), or `shell=True` in core runtime paths scanned.
- No obvious hardcoded production API secrets.

## Priority actions
1. Introduce optional outbound host allowlist + deny-by-default mode for hardened deployments.
2. Enforce HTTPS for non-loopback endpoints unless explicit insecure override is set.
3. Add URL safety checks (scheme + private-network policy toggle) for importer/CLI network targets.
