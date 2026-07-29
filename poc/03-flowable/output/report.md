# Flowable-Demo — Audit-Trail des Freigabe-Workflows

| Rechnung | DMN-Stufe | Entscheider | Ergebnis | Kommentar |
|---|---|---|---|---|
| RE-2026-0815 | AUTO | — | 🟢 gebucht | — |
| BL-77113 | SACHBEARBEITER | s.bearb | 🔴 abgelehnt | Summenfehler bestätigt — Korrekturrechnung beim Lieferanten angefordert |
| GIT-2026-442 | TEAMLEITUNG | t.lead | 🔴 abgelehnt | IBAN-Änderung telefonisch NICHT bestätigt — Verdacht auf Betrug, Fall an Compliance |
| DA-10077 | TEAMLEITUNG | t.lead | 🟢 gebucht | Bestellung und Wareneingang geprüft — Freigabe Großbetrag erteilt |
| RE-2026-0815 | ABGELEHNT | — | 🔴 abgelehnt | — |
| OC-889 | TEAMLEITUNG | t.lead | 🟢 gebucht | Beleg manuell geprüft, Lieferant neu angelegt — Felder korrekt extrahiert |
| RE-2026-0900 | SACHBEARBEITER | s.bearb | 🟢 gebucht | Preisabweichung mit dem Einkauf geklärt — Nachtrag zur Bestellung PO-4761 liegt vor |

## Durchlaufene Pfade

- **RE-2026-0815:** `Rechnung aus Pipeline → Freigabestufe ermitteln (DMN) → Freigabestufe? → Dunkelbuchung ausloesen → Gebucht`
- **BL-77113:** `Rechnung aus Pipeline → Freigabestufe ermitteln (DMN) → Freigabestufe? → Rechnung pruefen und freigeben → freigegeben? → Abgelehnt`
- **GIT-2026-442:** `Rechnung aus Pipeline → Freigabestufe ermitteln (DMN) → Freigabestufe? → Rechnung pruefen und freigeben → freigegeben? → Abgelehnt`
- **DA-10077:** `Rechnung aus Pipeline → Freigabestufe ermitteln (DMN) → Freigabestufe? → Rechnung pruefen und freigeben → freigegeben? → Dunkelbuchung ausloesen → Gebucht`
- **RE-2026-0815:** `Rechnung aus Pipeline → Freigabestufe ermitteln (DMN) → Freigabestufe? → Abgelehnt`
- **OC-889:** `Rechnung aus Pipeline → Freigabestufe ermitteln (DMN) → Freigabestufe? → Rechnung pruefen und freigeben → freigegeben? → Dunkelbuchung ausloesen → Gebucht`
- **RE-2026-0900:** `Rechnung aus Pipeline → Freigabestufe ermitteln (DMN) → Freigabestufe? → Rechnung pruefen und freigeben → freigegeben? → Dunkelbuchung ausloesen → Gebucht`

Jeder Schritt (inkl. DMN-Ausführung, Bearbeiter, Zeitstempel) liegt in der Flowable-Historie — das ist der IKS-taugliche Audit-Trail, den Skript-Automatisierung allein nicht liefert.