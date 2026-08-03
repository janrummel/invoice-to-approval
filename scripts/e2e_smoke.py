# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""End-to-End-Smoke: seed -> Queue -> eine Entscheidung -> Historie -> re-seed.

Exit-Codes: 0 ok · 1 Verhalten falsch · 2 Engine nicht erreichbar.
Aufruf:  uv run scripts/e2e_smoke.py   (Engine vorher starten, s. Checkliste)
"""

import subprocess
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
APP = REPO / "poc" / "06-cockpit" / "app"
API = "http://localhost:8080/flowable-rest/service"
AUTH = ("rest-admin", "test")
KEY = "rechnungsfreigabe"


def fail(msg):
    print(f"SMOKE FAIL: {msg}")
    sys.exit(1)


def offene_tasks():
    r = requests.get(f"{API}/runtime/tasks", auth=AUTH,
                     params={"processDefinitionKey": KEY, "size": 100}, timeout=10)
    r.raise_for_status()
    return r.json()["data"]


def main():
    try:
        requests.get(f"{API}/repository/deployments", auth=AUTH, timeout=5)
    except requests.ConnectionError:
        print("SMOKE SKIP: Engine nicht erreichbar — poc/03-flowable/start_engine.sh")
        sys.exit(2)

    seed = subprocess.run(["uv", "run", "seed.py"], cwd=APP)
    if seed.returncode != 0:
        fail("seed.py fehlgeschlagen")

    tasks = offene_tasks()
    if len(tasks) != 5:
        fail(f"erwartet 5 offene Tasks nach Seed, gefunden {len(tasks)}")

    task = tasks[0]
    r = requests.post(f"{API}/runtime/tasks/{task['id']}", auth=AUTH, json={
        "action": "complete",
        "variables": [
            {"name": "freigegeben", "type": "boolean", "value": True},
            {"name": "kommentar", "type": "string", "value": "E2E-Smoke"},
            {"name": "entschiedenVon", "type": "string", "value": "smoke"},
        ]}, timeout=10)
    if not r.ok:
        fail(f"Task-Complete antwortet {r.status_code}")

    if len(offene_tasks()) != 4:
        fail("Task ist nach Entscheidung nicht aus der Queue verschwunden")

    hv = requests.get(f"{API}/history/historic-variable-instances", auth=AUTH,
                      params={"processInstanceId": task["processInstanceId"],
                              "size": 50}, timeout=10).json()["data"]
    v = {x["variable"]["name"]: x["variable"]["value"] for x in hv}
    if v.get("kommentar") != "E2E-Smoke" or not v.get("gebucht"):
        fail(f"Historie unvollständig: {v}")

    subprocess.run(["uv", "run", "seed.py"], cwd=APP, check=True)
    print("SMOKE OK: seed -> queue(5) -> complete -> queue(4) -> Historie -> re-seed")
    sys.exit(0)


if __name__ == "__main__":
    main()
