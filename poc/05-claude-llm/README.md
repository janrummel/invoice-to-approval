# POC 05 — Claude als LLM-Baustein in der Automatisierungs-Kette

Antwort auf die Frage "Kann ein LLM/Claude in den Prozess?": **Ja — an genau den
Stellen, die die Produktionsreife-Ampel grün markiert.** Zwei lauffähige Demos
(Claude headless via `claude -p`; produktiv: Claude API mit Structured Outputs
bzw. Claude Agent SDK):

## Demo 1 — LLM-Fallback-Extraktion (`llm_extract.py`)

Ersetzt die Regex-Heuristik aus POC 02 für Belege ohne strukturiertes XML:
Claude extrahiert die Felder aus dem Scan-Text als striktes JSON → **dasselbe
Pydantic-Modell und dieselben deterministischen Regeln aus POC 02 validieren**
(Summen, IBAN-Prüfsumme, USt-Rechnung) → Confidence 85 % → Routing bleibt REVIEW.
Ergebnis im Demo-Lauf: alle Felder korrekt, Validierung bestanden
(`output/demo1_extraktion.md`).

## Demo 2 — Klärungs-Assistent (`klaerung_assist.py`)

Adressiert den teuersten manuellen Schritt aus POC 01 (Abweichungsklärung,
Ø 25 Min/Fall): Claude erhält die **strukturierten Pipeline-Befunde** (grounded
generation — keine eigenen Zahlen!) und entwirft Sachverhalts-Zusammenfassung
plus Lieferanten-Anfrage. Output ist markierter **Entwurf**, Versand erst nach
Freigabe (`output/demo2_klaerung.md`).

## Ausführen

```bash
# Voraussetzung: Claude Code CLI authentifiziert; POC-02-Outputs vorhanden
python3 llm_extract.py
python3 klaerung_assist.py
```

## Architektur-Einordnung (Kernsatz)

Das LLM sitzt **zwischen** deterministischen Schichten, nie an deren Stelle:

```
Eingang → [LLM: extrahieren]  → deterministische Validierung → Risk-Routing
Befund  → [LLM: formulieren]  → Human-in-the-Loop-Freigabe   → Versand/Buchung
```

- LLM-Aufgaben: extrahieren, zusammenfassen, formulieren, vorschlagen
- Nie LLM-Aufgaben: buchen, freigeben, Zahlen berechnen, Schwellwerte entscheiden
- Kontrolle liegt in Code (Pydantic/Regeln) und Prozess-Engine (BPMN/DMN),
  nicht im Prompt

## Produktiver Ausbau

- CLI → **Claude API** (structured outputs / tool use) bzw. `instructor`;
  Belegbild statt Text (Vision) für Scans/Handschrift
- Confidence aus Feld-Heuristiken statt Pauschale; Feld-Level-Review-UI
- Anbindung an n8n (POC 04): ein Execute-Command-/HTTP-Node ruft die Extraktion
  bzw. den Klärungs-Assistenten — der Rest der Kette bleibt unverändert
- **Claude Agent SDK / MCP** für den nächsten Schritt: Agent, der Klärungsfälle
  mit Werkzeugzugriff (ERP-Lookup via MCP, Mail-Entwurf, Wiedervorlage)
  vorbereitet — weiterhin mit Permission-Gates und HITL
- DSGVO/Policy: EU-Hosting bzw. lokales Modell prüfen, bevor echte Belegdaten
  an eine Cloud-API gehen
