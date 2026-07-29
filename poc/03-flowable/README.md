# POC 03 — Flowable: BPMN-Freigabe-Workflow mit DMN (risk-tiered)

Schließt die Kette aus POC 01/02: Die Routing-Entscheidungen der Invoice-Pipeline
(`../02-invoice-pipeline/output/results.json`) werden als Prozessinstanzen durch
einen **Flowable**-Workflow getrieben — Flowable als etabliertes
Open-Source-BPMN-Tool, hier produktiv demonstriert (Engine 7.2.0).

```
results.json ──> BPMN "rechnungsfreigabe"
                   └─ DMN-Tabelle "freigabestufe" (Hit Policy FIRST):
                        REJECT            -> ABGELEHNT   (Ende)
                        AUTO_POST         -> AUTO        (Dunkelbuchung, kein Mensch)
                        riskScore >= 50   -> TEAMLEITUNG (User-Task)
                        brutto > 10.000   -> TEAMLEITUNG (User-Task)
                        sonst             -> SACHBEARBEITER (User-Task)
                   └─ User-Task mit dynamischer candidateGroup aus DMN-Ergebnis
                   └─ Gateway freigegeben? -> Buchung oder Ablehnung
```

## Ausführen

```bash
./start_engine.sh        # Docker oder Java-WAR (H2 in-memory), Port 8080
pip install requests
python3 run_demo.py      # Deploy + 6 Instanzen + Tasks bearbeiten + Audit-Trail
```

## Demo-Ergebnis (siehe `output/report.md`)

| Rechnung | DMN-Stufe | Ausgang |
|---|---|---|
| RE-2026-0815 (s1) | AUTO | 🟢 dunkelgebucht — kein menschlicher Touch |
| BL-77113 (s2, Summenfehler) | SACHBEARBEITER | 🔴 abgelehnt, Korrekturrechnung angefordert |
| GIT-2026-442 (s3, IBAN-Wechsel) | TEAMLEITUNG | 🔴 abgelehnt, Fall an Compliance |
| DA-10077 (s4, 24.990 €) | TEAMLEITUNG | 🟢 nach Prüfung freigegeben und gebucht |
| RE-2026-0815 (s5, Dublette) | ABGELEHNT | 🔴 ohne menschlichen Aufwand verworfen |
| OC-889 (s6, Scan-Fallback) | TEAMLEITUNG | 🟢 nach Feldprüfung freigegeben |

## Warum das die richtige Architektur ist (Architektur-Begründung)

- **Freigabelogik als DMN-Tabelle, nicht als Code:** fachlich lesbar, vom
  Fachbereich pflegbar, versionierbar — Schwellwerte ändern heißt Tabelle ändern,
  nicht deployen.
- **BPMN = ausführbare Dokumentation:** Das Prozessmodell IST der laufende Prozess;
  Modell und Realität können nicht auseinanderlaufen.
- **Audit-Trail gratis:** Flowable-Historie protokolliert jede Aktivität, DMN-
  Ausführung, Bearbeiter und Zeitstempel — IKS-/Revisionsanforderung out of the box.
- **Human-in-the-Loop strukturell erzwungen:** Der Automat KANN oberhalb der
  Schwellen nicht buchen; die Kontrolle liegt in der Prozess-Engine, nicht im
  Goodwill eines Skripts (Kernprinzip "risk-tiered autonomy").

## Technische Notizen / Stolpersteine (ehrlich dokumentiert)

- `flowable-app-rest` deployt `.dmn`-Ressourcen **nicht** über das Prozess-Deployment
  mit — die DMN-Tabelle muss separat an `POST /dmn-api/dmn-repository/deployments`;
  der DMN-Task findet sie dann über den Fallback ohne Parent-Deployment.
- Dynamische Zuständigkeit via Expression in `flowable:candidateGroups`
  (`${stufe == 'TEAMLEITUNG' ? 'teamleitung' : 'sachbearbeiter'}`).
- H2 in-memory: Neustart = leere Engine — für die Demo ideal, produktiv PostgreSQL.
- Ohne BPMN-DI-Sektion liefert der Image-Endpoint kein Diagramm — fürs Showcase
  das Modell in bpmn.io öffnen (Datei ist standardkonform).
