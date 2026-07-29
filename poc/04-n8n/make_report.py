"""Report des n8n-Laufs: gestartete Instanzen + Zustand der Flowable-Queue."""

import json
from pathlib import Path

import requests

BASE = Path(__file__).parent
API = "http://localhost:8080/flowable-rest/service"
AUTH = ("rest-admin", "test")


def main() -> None:
    raw = (BASE / "output" / "execution.json").read_text()
    # n8n schreibt Runner-/Broker-Logzeilen vor das JSON — ab erster '{'-Zeile parsen
    execution = json.loads(raw[raw.index("\n{") + 1:])
    # rawOutput: {"data": {"resultData": {"runData": {"<node>": [...]}}}}
    run_data = execution["data"]["resultData"]["runData"]
    summary = run_data["Ergebnis zusammenfassen"][0]["data"]["main"][0]

    lines = ["# n8n-Demo — Orchestrierung Invoice-to-Approval", "",
             "n8n hat headless die Invoice-Pipeline (POC 02) ausgeführt und je Beleg "
             "eine Prozessinstanz im Flowable-Freigabe-Workflow (POC 03) gestartet.", "",
             "## Vom Workflow gestartete Prozessinstanzen", "",
             "| Rechnung | Flowable-Instanz | Sofort beendet |", "|---|---|---|"]
    for item in summary:
        j = item["json"]
        ended = "ja (AUTO/REJECT-Pfad)" if j["beendet"] else "nein (wartet auf Freigabe)"
        lines.append(f"| {j['rechnung']} | `{j['prozessInstanz'][:8]}…` | {ended} |")

    tasks = requests.get(f"{API}/runtime/tasks", auth=AUTH,
                         params={"processDefinitionKey": "rechnungsfreigabe",
                                 "size": 50}).json()["data"]
    lines += ["", f"## Offene Freigabe-Tasks in Flowable: {len(tasks)}", ""]
    for t in tasks:
        pv = requests.get(f"{API}/runtime/process-instances/{t['processInstanceId']}"
                          f"/variables", auth=AUTH).json()
        v = {x["name"]: x["value"] for x in pv}
        lines.append(f"- {v.get('rechnung')} — Stufe {v.get('stufe')} "
                     f"(Beleg {v.get('beleg')})")

    lines += ["", "Die Tasks warten jetzt in der Flowable-Queue auf Sachbearbeitung/"
              "Teamleitung — Bearbeitung wie in POC 03 demonstriert. n8n ist dabei "
              "reine Orchestrierung: keine Fachlogik, keine Freigabeentscheidung — "
              "die liegen in Pipeline (Python) und Prozess-Engine (BPMN/DMN)."]
    (BASE / "output" / "report.md").write_text("\n".join(lines))
    print(f"Report -> {BASE/'output'/'report.md'}")


if __name__ == "__main__":
    main()
