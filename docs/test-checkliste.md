# Test-Checkliste

| Testart | Was | Wann |
|---|---|---|
| Bedien-Test | das System wie eine Sachbearbeitung nutzen | Auftakt jeder Stufe |
| Szenario-Test | Drehbuch mit erwartetem Ausgang | Abschluss jeder Stufe |
| Adversarialer Belegtest | konstruierte Grenz-/Angriffsfälle | Stufe 1, danach Regression |
| Unit-Test | einzelne Regel isoliert | bei jedem Bau-Slice |
| Integrationstest | Zusammenspiel mit der Engine-Schnittstelle | bei Prozess-Änderungen |
| End-to-End-Smoke | ein Beleg durch die komplette Kette | vor Commits größerer Umbauten |
| Regressionslauf | ganze Suite auf Knopfdruck | nach jedem Umbau |
| Visueller Check | Cockpit in Hell und Dunkel | bei Oberflächen-Änderungen |

## Befehle

- Regressionslauf (Unit + adversarial): `uv run pytest`
- End-to-End-Smoke (braucht laufende Engine): `uv run scripts/e2e_smoke.py`
- Engine starten: `poc/03-flowable/start_engine.sh` · Demo seeden:
  `cd poc/06-cockpit/app && uv run seed.py` · Cockpit: `uv run server.py`
- Bedien-/Szenario-Test: Drehbuch: `scripts/belegflut.py`

## Regeln

- Exit-Code entscheidet; Testbefehle nie durch Pipes entschärfen.
- Neuer Test/Wächter gilt erst nach Mutation-Beweis (einmal absichtlich rot).
