#!/bin/bash
# Chooses how this image runs, so one image serves both RunPod products against
# the same SwarmUI install on the same network volume.
#
#   serverless - SwarmUI runs in the background and the RunPod job handler runs in
#                the foreground, because the handler is what RunPod supervises.
#   pod        - SwarmUI runs in the foreground. There is no job handler in a pod:
#                nothing would call it, and when it exits the container stops.
#
# Getting this wrong is what breaks pods. If the handler is the foreground process
# in a pod it exits immediately (there is no serverless job to serve), the container
# dies with it, nothing is left listening on the SwarmUI port, and RunPod's proxy
# answers 404.
#
# Set SWARM_MODE to force a mode. Left on auto, serverless is detected by
# RUNPOD_ENDPOINT_ID, which RunPod sets only for serverless workers.

set -e

MODE="${SWARM_MODE:-auto}"

if [ "$MODE" = "auto" ]; then
    if [ -n "$RUNPOD_ENDPOINT_ID" ]; then
        MODE="serverless"
    else
        MODE="pod"
    fi
fi

echo "=============================================================================="
echo "SwarmUI RunPod worker starting in '$MODE' mode"
echo "  SWARM_MODE:          ${SWARM_MODE:-auto (detected)}"
echo "  RUNPOD_ENDPOINT_ID:  ${RUNPOD_ENDPOINT_ID:-<unset>}"
echo "  RUNPOD_POD_ID:       ${RUNPOD_POD_ID:-<unset>}"
echo "=============================================================================="

case "$MODE" in
    serverless)
        /start.sh &
        exec python3 -u /rp_handler.py
        ;;
    pod)
        exec /start.sh
        ;;
    *)
        echo "ERROR: SWARM_MODE must be 'serverless', 'pod', or 'auto' (got '$MODE')."
        exit 1
        ;;
esac
