# Invoice-Pipeline — Ergebnis des Demo-Laufs

7 Belege verarbeitet (Stichtag 2026-07-28).

| Beleg | Format | Rechnung | Brutto | Route | Risk |
|---|---|---|---|---|---|
| s1_xrechnung_ubl_ok.xml | xrechnung-ubl | RE-2026-0815 | 714.00 EUR | 🟢 AUTO_POST | 0 |
| s2_xrechnung_cii_summenfehler.xml | xrechnung-cii | BL-77113 | 773.50 EUR | 🟡 REVIEW | 40 |
| s3_zugferd_iban_geaendert.pdf | zugferd-pdf | GIT-2026-442 | 1428.00 EUR | 🟡 REVIEW | 50 |
| s4_xrechnung_ubl_grossbetrag.xml | xrechnung-ubl | DA-10077 | 24990.00 EUR | 🟡 REVIEW | 20 |
| s5_xrechnung_ubl_dublette.xml | xrechnung-ubl | RE-2026-0815 | 714.00 EUR | 🔴 REJECT | 100 |
| s6_scan_ohne_xml.pdf | pdf-fallback | OC-889 | 106.98 EUR | 🟡 REVIEW | 75 |
| s7_xrechnung_ubl_po_abweichung.xml | xrechnung-ubl | RE-2026-0900 | 714.00 EUR | 🟡 REVIEW | 30 |

## Begründungen je Beleg

### s1_xrechnung_ubl_ok.xml — 🟢 AUTO_POST
- Alle Prüfungen bestanden — Dunkelbuchung

### s2_xrechnung_cii_summenfehler.xml — 🟡 REVIEW
- Validierungsfehler V01: Positionssumme 600.00 != Nettosumme 650.00
- Validierung: [error] V01 Positionssumme 600.00 != Nettosumme 650.00

### s3_zugferd_iban_geaendert.pdf — 🟡 REVIEW
- Bankverbindung weicht von Stammdaten ab (DE75512108001245126199 -> DE02120300000000202051) — Fraud-Check!

### s4_xrechnung_ubl_grossbetrag.xml — 🟡 REVIEW
- Brutto 24990.00 EUR über Dunkelbuchungsgrenze 10000 EUR — Freigabe erforderlich

### s5_xrechnung_ubl_dublette.xml — 🔴 REJECT
- Dublette: Rechnung RE-2026-0815 von Alpha Buero GmbH bereits verarbeitet

### s6_scan_ohne_xml.pdf — 🟡 REVIEW
- Neuer Lieferant 'Omega Catering Service' — Stammdatenprüfung erforderlich
- Extraktions-Confidence 60% unter Schwellwert 90% — manuelle Prüfung der extrahierten Felder
- Kein Bestellbezug — Dunkelbuchung nur mit erfolgreichem 3-Way-Match möglich
- Validierung: [warning] V05 Keine USt-ID des Lieferanten vorhanden

### s7_xrechnung_ubl_po_abweichung.xml — 🟡 REVIEW
- Netto 600.00 über Bestellwert 500.00 zzgl. 2% Toleranz — Preis-/Mengenabweichung klären
