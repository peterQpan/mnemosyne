# Vollständiger Leitfaden: Hermes Agent + Mnemosyne mit lokalen Ollama-Modellen

**Stand:** 2026-05-17  
**Ziel:** Produktionsnahe, konsistente Hermes+Mnemosyne-Konfiguration mit:
- lokaler LLM-Inferenz über **Ollama**
- **Nemotron 3 Nano 4B (Q8)** für Fact-Extraktion (und optional Consolidation)
- mehrsprachigem Embedding-Modell mit Deutsch-Support
- robustem Boot-Verhalten (Autostart + Warmup)
- sauberem Umgang mit Embedding-Dimensionswechseln

---

## 1) Architekturentscheidung (Best Practice)

Mnemosyne hat bereits einen klaren LLM-Fallback-Stack:

1. Host-LLM-Adapter (wenn `MNEMOSYNE_HOST_LLM_ENABLED=true`)
2. OpenAI-kompatibler Remote-Endpunkt (`MNEMOSYNE_LLM_BASE_URL`)
3. Lokales GGUF (TinyLlama-Default, über `MNEMOSYNE_LLM_REPO`/`MNEMOSYNE_LLM_FILE`)
4. AAAK-Fallback ohne LLM

Für dein Ziel („alles lokal auf Ollama“) ist der **OpenAI-kompatible Pfad** der sauberste Primärweg.

---

## 2) Zielkonfiguration auf einen Blick

## Muss-Ziele

- Ollama läuft lokal und wird von Mnemosyne über `http://127.0.0.1:11434/v1` angesprochen.
- Fakt-Extraktion nutzt Nemotron 3 Nano 4B Q8 (Modellname laut lokalem Ollama-Tag).
- Embeddings laufen ebenfalls lokal über Ollama/OpenAI-kompatible Embedding-API.
- Hermes nutzt Mnemosyne als Memory Provider.
- Wiederanlauf nach Reboot ist abgesichert (Service + optionales Warmup).

## Soll-Ziele

- deterministic Extraction (Mnemosyne macht das bereits mit `temperature=0.0` für Facts).
- klare Fallback-Strategie bei Modell-/Service-Ausfällen.
- Diagnose- und Reindex-Prozedur dokumentiert.

---

## 3) Konkrete Einrichtungsschritte

## Schritt A — Hermes auf Mnemosyne als Provider setzen

```bash
hermes config set memory.provider mnemosyne
```

Alternativ in `~/.hermes/config.yaml`:

```yaml
memory:
  provider: mnemosyne
```

## Schritt B — Ollama als LLM-Endpoint für Mnemosyne

In der Laufzeitumgebung (Shell/Service-Env), z. B. `~/.profile`, `~/.bashrc` oder systemd `Environment=`:

```bash
# Mnemosyne LLM routing -> Ollama OpenAI-compatible endpoint
export MNEMOSYNE_LLM_ENABLED=true
export MNEMOSYNE_LLM_BASE_URL=http://127.0.0.1:11434/v1

# Nemotron für text generation tasks (Consolidation/Extraction über remote path)
export MNEMOSYNE_LLM_MODEL=nemotron3:4b-instruct-q8_0
```

> Hinweis: Der genaue Modelltag kann abweichen. Immer mit `ollama list` verifizieren.

## Schritt C — Lokales mehrsprachiges Embedding via Ollama

Mnemosyne unterstützt OpenAI-kompatible Embedding-API-Pfade (`openai/*`).
Nutze daher ein lokales Ollama-Embedding-Modell, z. B. (beispielhaft):

```bash
# wichtig: openai/<modellname> triggert API-Embedding-Pfad in Mnemosyne
export MNEMOSYNE_EMBEDDING_MODEL=openai/mxbai-embed-large
# optional (falls nicht ohnehin vom LLM base URL identisch):
export OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export OPENAI_API_KEY=ollama
```

Warum so? Mnemosyne erkennt `openai/...` als API-Embedding-Modell und nutzt dann den Embeddings-Endpunkt.

## Schritt D — Optional: Hermes-Host-Adapter bewusst ein/aus

Wenn du *nur* Ollama lokal willst, setze den Host-Adapter typischerweise auf `false`:

```bash
export MNEMOSYNE_HOST_LLM_ENABLED=false
```

`true` ist primär sinnvoll für Hermes-OAuth-Provider (z. B. Codex/OpenAI-Hosted), nicht für rein lokalen Ollama-Betrieb.

---

## 4) Ollama Autostart + Modellbereitstellung nach Reboot

## Linux (systemd) – empfohlene Praxis

1. Service aktivieren:

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama
```

2. Modelle vorab ziehen:

```bash
ollama pull nemotron3:4b-instruct-q8_0
ollama pull mxbai-embed-large
```

3. Warmup-Unit anlegen (empfohlen, damit beim ersten Agent-Request keine Kaltstart-Latenz):

`/etc/systemd/system/ollama-warmup.service`

```ini
[Unit]
Description=Warm up Ollama models for Hermes/Mnemosyne
After=ollama.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/bin/bash -lc 'ollama run nemotron3:4b-instruct-q8_0 "warmup" >/dev/null 2>&1 || true'
ExecStart=/bin/bash -lc 'curl -sS http://127.0.0.1:11434/v1/embeddings -H "Content-Type: application/json" -d "{\"model\":\"mxbai-embed-large\",\"input\":\"warmup\"}" >/dev/null 2>&1 || true'
RemainAfterExit=true

[Install]
WantedBy=multi-user.target
```

Dann:

```bash
sudo systemctl daemon-reload
sudo systemctl enable ollama-warmup
sudo systemctl start ollama-warmup
```

---

## 5) Embedding-Modellwechsel: Muss die Datenbank angepasst werden?

Kurz: **Ja, wenn sich die Embedding-Dimension ändert, musst du migrieren/reindexen.**

Warum:
- Mnemosyne verwendet Vektorindizes (`vec0`) mit fester Dimension.
- Die Dimension ist in der Tabellenstruktur verankert (`... embedding <type>[DIM] ...`).
- Wechselst du z. B. von 384-D auf 768/1024/1536, passen alte Vektoren nicht mehr konsistent.

## Praktische Regeln

1. **Wenn neue und alte Dimension gleich sind**:
   - kein harter Schema-Wechsel nötig,
   - aber Re-Embedding ist trotzdem empfehlenswert für semantische Konsistenz.

2. **Wenn Dimension unterschiedlich ist**:
   - Vektorstruktur muss neu aufgebaut werden,
   - bestehende Embeddings/vec-Indizes löschen oder neu initialisieren,
   - Inhalte erneut einbetten (Working + Episodic + Facts, sofern Vektorpfad genutzt).

## Sichere Vorgehensweise (Best Practice)

1. DB-Backup erstellen.
2. Neues Embedding-Modell konfigurieren.
3. Neue DB oder Reindex-Migration fahren.
4. Inhalt schrittweise neu einbetten.
5. Recall-Qualität mit Testqueries vergleichen.

## Zu Mnemosyne-spezifischen Defaults

- Die Doku nennt standardmäßig 384-D (bge-small).
- Der Code hat model-basierte Dimensionszuordnung für bekannte Modelle und fallback auf 384.
- Zusätzlich existiert `MNEMOSYNE_EMBEDDING_DIM` für die vec-Tabellenkonfiguration.

**Wichtig:** `MNEMOSYNE_EMBEDDING_MODEL` und effektive Embedding-Dimension müssen zur DB/vec-Konfiguration passen.

---

## 6) Fact-Extraktion explizit auf Nemotron absichern

Der aktuelle Remote-Pfad nutzt ein globales `MNEMOSYNE_LLM_MODEL`. Wenn Fact-Extraktion zwingend ein anderes Modell als Consolidation bekommen soll, brauchst du eine der folgenden Strategien:

1. **Ein-Modell-Strategie (einfach, robust):**
   - `MNEMOSYNE_LLM_MODEL=nemotron3:4b-instruct-q8_0`
   - gilt für Consolidation + Extraction

2. **Host-Routing-Strategie (fortgeschritten):**
   - Hermes Host-Adapter aktivieren,
   - provider/model pro task über Host-Layer regeln

3. **Erweiterung in Mnemosyne (Roadmap):**
   - separates `MNEMOSYNE_EXTRACTION_MODEL`
   - separates `MNEMOSYNE_CONSOLIDATION_MODEL`

Für Stabilität heute: **Strategie 1**.

---

## 7) Vollständige Checkliste (was oft vergessen wird)

- [ ] `memory.provider` wirklich auf `mnemosyne` gesetzt?
- [ ] `MNEMOSYNE_LLM_ENABLED=true`?
- [ ] `MNEMOSYNE_LLM_BASE_URL` zeigt auf `/v1`?
- [ ] `MNEMOSYNE_LLM_MODEL` entspricht exakt lokalem Ollama-Tag?
- [ ] Embedding-Modell lokal vorhanden und über Embeddings-Endpoint erreichbar?
- [ ] `MNEMOSYNE_EMBEDDING_MODEL` korrekt (`openai/<embedding-model>`) gesetzt?
- [ ] Bei Dimensionwechsel: Reindex-/Migrationsplan durchgeführt?
- [ ] Ollama systemd-Enable + Warmup aktiv?
- [ ] `mnemosyne diagnose` ohne kritische Fehler?
- [ ] Smoke-Test: speichern → recall → fact extraction validiert?

---

## 8) Empfohlener Smoke-Test nach Setup

```bash
# 1) Diagnose
python -m mnemosyne.diagnose

# 2) Hermes-Status
hermes memory status

# 3) Funktionaler Mini-Test
# (je nach eurem Tooling: mnemosyne_remember / mnemosyne_recall / mnemosyne_facts)
```

Akzeptanzkriterien:
- keine Import-/Dependency-Fehler
- Recall liefert sinnvolle Treffer
- Fact-Extraktion liefert konsistente, deduplizierbare Facts

---

## 9) Minimal-konservative Beispiel-Env (Startpunkt)

```bash
export MNEMOSYNE_LLM_ENABLED=true
export MNEMOSYNE_HOST_LLM_ENABLED=false

# Ollama chat/completions
export MNEMOSYNE_LLM_BASE_URL=http://127.0.0.1:11434/v1
export MNEMOSYNE_LLM_MODEL=nemotron3:4b-instruct-q8_0

# Ollama embeddings via OpenAI-compatible path
export OPENAI_BASE_URL=http://127.0.0.1:11434/v1
export OPENAI_API_KEY=ollama
export MNEMOSYNE_EMBEDDING_MODEL=openai/mxbai-embed-large

# Nur setzen, wenn Dimension explizit bekannt/gewünscht:
# export MNEMOSYNE_EMBEDDING_DIM=<z.B. 1024 oder 1536>
```

---

## 10) Fazit

Du hast mit Mnemosyne bereits die richtigen Paradigmen:
- lokaler Betrieb ist unterstützt,
- Fallbacks sind vorhanden,
- Hermes-Integration ist klar getrennt,
- Embedding/LLM sind konfigurierbar.

Der wichtigste Praxispunkt ist die **Dimensionstreue der Embeddings zur DB-Struktur**.
Wenn ihr das sauber migriert/reindiziert und Ollama stabil als Service + Warmup betreibt, bekommt ihr einen konsistenten, robusten Agentenbetrieb.
