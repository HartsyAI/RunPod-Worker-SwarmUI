#!/usr/bin/env bash
# CPU smoke test for a built RunPod worker image. Usage: tests/smoke/smoke.sh <image>
#   1. Serverless: drives one real lease through the handler (tests/smoke/lease_smoke.py): the lease
#      token opens the gateway, no token is refused, and the token dies when the lease releases.
#   2. Pod: starts standalone mode and checks the gateway refuses requests without the token.
set -euo pipefail

IMAGE="$1"
LOG=smoke-container.log
: > "$LOG"

fail() {
    echo "SMOKE FAIL: $*" >&2
    exit 1
}

echo "== Serverless lease =="
out="$(docker run --rm -i -e SWARMUI_STARTUP_GRACE_SECONDS=10 -e SWARMUI_POLL_INTERVAL=1 \
    --entrypoint /opt/worker/venv/bin/python "$IMAGE" - < tests/smoke/lease_smoke.py 2>&1)" \
    || { echo "$out" >> "$LOG"; fail "lease smoke failed (see $LOG)"; }
echo "$out" >> "$LOG"
echo "$out" | grep -q "LEASE SMOKE PASS" || fail "lease smoke did not complete"

echo "== Pod mode gateway =="
NAME="swarmui-rp-smoke-$$"
trap 'docker logs "$NAME" >> "$LOG" 2>&1 || true; docker rm -f "$NAME" > /dev/null 2>&1 || true' EXIT
TOKEN="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 48)"
docker run -d --name "$NAME" -p 127.0.0.1:17802:7801 -e SWARMUI_WORKER_TOKEN="$TOKEN" "$IMAGE" > /dev/null
for _ in $(seq 1 180); do
    code="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' \
        http://127.0.0.1:17802/API/GetNewSession || true)"
    [ "$code" = "200" ] && break
    sleep 5
done
[ "$code" = "200" ] || fail "pod-mode SwarmUI never answered through the gateway (HTTP $code)"
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:17802/API/GetNewSession)"
[ "$code" = "401" ] || fail "pod mode accepted a request without the token (HTTP $code)"

echo "SMOKE PASS"
