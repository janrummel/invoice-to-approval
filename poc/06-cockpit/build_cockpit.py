"""Freigabe-Cockpit: statisches, selbst-tragendes HTML-Dashboard aus den POC-Outputs.

Liest die committeten Ergebnisse der Kette
  POC 01 (Process-Mining-Report)  -> Mining-Panel (Varianten, Touches, FTE)
  POC 02 (results.json)           -> Belegliste mit Routing/Risk/Findings
  POC 03 (Audit-Report)           -> DMN-Stufe, Entscheider, Ergebnis, Prozesspfad
und erzeugt output/cockpit.html — offline, ohne Server, ohne CDN.

Ausführen:  python3 build_cockpit.py
"""

import json
import re
from datetime import datetime, timezone
from html import escape
from pathlib import Path

BASE = Path(__file__).resolve().parent
POC = BASE.parent
OUT = BASE / "output"


# ── Datenquellen einlesen ──────────────────────────────────────────────────

def load_invoices():
    rows = json.loads((POC / "02-invoice-pipeline/output/results.json").read_text())
    report = (POC / "03-flowable/output/report.md").read_text()

    audit = []
    for line in report.splitlines():
        m = re.match(r"\| ([^|]+) \| ([A-ZÄÖÜ]+) \| ([^|]+) \| (🟢|🔴) ([^|]+) \| ([^|]+) \|", line)
        if m:
            audit.append({
                "dmn": m.group(2).strip(),
                "entscheider": m.group(3).strip(),
                "ergebnis": m.group(5).strip(),
                "kommentar": m.group(6).strip(),
            })
    pfade = re.findall(r"- \*\*[^:]+:\*\* `([^`]+)`", report)

    if len(audit) != len(rows) or len(pfade) != len(rows):
        raise SystemExit(
            f"Audit-Zeilen ({len(audit)}) / Pfade ({len(pfade)}) passen nicht zu "
            f"Belegen ({len(rows)}) — POC 03 report.md prüfen."
        )
    for row, a, pfad in zip(rows, audit, pfade):  # Reihenfolge = Lauf-Reihenfolge s1..s6
        row.update(a)
        row["pfad"] = pfad
    return rows


def load_mining():
    text = (POC / "01-process-mining/output/report.md").read_text()
    varianten = [
        {"name": m[0], "faelle": int(m[1]), "anteil": m[2], "dauer": float(m[3])}
        for m in re.findall(r"\| (V\d\S+) \| (\d+) \| (\d+%) \| ([\d.]+) d \|", text)
    ]
    touches = [
        {"name": m[0].strip(), "touches": int(m[1]), "stunden": int(m[2])}
        for m in re.findall(r"\| ([A-Za-zÄÖÜäöüß3\- ]+) \| (\d+) \| \d+ \| (\d+) \|", text)
    ]
    kpi = {
        "events": re.search(r"\*\*(\d+) Events", text).group(1),
        "cases": re.search(r"(\d+) Rechnungsvorgänge", text).group(1),
        "faktor": re.search(r"\*\*([\d.]+)x länger\*\*", text).group(1),
        "touch_anteil": re.search(r"\((\d+)% aller Events\)", text).group(1),
        "fte": re.search(r"\*\*~([\d.]+) FTE\*\*", text).group(1),
    }
    if not varianten or not touches:
        raise SystemExit("Mining-Report nicht parsebar — POC 01 report.md prüfen.")
    return {"varianten": varianten, "touches": touches, "kpi": kpi}


# ── HTML erzeugen ──────────────────────────────────────────────────────────

STATUS = {
    "AUTO_POST": ("good", "✓", "Auto-gebucht"),
    "REVIEW": ("warning", "⚠", "Prüfung"),
    "REJECT": ("critical", "✕", "Abgewiesen"),
}
ERGEBNIS = {"gebucht": ("good", "✓"), "abgelehnt": ("critical", "✕")}


def chip(role, icon, label):
    return f'<span class="chip chip-{role}"><span aria-hidden="true">{icon}</span>{escape(label)}</span>'


def de_betrag(value, decimals=2):
    """1428.0 -> '1.428,00' (deutsches Zahlenformat)."""
    s = f"{value:,.{decimals}f}"
    return s.replace(",", "\u00a7").replace(".", ",").replace("\u00a7", ".")


def build_html(invoices, mining):
    n = len(invoices)
    ohne_mensch = sum(1 for r in invoices if r["entscheider"] == "—")
    tasks = n - ohne_mensch
    summe = sum(float(r["total_gross"]) for r in invoices)

    rows_html = []
    for i, r in enumerate(invoices):
        role, icon, label = STATUS[r["route"]]
        e_role, e_icon = ERGEBNIS.get(r["ergebnis"], ("warning", "⚠"))
        gruende = "".join(f"<li>{escape(g)}</li>" for g in r["reasons"])
        kommentar = (f'<p class="detail-kommentar"><strong>Entscheidung '
                     f'({escape(r["entscheider"])}):</strong> {escape(r["kommentar"])}</p>'
                     if r["kommentar"] != "—" else "")
        pfad = " → ".join(escape(s) for s in r["pfad"].split(" → "))
        rows_html.append(f"""
      <tbody class="beleg" data-route="{r['route']}">
        <tr class="beleg-row" tabindex="0" role="button" aria-expanded="false"
            onclick="toggleDetail(this)" onkeydown="if(event.key==='Enter')toggleDetail(this)">
          <td class="mono">{escape(r['invoice_number'])}</td>
          <td class="num">{de_betrag(float(r['total_gross']))}&nbsp;€</td>
          <td>{chip(role, icon, label)}</td>
          <td class="num">{r['risk_score']}</td>
          <td>{escape(r['dmn'])}</td>
          <td>{chip(e_role, e_icon, r['ergebnis'])}</td>
          <td class="caret" aria-hidden="true">▸</td>
        </tr>
        <tr class="beleg-detail" hidden>
          <td colspan="7">
            <p class="detail-quelle">Quelle: <span class="mono">{escape(r['source_file'])}</span></p>
            <ul class="detail-gruende">{gruende}</ul>
            {kommentar}
            <p class="detail-pfad"><strong>Prozesspfad (Flowable-Audit):</strong><br>{pfad}</p>
          </td>
        </tr>
      </tbody>""")

    max_d = max(v["dauer"] for v in mining["varianten"])
    var_bars = "".join(f"""
        <div class="bar-row" title="{v['faelle']} Fälle ({v['anteil']})">
          <span class="bar-label">{escape(v['name'])}</span>
          <span class="bar-track"><span class="bar-fill" style="width:{v['dauer'] / max_d * 100:.0f}%"></span></span>
          <span class="bar-value">{str(v['dauer']).replace('.', ',')}&nbsp;d</span>
        </div>""" for v in sorted(mining["varianten"], key=lambda v: -v["dauer"]))

    max_h = max(t["stunden"] for t in mining["touches"])
    touch_bars = "".join(f"""
        <div class="bar-row" title="{t['touches']} Touches">
          <span class="bar-label">{escape(t['name'])}</span>
          <span class="bar-track"><span class="bar-fill" style="width:{t['stunden'] / max_h * 100:.0f}%"></span></span>
          <span class="bar-value">{t['stunden']}&nbsp;h/M</span>
        </div>""" for t in sorted(mining["touches"], key=lambda t: -t["stunden"]))

    k = mining["kpi"]
    stamp = datetime.now(timezone.utc).astimezone().strftime("%d.%m.%Y %H:%M")

    return f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Freigabe-Cockpit — Invoice-to-Approval</title>
<style>
  :root {{
    color-scheme: light;
    --surface: #fcfcfb; --card: #ffffff; --line: #e4e3df;
    --ink: #0b0b0b; --ink-2: #52514e; --ink-3: #8a897f;
    --bar: #2a78d6;
    --good: #0ca30c; --warning: #fab219; --critical: #d03b3b;
    --good-bg: #e9f6e9; --warning-bg: #fdf3dd; --critical-bg: #fbe7e7;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      color-scheme: dark;
      --surface: #1a1a19; --card: #232322; --line: #3a3936;
      --ink: #ffffff; --ink-2: #c3c2b7; --ink-3: #8a897f;
      --bar: #3987e5;
      --good-bg: #12330f; --warning-bg: #3a2e0b; --critical-bg: #3d1414;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--surface); color: var(--ink);
         font: 15px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif; }}
  main {{ max-width: 1080px; margin: 0 auto; padding: 28px 20px 60px; }}
  h1 {{ font-size: 22px; margin: 0 0 2px; }}
  h2 {{ font-size: 16px; margin: 0 0 12px; }}
  .sub {{ color: var(--ink-2); margin: 0 0 6px; }}
  .demo-hinweis {{ display: inline-block; font-size: 12px; color: var(--ink-2);
    border: 1px solid var(--line); border-radius: 999px; padding: 2px 10px; margin-bottom: 24px; }}
  .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
           gap: 12px; margin-bottom: 28px; }}
  .kpi {{ background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px; }}
  .kpi b {{ display: block; font-size: 26px; font-weight: 650; }}
  .kpi span {{ color: var(--ink-2); font-size: 13px; }}
  section {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px;
             padding: 18px 20px; margin-bottom: 20px; }}
  .filter {{ display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }}
  .filter button {{ font: inherit; font-size: 13px; padding: 4px 12px; border-radius: 999px;
    border: 1px solid var(--line); background: transparent; color: var(--ink-2); cursor: pointer; }}
  .filter button[aria-pressed="true"] {{ background: var(--ink); color: var(--surface); border-color: var(--ink); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
  th {{ text-align: left; color: var(--ink-3); font-weight: 500; font-size: 12px;
        padding: 6px 10px; border-bottom: 1px solid var(--line); }}
  td {{ padding: 9px 10px; border-bottom: 1px solid var(--line); }}
  .beleg-row {{ cursor: pointer; }}
  .beleg-row:hover td {{ background: color-mix(in oklab, var(--ink) 4%, transparent); }}
  .beleg[data-hidden] {{ display: none; }}
  .mono {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 13px; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .caret {{ color: var(--ink-3); width: 20px; }}
  .beleg-row[aria-expanded="true"] .caret {{ transform: rotate(90deg); display: inline-block; }}
  .beleg-detail td {{ background: color-mix(in oklab, var(--ink) 3%, transparent);
                      color: var(--ink-2); font-size: 13px; }}
  .detail-gruende {{ margin: 6px 0; padding-left: 18px; }}
  .detail-pfad, .detail-quelle, .detail-kommentar {{ margin: 6px 0; }}
  .chip {{ display: inline-flex; align-items: center; gap: 5px; font-size: 12.5px; font-weight: 550;
           padding: 2px 9px; border-radius: 999px; white-space: nowrap; }}
  .chip-good {{ background: var(--good-bg); color: var(--good); }}
  .chip-warning {{ background: var(--warning-bg); color: color-mix(in oklab, var(--warning) 62%, var(--ink)); }}
  .chip-critical {{ background: var(--critical-bg); color: var(--critical); }}
  .mining {{ display: grid; grid-template-columns: 1fr 1fr; gap: 28px; }}
  @media (max-width: 760px) {{ .mining {{ grid-template-columns: 1fr; }} }}
  .bar-row {{ display: grid; grid-template-columns: 190px 1fr 58px; gap: 10px;
              align-items: center; margin: 7px 0; font-size: 13px; }}
  .bar-label {{ color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .bar-track {{ background: color-mix(in oklab, var(--ink) 6%, transparent);
                border-radius: 4px; height: 14px; }}
  .bar-fill {{ display: block; height: 100%; background: var(--bar); border-radius: 4px; min-width: 2px; }}
  .bar-value {{ text-align: right; font-variant-numeric: tabular-nums; color: var(--ink-2); }}
  .befund {{ font-size: 13px; color: var(--ink-2); border-left: 3px solid var(--bar);
             padding-left: 10px; margin-top: 14px; }}
  footer {{ color: var(--ink-3); font-size: 12px; margin-top: 8px; }}
</style>
</head>
<body>
<main>
  <h1>Freigabe-Cockpit — Invoice-to-Approval</h1>
  <p class="sub">Rechnungseingang → Validierung → risk-tiered Freigabe. Pipeline: Python (POC&nbsp;02) · Regeln: DMN · Prozess: Flowable BPMN (POC&nbsp;03) · Orchestrierung: n8n (POC&nbsp;04)</p>
  <span class="demo-hinweis">Demo-Lauf mit synthetischen Belegen — keine Echtdaten</span>

  <div class="kpis">
    <div class="kpi"><b>{n}</b><span>Belege verarbeitet ({de_betrag(summe, 0)}&nbsp;€ brutto)</span></div>
    <div class="kpi"><b>{ohne_mensch}&nbsp;von&nbsp;{n}</b><span>ohne menschlichen Touch erledigt (Dunkelbuchung&nbsp;+ Dubletten-Abweisung)</span></div>
    <div class="kpi"><b>{tasks}</b><span>Freigabe-Tasks über Flowable-Queue bearbeitet</span></div>
    <div class="kpi"><b>~{k['fte'].replace('.', ',')}&nbsp;FTE</b><span>gebundene Kapazität laut Mining ({k['touch_anteil']}&nbsp;% manuelle Touches)</span></div>
  </div>

  <section>
    <h2>Belegliste mit Audit-Trail</h2>
    <div class="filter" role="group" aria-label="Nach Routing filtern">
      <button aria-pressed="true" onclick="setFilter(this,'ALLE')">Alle ({n})</button>
      <button aria-pressed="false" onclick="setFilter(this,'AUTO_POST')">✓ Auto-gebucht</button>
      <button aria-pressed="false" onclick="setFilter(this,'REVIEW')">⚠ Prüfung</button>
      <button aria-pressed="false" onclick="setFilter(this,'REJECT')">✕ Abgewiesen</button>
    </div>
    <table>
      <thead><tr>
        <th>Beleg</th><th style="text-align:right">Brutto</th><th>Pipeline-Routing</th>
        <th style="text-align:right">Risk</th><th>DMN-Stufe</th><th>Ergebnis</th><th></th>
      </tr></thead>
      {''.join(rows_html)}
    </table>
  </section>

  <section>
    <h2>Warum automatisieren? Befunde aus dem Process Mining (POC&nbsp;01)</h2>
    <div class="mining">
      <div>
        <h3 style="font-size:13.5px;color:var(--ink-2);margin:0 0 8px">Ø&nbsp;Durchlaufzeit je Prozessvariante</h3>
        {var_bars}
        <p class="befund">Abweichungsfälle laufen <strong>{k['faktor'].replace('.', ',')}× länger</strong> als der Happy&nbsp;Path — die Liegezeiten entstehen vor manuellen Klärungs- und Freigabeschritten.</p>
      </div>
      <div>
        <h3 style="font-size:13.5px;color:var(--ink-2);margin:0 0 8px">Manuelle Touches — gebundene Stunden/Monat</h3>
        {touch_bars}
        <p class="befund">Datenbasis: {k['events']}&nbsp;Events, {k['cases']}&nbsp;Vorgänge (synthetisch, Seed&nbsp;42). Top-Hebel: Rechnungserfassung (E-Rechnung/IDP) und Abweichungsklärung (Assistent&nbsp;+ HITL, POC&nbsp;05).</p>
      </div>
    </div>
  </section>

  <footer>Statisch generiert aus den POC-Outputs (01/02/03) am {stamp} · <span class="mono">build_cockpit.py</span></footer>
</main>
<script>
function toggleDetail(row) {{
  const detail = row.nextElementSibling;
  const open = detail.hasAttribute('hidden');
  detail.toggleAttribute('hidden', !open);
  row.setAttribute('aria-expanded', open);
}}
function setFilter(btn, route) {{
  document.querySelectorAll('.filter button').forEach(b => b.setAttribute('aria-pressed', b === btn));
  document.querySelectorAll('.beleg').forEach(tb => {{
    const show = route === 'ALLE' || tb.dataset.route === route;
    tb.toggleAttribute('data-hidden', !show);
  }});
}}
</script>
</body>
</html>
"""


def main():
    invoices = load_invoices()
    mining = load_mining()
    OUT.mkdir(exist_ok=True)
    out = OUT / "cockpit.html"
    out.write_text(build_html(invoices, mining))
    print(f"Cockpit -> {out}  ({len(invoices)} Belege)")


if __name__ == "__main__":
    main()
