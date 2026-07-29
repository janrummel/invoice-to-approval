"""Erzeugt einen synthetischen Purchase-to-Pay-Event-Log (CSV).

Simuliert werden 2.000 Rechnungsvorgänge eines Handelsunternehmens über 6 Monate
mit realistischen Prozessvarianten:

  V1  Happy Path mit Bestellbezug (automatischer 3-Way-Match)
  V2  Preisabweichung  -> manuelle Klärung (ggf. mehrfach) + Fachbereichs-Freigabe
  V3  Mengenabweichung -> manuelle Klärung + Fachbereichs-Freigabe
  V4  Rechnung ohne Bestellbezug (Maverick Buying) -> manuelle Kontierung + Freigabe
  V5  Dublettenverdacht -> Prüfung, teils Storno

Jede Aktivität trägt ein resource-Flag (system|sachbearbeiter), damit die Analyse
manuelle Touches zählen kann.
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

OUT = Path(__file__).parent / "data" / "p2p_eventlog.csv"

VENDORS = [f"Lieferant_{i:02d}" for i in range(1, 26)]
# Einige Lieferanten sind "Problemlieferanten" mit erhöhter Abweichungsquote
PROBLEM_VENDORS = set(random.sample(VENDORS, 5))

# (activity, resource_type, min_hours, max_hours) — Dauer bis zur NÄCHSTEN Aktivität
STEP = {
    "Bestellung angelegt":            ("system",         0.1, 0.5),
    "Bestellung freigegeben":         ("sachbearbeiter", 4.0, 48.0),
    "Wareneingang gebucht":           ("system",         24.0, 240.0),
    "Rechnung empfangen":             ("system",         0.1, 0.3),
    "Rechnung erfasst":               ("sachbearbeiter", 1.0, 24.0),
    "3-Way-Match durchgefuehrt":      ("system",         0.1, 0.5),
    "Preisabweichung geklaert":       ("sachbearbeiter", 24.0, 192.0),   # 1-8 Tage!
    "Mengenabweichung geklaert":      ("sachbearbeiter", 24.0, 120.0),
    "Kontierung manuell ergaenzt":    ("sachbearbeiter", 4.0, 48.0),
    "Freigabe Fachbereich":           ("sachbearbeiter", 24.0, 120.0),   # 1-5 Tage
    "Dublettenpruefung":              ("sachbearbeiter", 4.0, 48.0),
    "Rechnung storniert":             ("sachbearbeiter", 0.5, 2.0),
    "Rechnung gebucht":               ("system",         0.1, 0.5),
    "Zahlung ausgefuehrt":            ("system",         24.0, 72.0),
}


def build_trace(case_id: str, start: datetime) -> list[dict]:
    vendor = random.choice(VENDORS)
    problem = vendor in PROBLEM_VENDORS
    amount = round(random.lognormvariate(6.5, 1.2), 2)  # Median ~665 EUR

    r = random.random()
    if r < 0.10:                       # V4: ohne Bestellbezug
        acts = ["Rechnung empfangen", "Rechnung erfasst", "Kontierung manuell ergaenzt",
                "Freigabe Fachbereich", "Rechnung gebucht", "Zahlung ausgefuehrt"]
        variant = "V4_ohne_bestellbezug"
    elif r < 0.13:                     # V5: Dublettenverdacht
        acts = ["Rechnung empfangen", "Rechnung erfasst", "Dublettenpruefung"]
        if random.random() < 0.6:
            acts += ["Rechnung storniert"]
            variant = "V5_dublette_storno"
        else:
            acts += ["Rechnung gebucht", "Zahlung ausgefuehrt"]
            variant = "V5_dublette_ok"
    else:
        base = ["Bestellung angelegt", "Bestellung freigegeben", "Wareneingang gebucht",
                "Rechnung empfangen", "Rechnung erfasst", "3-Way-Match durchgefuehrt"]
        mismatch_p = 0.55 if problem else 0.22
        if random.random() < mismatch_p:
            if random.random() < 0.6:  # V2: Preisabweichung, evtl. Schleife
                loops = ["Preisabweichung geklaert"] * (1 + (random.random() < 0.3))
                acts = base + loops + ["Freigabe Fachbereich", "Rechnung gebucht",
                                       "Zahlung ausgefuehrt"]
                variant = "V2_preisabweichung"
            else:                      # V3: Mengenabweichung
                acts = base + ["Mengenabweichung geklaert", "Freigabe Fachbereich",
                               "Rechnung gebucht", "Zahlung ausgefuehrt"]
                variant = "V3_mengenabweichung"
        else:                          # V1: Happy Path
            acts = base + ["Rechnung gebucht", "Zahlung ausgefuehrt"]
            variant = "V1_happy_path"

    rows, ts = [], start
    for act in acts:
        resource, lo, hi = STEP[act]
        rows.append({
            "case_id": case_id, "activity": act,
            "timestamp": ts.strftime("%Y-%m-%d %H:%M:%S"),
            "resource": resource, "vendor": vendor,
            "amount": amount, "variant": variant,
        })
        ts += timedelta(hours=random.uniform(lo, hi))
    return rows


def main() -> None:
    OUT.parent.mkdir(exist_ok=True)
    t0 = datetime(2026, 1, 5, 8, 0)
    rows = []
    for i in range(2000):
        start = t0 + timedelta(hours=random.uniform(0, 24 * 175))
        rows.extend(build_trace(f"INV-{i:05d}", start))
    rows.sort(key=lambda x: (x["case_id"], x["timestamp"]))
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} Events / 2000 Cases -> {OUT}")


if __name__ == "__main__":
    main()
