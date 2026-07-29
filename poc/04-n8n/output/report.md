# n8n-Demo — Orchestrierung Invoice-to-Approval

n8n hat headless die Invoice-Pipeline (POC 02) ausgeführt und je Beleg eine Prozessinstanz im Flowable-Freigabe-Workflow (POC 03) gestartet.

## Vom Workflow gestartete Prozessinstanzen

| Rechnung | Flowable-Instanz | Sofort beendet |
|---|---|---|
| RE-2026-0815 | `8d8602c8…` | ja (AUTO/REJECT-Pfad) |
| BL-77113 | `8d8602c4…` | nein (wartet auf Freigabe) |
| GIT-2026-442 | `8d8602c5…` | nein (wartet auf Freigabe) |
| DA-10077 | `8d8602c7…` | nein (wartet auf Freigabe) |
| RE-2026-0815 | `8d8602c3…` | ja (AUTO/REJECT-Pfad) |
| OC-889 | `8d867804…` | nein (wartet auf Freigabe) |
| RE-2026-0900 | `8d8602c6…` | nein (wartet auf Freigabe) |

## Offene Freigabe-Tasks in Flowable: 5

- RE-2026-0900 — Stufe SACHBEARBEITER (Beleg s7_xrechnung_ubl_po_abweichung.xml)
- OC-889 — Stufe TEAMLEITUNG (Beleg s6_scan_ohne_xml.pdf)
- BL-77113 — Stufe SACHBEARBEITER (Beleg s2_xrechnung_cii_summenfehler.xml)
- DA-10077 — Stufe TEAMLEITUNG (Beleg s4_xrechnung_ubl_grossbetrag.xml)
- GIT-2026-442 — Stufe TEAMLEITUNG (Beleg s3_zugferd_iban_geaendert.pdf)

Die Tasks warten jetzt in der Flowable-Queue auf Sachbearbeitung/Teamleitung — Bearbeitung wie in POC 03 demonstriert. n8n ist dabei reine Orchestrierung: keine Fachlogik, keine Freigabeentscheidung — die liegen in Pipeline (Python) und Prozess-Engine (BPMN/DMN).