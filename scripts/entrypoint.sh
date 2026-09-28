#!/usr/bin/env bash
# Starts the worker in the right mode for how RunPod launched this container.
#
#   serverless  RunPod sets RUNPOD_ENDPOINT_ID only for serverless workers. The job handler is the
#               foreground process, because that is what RunPod supervises; it starts SwarmUI itself.
#   pod         Anything else. The base image's standalone supervisor runs SwarmUI behind the
#               gateway with a fixed token (SWARMUI_WORKER_TOKEN, set when the pod is created).
#
# Set SWARM_MODE=serverless or SWARM_MODE=pod to force a mode.
set -euo pipefail

MODE="${SWARM_MODE:-auto}"
if [ "$MODE" = "auto" ]; then
    if [ -n "${RUNPOD_ENDPOINT_ID:-}" ]; then MODE=serverless; else MODE=pod; fi
fi

# Models live on the network volume. Serverless mounts it at /runpod-volume, pods usually at
# /workspace. Version 1 of this image installed SwarmUI onto the volume, so its models are under
# SwarmUI/Models; that layout is checked first so existing volumes keep working unchanged.
if [ -z "${SWARMUI_MODEL_ROOT:-}" ]; then
    for volume in "${VOLUME_PATH:-}" /runpod-volume /workspace; do
        [ -n "$volume" ] || continue
        for candidate in "$volume/SwarmUI/Models" "$volume/Models"; do
            if [ -d "$candidate" ]; then
                export SWARMUI_MODEL_ROOT="$candidate"
                break 2
            fi
        done
    done
fi
echo "SwarmUI worker (RunPod) starting in '$MODE' mode; models: ${SWARMUI_MODEL_ROOT:-<image default, no volume found>}"

case "$MODE" in
    serverless)
        exec /opt/worker/venv/bin/python -u /opt/worker/handler.py
        ;;
    pod)
        exec /opt/worker/venv/bin/python -u -m swarmui_worker
        ;;
    *)
        echo "SWARM_MODE must be 'serverless', 'pod', or 'auto' (got '$MODE')" >&2
        exit 1
        ;;
esac
