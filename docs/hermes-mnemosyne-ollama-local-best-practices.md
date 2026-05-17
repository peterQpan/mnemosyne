# Vollständiger Leitfaden: Hermes Agent + Mnemosyne mit lokalen Ollama-Modellen

**Stand:** 2026-05-17  
**Ziel:** Produktionsnahe, konsistente Hermes+Mnemosyne-Konfiguration mit:
- lokaler LLM-Inferenz über **Ollama**
- **Nemotron 3 Nano 4B (Q8)** für Fact-Extraktion
- mehrsprachigem Embedding-Modell mit Deutsch-Support
- robustem Boot-Verhalten (Autostart + Warmup)
- sauberem Umgang mit Embedding-Dimensionswechseln

---

## 1) Wichtige Korrektur vorab (zum Feedback)

Das Feedback ist in einem Kernpunkt berechtigt: Die Embedding-API-Pfade bei Ollama sind versionsabhängig.

- Klassischer Ollama-Pfad: `POST /api/embeddings`
- Neuer OpenAI-kompatibler Pfad: `POST /v1/embeddings` (nicht in allen Installationen gleich zuverlässig)

**Mnemosyne-Stand heute (Code):**
- API-Embeddings laufen über `OPENAI_BASE_URL + /embeddings`.
- Es gibt aktuell **kein** separates `MNEMOSYNE_EMBEDDING_BASE_URL`.
- Es gibt aktuell **kein** `MNEMOSYNE_LLM_PROVIDER`.

Konsequenz:
- Für API-Embeddings muss die Umgebung `OPENAI_BASE_URL` korrekt setzen.
- Vor Go-Live muss ein echter Endpoint-Check erfolgen (`/v1/embeddings` getestet).

---

## 2) Architekturentscheidung (Best Practice)

Mnemosyne nutzt bereits diesen LLM-Fallback-Stack:

1. Host-LLM-Adapter (wenn `MNEMOSYNE_HOST_LLM_ENABLED=true`)
2. OpenAI-kompatibler Remote-Endpunkt (`MNEMOSYNE_LLM_BASE_URL`)
3. Lokales GGUF (TinyLlama-Default, über `MNEMOSYNE_LLM_REPO`/`MNEMOSYNE_LLM_FILE`)
4. AAAK-Fallback ohne LLM

Für „alles lokal auf Ollama“ ist der OpenAI-kompatible Pfad für Generierung aktuell der sauberste Weg.

---

## 3) Zielkonfiguration (konkret)

## A) Hermes auf Mnemosyne setzen

```bash
hermes config set memory.provider mnemosyne
```

## B) Lokale LLM-Generierung über Ollama

```bash
export MNEMOSYNE_LLM_ENABLED=true
export MNEMOSYNE_HOST_LLM_ENABLED=false

export MNEMOSYNE_LLM_BASE_URL=http://127.0.0.1:11434/v1
export MNEMOSYNE_LLM_MODEL=nemotron3:4b-instruct-q8_0

# Lokale Endpunkte brauchen i.d.R. keinen echten API Key;
# falls euer Stack nicht-leeren Wert erwartet, Dummy setzen:
export MNEMOSYNE_LLM_API_KEY=ollama
```

> Modelltag immer mit `ollama list` verifizieren.

## C) Embeddings lokal (zwei valide Betriebsmodi)

### Modus 1 (stabiler heute): fastembed lokal in Mnemosyne

Wenn ihr maximale Robustheit wollt, nutzt lokales fastembed statt Ollama-Embedding-API:

```bash
export MNEMOSYNE_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
# oder multilinguales fastembed-kompatibles Modell, falls verfügbar/verifiziert
```

### Modus 2 (dein Ziel: Embeddings auch über Ollama)

Mnemosyne API-Embedding-Pfad wird durch `openai/...`-Modelnamen aktiviert:

```bash
export OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export OPENAI_API_KEY=ollama
export MNEMOSYNE_EMBEDDING_MODEL=openai/mxbai-embed-large
```

**Wichtig:** Vorher technisch verifizieren, dass eure Ollama-Version `POST /v1/embeddings` zuverlässig liefert.

Validierung:

```bash
curl -sS http://127.0.0.1:11434/v1/embeddings \
  -H 'Content-Type: application/json' \
  -H 'Authorization: Bearer ollama' \
  -d '{"model":"openai/mxbai-embed-large","input":"Warmup Deutsch: Ich mag zuverlässige Speicher."}'
```

Wenn das scheitert: auf Modus 1 wechseln **oder** Mnemosyne-Code für `/api/embeddings`-Kompatibilität erweitern.

---

## 4) Ollama-Autostart & Warmup (vollständig)

## Service-Name und Host-Binding

Standard-Service unter Linux: `ollama.service`.

Bei Remote-Bindings:

```bash
# Beispiel, falls nicht localhost gewünscht
export OLLAMA_HOST=0.0.0.0:11434
```

## systemd aktivieren

```bash
sudo systemctl enable ollama.service
sudo systemctl start ollama.service
sudo systemctl status ollama.service
```

## Modelle ziehen

```bash
ollama pull nemotron3:4b-instruct-q8_0
ollama pull mxbai-embed-large
```

## Warmup-Unit (konkret)

`/etc/systemd/system/ollama-warmup.service`

```ini
[Unit]
Description=Warm up Ollama models for Hermes/Mnemosyne
After=ollama.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash -lc 'ollama run nemotron3:4b-instruct-q8_0 "warmup" >/dev/null 2>&1 || true'
ExecStart=/bin/bash -lc 'curl -sS http://127.0.0.1:11434/v1/embeddings -H "Content-Type: application/json" -H "Authorization: Bearer ollama" -d "{\"model\":\"openai/mxbai-embed-large\",\"input\":\"warmup\"}" >/dev/null 2>&1 || true'
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
```

Aktivieren:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama-warmup.service
sudo systemctl start ollama-warmup.service
```

---

## 5) Embedding-Dimension & DB-Migration (konkret statt vage)

Kurz: **Wenn sich die Embedding-Dimension ändert, ist Migration/Reindex Pflicht.**

## Warum

- `vec0`-Tabellen sind dimensionsfest (`embedding ...[DIM]`).
- Mnemosyne nutzt `EMBEDDING_DIM` in vec-Schema-Erstellung.
- Falsche Dimension führt zu inkonsistenten Writes/Queries.

## Konkreter Migrationsablauf (Best Practice)

1. **Backup erstellen**

```bash
mnemosyne backup
mnemosyne backups
```

2. **Konsistenz-Export erstellen**

```bash
hermes mnemosyne export --output /tmp/mnemosyne-export-pre-embed-switch.json
```

3. **Neue Embedding-Config setzen** (`MNEMOSYNE_EMBEDDING_MODEL`, ggf. `MNEMOSYNE_EMBEDDING_DIM`).

4. **Sauberer Neuaufbau bevorzugt**
   - neue Datenbank initialisieren,
   - Import aus Export durchführen:

```bash
hermes mnemosyne import --input /tmp/mnemosyne-export-pre-embed-switch.json --force
```

5. **Warmup + Smoke-Test + Recall-Qualitätscheck**

6. **Restore-Test dokumentieren**
   - im Zweifel `mnemosyne restore <backup.db.gz>` auf Testinstanz ausführen.

---

## 6) Was im ursprünglichen Feedback noch wichtig war (und hier ergänzt ist)

- Service-Name präzisiert (`ollama.service`)
- Warmup konkret mit Commands/Unit spezifiziert
- fehlende Variablen richtig eingeordnet:
  - `MNEMOSYNE_LLM_API_KEY`: optional/dummy für lokale Endpunkte
  - `MNEMOSYNE_LLM_PROVIDER`: aktuell nicht Teil der Mnemosyne-Config
  - `MNEMOSYNE_EMBEDDING_BASE_URL`: aktuell nicht vorhanden (stattdessen `OPENAI_BASE_URL`)
- Migrationspfad konkret mit vorhandenen CLI-Befehlen dokumentiert
- Endpoint-Validierung zwingend gemacht

---

## 7) Vollständige Betriebs-Checkliste

- [ ] `memory.provider=mnemosyne` gesetzt
- [ ] `ollama.service` aktiv und enabled
- [ ] Nemotron-Tag per `ollama list` verifiziert
- [ ] Embedding-Tag per `ollama list` verifiziert
- [ ] `MNEMOSYNE_LLM_BASE_URL` korrekt (`.../v1`)
- [ ] `OPENAI_BASE_URL` korrekt (`.../v1`) für API-Embeddings
- [ ] `/v1/embeddings` gegen echte Payload getestet
- [ ] Backup + Export vor Embedding-Wechsel erstellt
- [ ] Bei Dimensionswechsel Neuaufbau/Reimport durchgeführt
- [ ] `python -m mnemosyne.diagnose` ohne kritische Findings
- [ ] Save/Recall/Fact-Extraction Smoke-Test dokumentiert

