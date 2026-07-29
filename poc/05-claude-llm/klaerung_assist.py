"""Klaerungs-Assistent: Claude bereitet den Abweichungsfall fuer den Pruefer auf.

Demonstriert "grounded generation" fuer den teuersten manuellen Schritt aus
POC 01 (Preis-/Summenabweichung klaeren, Ø 25 Min/Fall):
  - ALLE Zahlen und Befunde kommen als strukturierte Daten aus der Pipeline
  - Claude fasst zusammen und entwirft die Lieferanten-Anfrage
  - Output ist ausdruecklich ENTWURF — Freigabe durch Sachbearbeiter (HITL)
"""

import json
import subprocess
from pathlib import Path

BASE = Path(__file__).parent
RESULTS = BASE.parent / "02-invoice-pipeline" / "output" / "results.json"


def main() -> None:
    decisions = json.loads(RESULTS.read_text())
    fall = next(d for d in decisions if d["invoice_number"] == "BL-77113")

    prompt = f"""Du unterstuetzt die Kreditorenbuchhaltung eines Handelsunternehmens.
Fuer folgende Eingangsrechnung hat die automatische Pruefung Befunde ergeben
(strukturierte Daten der Pruef-Pipeline, alle Zahlen sind verbindlich —
erfinde KEINE neuen Zahlen und rechne nichts eigenmaechtig um):

{json.dumps(fall, indent=2, ensure_ascii=False)}

Erstelle auf Deutsch:
1. SACHVERHALT: 3-4 Saetze fuer den Pruefer — was ist auffaellig, was ist zu tun.
2. ENTWURF LIEFERANTEN-ANFRAGE: kurze, professionelle E-Mail an die
   Beta Logistik AG mit Bitte um Korrekturrechnung oder Aufklaerung
   (Rechnungsnummer und konkrete Differenz nennen).

Format: Markdown mit den zwei Ueberschriften. Keine weiteren Abschnitte."""

    r = subprocess.run(["claude", "-p"], input=prompt, capture_output=True,
                       text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"claude CLI fehlgeschlagen: {r.stderr[:500]}")

    out = BASE / "output"
    out.mkdir(exist_ok=True)
    content = ("## Demo 2 — Klaerungs-Assistent (BL-77113, Summenfehler)\n\n"
               "> ⚠️ ENTWURF — generiert aus Pipeline-Befunden, Versand erst nach "
               "Freigabe durch Sachbearbeitung (Human-in-the-Loop).\n\n"
               + r.stdout.strip() + "\n")
    (out / "demo2_klaerung.md").write_text(content)
    print(content)


if __name__ == "__main__":
    main()
