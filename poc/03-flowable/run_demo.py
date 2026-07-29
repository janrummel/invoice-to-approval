"""End-to-End-Demo: POC-02-Ergebnisse durch den Flowable-Freigabe-Workflow treiben.

Voraussetzung: laufende Flowable-REST-Engine (siehe README / start_engine.sh).

Ablauf:
  1. BPMN + DMN als ZIP-Deployment hochladen
  2. Je Beleg aus ../02-invoice-pipeline/output/results.json eine Prozessinstanz
     starten (Variablen: route, riskScore, brutto, rechnung)
  3. Offene User-Tasks abrufen und als Sachbearbeiter/Teamleitung entscheiden
     (Demo-Entscheidungen mit realistischen Kommentaren)
  4. Historie auslesen -> output/report.md (Audit-Trail je Rechnung)
"""

import json
import time
from pathlib import Path

import requests

BASE = Path(__file__).parent
API = "http://localhost:8080/flowable-rest/service"
DMN_API = "http://localhost:8080/flowable-rest/dmn-api"
AUTH = ("rest-admin", "test")

# Demo-Entscheidungen der Prüfer je Rechnung (Task-Outcome für REVIEW-Fälle)
DECISIONS = {
    "BL-77113":     (False, "Summenfehler bestätigt — Korrekturrechnung beim Lieferanten angefordert"),
    "GIT-2026-442": (False, "IBAN-Änderung telefonisch NICHT bestätigt — Verdacht auf Betrug, Fall an Compliance"),
    "DA-10077":     (True,  "Bestellung und Wareneingang geprüft — Freigabe Großbetrag erteilt"),
    "OC-889":       (True,  "Beleg manuell geprüft, Lieferant neu angelegt — Felder korrekt extrahiert"),
    "RE-2026-0900": (True,  "Preisabweichung mit dem Einkauf geklärt — Nachtrag zur Bestellung PO-4761 liegt vor"),
}


def wait_for_engine(timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{API}/repository/deployments", auth=AUTH, timeout=3)
            if r.status_code == 200:
                print("Engine erreichbar.")
                return
        except requests.ConnectionError:
            pass
        time.sleep(3)
    raise TimeoutError("Flowable-Engine nicht erreichbar")


def deploy() -> None:
    # DMN zuerst an die DMN-Engine (eigene API — ein BPMN-Deployment nimmt die
    # .dmn-Ressource im flowable-rest-App nicht mit); der DMN-Task im Prozess
    # findet die Decision dann über den Fallback ohne Parent-Deployment.
    with (BASE / "models" / "freigabestufe.dmn").open("rb") as f:
        r = requests.post(f"{DMN_API}/dmn-repository/deployments", auth=AUTH,
                          files={"file": ("freigabestufe.dmn", f, "application/xml")})
    r.raise_for_status()
    print(f"DMN-Deployment ok: {r.json()['id']}")

    with (BASE / "models" / "rechnungsfreigabe.bpmn20.xml").open("rb") as f:
        r = requests.post(f"{API}/repository/deployments", auth=AUTH,
                          files={"file": ("rechnungsfreigabe.bpmn20.xml", f,
                                          "application/xml")})
    r.raise_for_status()
    print(f"BPMN-Deployment ok: {r.json()['id']}")


def start_instances() -> dict[str, str]:
    results = json.loads(
        (BASE.parent / "02-invoice-pipeline" / "output" / "results.json").read_text())
    instances = {}
    for d in results:
        payload = {
            "processDefinitionKey": "rechnungsfreigabe",
            "businessKey": d["invoice_number"],
            "variables": [
                {"name": "route", "type": "string", "value": d["route"]},
                {"name": "riskScore", "type": "integer", "value": d["risk_score"]},
                {"name": "brutto", "type": "double", "value": float(d["total_gross"])},
                {"name": "rechnung", "type": "string", "value": d["invoice_number"]},
                {"name": "beleg", "type": "string", "value": d["source_file"]},
            ],
        }
        r = requests.post(f"{API}/runtime/process-instances", auth=AUTH, json=payload)
        r.raise_for_status()
        instances[r.json()["id"]] = d["invoice_number"]
        print(f"Instanz gestartet: {d['invoice_number']} ({d['source_file']})")
    return instances


def work_tasks() -> None:
    r = requests.get(f"{API}/runtime/tasks", auth=AUTH,
                     params={"processDefinitionKey": "rechnungsfreigabe", "size": 50})
    r.raise_for_status()
    tasks = r.json()["data"]
    print(f"\n{len(tasks)} offene Freigabe-Tasks:")
    for t in tasks:
        # Prozessvariablen der Instanz holen (Rechnungsnummer, Stufe)
        pv = requests.get(f"{API}/runtime/process-instances/{t['processInstanceId']}"
                          f"/variables", auth=AUTH).json()
        v = {x["name"]: x["value"] for x in pv}
        num, stufe = v.get("rechnung"), v.get("stufe")
        approved, comment = DECISIONS.get(num, (True, "Standardfreigabe"))
        user = "t.lead" if stufe == "TEAMLEITUNG" else "s.bearb"
        requests.post(f"{API}/runtime/tasks/{t['id']}", auth=AUTH, json={
            "action": "complete",
            "variables": [
                {"name": "freigegeben", "type": "boolean", "value": approved},
                {"name": "kommentar", "type": "string", "value": comment},
                {"name": "entschiedenVon", "type": "string", "value": user},
            ]}).raise_for_status()
        print(f"  {num} [{stufe} -> {user}]: "
              f"{'freigegeben' if approved else 'abgelehnt'} — {comment}")


# Topologischer Rang als Tie-Breaker (Zeitstempel haben Sekunden-Auflösung)
ORDER = {"start": 0, "ermittleStufe": 1, "gwStufe": 2, "pruefen": 3,
         "gwEntscheid": 4, "buchen": 5, "endGebucht": 6, "endAbgelehnt": 6}


def report(instances: dict[str, str]) -> None:
    out = BASE / "output"
    out.mkdir(exist_ok=True)
    rows, paths = [], []
    for pid, num in instances.items():
        hv = requests.get(f"{API}/history/historic-variable-instances", auth=AUTH,
                          params={"processInstanceId": pid, "size": 50}).json()["data"]
        v = {x["variable"]["name"]: x["variable"]["value"] for x in hv}
        outcome = ("🟢 gebucht" if v.get("gebucht")
                   else "🔴 abgelehnt" if v.get("stufe") == "ABGELEHNT"
                   or v.get("freigegeben") is False else "läuft")
        rows.append(f"| {num} | {v.get('stufe','—')} | {v.get('entschiedenVon','—')} "
                    f"| {outcome} | {v.get('kommentar','—')} |")

        acts = requests.get(f"{API}/history/historic-activity-instances", auth=AUTH,
                            params={"processInstanceId": pid, "size": 50}).json()["data"]
        acts.sort(key=lambda a: (a["startTime"], ORDER.get(a["activityId"], 99)))
        path = " → ".join(a.get("activityName") or a["activityId"]
                          for a in acts if a["activityType"] != "sequenceFlow")
        paths.append(f"- **{num}:** `{path}`")

    lines = (["# Flowable-Demo — Audit-Trail des Freigabe-Workflows", "",
              "| Rechnung | DMN-Stufe | Entscheider | Ergebnis | Kommentar |",
              "|---|---|---|---|---|"] + rows
             + ["", "## Durchlaufene Pfade", ""] + paths
             + ["", "Jeder Schritt (inkl. DMN-Ausführung, Bearbeiter, Zeitstempel) liegt "
                "in der Flowable-Historie — das ist der IKS-taugliche Audit-Trail, "
                "den Skript-Automatisierung allein nicht liefert."])
    (out / "report.md").write_text("\n".join(lines))
    print(f"\nReport -> {out/'report.md'}")


def diagram() -> None:
    r = requests.get(f"{API}/repository/process-definitions", auth=AUTH,
                     params={"key": "rechnungsfreigabe", "latest": "true"})
    pd = r.json()["data"][0]
    img = requests.get(f"{API}/repository/process-definitions/{pd['id']}/image",
                       auth=AUTH)
    if img.status_code == 200:
        (BASE / "output" / "process-diagram.png").write_bytes(img.content)
        print("Prozessdiagramm gespeichert.")


if __name__ == "__main__":
    wait_for_engine()
    deploy()
    instances = start_instances()
    time.sleep(2)          # DMN + Gateways laufen synchron, kurz warten schadet nicht
    work_tasks()
    time.sleep(1)
    report(instances)
    diagram()
