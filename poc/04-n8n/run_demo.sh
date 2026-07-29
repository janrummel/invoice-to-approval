#!/usr/bin/env bash
# End-to-End-Orchestrierung: n8n fuehrt Pipeline (POC 02) aus und startet je
# Beleg den Flowable-Freigabeprozess (POC 03). Headless via n8n-CLI.
#
# Voraussetzungen: npm i -g n8n; laufende Flowable-Engine (POC 03/start_engine.sh)
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
# Repo-Basis zur Laufzeit ermittelt, keine hartkodierten Pfade.
# Case-Kanonisierung noetig: macOS-Dateisysteme sind case-insensitiv, n8ns
# N8N_RESTRICT_FILE_ACCESS_TO vergleicht aber case-sensitiv gegen den echten Pfad.
BASE="$(python3 - "$DIR/../.." <<'PYEOF'
import os, sys
p = os.path.realpath(sys.argv[1])
out = "/"
for seg in p.strip("/").split("/"):
    try:
        names = os.listdir(out)
        seg = next((n for n in names if n.lower() == seg.lower()), seg)
    except (PermissionError, FileNotFoundError):
        pass
    out = os.path.join(out, seg)
print(out)
PYEOF
)"
export N8N_USER_FOLDER="${N8N_USER_FOLDER:-${TMPDIR:-/tmp}/n8n-demo}"
export N8N_DIAGNOSTICS_ENABLED=false
# Hinweis: DB_SQLITE_POOL_SIZE nicht setzen — erzwingt den Legacy-sqlite3-Treiber,
# der bei npm-Standardinstallation fehlt; Default (better-sqlite3) ist gebündelt.
# n8n >= 2.x Security-Defaults: Execute Command ist ausgeschlossen und
# Dateizugriff auf ~/.n8n-files beschraenkt — fuer diese Self-Hosted-Demo
# bewusst und explizit freigeschaltet (gutes Governance-Beispiel):
export NODES_EXCLUDE="[]"
export N8N_RESTRICT_FILE_ACCESS_TO="$BASE"

echo "== 1/4 Flowable-Modelle deployen (frische Engine vorausgesetzt) =="
python3 - "$BASE/poc/03-flowable" <<'EOF'
import sys
sys.path.insert(0, sys.argv[1])
from run_demo import wait_for_engine, deploy
wait_for_engine()
deploy()
EOF

echo "== 2/4 Workflow importieren (Platzhalter __POC_BASE__ -> lokaler Pfad) =="
WF_TMP="${TMPDIR:-/tmp}/invoice-to-approval.resolved.json"
sed "s|__POC_BASE__|$BASE|g" "$DIR/workflows/invoice-to-approval.json" > "$WF_TMP"
n8n import:workflow --input="$WF_TMP" 2>/dev/null

WF_ID=$(n8n list:workflow 2>/dev/null | grep "invoice-to-approval" | cut -d'|' -f1 | tail -1)
echo "Workflow-ID: $WF_ID"

echo "== 3/4 Workflow headless ausfuehren =="
mkdir -p "$DIR/output"
n8n execute --id="$WF_ID" --rawOutput > "$DIR/output/execution.json" 2>"$DIR/output/execution.log" \
  || { cat "$DIR/output/execution.log"; exit 1; }
echo "Ausfuehrung ok."

echo "== 4/4 Ergebnis-Report =="
python3 "$DIR/make_report.py"
