# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""Demo-Seed für das Live-Cockpit (Stufe B).

Deployt BPMN + DMN und startet je Beleg aus POC 02 eine Prozessinstanz —
anders als poc/03-flowable/run_demo.py werden die User-Tasks NICHT
automatisch entschieden: die Queue bleibt offen, damit die Freigabe
aus dem Cockpit heraus passiert.

Ausführen:  uv run seed.py [--keep-history]
  Default räumt laufende Instanzen UND Historie des Prozesses ab
  (sauberer Demo-Start); --keep-history lässt die Historie wachsen.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parent          # .../06-cockpit/app
POC = BASE.parent.parent                        # .../poc
FLOWABLE = BASE.parent.parent / "03-flowable"
API = "http://localhost:8080/flowable-rest/service"
DMN_API = "http://localhost:8080/flowable-rest/dmn-api"
AUTH = ("rest-admin", "test")
KEY = "rechnungsfreigabe"


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
    sys.exit("Flowable-Engine nicht erreichbar — poc/03-flowable/start_engine.sh ausführen.")


def clean(keep_history: bool) -> None:
    r = requests.get(f"{API}/runtime/process-instances", auth=AUTH,
                     params={"processDefinitionKey": KEY, "size": 100})
    r.raise_for_status()
    running = r.json()["data"]
    for p in running:
        requests.delete(f"{API}/runtime/process-instances/{p['id']}",
                        auth=AUTH).raise_for_status()
    if running:
        print(f"{len(running)} laufende Instanzen entfernt.")

    if not keep_history:
        r = requests.get(f"{API}/history/historic-process-instances", auth=AUTH,
                         params={"processDefinitionKey": KEY, "size": 200})
        r.raise_for_status()
        hist = r.json()["data"]
        for p in hist:
            requests.delete(f"{API}/history/historic-process-instances/{p['id']}",
                            auth=AUTH).raise_for_status()
        if hist:
            print(f"{len(hist)} historische Instanzen entfernt.")


def deploy() -> None:
    # DMN an die DMN-Engine, BPMN an die Prozess-Engine (siehe run_demo.py:
    # ein BPMN-Deployment nimmt die .dmn-Ressource im flowable-rest-App nicht mit)
    with (FLOWABLE / "models" / "freigabestufe.dmn").open("rb") as f:
        r = requests.post(f"{DMN_API}/dmn-repository/deployments", auth=AUTH,
                          files={"file": ("freigabestufe.dmn", f, "application/xml")})
    r.raise_for_status()
    with (FLOWABLE / "models" / "rechnungsfreigabe.bpmn20.xml").open("rb") as f:
        r = requests.post(f"{API}/repository/deployments", auth=AUTH,
                          files={"file": ("rechnungsfreigabe.bpmn20.xml", f,
                                          "application/xml")})
    r.raise_for_status()
    print("BPMN + DMN deployed.")


def start_instances() -> None:
    results = json.loads(
        (POC / "02-invoice-pipeline" / "output" / "results.json").read_text())
    for d in results:
        payload = {
            "processDefinitionKey": KEY,
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
        print(f"  Instanz: {d['invoice_number']} ({d['source_file']}, {d['route']})")

    time.sleep(2)  # DMN + Gateways laufen synchron kurz nach
    r = requests.get(f"{API}/runtime/tasks", auth=AUTH,
                     params={"processDefinitionKey": KEY, "size": 100})
    open_tasks = r.json()["total"]
    print(f"\nSeed fertig: {len(results)} Instanzen, {open_tasks} offene Freigabe-Tasks "
          f"({len(results) - open_tasks} ohne menschlichen Touch durchgelaufen).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep-history", action="store_true",
                    help="Historie nicht abräumen (Audit wächst über Seeds hinweg)")
    args = ap.parse_args()
    wait_for_engine()
    clean(args.keep_history)
    deploy()
    start_instances()
