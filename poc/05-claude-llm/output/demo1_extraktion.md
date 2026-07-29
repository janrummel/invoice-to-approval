## Demo 1 — LLM-Fallback-Extraktion (s6, Scan ohne XML)

Von Claude extrahiert und durch die deterministischen Regeln aus POC 02 validiert:

| Feld | Wert |
|---|---|
| Rechnungsnummer | OC-889 |
| Datum | 2026-07-15 |
| Lieferant | Omega Catering Service |
| IBAN | DE89370400440532013000 |
| Netto / USt / Brutto | 89.9 / 17.08 / 106.98 |
| Extraktions-Confidence | 85% (LLM-Pfad) |

**Deterministische Validierung:** [warning] V05 Keine USt-ID des Lieferanten vorhanden

Routing bleibt REVIEW (Confidence < 90 %, neuer Lieferant) — das LLM beschleunigt die Erfassung, entscheidet aber nicht.
