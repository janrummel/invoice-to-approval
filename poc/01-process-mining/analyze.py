"""PM4Py-Quick-Scan auf dem P2P-Event-Log.

Erzeugt output/report.md mit:
  1. Varianten-Analyse (Anteile, Durchlaufzeiten)
  2. Bottleneck-Analyse (Wartezeiten zwischen Aktivitäten, Performance-DFG)
  3. Manuelle-Touches-Analyse (FTE-Abschätzung)
  4. Automatisierungs-Heatmap (Score = Häufigkeit x manuell x Zeitbindung)
     inkl. empfohlenem Automatisierungs-Hebel je Aktivität
sowie Prozesslandkarten (DFG frequency/performance) als PNG.
"""

from collections import defaultdict
from pathlib import Path

import pandas as pd
import pm4py

BASE = Path(__file__).parent
DATA = BASE / "data" / "p2p_eventlog.csv"
OUT = BASE / "output"

# Annahme für FTE-Abschätzung: aktive Bearbeitungszeit pro manuellem Touch (Minuten)
HANDLING_MIN = {
    "Rechnung erfasst": 6,
    "Bestellung freigegeben": 3,
    "Preisabweichung geklaert": 25,
    "Mengenabweichung geklaert": 20,
    "Kontierung manuell ergaenzt": 10,
    "Freigabe Fachbereich": 5,
    "Dublettenpruefung": 12,
    "Rechnung storniert": 8,
}

# Automatisierungs-Hebel je Aktivität (Wissensbasis aus der Research-Note)
LEVER = {
    "Rechnung erfasst": "IDP/E-Rechnung: XRechnung/ZUGFeRD strukturiert parsen, Rest via Extraktion+Validierung",
    "Bestellung freigegeben": "Workflow (DPA): Schwellwert-basierte Auto-Freigabe via DMN-Regeln",
    "Preisabweichung geklaert": "Agent+HITL: Toleranzregeln automatisch, Rest LLM-Vorklärung mit Beleg-Kontext",
    "Mengenabweichung geklaert": "Regeln+Workflow: Toleranzband, automatische Nachforderung an Lieferant",
    "Kontierung manuell ergaenzt": "ML/LLM-Kontierungsvorschlag aus Historie (Confidence-Gate)",
    "Freigabe Fachbereich": "Workflow (DPA): risk-tiered — Kleinbetrag/bekannter Kreditor automatisch",
    "Dublettenpruefung": "Deterministisch: Fuzzy-Matching (Betrag+Datum+Vendor+Referenz)",
    "Rechnung storniert": "Folgeprozess der Dublettenpruefung — entfällt größtenteils mit ihr",
}


def fmt_h(hours: float) -> str:
    return f"{hours / 24:.1f} d" if hours >= 48 else f"{hours:.1f} h"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    df = pd.read_csv(DATA)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    log = pm4py.format_dataframe(df, case_id="case_id", activity_key="activity",
                                 timestamp_key="timestamp")

    n_cases = df["case_id"].nunique()
    lines = ["# P2P Process-Mining-Quick-Scan — Ergebnisbericht", ""]
    lines += [f"Datenbasis: **{len(df)} Events, {n_cases} Rechnungsvorgänge**, "
              f"{df['timestamp'].min():%Y-%m-%d} bis {df['timestamp'].max():%Y-%m-%d} "
              f"(synthetischer Log, Seed 42).", ""]

    # --- 1. Varianten ---------------------------------------------------
    case_meta = df.groupby("case_id").agg(
        variant=("variant", "first"),
        start=("timestamp", "min"), end=("timestamp", "max"),
        amount=("amount", "first"))
    case_meta["tput_h"] = (case_meta["end"] - case_meta["start"]).dt.total_seconds() / 3600

    lines += ["## 1. Prozessvarianten", "",
              "| Variante | Fälle | Anteil | Ø Durchlaufzeit | Median |",
              "|---|---|---|---|---|"]
    for var, grp in sorted(case_meta.groupby("variant"), key=lambda x: -len(x[1])):
        lines.append(f"| {var} | {len(grp)} | {len(grp)/n_cases:.0%} "
                     f"| {fmt_h(grp['tput_h'].mean())} | {fmt_h(grp['tput_h'].median())} |")
    happy = case_meta[case_meta["variant"] == "V1_happy_path"]["tput_h"].mean()
    dev = case_meta[case_meta["variant"].str.startswith(("V2", "V3"))]["tput_h"].mean()
    lines += ["", f"**Befund:** Abweichungsfälle (V2/V3) laufen im Schnitt "
              f"**{dev/happy:.1f}x länger** als der Happy Path "
              f"({fmt_h(dev)} vs. {fmt_h(happy)}).", ""]

    # --- 2. Bottlenecks (Wartezeit vor Aktivität) ------------------------
    df_s = df.sort_values(["case_id", "timestamp"])
    df_s["wait_h"] = df_s.groupby("case_id")["timestamp"].diff().dt.total_seconds() / 3600
    waits = (df_s.dropna(subset=["wait_h"]).groupby("activity")["wait_h"]
             .agg(["mean", "median", "count"]).sort_values("mean", ascending=False))

    lines += ["## 2. Bottlenecks (Wartezeit bis zur Aktivität)", "",
              "| Aktivität | Ø Wartezeit | Median | Vorkommen |", "|---|---|---|---|"]
    for act, row in waits.head(8).iterrows():
        lines.append(f"| {act} | {fmt_h(row['mean'])} | {fmt_h(row['median'])} "
                     f"| {int(row['count'])} |")
    lines += ["", "**Befund:** Die größten Liegezeiten entstehen vor manuellen "
              "Klärungs- und Freigabeschritten — nicht in der Systemverarbeitung.", ""]

    # --- 3. Manuelle Touches / FTE-Abschätzung ---------------------------
    manual = df[df["resource"] == "sachbearbeiter"]
    per_act = manual.groupby("activity").size().sort_values(ascending=False)
    months = (df["timestamp"].max() - df["timestamp"].min()).days / 30.4
    total_min = sum(cnt * HANDLING_MIN.get(act, 5) for act, cnt in per_act.items())
    fte = total_min / 60 / months / 140  # 140 produktive h/Monat

    lines += ["## 3. Manuelle Touches", "",
              f"{len(manual)} manuelle Bearbeitungsschritte "
              f"({len(manual)/len(df):.0%} aller Events); geschätzte Bindung: "
              f"**~{fte:.1f} FTE** (Annahmen: Handling-Minuten je Touch, 140 prod. h/Monat).",
              "", "| Aktivität | Touches | Min/Touch (Annahme) | Std/Monat |",
              "|---|---|---|---|"]
    for act, cnt in per_act.items():
        m = HANDLING_MIN.get(act, 5)
        lines.append(f"| {act} | {cnt} | {m} | {cnt*m/60/months:.0f} |")
    lines.append("")

    # --- 4. Automatisierungs-Heatmap -------------------------------------
    lines += ["## 4. Automatisierungs-Heatmap", "",
              "Score = Touches x Handling-Zeit (Std/Monat), d.h. gebundene Kapazität — "
              "gerankt nach Automatisierungspotenzial:", "",
              "| Rang | Aktivität | Std/Monat | Empfohlener Hebel |", "|---|---|---|---|"]
    scored = sorted(((act, cnt * HANDLING_MIN.get(act, 5) / 60 / months)
                     for act, cnt in per_act.items()), key=lambda x: -x[1])
    for i, (act, h) in enumerate(scored, 1):
        lines.append(f"| {i} | {act} | {h:.0f} | {LEVER.get(act, '-')} |")
    lines += ["", "**Lesart für die Priorisierung (2x2 Aufwand x Nutzen):** "
              "Dublettenpruefung und Freigaben sind Quick Wins (deterministisch, "
              "geringer Aufwand); Rechnungserfassung ist der größte Hebel, braucht aber "
              "IDP/E-Rechnungs-Pipeline; Abweichungsklärung ist wertvoll, aber "
              "Agent+HITL-Terrain (höchste Komplexität).", ""]

    # --- 5. Prozesslandkarten --------------------------------------------
    dfg, start_acts, end_acts = pm4py.discover_dfg(log)
    pm4py.save_vis_dfg(dfg, start_acts, end_acts, str(OUT / "dfg_frequency.png"))
    perf_dfg, s2, e2 = pm4py.discover_performance_dfg(log)
    pm4py.save_vis_performance_dfg(perf_dfg, s2, e2, str(OUT / "dfg_performance.png"))
    lines += ["## 5. Prozesslandkarten", "",
              "![Frequency DFG](dfg_frequency.png)", "",
              "![Performance DFG](dfg_performance.png)", ""]

    (OUT / "report.md").write_text("\n".join(lines))
    print(f"Report -> {OUT/'report.md'}")
    print(f"Varianten: {case_meta['variant'].nunique()}, FTE-Schätzung: {fte:.1f}")


if __name__ == "__main__":
    main()
