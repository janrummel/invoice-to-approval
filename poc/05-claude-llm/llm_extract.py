"""LLM-Fallback-Extraktion: Claude extrahiert Rechnungsfelder aus dem Scan ohne XML.

Demonstriert das Muster "LLM extrahiert — deterministische Regeln validieren":
  1. Text aus dem PDF (s6, kein eingebettetes XML) extrahieren
  2. Claude (headless via `claude -p`) extrahiert Felder als striktes JSON
  3. Pydantic-Modell aus POC 02 validiert Schema, Validierungsregeln (Summen,
     IBAN-Pruefsumme, USt-Rechnung) pruefen den Inhalt
  4. Ergebnis geht mit Confidence < 1.0 ins Risk-Routing — nie Dunkelbuchung

Produktiv wuerde statt des CLI die Claude API (structured outputs / instructor)
mit dem Belegbild (Vision) genutzt — das Muster ist identisch.
"""

import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import pdfplumber

BASE = Path(__file__).parent
POC02 = BASE.parent / "02-invoice-pipeline"
sys.path.insert(0, str(POC02))

from pipeline.models import Invoice, Party, SourceFormat  # noqa: E402
from pipeline.validation import validate  # noqa: E402

SCHEMA_HINT = """{
  "invoice_number": "string",
  "issue_date": "YYYY-MM-DD",
  "seller_name": "string",
  "vat_id": "string oder null",
  "iban": "string ohne Leerzeichen oder null",
  "total_net": "Zahl mit Dezimalpunkt",
  "total_tax": "Zahl mit Dezimalpunkt",
  "total_gross": "Zahl mit Dezimalpunkt"
}"""


def ask_claude(prompt: str) -> str:
    r = subprocess.run(["claude", "-p"], input=prompt, capture_output=True,
                       text=True, timeout=300)
    if r.returncode != 0:
        raise RuntimeError(f"claude CLI fehlgeschlagen: {r.stderr[:500]}")
    return r.stdout.strip()


def extract(pdf_path: Path) -> tuple[Invoice, list]:
    with pdfplumber.open(str(pdf_path)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)

    prompt = f"""Du bist ein Extraktionsdienst fuer Eingangsrechnungen.
Extrahiere die Felder aus folgendem Belegtext und antworte AUSSCHLIESSLICH mit
einem JSON-Objekt nach diesem Schema (keine Erklaerungen, kein Markdown):
{SCHEMA_HINT}

Regeln: Werte exakt aus dem Beleg uebernehmen, nichts erfinden; fehlende Felder
als null; deutsche Zahlen (89,90) als Dezimalpunkt-Zahlen (89.90).

Belegtext:
---
{text}
---"""

    raw = ask_claude(prompt)
    raw = re.sub(r"^```(json)?|```$", "", raw.strip(), flags=re.M).strip()
    data = json.loads(raw)

    inv = Invoice(
        invoice_number=data["invoice_number"],
        issue_date=date.fromisoformat(data["issue_date"]),
        seller=Party(name=data["seller_name"], vat_id=data.get("vat_id"),
                     iban=data.get("iban")),
        total_net=str(data["total_net"]),
        total_tax=str(data["total_tax"]),
        total_gross=str(data["total_gross"]),
        source_format=SourceFormat.PDF_FALLBACK,
        extraction_confidence=0.85,   # LLM-Extraktion: besser als Regex, nie 1.0
        source_file=pdf_path.name,
    )
    findings = validate(inv, today=date(2026, 7, 28))
    return inv, findings


def main() -> None:
    pdf = POC02 / "samples" / "s6_scan_ohne_xml.pdf"
    inv, findings = extract(pdf)

    out = BASE / "output"
    out.mkdir(exist_ok=True)
    lines = ["## Demo 1 — LLM-Fallback-Extraktion (s6, Scan ohne XML)", "",
             "Von Claude extrahiert und durch die deterministischen Regeln aus "
             "POC 02 validiert:", "",
             "| Feld | Wert |", "|---|---|",
             f"| Rechnungsnummer | {inv.invoice_number} |",
             f"| Datum | {inv.issue_date} |",
             f"| Lieferant | {inv.seller.name} |",
             f"| IBAN | {inv.seller.iban} |",
             f"| Netto / USt / Brutto | {inv.total_net} / {inv.total_tax} / {inv.total_gross} |",
             f"| Extraktions-Confidence | {inv.extraction_confidence:.0%} (LLM-Pfad) |",
             "",
             "**Deterministische Validierung:** "
             + ("; ".join(f"[{f.severity.value}] {f.code} {f.message}"
                          for f in findings) if findings
                else "alle Pruefungen bestanden (Summen, IBAN, Datum)"),
             "",
             "Routing bleibt REVIEW (Confidence < 90 %, neuer Lieferant) — das "
             "LLM beschleunigt die Erfassung, entscheidet aber nicht.", ""]
    (out / "demo1_extraktion.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
