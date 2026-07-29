# /// script
# requires-python = ">=3.11"
# dependencies = ["fastapi", "uvicorn", "requests"]
# ///
"""Freigabe-Cockpit Stufe B — FastAPI-Proxy vor der Flowable-REST-Engine.

Aufgaben des Proxys:
  - hält die Flowable-Credentials aus dem Frontend (Basic Auth nur serverseitig)
  - reichert Flowable-Tasks um die Beleg-Daten aus POC 02 an (Join über source_file,
    weil Belegnummern durch den Dubletten-Fall nicht eindeutig sind)
  - liefert das Frontend als Same-Origin-Static-Files aus (kein CORS nötig)

Endpunkte:
  GET  /api/health                   Engine-Status + Queue-Größe
  GET  /api/queue                    offene Freigabe-Tasks, angereichert
  POST /api/tasks/{task_id}/complete freigeben/ablehnen mit Kommentar
  GET  /api/history                  alle Instanzen (laufend + beendet) mit Audit-Pfad
  GET  /api/mining                   Kennzahlen aus dem Process-Mining-Report (POC 01)

Ausführen:  uv run server.py   →  http://localhost:8000
"""

import json
import os
import re
from pathlib import Path

import requests
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
POC = BASE.parent.parent
API = os.environ.get("FLOWABLE_API", "http://localhost:8080/flowable-rest/service")
AUTH = (os.environ.get("FLOWABLE_USER", "rest-admin"),
        os.environ.get("FLOWABLE_PASSWORD", "test"))
KEY = "rechnungsfreigabe"

app = FastAPI(title="Freigabe-Cockpit Proxy")


# ── Beleg-Daten aus POC 02 (Join-Schlüssel: source_file) ───────────────────

def load_invoices() -> dict[str, dict]:
    rows = json.loads((POC / "02-invoice-pipeline/output/results.json").read_text())
    return {r["source_file"]: r for r in rows}


INVOICES = load_invoices()


def flowable(method: str, path: str, **kw):
    """Flowable-Call mit sauberem Fehlerbild Richtung Frontend."""
    try:
        r = requests.request(method, f"{API}{path}", auth=AUTH, timeout=10, **kw)
    except requests.ConnectionError:
        raise HTTPException(502, "Flowable-Engine nicht erreichbar — "
                                 "poc/03-flowable/start_engine.sh ausführen, dann seed.py.")
    if r.status_code == 404:
        raise HTTPException(409, "Objekt existiert nicht (mehr) — Queue neu laden.")
    if not r.ok:
        raise HTTPException(502, f"Flowable antwortet {r.status_code}: {r.text[:200]}")
    return r


def variables_of(pid: str, historic: bool = False) -> dict:
    if historic:
        data = flowable("GET", "/history/historic-variable-instances",
                        params={"processInstanceId": pid, "size": 50}).json()["data"]
        return {x["variable"]["name"]: x["variable"]["value"] for x in data}
    data = flowable("GET", f"/runtime/process-instances/{pid}/variables").json()
    return {x["name"]: x["value"] for x in data}


def enrich(v: dict) -> dict:
    """Prozessvariablen + Beleg-Daten aus POC 02 zu einem Frontend-Objekt mischen."""
    inv = INVOICES.get(v.get("beleg"), {})
    return {
        "rechnung": v.get("rechnung"),
        "beleg": v.get("beleg"),
        "brutto": v.get("brutto"),
        "waehrung": inv.get("currency", "EUR"),
        "route": v.get("route"),
        "riskScore": v.get("riskScore"),
        "stufe": v.get("stufe"),
        "gruende": inv.get("reasons", []),
        "findings": inv.get("findings", []),
    }


# ── Endpunkte ──────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    try:
        tasks = flowable("GET", "/runtime/tasks",
                         params={"processDefinitionKey": KEY, "size": 1}).json()
        return {"engine": "ok", "offeneTasks": tasks["total"]}
    except HTTPException as e:
        return {"engine": "down", "detail": e.detail}


@app.get("/api/queue")
def queue():
    tasks = flowable("GET", "/runtime/tasks",
                     params={"processDefinitionKey": KEY, "size": 100,
                             "order": "asc", "sort": "createTime"}).json()["data"]
    out = []
    for t in tasks:
        v = variables_of(t["processInstanceId"])
        out.append({
            "taskId": t["id"],
            "taskName": t["name"],
            "erstellt": t["createTime"],
            "rolle": "t.lead" if v.get("stufe") == "TEAMLEITUNG" else "s.bearb",
            **enrich(v),
        })
    return out


class Decision(BaseModel):
    approved: bool
    comment: str = Field(default="", max_length=500)


@app.post("/api/tasks/{task_id}/complete")
def complete(task_id: str, d: Decision):
    comment = d.comment.strip()
    if not d.approved and not comment:
        raise HTTPException(400, "Ablehnung braucht einen Kommentar (Audit-Pflicht).")
    task = flowable("GET", f"/runtime/tasks/{task_id}").json()
    v = variables_of(task["processInstanceId"])
    user = "t.lead" if v.get("stufe") == "TEAMLEITUNG" else "s.bearb"
    flowable("POST", f"/runtime/tasks/{task_id}", json={
        "action": "complete",
        "variables": [
            {"name": "freigegeben", "type": "boolean", "value": d.approved},
            {"name": "kommentar", "type": "string",
             "value": comment or "Freigabe ohne Kommentar"},
            {"name": "entschiedenVon", "type": "string", "value": user},
        ]})
    return {"ok": True, "rechnung": v.get("rechnung"), "entschiedenVon": user,
            "freigegeben": d.approved}


# Topologischer Rang als Tie-Breaker (Zeitstempel haben Sekunden-Auflösung),
# übernommen aus poc/03-flowable/run_demo.py
ORDER = {"start": 0, "ermittleStufe": 1, "gwStufe": 2, "pruefen": 3,
         "gwEntscheid": 4, "buchen": 5, "endGebucht": 6, "endAbgelehnt": 6}


@app.get("/api/history")
def history():
    procs = flowable("GET", "/history/historic-process-instances",
                     params={"processDefinitionKey": KEY, "size": 200,
                             "order": "asc", "sort": "startTime"}).json()["data"]
    out = []
    for p in procs:
        v = variables_of(p["id"], historic=True)
        acts = flowable("GET", "/history/historic-activity-instances",
                        params={"processInstanceId": p["id"], "size": 50}).json()["data"]
        acts.sort(key=lambda a: (a["startTime"], ORDER.get(a["activityId"], 99)))
        pfad = [{"schritt": a.get("activityName") or a["activityId"],
                 "typ": a["activityType"], "start": a["startTime"],
                 "ende": a.get("endTime"), "bearbeiter": a.get("assignee")}
                for a in acts if a["activityType"] != "sequenceFlow"]
        status = ("gebucht" if v.get("gebucht")
                  else "abgelehnt" if v.get("stufe") == "ABGELEHNT"
                  or v.get("freigegeben") is False
                  else "offen" if p.get("endTime") is None else "beendet")
        out.append({
            "status": status,
            "gestartet": p["startTime"],
            "beendet": p.get("endTime"),
            "entschiedenVon": v.get("entschiedenVon"),
            "kommentar": v.get("kommentar"),
            "pfad": pfad,
            **enrich(v),
        })
    return out


@app.get("/api/mining")
def mining():
    """Kennzahlen aus dem committeten Mining-Report (POC 01) — Parser wie in
    build_cockpit.py, damit beide Cockpit-Stufen dieselben Zahlen zeigen."""
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
        "touchAnteil": re.search(r"\((\d+)% aller Events\)", text).group(1),
        "fte": re.search(r"\*\*~([\d.]+) FTE\*\*", text).group(1),
    }
    if not varianten or not touches:
        raise HTTPException(500, "Mining-Report nicht parsebar — POC 01 report.md prüfen.")
    return {"varianten": varianten, "touches": touches, "kpi": kpi}


app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
