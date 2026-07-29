#!/usr/bin/env bash
# Startet die Flowable-REST-Engine (Variante A: Docker, Variante B: Java-WAR).
# Default-Credentials der REST-API: rest-admin / test
set -euo pipefail

WAR_URL="https://repo1.maven.org/maven2/org/flowable/flowable-app-rest/7.2.0/flowable-app-rest-7.2.0.war"
WAR="${TMPDIR:-/tmp}/flowable-rest.war"

if command -v docker >/dev/null && docker info >/dev/null 2>&1; then
  echo "Starte via Docker..."
  docker run -d --name flowable -p 8080:8080 flowable/flowable-rest
else
  echo "Kein Docker verfuegbar — starte Spring-Boot-WAR mit lokalem Java (>=17)..."
  [ -f "$WAR" ] || curl -sSf -o "$WAR" "$WAR_URL"
  nohup java -jar "$WAR" > "${TMPDIR:-/tmp}/flowable.log" 2>&1 &
fi

echo -n "Warte auf Engine "
for _ in $(seq 1 40); do
  if curl -s -u rest-admin:test -o /dev/null -w "%{http_code}" \
      http://localhost:8080/flowable-rest/service/repository/deployments \
      | grep -q 200; then
    echo " — bereit: http://localhost:8080/flowable-rest/service"
    exit 0
  fi
  echo -n "."
  sleep 4
done
echo " Timeout — Log pruefen."
exit 1
