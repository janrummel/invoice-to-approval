# POC 06 — Freigabe-Cockpit (Frontend für den Fachbereich)

Beantwortet die Frage, die Backends nie beantworten: **"Wie sieht das für die
Sachbearbeitung aus?"** — in zwei Ausbaustufen:

| Stufe | Was | Wo |
|---|---|---|
| **A — Report-Dashboard** | Statisches, selbst-tragendes HTML über den committeten POC-Outputs (offline, ohne Server) | `build_cockpit.py` → `output/cockpit.html` |
| **B — Live-App** | Echte Bedienung gegen die laufende Flowable-Engine: Freigeben/Ablehnen aus dem Cockpit, Task verschwindet live aus der Queue, Audit-Trail wächst sichtbar | `app/` (FastAPI-Proxy + Vanilla-JS-Frontend) |

## Stufe B ausführen (Live-Demo)

```bash
../03-flowable/start_engine.sh   # Flowable-REST via Docker (rest-admin/test)
uv run app/seed.py               # deployt BPMN+DMN, startet 7 Instanzen,
                                 # lässt die 5 REVIEW-Tasks OFFEN
uv run app/server.py             # Proxy + Frontend → http://localhost:8000
```

`seed.py` räumt per Default Runtime + Historie ab (sauberer Demo-Start);
`--keep-history` lässt den Audit-Trail über mehrere Läufe wachsen.

### Architektur Stufe B

- **FastAPI-Proxy** (`app/server.py`): hält die Flowable-Credentials aus dem
  Frontend, liefert das Frontend same-origin aus (kein CORS) und reichert die
  Flowable-Tasks um die Beleg-Daten aus POC 02 an — Join über die Quelldatei,
  weil Belegnummern durch den Dubletten-Fall nicht eindeutig sind.
  Endpunkte: `/api/queue`, `/api/tasks/{id}/complete`, `/api/history`, `/api/mining`.
- **Frontend** (`app/static/`, Vanilla HTML/CSS/JS, kein Framework):
  App-Shell (Posteingang / Freigaben / Auswertung / Audit), Arbeitsliste mit
  Suche, Stufen-Filter und Sortierung, Detail-Drawer mit Tabs
  (Beleg | Prüfungen | Prozess/Audit), Leerzustand/Skeleton/Fehlerzustand,
  Tastatur (↑/↓ Zeilen, Enter öffnet, Esc schließt, `/` fokussiert Suche),
  Theme-Toggle (Light/Dark, folgt sonst dem System).
- **Governance im Kleinen:** Ablehnung ohne Kommentar wird abgewiesen
  (client- und serverseitig) — der Kommentar ist Teil des Audit-Trails.

## Stufe A ausführen (offline, ohne Engine)

```bash
python3 build_cockpit.py     # liest die committeten Outputs von POC 01/02/03
open output/cockpit.html
```

## Design-Entscheidungen

- **Status-Farben nach festen Regeln:** good/warning/critical sind reserviert,
  tragen immer Icon + Text (farbfehlsichtstauglich), und die Balken nutzen eine
  einzige Farbreihe — Farben folgen der Funktion, nicht der Dekoration. Beide
  Stufen teilen dasselbe validierte Farbsystem.
- **Ein Werkzeug, zwei Fragen:** Posteingang/Freigaben — "Was ist mit meinen
  Belegen passiert?" (operativ); Auswertung — "Warum automatisieren wir?"
  (Business Case, Mining aus POC 01). Genau die zwei Gespräche, die ein
  Solution Architect mit dem Fachbereich führt.
- **Proxy statt Direktzugriff:** Das Frontend spricht nie selbst mit Flowable —
  Credentials, Fehlerbilder und Datenanreicherung gehören in eine Serverschicht.
  Produktiv wäre das der Platz für SSO/OAuth, Rollenprüfung und Rate-Limits.
- **Demo-Scope bewusst:** Rollen sind abgeleitet, nicht authentifiziert
  (kein Login); Persistenz der Beleg-Anreicherung kommt aus committeten
