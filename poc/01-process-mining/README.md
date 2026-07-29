# POC 01 — Process-Mining-Quick-Scan (PM4Py)

Demonstriert den ersten Schritt der Potenzialermittlung: Aus einem
Purchase-to-Pay-Event-Log wird datenbasiert eine **Automatisierungs-Heatmap**
abgeleitet — Varianten, Bottlenecks, manuelle Touches, FTE-Bindung und je
Aktivität der passende Automatisierungs-Hebel (IDP, DPA/Workflow, Regeln, Agent+HITL).

## Ausführen

```bash
pip install pm4py            # benötigt zusätzlich graphviz (apt install graphviz)
python3 generate_eventlog.py # erzeugt data/p2p_eventlog.csv (synthetisch, Seed 42)
python3 analyze.py           # erzeugt output/report.md + Prozesslandkarten (PNG)
```

## Ergebnis (committed unter `output/`)

Kernbefunde des synthetischen Logs (2.000 Rechnungsvorgänge, 6 Monate):

- Abweichungsfälle (Preis/Menge) laufen **2,1x länger** als der Happy Path (14,8 vs. 7,1 Tage)
- Liegezeiten entstehen vor **manuellen Klärungs-/Freigabeschritten**, nicht im System
- 32 % aller Events sind manuelle Touches (~0,7 FTE bei 2.000 Vorgängen/Halbjahr)
- Top-Hebel: Rechnungserfassung (IDP/E-Rechnung) und Preisabweichungsklärung (Agent+HITL)

## Warum so gebaut

- **Synthetischer Log statt Realdaten:** reproduzierbar (Seed), keine Datenschutzfragen,
  Varianten bewusst konstruiert (Happy Path, Preis-/Mengenabweichung, Maverick Buying,
  Dubletten) — die Analyse-Logik überträgt sich 1:1 auf echte ERP-Extrakte.
- **Heatmap statt nur Discovery:** Prozessgraphen allein beantworten nicht "was zuerst
  automatisieren?" — der Report übersetzt Mining-Befunde in eine priorisierte
  Automatisierungs-Pipeline (2x2 Aufwand x Nutzen).

## Caveats

- **PM4Py ist AGPL-lizenziert** — für interne Analysen unkritisch, bei Einbettung in
  ausgelieferte Produkte/SaaS Lizenzprüfung nötig (kommerzielle Lizenz verfügbar).
- FTE-Schätzung beruht auf angenommenen Handling-Zeiten je Touch — im Realeinsatz
  durch Task Mining oder Interviews kalibrieren.
- Nächste Ausbaustufe: OCEL 2.0 (Object-Centric) für die echte n:m-Beziehung
  Bestellung ↔ Rechnung ↔ Zahlung.
