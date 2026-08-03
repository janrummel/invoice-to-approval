# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown", "pygments"]
# ///
"""Erzeugt die Lern-Seiten (Markdown+Mermaid -> HTML) mit gemeinsamer Navigation.

- Markdown -> HTML (tables, fenced code, md_in_html, codehilite/Pygments)
- ```mermaid-Blöcke -> <pre class="mermaid"> (Renderer: gemeinsame
  docs/mermaid.min.js — Seiten bleiben offline lesbar, solange die Datei
  daneben liegt)
- Links auf .md werden auf .html umgeschrieben (GitHub rendert die .md,
  lokal klickt man durch die .html)
- Sticky-Navigationsleiste über alle Seiten; aktuelle Seite markiert
- Light/Dark folgt dem System; Druck-CSS

Aufruf: uv run tools/build_walkthrough_html.py <mermaid.min.js> [quell.md|--all]
        --all baut alle Seiten aus PAGES (Default: docs/poc-walkthrough.md)
"""

import re
import shutil
import sys
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"

# Reihenfolge = Navigationsleiste. (Dateistamm, Anzeigename)
PAGES = [
    ("poc-walkthrough", "POC-Walkthrough"),
    ("skript-atlas", "Skript-Atlas"),
    ("atlas-parsers", "parsers.py"),
    ("atlas-validation", "validation.py"),
    ("atlas-routing", "routing.py"),
    ("atlas-run", "run.py"),
    ("atlas-belegflut", "belegflut.py"),
    ("atlas-e2e-smoke", "e2e_smoke.py"),
]

PYG_LIGHT = HtmlFormatter(style="default").get_style_defs(".codehilite")
PYG_DARK = HtmlFormatter(style="monokai").get_style_defs(".codehilite")


def nav_html(current_stem: str) -> str:
    links = []
    for stem, label in PAGES:
        cls = ' class="active"' if stem == current_stem else ""
        links.append(f'<a href="{stem}.html"{cls}>{label}</a>')
        if stem == "skript-atlas":
            links.append('<span class="sep" aria-hidden="true">·</span>')
    return ('<nav class="topnav"><div class="inner">'
            '<span class="brand">Invoice-to-Approval · Lernseiten</span>'
            + "".join(links) + "</div></nav>")


def build(src: Path) -> None:
    md = src.read_text()
    m = re.match(r"# (.+)", md)
    title = m.group(1).strip() if m else src.stem

    # <details>-Inhalte als Markdown behandeln
    md = md.replace("<details>", '<details markdown="1">')

    # Python-Markdown braucht (anders als GitHub) eine Leerzeile vor Listen
    lines, fixed = md.splitlines(), []
    for line in lines:
        if (line.startswith("- ") and fixed and fixed[-1].strip()
                and not fixed[-1].startswith(("- ", "  "))):
            fixed.append("")
        fixed.append(line)
    md = "\n".join(fixed)

    # Mermaid-Blöcke VOR der Konvertierung ausparken (codehilite würde sie
    # sonst als Code einfärben) und danach wieder einsetzen
    mermaids: list[str] = []

    def _stash(match):
        mermaids.append(match.group(1))
        return f"MERMAIDBLOCK{len(mermaids) - 1}ENDBLOCK"

    md = re.sub(r"```mermaid\n(.*?)```", _stash, md, flags=re.S)

    body = markdown.markdown(
        md,
        extensions=["tables", "fenced_code", "md_in_html", "sane_lists",
                    "codehilite"],
        extension_configs={"codehilite": {"guess_lang": False}})

    for i, code in enumerate(mermaids):
        token = f"MERMAIDBLOCK{i}ENDBLOCK"
        block = f'<pre class="mermaid">{code}</pre>'
        body = body.replace(f"<p>{token}</p>", block).replace(token, block)

    # Lokale .md-Links -> .html (Anker bleiben erhalten)
    body = re.sub(r'href="([a-zA-Z0-9\-]+)\.md(#[^"]*)?"',
                  r'href="\1.html\2"', body)

    html = f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta property="og:title" content="{title}">
<meta property="og:description" content="Invoice-to-Approval: sechs verzahnte POCs für Rechnungsautomatisierung (Process Mining, E-Rechnung, BPMN/DMN, n8n, LLM mit Human-in-the-Loop), als selbst-erklärendes Lern-Portal.">
<meta property="og:type" content="website">
<meta name="twitter:card" content="summary">
<style>
  :root {{
    color-scheme: light dark;
    --surface: #fcfcfb; --card: #ffffff; --line: #e4e3df;
    --ink: #1b1b1a; --ink-2: #52514e; --ink-3: #8a897f; --accent: #2a78d6;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --surface: #1a1a19; --card: #232322; --line: #3a3936;
             --ink: #f2f1ec; --ink-2: #c3c2b7; --ink-3: #8a897f; --accent: #3987e5; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--surface); color: var(--ink);
         font: 16px/1.65 -apple-system, "Segoe UI", Roboto, sans-serif; }}
  .topnav {{ position: sticky; top: 0; z-index: 10; background: var(--surface);
    border-bottom: 1px solid var(--line); font-size: 13.5px; }}
  .topnav .inner {{ max-width: 1220px; margin: 0 auto; padding: 9px 24px;
    display: flex; gap: 4px 10px; flex-wrap: wrap; align-items: center; }}
  .topnav .brand {{ font-weight: 650; color: var(--ink); margin-right: 10px; }}
  .topnav a {{ color: var(--ink-2); text-decoration: none; padding: 2px 9px;
    border-radius: 999px; }}
  .topnav a:hover {{ background: color-mix(in oklab, var(--ink) 6%, transparent); }}
  .topnav a.active {{ color: var(--accent); font-weight: 650;
    background: color-mix(in oklab, var(--accent) 12%, transparent); }}
  .topnav .sep {{ color: var(--ink-3); }}
  main {{ max-width: 880px; margin: 0 auto; padding: 40px 24px 80px; }}
  h1 {{ font-size: 28px; line-height: 1.25; margin: 0 0 10px; }}
  h2 {{ font-size: 21px; margin: 2.2em 0 .6em; padding-top: .6em;
        border-top: 1px solid var(--line); }}
  h1 + p, h2 + p {{ margin-top: 0; }}
  strong {{ font-weight: 650; }}
  hr {{ border: 0; border-top: 1px solid var(--line); margin: 2em 0; }}
  a {{ color: var(--accent); }}
  code {{ font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: .88em;
         background: color-mix(in oklab, var(--ink) 7%, transparent);
         padding: 1px 5px; border-radius: 5px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 14.5px; }}
  th {{ text-align: left; color: var(--ink-3); font-weight: 550; font-size: 12.5px; }}
  th, td {{ padding: 7px 10px; border-bottom: 1px solid var(--line); vertical-align: top; }}
  pre.mermaid {{ background: var(--card); border: 1px solid var(--line);
    border-radius: 12px; padding: 18px; text-align: center; overflow-x: auto; }}
  pre.mermaid svg {{ max-width: none; }} /* nicht herunterskalieren — Schrift bleibt lesbar */
  /* Syntax-Highlighting (Pygments) — hell/dunkel getrennt */
  {PYG_LIGHT}
  @media (prefers-color-scheme: dark) {{ {PYG_DARK} }}
  .codehilite {{ border: 1px solid var(--line); border-radius: 10px;
    overflow-x: auto; margin: 0 0 8px; }}
  .codehilite pre {{ margin: 0; padding: 12px 16px;
    font: 13px/1.55 ui-monospace, "SF Mono", Menlo, monospace; }}
  .codehilite code {{ background: transparent; padding: 0; }} /* Inline-code-Stil neutralisieren */
  /* Farb-Labels: verbinden Code-Abschnitte mit den Diagramm-Blöcken */
  .codeblock-label {{ display: inline-block; font-size: 12.5px; font-weight: 600;
    padding: 3px 12px; margin: 16px 0 0; border-radius: 8px 8px 0 0;
    background: color-mix(in oklab, var(--ink) 6%, transparent);
    color: var(--ink-2); border-left: 4px solid var(--ink-3); }}
  .codeblock-label + .codehilite {{ border-top-left-radius: 0; }}
  .codeblock-label[data-tone="blau"] {{ border-left-color: #2a78d6; }}
  .codeblock-label[data-tone="rot"] {{ border-left-color: #d03b3b; }}
  .codeblock-label[data-tone="gelb"] {{ border-left-color: #fab219; }}
  .codeblock-label[data-tone="gruen"] {{ border-left-color: #0ca30c; }}
  .codeblock-label[data-tone="blau"] + .codehilite {{ border-left: 4px solid #2a78d6; }}
  .codeblock-label[data-tone="rot"] + .codehilite {{ border-left: 4px solid #d03b3b; }}
  .codeblock-label[data-tone="gelb"] + .codehilite {{ border-left: 4px solid #fab219; }}
  .codeblock-label[data-tone="gruen"] + .codehilite {{ border-left: 4px solid #0ca30c; }}
  /* Zweispaltige Code-Ansicht: Code links, Erklärnotizen rechts daneben.
     Bricht aus der Textspalte aus (breiter als main), damit der Code Platz hat. */
  .code-row {{ display: grid; grid-template-columns: minmax(0, 1fr) 320px;
    gap: 0 20px; align-items: start; margin: 16px 0 8px;
    width: min(1220px, calc(100vw - 48px));
    position: relative; left: 50%; transform: translateX(-50%); }}
  .code-row .codeblock-label {{ margin-top: 0; }}
  .code-notes {{ font-size: 13.5px; color: var(--ink-2); line-height: 1.55;
    padding: 30px 0 0 14px; border-left: 1px solid var(--line); }}
  .code-notes ul {{ margin: 0; padding-left: 16px; }}
  .code-notes li {{ margin: 0 0 9px; }}
  .code-notes code {{ font-size: .85em; }}
  @media (max-width: 1000px) {{
    .code-row {{ grid-template-columns: 1fr; width: auto; left: 0; transform: none; }}
    .code-notes {{ padding: 6px 0 0; border-left: 0; }}
  }}
  details {{ background: var(--card); border: 1px solid var(--line);
    border-radius: 10px; padding: 10px 16px; margin: 10px 0; }}
  details summary {{ cursor: pointer; font-weight: 550; }}
  details[open] summary {{ margin-bottom: 6px; color: var(--accent); }}
  blockquote {{ border-left: 3px solid var(--accent); margin: 1em 0;
    padding: 2px 0 2px 14px; color: var(--ink-2); }}
  li {{ margin: .25em 0; }}
  @media print {{
    body {{ background: #fff; color: #000; font-size: 12px; }}
    .topnav {{ display: none; }}
    .code-row {{ width: auto; left: 0; transform: none; }}
    details {{ break-inside: avoid; }} details:not([open]) summary ~ * {{ display: block; }}
    pre.mermaid {{ break-inside: avoid; border: 1px solid #ccc; }}
    h2 {{ break-after: avoid; }}
  }}
</style>
</head>
<body>
{nav_html(src.stem)}
<main>
{body}
</main>
<script src="mermaid.min.js"></script>
<script>
  mermaid.initialize({{
    startOnLoad: true,
    securityLevel: "loose",  /* erlaubt click-Links in Diagrammen */
    theme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "neutral",
    themeVariables: {{ fontSize: "16px",
      fontFamily: '-apple-system, "Segoe UI", Roboto, sans-serif' }},
    flowchart: {{ htmlLabels: true, curve: "basis", useMaxWidth: false }}
  }});
</script>
</body>
</html>
"""
    out = src.with_suffix(".html")
    out.write_text(html)
    print(f"{out} ({len(html) // 1024} KB)")


def main() -> None:
    mermaid_src = Path(sys.argv[1])
    target = DOCS / "mermaid.min.js"
    if not target.exists() or target.stat().st_size != mermaid_src.stat().st_size:
        shutil.copy(mermaid_src, target)
        print(f"{target} aktualisiert")

    arg = sys.argv[2] if len(sys.argv) > 2 else None
    if arg == "--all":
        for stem, _ in PAGES:
            src = DOCS / f"{stem}.md"
            if src.exists():
                build(src)
            else:
                print(f"WARN: {src} fehlt — übersprungen")
    else:
        build(Path(arg).resolve() if arg else DOCS / "poc-walkthrough.md")


if __name__ == "__main__":
    main()


# Aufruf-Beispiele:
#   curl -sL https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js -o /tmp/mermaid.min.js
#   uv run tools/build_walkthrough_html.py /tmp/mermaid.min.js --all
