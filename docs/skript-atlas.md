# Skript-Atlas: die Bausteine auf Code-Ebene

Ergänzung zum [POC-Walkthrough](poc-walkthrough.md): Dort stehen die Konzepte
je POC (Proof of Concept: Machbarkeitsnachweis) — hier wird **jedes Skript
einzeln aufgemacht**: Was liest es ein, in welchen Schritten verarbeitet es
das, mit welchen Variablen und Schwellwerten, welche Prüfungen laufen, was
kommt heraus. Ziel: Du kannst jedes Skript erklären, als hättest Du es selbst
geschrieben. Fachbegriffe: erste Nennung in Klammern erklärt; alphabetisch im
[Glossar des Walkthroughs](poc-walkthrough.md#glossar-alphabetisch).

Jede Seite folgt demselben Raster: **Zweck → Eingaben → Ablauf (Diagramm mit
den echten Funktionsnamen) → Variablen und Rahmenkriterien → Prüfungen und
Fehlerpfade → Ausgaben → der vollständige Code, geführt (links Code, rechts
Erklärnotizen) → Selbsttest.** Die Farb-Labels an den Code-Abschnitten
entsprechen den Blöcken im jeweiligen Ablauf-Diagramm.

## Die Seiten

| Skript | Rolle in der Kette | Seite |
|---|---|---|
| `parsers.py` | POC 02 · Schicht 1: Belege einlesen (UBL, CII, ZUGFeRD, Text-Fallback) | [→ parsers](atlas-parsers.md) |
| `validation.py` | POC 02 · Schicht 2: die acht deterministischen Prüfregeln V01–V08 | [→ validation](atlas-validation.md) |
| `routing.py` | POC 02 · Schicht 3: risikogestaffeltes Routing + Punktetabelle | [→ routing](atlas-routing.md) |
| `run.py` | POC 02 · der Dirigent: alle Belege durch die drei Schichten, Ergebnis-Dateien | [→ run](atlas-run.md) |
| `belegflut.py` | Szenario-Abnahme: 30 konstruierte Belege gegen eine Soll-Verteilung | [→ belegflut](atlas-belegflut.md) |
| `e2e_smoke.py` | Wächter: ein Beleg durch die komplette Kette gegen die laufende Engine | [→ e2e_smoke](atlas-e2e-smoke.md) |

Der Atlas wächst mit dem Projekt — neue Skripte bekommen neue Seiten.

## Lese-Empfehlung

In Pipeline-Reihenfolge: **parsers → validation → routing → run** (so fließt
ein Beleg durchs System), danach die zwei Test-Werkzeuge **belegflut** und
**e2e_smoke** — sie zeigen, wie man dasselbe System von außen prüft. Wer die
Konzepte davor auffrischen will: [POC-Walkthrough](poc-walkthrough.md),
Abschnitt POC 02.
