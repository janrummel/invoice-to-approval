"""Pipeline-Lauf: samples/ -> Parse -> Validierung -> Routing -> output/.

Erzeugt output/results.md (menschenlesbar) und output/results.json
(maschinenlesbar — das Format, das ein Workflow-System wie Flowable/n8n
als Trigger-Payload konsumieren würde; siehe POC 03/04).
"""

import json
from datetime import date
from pathlib import Path

from pipeline.models import Route
from pipeline.parsers import parse_file
from pipeline.routing import Router
from pipeline.validation import validate

BASE = Path(__file__).parent
TODAY = date(2026, 7, 28)   # fixiert für Reproduzierbarkeit

ROUTE_ICON = {Route.AUTO_POST: "🟢", Route.REVIEW: "🟡", Route.REJECT: "🔴"}


def main() -> None:
    out = BASE / "output"
    out.mkdir(exist_ok=True)
    router = Router(BASE / "masterdata" / "vendors.json")

    decisions = []
    files = sorted(p for p in (BASE / "samples").iterdir()
                   if p.suffix.lower() in (".xml", ".pdf"))
    for path in files:
        inv = parse_file(path)
        findings = validate(inv, TODAY)
        decisions.append((inv, router.route(inv, findings)))

    lines = ["# Invoice-Pipeline — Ergebnis des Demo-Laufs", "",
             f"{len(decisions)} Belege verarbeitet (Stichtag {TODAY}).", "",
             "| Beleg | Format | Rechnung | Brutto | Route | Risk |",
             "|---|---|---|---|---|---|"]
    for inv, d in decisions:
        lines.append(f"| {d.source_file} | {inv.source_format.value} "
                     f"| {d.invoice_number} | {inv.total_gross} {inv.currency} "
                     f"| {ROUTE_ICON[d.route]} {d.route.value} | {d.risk_score} |")

    lines += ["", "## Begründungen je Beleg", ""]
    for inv, d in decisions:
        lines.append(f"### {d.source_file} — {ROUTE_ICON[d.route]} {d.route.value}")
        for r in d.reasons:
            lines.append(f"- {r}")
        if d.findings:
            lines.append(f"- Validierung: "
                         + "; ".join(f"[{f.severity.value}] {f.code} {f.message}"
                                     for f in d.findings))
        lines.append("")

    (out / "results.md").write_text("\n".join(lines))
    (out / "results.json").write_text(json.dumps(
        [d.model_dump(mode="json") for _, d in decisions],
        indent=2, ensure_ascii=False))

    for inv, d in decisions:
        print(f"{ROUTE_ICON[d.route]} {d.route.value:9s} {d.source_file}")
    print(f"\nReport -> {out/'results.md'}")


if __name__ == "__main__":
    main()
