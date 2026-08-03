"""Der committete Mining-Report muss von den Cockpit-Parsern lesbar bleiben.
Die Muster sind Kopien aus build_cockpit.py / app/server.py (bewusste Dopplung,
dort dokumentiert) — ändert sich der Report, muss dieser Test grün bleiben."""

import re
from pathlib import Path

REPORT = (Path(__file__).resolve().parents[1]
          / "poc" / "01-process-mining" / "output" / "report.md")


def test_report_bleibt_cockpit_parsebar():
    text = REPORT.read_text()
    assert re.findall(r"\| (V\d\S+) \| (\d+) \| (\d+%) \| ([\d.]+) d \|", text)
    assert re.search(r"\*\*(\d+) Events", text)
    assert re.search(r"\*\*([\d.]+)x länger\*\*", text)
    assert re.search(r"\*\*~([\d.]+) FTE\*\*", text)


def test_befund_nennt_median():
    assert "auf dem Median" in REPORT.read_text()
