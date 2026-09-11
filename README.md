# invoice-to-approval

**Rechnungseingang bis Freigabe, End-to-End automatisiert** — sechs verzahnte
Proof-of-Concepts: Process Mining begründet die Automatisierung, eine
E-Rechnungs-Pipeline validiert und routet, Flowable (BPMN + DMN) orchestriert die
risk-tiered Freigabe, n8n verbindet die Bausteine, ein LLM übernimmt die
unscharfen Ränder, und ein Live-Cockpit macht die Freigabe bedienbar.

Alle Daten sind **synthetisch** (Seed 42). Kein Kundenbezug, keine Echtdaten.

**Website / Lern-Portal:** <https://janrummel.github.io/invoice-to-approval/>
(ohne Installation lesbar: alle Bausteine erklärt, Code kommentiert, Cockpit-Demo)

**Für wen:** Entwickler:innen, Architekt:innen und Fachbereichs-Menschen, die
verstehen wollen, wie moderne Rechnungsautomatisierung (Purchase-to-Pay)
zusammenspielt: E-Rechnung, Prozess-Engine, Entscheidungstabellen, LLM-Einsatz
mit Kontrolle. Python-Grundkenntnisse reichen; das Lern-Portal unter `docs/`
erklärt alle Fachbegriffe und den kompletten Code.

**Was du lernst:**

- wie E-Rechnungen (XRechnung UBL/CII, ZUGFeRD) maschinell gelesen und
  deterministisch validiert werden
- wie risikogestaffeltes Routing und DMN-Entscheidungstabellen Freigaben
  steuern — und warum Regel-Reihenfolge Semantik ist
- wo ein LLM in einen Finance-Prozess darf und wo nicht (Confidence-Gate,
  Human-in-the-Loop)
- wie man ein KI-gebautes System absichert: TDD, Mutation-Beweise,
  adversariale Belege, End-to-End-Smoke

**Zeit:** ~4–6 h für alles; jedes Kapitel einzeln in 20–30 min lesbar.

```
POC 01              POC 02                 POC 03                  POC 06
Process Mining ──▶  Invoice-Pipeline ──▶   Flowable BPMN+DMN ──▶   Freigabe-Cockpit
"Warum?"            Parse·Validierung·     risk-tiered Freigabe,   Live-Bedienung
                    Risk-Routing           Audit-Trail             der Queue
                         │                      ▲
                         └──── POC 04 n8n ──────┘        POC 05: LLM-Baustein
                               (Orchestrierung)          (Extraktion + Klärung)
```

## In 2 Minuten ansehen (ohne Setup)

Die Ergebnisse jedes Bausteins sind committet — man kann alles lesen, ohne etwas
zu installieren:

| Was | Wo |
|---|---|
| Statisches Freigabe-Cockpit (HTML, offline) | `poc/06-cockpit/output/cockpit.html` öffnen |
| Process-Mining-Befund (Varianten, Touches, FTE) | `poc/01-process-mining/output/report.md` |
| Pipeline-Ergebnis der 7 Testbelege | `poc/02-invoice-pipeline/output/results.md` |
| Flowable-Audit-Trail des Freigabe-Laufs | `poc/03-flowable/output/report.md` |
| n8n-Ausführungsprotokoll | `poc/04-n8n/output/execution.json` |

## Die sechs Bausteine

| POC | Inhalt | Kern-Aussage |
|---|---|---|
| [01-process-mining](poc/01-process-mining/) | PM4Py-Quick-Scan auf synthetischem P2P-Event-Log (16.518 Events, 2.000 Vorgänge) | Abweichungsfälle laufen 2,1× länger; ~0,7 FTE gebunden — das begründet die Automatisierung |
| [02-invoice-pipeline](poc/02-invoice-pipeline/) | XRechnung/ZUGFeRD-Parse, Validierung, Dubletten, 2-/3-Way-Match, Risk-Routing | Deterministische Regeln entscheiden AUTO_POST / REVIEW / REJECT, nichts bucht dunkel ohne bestandene Prüfungen |
| [03-flowable](poc/03-flowable/) | BPMN-Freigabe-Workflow, Freigabestufe als DMN-Tabelle, Engine real betrieben | Freigabelogik fachlich lesbar in DMN statt im Code; jede Entscheidung im Audit-Trail |
| [04-n8n](poc/04-n8n/) | Headless-Orchestrierung der Gesamtkette via CLI | Ein Workflow verbindet Pipeline und Prozess-Engine, mit Fehlerpfad |
| [05-claude-llm](poc/05-claude-llm/) | LLM als Baustein: Extraktion aus Scan-Fallback + Klärungs-Assistent | Das LLM sitzt zwischen deterministischen Schichten, nie an deren Stelle; Confidence-Gate verhindert Dunkelbuchung |
| [06-cockpit](poc/06-cockpit/) | Freigabe-Cockpit: statisches Dashboard (A) und Live-App gegen die Flowable-Queue (B) | Freigeben/Ablehnen aus der Oberfläche, Task verschwindet live, Audit wächst sichtbar |

## Live-Demo (Cockpit Stufe B)

Voraussetzungen: Docker, [uv](https://docs.astral.sh/uv/), Python ≥ 3.11.

```bash
poc/03-flowable/start_engine.sh      # Flowable-REST-Engine via Docker
cd poc/06-cockpit/app
uv run seed.py                       # deployt BPMN+DMN, startet 7 Instanzen,
                                     # lässt die 5 Prüf-Tasks offen
uv run server.py                     # → http://localhost:8000
```

Im Cockpit: Posteingang mit Suche/Filter/Sortierung, Detail-Panel mit Tabs
(Beleg, Prüfungen, Prozess/Audit), Freigeben/Ablehnen mit Kommentar
(Ablehnung ohne Kommentar wird abgewiesen — Audit-Pflicht), Tastaturbedienung
(↑/↓, Enter, Esc, `/`), Light/Dark.

Jeder POC ist auch einzeln lauffähig; die READMEs in den Unterordnern erklären
Ausführung, Design-Entscheidungen und bewusste Demo-Grenzen.

## Testfundament

Die Kette ist automatisiert abgesichert: **33 Tests** (`uv run pytest`) decken
alle Validierungsregeln (V01–V08), die komplette Routing-Punktetabelle und
Angriffs-Belege ab (XXE-Regression, kaputtes XML, nicht-positive Beträge —
Regel V08 entstand test-getrieben). Jeder Test wurde per Mutation-Beweis
geprüft (absichtlich rot gesehen). Dazu: End-to-End-Smoke gegen die laufende
Engine (`uv run scripts/e2e_smoke.py`, harte Exit-Codes) und das
Abnahme-Szenario "Belegflut" (`uv run scripts/belegflut.py`, 30 Belege gegen
eine Soll-Verteilung). Details: [docs/test-checkliste.md](docs/test-checkliste.md).

## Lern-Portal: das Repo erklärt sich selbst

Das Lern-Portal ist live unter
**<https://janrummel.github.io/invoice-to-approval/>** (GitHub Pages, Quelle:
`docs/`). Dieselben Seiten liegen im Repo und sind offline lesbar, indem man die
HTML-Dateien in `docs/` im Browser öffnet.

| Seite | Inhalt |
|---|---|
| **[Start / Übersicht](https://janrummel.github.io/invoice-to-approval/)** | Einstieg, Navigation über alle Seiten |
| **[POC-Walkthrough](https://janrummel.github.io/invoice-to-approval/poc-walkthrough.html)** | Konzepte je Baustein: Diagramme, die Zahlen, bewusste Grenzen, Glossar (~90 Begriffe, alle Abkürzungen erklärt) |
| **[Skript-Atlas](https://janrummel.github.io/invoice-to-approval/skript-atlas.html)** | sechs Skripte auf Code-Ebene geöffnet: Ablauf-Diagramm, Variablen mit Begründung, der **vollständige Code mit Erklärnotizen in einer zweiten Spalte**, Selbsttest-Fragen |
| **[Cockpit-Demo](https://janrummel.github.io/invoice-to-approval/demo-cockpit.html)** | das Freigabe-Cockpit als Demo-Ansicht |

Markdown-Quellen im Repo: [poc-walkthrough.md](docs/poc-walkthrough.md),
[skript-atlas.md](docs/skript-atlas.md).

## Bewusste Grenzen

Das ist ein Demonstrations-Stack, kein Produkt. Die wichtigsten bewussten
Vereinfachungen stehen je POC im Abschnitt "Grenzen" bzw.
"Design-Entscheidungen" — u.a.: In-Memory-Dublettenregister, Stammdaten als
JSON-Fixtures statt ERP-Anbindung, abgeleitete statt authentifizierte Rollen im
Cockpit, Demo-Credentials der Engine. Produktiv gehören dahin: Idempotenz-Keys
in einer DB, OData/REST ans ERP, SSO/Rollenprüfung, Secret-Store.

## FAQ

**Warum synthetische Daten?** Reproduzierbar (fester Seed), keine
Datenschutzfragen, und die Logik überträgt sich unverändert auf echte
ERP-Extrakte.

**Warum sechs POCs statt einem Tool?** Jeder Baustein beantwortet eine eigene
Frage (Warum automatisieren? Wie sicher einlesen? Wer gibt frei?). Die Trennung
macht Architektur-Entscheidungen sichtbar, die ein Monolith verstecken würde.

**Warum darf das LLM so wenig?** These des Projekts: Das LLM extrahiert,
formuliert und schlägt vor. Buchen, freigeben und rechnen tun deterministische
Regeln, Prozess-Engine und Mensch, gestaffelt nach Risiko. Automatisierung im
Finance-Umfeld ist ein Governance-Problem mit technischer Komponente.

**Ist das produktionsreif?** Nein, bewusst nicht (siehe "Bewusste Grenzen").
Es ist ein Demonstrations- und Lern-Stack mit ehrlich markierten Lücken und
benannten produktiven Ausbauschritten.

**Wie wurde das gebaut?** KI-gestützt (Claude Code): Ich habe gelesen, geprüft
und dirigiert. Das Testfundament (33 Tests, Mutation-geprüft) ist die Antwort
darauf, wie man KI-gebautem Code trauen kann.

## Lizenz

MIT — siehe [LICENSE](LICENSE).
