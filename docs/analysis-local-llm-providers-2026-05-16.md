# Analyse: Mehrere lokale LLM-Provider & frei wählbare Modelle

Datum: 2026-05-16

## Kurzantwort

Ja — die Grundlage ist **bereits vorhanden**.

Mnemosyne kann heute schon zwischen mehreren LLM-Pfaden routen:

1. **Host-LLM über Hermes** (`MNEMOSYNE_HOST_LLM_ENABLED=true`)
2. **Remote OpenAI-kompatibel** (`MNEMOSYNE_LLM_BASE_URL` + `MNEMOSYNE_LLM_MODEL`)
3. **Lokales GGUF** über `llama-cpp-python` / `ctransformers` (TinyLlama default)
4. Fallback ohne LLM (AAAK)

Damit sind **Ollama** und **LM Studio** bereits im Zielbild (über den OpenAI-kompatiblen Endpoint, z. B. `/v1`).

---

## Was ist heute schon angelegt?

## 1) Remote-Provider (OpenAI-kompatibel) ist vorhanden

Die Konfiguration dokumentiert explizit:
- `MNEMOSYNE_LLM_BASE_URL`
- `MNEMOSYNE_LLM_API_KEY`
- `MNEMOSYNE_LLM_MODEL`

Und nennt direkt als kompatibel:
- llama.cpp server
- vLLM
- **Ollama**
- **LM Studio**

=> Für deinen Wunsch „unterschiedliche lokale Provider“ ist der Standardweg **bereits implementiert**.

## 2) Modellwahl ist vorhanden

Bei Remote-Aufruf wird das Modell über `MNEMOSYNE_LLM_MODEL` gesetzt. Das erlaubt z. B.:
- `nemotron-*`
- `qwen*`
- `gemma*`
- `llama*`

solange der jeweilige Provider dieses Modell lokal bereitstellt und über die kompatible API annimmt.

## 3) Lokales Default-Modell (TinyLlama) ist austauschbar

Für den lokalen GGUF-Pfad sind vorhanden:
- `MNEMOSYNE_LLM_REPO`
- `MNEMOSYNE_LLM_FILE`

Damit kann TinyLlama ersetzt werden, ohne Codeänderung.

## 4) Hermes-Host-Adapter existiert

Wenn Mnemosyne als Hermes-Provider läuft, kann es über den Host adapter (`agent.auxiliary_client.call_llm`) auf Hermes-seitig authentifizierte Provider zugreifen. Das ist relevant, falls du dort zentrale Modell/Provider-Routing-Logik pflegen willst.

---

## Gap-Analyse (was fehlt vermutlich noch?)

Technisch ist die Fähigkeit da; was typischerweise fehlt, ist **Produktisierung/Bedienbarkeit**:

1. **Provider-Profile**
   - Heute primär env-var-basiert (ein aktiver Endpoint gleichzeitig pro Prozess).
   - Kein eingebautes Profilsystem wie `provider=ollama-dev` vs `provider=lmstudio-large`.

2. **Dynamischer Provider-Wechsel zur Laufzeit**
   - Kein explizites Runtime-Switching pro Request in der Mnemosyne-API sichtbar (außer Host-Route mit provider/model overrides).

3. **Validierung & Discoverability**
   - Keine sichtbare Funktion „liste verfügbare Modelle von Endpoint X“ in Mnemosyne selbst.

4. **Policy/Guardrails**
   - Kein dediziertes Mapping „Extraction immer Modell A, Consolidation immer Modell B“ via zentraler config (außer über Host-Backend-Policy oder externe Orchestrierung).

---

## Wie würde man es sauber anlegen? (Plan ohne Code)

## Zielbild

Ein konfigurierbares Multi-Provider-System mit:
- mehreren benannten Endpoints (Ollama, LM Studio, ggf. vLLM)
- pro Task wählbarem Modell (sleep/consolidation vs extraction)
- klarer Fallback-Strategie
- optionalem Model-Discovery

## Planphase 1 — Konfigurationsdesign

1. **Provider-Profile in `config.yaml` definieren**
   - Beispielstruktur:
     - `memory.mnemosyne.llm.providers.<name>.base_url`
     - `...api_key`
     - `...default_model`
     - `...timeout`

2. **Task-Routing definieren**
   - `memory.mnemosyne.llm.routing.consolidation.provider/model`
   - `memory.mnemosyne.llm.routing.extraction.provider/model`

3. **Fallback-Liste definieren**
   - z. B. `consolidation: [ollama_fast, lmstudio_quality, local_gguf]`

## Planphase 2 — Laufzeitverhalten

4. **Resolver spezifizieren**
   - Eingabe: Task-Typ + optional Override
   - Ausgabe: `(provider_profile, model)`

5. **Fehlerklassen festlegen**
   - Retry bei Timeout/429
   - Kein Retry bei 4xx-Konfigurationsfehler

6. **Determinismus für Extraction absichern**
   - `temperature=0.0` beibehalten
   - Idempotenztestfälle definieren

## Planphase 3 — UX/Operations

7. **Diagnose-Command erweitern (Spezifikation)**
   - zeigt aktives Profil, Model, zuletzt verwendeten Pfad

8. **Optionale Model-Discovery (Spezifikation)**
   - OpenAI-kompatibel: `/models` abfragen
   - Ergebnis cachen + health-status

9. **Doku-Templates**
   - „Ollama-Profil“, „LM-Studio-Profil“, „Gemischter Betrieb“

---

## Konkrete Nutzungsbeispiele (heute, ohne Code)

## A) Ollama nutzen

- `MNEMOSYNE_LLM_BASE_URL=http://localhost:11434/v1`
- `MNEMOSYNE_LLM_MODEL=qwen3:8b` (oder `gemma3:12b`, etc. je nach lokalem Pull)

## B) LM Studio nutzen

- `MNEMOSYNE_LLM_BASE_URL=http://localhost:1234/v1`
- `MNEMOSYNE_LLM_MODEL=<modellname-aus-lm-studio>`

## C) Default TinyLlama ersetzen (lokaler GGUF-Pfad)

- `MNEMOSYNE_LLM_REPO=<hf-repo>`
- `MNEMOSYNE_LLM_FILE=<gguf-datei>`

---

## Empfehlung

Kurzfristig (ohne Code):
1. Nutze bereits jetzt den Remote-kompatiblen Pfad für Ollama/LM Studio.
2. Pflege Provider/Model-Kombinationen über `.env`-Profile (z. B. `.env.ollama`, `.env.lmstudio`).

Mittelfristig (mit Code in separatem Schritt):
3. Implementiere ein echtes Profil- und Routing-System in `config.yaml`, damit Provider/Model pro Task stabil und transparent steuerbar sind.

