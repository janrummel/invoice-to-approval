# Upgrade-Brief: Vom Report-Dashboard zur professionellen App

Stand 2026-07-28. Das heutige Cockpit ist ein **statisch generiertes Read-only-Dashboard**
mit gutem visuellen Grundniveau (Status-System, Light/Dark, deutsche Formate), aber es
ist keine App: keine Aktionen, keine Navigation, keine Zustände, Daten nur zur Build-Zeit.

## Zielbild in zwei Ausbaustufen

### Stufe A — polierte App-Simulation (statisch bleibt ok)
- **App-Shell:** schmale Seitennavigation (Posteingang / Freigaben / Auswertung / Audit),
  Topbar mit Titel, Umgebungs-Badge ("Demo"), Theme-Toggle
- **Arbeitsliste statt Tabelle:** Sortierung (Betrag, Risk, Status), Freitextsuche,
  Filter als Segmente, Zeilen-Hover mit Aktions-Andeutung
- **Detail als Seitenpanel** (Drawer) statt Inline-Aufklappen: Tabs "Beleg | Prüfungen |
  Prozess/Audit", Beleg-Rohdaten einsehbar
- **Zustände:** Leerzustand je Filter, Skeleton beim (simulierten) Laden, Fehlerzustand
- **Tastatur:** ↑/↓ Zeilennavigation, Enter öffnet Panel, Esc schließt, / fokussiert Suche
- **Micro-UX:** Zahlen tabellarisch ausgerichtet, relative Zeitstempel, Kopieren-Buttons
  für Belegnummern, Fokus-Ringe, reduzierte Motion via prefers-reduced-motion

### Stufe B — echte App gegen die laufende Kette (der eigentliche Reifegrad-Sprung)
- Kleiner lokaler **FastAPI-Proxy** (löst CORS + hält die Flowable-Credentials aus dem
  Frontend): `GET /api/queue` (offene Tasks aus Flowable), `POST /api/tasks/{id}/complete`
  (freigeben/ablehnen mit Kommentar), `GET /api/history/{beleg}`
- Damit werden die Buttons echt: **Freigeben/Ablehnen aus dem Cockpit**, Task verschwindet
  live aus der Queue, Audit-Trail wächst sichtbar — das ist die Demo, die man
  selten sieht
- Optional: Claude-Klärungs-Assistent (POC 05) als Panel-Aktion "Klärungsentwurf erstellen"

## Leitplanken
- Kein Framework-Zwang: Vanilla HTML/CSS/JS reicht für A; für B kommt nur FastAPI dazu
- Status-Farbsystem und Dark/Light aus dem heutigen Stand übernehmen (validiert)
- Empfohlener Weg: A als Zwischenschritt überspringen und direkt B bauen, A-Elemente
  (Shell, Panel, Zustände, Tastatur) darin umsetzen
- Aufwand geschätzt: B ≈ ein konzentrierter Halbtag inkl. visueller Abnahme

## Status: Stufe B umgesetzt (2026-07-29)

Direkt B gebaut (A-Elemente darin umgesetzt), wie oben empfohlen. Ergebnis in
`app/` (FastAPI-Proxy + Vanilla-Frontend), E2E gegen die laufende Engine
verifiziert, Light + Dark visuell abgenommen. Details: README dieses POCs.

Neue Sprachregelung: "Das Cockpit bedient die Flowable-Queue live — Freigeben/
Ablehnen aus der Oberfläche, der Audit-Trail wächst sichtbar mit. Rollen sind im
Demo-Scope abgeleitet statt authentifiziert; SSO/Login wäre der nächste Baustein."
Optional offen: Claude-Klärungs-Assistent (POC 05) als Panel-Aktion.
