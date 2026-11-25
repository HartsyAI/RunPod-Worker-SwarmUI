#!/usr/bin/env bash
# CPU smoke test for a built RunPod worker image. Usage: tests/smoke/smoke.sh <image>
#   1. The entrypoint uses the worker config's volume_path, and stops on an invalid config.
#   2. Serverless: drives one real lease through the handler (tests/smoke/lease_smoke.py): the lease
#      token opens the gateway, no token is refused, and the token dies when the lease releases.
#   3. Pod: starts standalone mode and checks the gateway refuses requests without the token.
set -euo pipefail

IMAGE="$1"
LOG=smoke-container.log
: > "$LOG"

fail() {
    echo "SMOKE FAIL: $*" >&2
    exit 1
}

echo "== Worker config in the entrypoint =="
# An unknown mode stops the entrypoint right after it has picked the models.
out="$(docker run --rm --tmpfs /data/Models -e SWARM_MODE=none -e SWARMUI_WORKER_CONFIG='{"volume_path":"/data"}' "$IMAGE" 2>&1 || true)"
echo "$out" >> "$LOG"
grep -qF "models: /data/Models" <<< "$out" || fail "the entrypoint did not use the config's volume_path"
out="$(docker run --rm -e SWARM_MODE=none -e SWARMUI_WORKER_CONFIG='{"unknown":1}' "$IMAGE" 2>&1 || true)"
echo "$out" >> "$LOG"
grep -qF "Invalid configuration: SWARMUI_WORKER_CONFIG" <<< "$out" || fail "an invalid config was not reported"
grep -qF "starting in" <<< "$out" && fail "the entrypoint carried on with an invalid config"

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
# base64url without padding, as the Cloud Backends extension sends it.
CONFIG="$(printf '{"worker_token":"%s"}' "$TOKEN" | base64 | tr '+/' '-_' | tr -d '=\n')"
docker run -d --name "$NAME" -p 127.0.0.1:17802:7801 -e SWARMUI_WORKER_CONFIG="$CONFIG" "$IMAGE" > /dev/null
for _ in $(seq 1 180); do
    code="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d '{}' \
        http://127.0.0.1:17802/API/GetNewSession || true)"
    [ "$code" = "200" ] && break
    sleep 5
done
[ "$code" = "200" ] || fail "pod-mode SwarmUI never answered through the gateway (HTTP $code)"
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST -H 'Content-Type: application/json' -d '{}' http://127.0.0.1:17802/API/GetNewSession)"
[ "$code" = "401" ] || fail "pod mode accepted a request without the token (HTTP $code)"
# Read in full first: with pipefail, grep -q stopping at a match would fail the pipe and hide the leak.
logs="$(docker logs "$NAME" 2>&1)"
grep -qF -e "$TOKEN" -e "$CONFIG" <<< "$logs" && fail "the worker token appears in the container log"

echo "SMOKE PASS"
