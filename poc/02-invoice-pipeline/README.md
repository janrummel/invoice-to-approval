# POC 02 — Invoice-Pipeline: E-Rechnung + Validierung + Risk-tiered Routing

Referenzimplementierung des Rechnungseingangs-Musters aus der Research-Note —
und Antwort auf den Top-Hebel aus POC 01 ("Rechnung erfasst"):

```
Eingang (XML/PDF)
  └─> 1. Parse      XRechnung (UBL + CII), ZUGFeRD (XML aus PDF/A-3),
                    Fallback: Text-Heuristik (produktiv: LLM-Extraktion)
  └─> 2. Validate   deterministisch: Summen, USt-Rechnung, IBAN-/USt-ID-Prüfsumme,
                    Pflichtfelder, Datums-Plausibilität (Pydantic + python-stdnum)
  └─> 3. Route      risk-tiered autonomy: AUTO_POST / REVIEW / REJECT
                    (Dubletten, Stammdaten-Abgleich inkl. IBAN-Fraud-Check,
                    2-/3-Way-Match gegen Bestellung + Wareneingang [2 % Toleranz],
                    Währungs- und Betragsschwelle, Zahlweg, Extraktions-Confidence)
```

## Ausführen

```bash
pip install -r requirements.txt
python3 samples/generate_samples.py   # erzeugt 6 Demo-Belege (XML + PDF)
python3 run.py                        # -> output/results.md + results.json
```

## Demo-Szenarien (alle laufen wie erwartet, siehe `output/`)

| Beleg | Szenario | Ergebnis |
|---|---|---|
| s1 | XRechnung (UBL), konsistent, bekannter Lieferant | 🟢 AUTO_POST |
| s2 | XRechnung (CII), Positionssumme ≠ Netto | 🟡 REVIEW (V01) |
| s3 | ZUGFeRD-PDF, IBAN weicht von Stammdaten ab | 🟡 REVIEW (Fraud-Check) |
| s4 | Konsistent, aber 24.990 € > Dunkelbuchungsgrenze | 🟡 REVIEW (Freigabe) |
| s5 | Dublette von s1 | 🔴 REJECT |
| s6 | Scan ohne XML → Fallback-Extraktion (Confidence 60 %), kein Bestellbezug | 🟡 REVIEW |
| s7 | In sich konsistent, aber Netto über Bestellwert + 2 % Toleranz | 🟡 REVIEW (3-Way-Match) |

## Design-Entscheidungen

- **E-Rechnung zuerst:** Seit der E-Rechnungspflicht kommen Daten zunehmend
  strukturiert (XRechnung/ZUGFeRD) — deterministisches Parsing schlägt jede
  OCR/LLM-Extraktion in Kosten, Genauigkeit und Auditierbarkeit. IDP/LLM ist nur
  noch der Fallback-Pfad für Altbelege/Ausland (Andockpunkt: `llm_extract_stub`).
- **Validierung ist nicht verhandelbar:** Auch strukturierte Belege werden
  rechnerisch geprüft; bei LLM-Extraktion sind dieselben Regeln die Absicherung
  gegen Betrags-Halluzinationen.
- **Routing deterministisch und erklärbar:** Jede Entscheidung trägt Gründe +
  Risk-Score — das ist der Audit-Trail, den IKS/Revision verlangen. Keine
  LLM-Entscheidung über Buchung oder Zahlung.
- **`results.json` als Übergabeformat:** genau der Payload, den POC 03 (Flowable,
  Freigabe-Workflow) bzw. POC 04 (n8n, Orchestrierung) konsumieren.

## Grenzen / produktive Ausbaustufen

- Keine vollständige EN-16931-Validierung — produktiv den KoSIT-Validator
  (Schematron) vorschalten.
- Dubletten-Register ist In-Memory — produktiv: Datenbank mit Fuzzy-Matching
  (Betrag+Datum+Vendor, z.B. via Splink).
- 2-/3-Way-Match läuft gegen JSON-Stammdaten (masterdata/purchase_orders.json,
  2 % Toleranz) — produktiv ersetzt eine ERP-Anbindung die Fixtures
  (Integrationsmuster: OData/REST).
- Fallback-Parser ist Regex-Heuristik; produktiv: Vision-LLM + `instructor`
  mit demselben Pydantic-Schema und Feld-Confidences.
