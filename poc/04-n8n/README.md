# POC 04 — n8n: Orchestrierung Invoice-to-Approval

Die Klammer um POC 01–03: Ein **n8n**-Workflow orchestriert die Kette End-to-End —

```
Trigger (manuell/Zeitplan/Webhook)
  → Execute Command:  Invoice-Pipeline ausführen (POC 02, Python)
  → Read File + Extract + Split Out:  results.json in Einzelbelege zerlegen
  → HTTP Request:  je Beleg Flowable-Prozessinstanz starten (POC 03, REST)
  → Set:  Lauf-Zusammenfassung
```

n8n ist hier bewusst **reine Orchestrierung**: keine Fachlogik, keine
Freigabeentscheidung. Validierung lebt in der Pipeline (Python, testbar),
Freigaberegeln in der DMN-Tabelle (fachlich pflegbar), Human-Tasks in der
BPMN-Engine (auditierbar). Genau diese Arbeitsteilung ist das Architektur-Muster
aus der Research-Note.

## Ausführen (headless, ohne UI)

```bash
npm install -g n8n
../03-flowable/start_engine.sh          # Flowable muss laufen
./run_demo.sh                           # Import + Execute via n8n-CLI
```

`run_demo.sh` nutzt die n8n-CLI (`import:workflow`, `execute --id`) — derselbe
Workflow ist über die n8n-UI (`n8n start` → http://localhost:5678) visuell
editierbar; `workflows/invoice-to-approval.json` ist das Standard-Exportformat.

## Ergebnis

Siehe `output/report.md`: 6 gestartete Prozessinstanzen — AUTO/REJECT-Fälle
laufen sofort durch (Dunkelbuchung bzw. Abweisung), die übrigen 4 landen als
offene Freigabe-Tasks in der Flowable-Queue (Sachbearbeiter/Teamleitung).

## Notizen

- **Lizenz-Einordnung (Einordnung):** n8n ist fair-code (Sustainable Use
  License), nicht OSI-Open-Source — interne Nutzung frei, Embedding/Resale nicht;
  SSO/RBAC/Log-Streaming liegen in der Enterprise-Lizenz. Für IKS-relevante
  Workflows einkalkulieren.
- Auth zum Flowable-REST hier als statischer Basic-Auth-Header im Workflow —
  produktiv: n8n-Credential-Store bzw. Secrets-Management.
- `Execute Command` setzt Self-Hosting voraus (in n8n Cloud nicht verfügbar) —
  ein bewusstes Argument für Self-Hosted bei Automatisierung mit lokalen Skripten.
- Alternativ-Trigger für den Realbetrieb: IMAP/Mail-Eingang, Ordner-Watcher,
  Webhook vom DMS — der Rest des Workflows bleibt identisch.
