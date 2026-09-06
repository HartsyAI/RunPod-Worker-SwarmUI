#!/bin/bash
# SwarmUI Startup Script - Uses Official SwarmUI Scripts
# No manual building or installation - let SwarmUI handle it!

set -e

echo "=============================================================================="
echo "SwarmUI RunPod Serverless - Startup"
echo "=============================================================================="

# Configuration
VOLUME_PATH="${VOLUME_PATH:-/runpod-volume}"
SWARMUI_PATH="$VOLUME_PATH/SwarmUI"
SWARMUI_PORT="${SWARMUI_PORT:-7801}"
SWARMUI_HOST="${SWARMUI_HOST:-0.0.0.0}"

echo "Volume Path: $VOLUME_PATH"
echo "SwarmUI Path: $SWARMUI_PATH"
echo "=============================================================================="

# Check if network volume is mounted
if [ ! -d "$VOLUME_PATH" ]; then
    echo "ERROR: Network volume not mounted at $VOLUME_PATH"
    exit 1
fi

echo "✓ Network volume detected"

# ==============================================================================
# First-Time Installation
# ==============================================================================
if [ ! -d "$SWARMUI_PATH" ]; then
    echo "=============================================================================="
    echo "First-Time Setup: Installing SwarmUI"
    echo "=============================================================================="

    if [ -d /opt/SwarmUI-baked ]; then
        # Fast path: the Dockerfile already git-cloned and dotnet-built SwarmUI once at image
        # build time (see "Bake a pre-built SwarmUI into the image"), so this is a local file
        # copy - seconds, no network, no build. This matters most for Vast.ai Serverless: its
        # workergroups cannot attach a volume at all (confirmed empirically - there is no such
        # option anywhere in the console's endpoint/workergroup creation flow, unlike RunPod's
        # persistent network volume), so every single cold worker used to have to git clone and
        # dotnet build SwarmUI from scratch over the network before it could even start - and
        # Vast's autoscaler routinely replaces a not-yet-ready worker with a cheaper candidate
        # before that multi-minute build finishes, so a serverless endpoint could churn
        # indefinitely without ever reaching "ready". A local copy wins that race instead.
        echo "Using the pre-built SwarmUI baked into this image..."
        cp -a /opt/SwarmUI-baked "$SWARMUI_PATH"
    else
        # Defensive fallback for anyone running start.sh against an image that skipped the bake
        # step. Cloning and building directly (rather than downloading and running the official
        # install-linux.sh) is deliberate: that script's own last line launches SwarmUI itself
        # and never returns control here, since that launch runs in the foreground for as long
        # as the container lives - it would silently skip the ComfyUI install below, same as the
        # bake step already does correctly by stopping short of any launch.
        echo "No baked SwarmUI found in this image; cloning and building it now (this is slow - expect several minutes)..."
        git clone --depth 1 https://github.com/mcmonkeyprojects/SwarmUI "$SWARMUI_PATH"
        cd "$SWARMUI_PATH"
        dotnet build src/SwarmUI.csproj --configuration Release -o ./src/bin/live_release
        git rev-parse HEAD > src/bin/last_build
        cd "$VOLUME_PATH"
    fi

    if [ ! -d "$SWARMUI_PATH" ]; then
        echo "ERROR: SwarmUI installation failed - directory not created"
        exit 1
    fi

    echo "✓ SwarmUI installed successfully"

    # Install ComfyUI Backend, unless this is a Vast.ai Serverless worker - those configure
    # their own backend (this extension's own providers, typically) and never want ComfyUI.
    if [ "$SWARM_MODE" = "vast_serverless" ]; then
        echo "Skipping ComfyUI auto-install (SWARM_MODE=vast_serverless configures its own backend)."
    else
        echo "=============================================================================="
        echo "Installing ComfyUI Backend"
        echo "=============================================================================="

        cd "$SWARMUI_PATH"

        if [ -f "launchtools/comfy-install-linux.sh" ]; then
            echo "Running ComfyUI installer..."
            chmod +x launchtools/comfy-install-linux.sh

            # Run with 'nv' for NVIDIA GPUs
            bash launchtools/comfy-install-linux.sh nv

            if [ $? -eq 0 ]; then
                echo "✓ ComfyUI installed successfully"
            else
                echo "ERROR: ComfyUI installation failed"
                exit 1
            fi
        else
            echo "ERROR: ComfyUI installer not found at launchtools/comfy-install-linux.sh"
            exit 1
        fi
    fi

else
    echo "✓ SwarmUI already installed"
fi

# ============================================================================== 
# Launch SwarmUI Using Official Script
# ============================================================================== 
echo "=============================================================================="
echo "Starting SwarmUI Server"
echo "=============================================================================="

cd "$SWARMUI_PATH"

# Verify launch script exists
if [ ! -f "launch-linux.sh" ]; then
    echo "ERROR: launch-linux.sh not found in $SWARMUI_PATH"
    echo "SwarmUI installation may be corrupted"
    exit 1
fi

chmod +x launch-linux.sh

# Optional private data directory.
#
# SwarmUI keeps its users, model metadata, settings and backend config in Data/, and
# the user and metadata stores are LiteDB files. LiteDB expects a single process, so
# two SwarmUI instances sharing one Data/ over a network volume can corrupt it.
#
# Leave SWARM_DATA_DIR unset to use the shared Data/ (fine when only one instance runs
# at a time, and it keeps your configured backends). Set it when a pod and serverless
# workers may run together, or when serverless scales past one worker. It is seeded
# from the shared Data/ on first use so the instance still starts with your backends
# and settings rather than an empty SwarmUI with no backend at all.
EXTRA_ARGS=""
if [ -n "$SWARM_DATA_DIR" ]; then
    echo "Using private data directory: $SWARM_DATA_DIR"
    mkdir -p "$SWARM_DATA_DIR"
    if [ ! -f "$SWARM_DATA_DIR/Settings.fds" ] && [ -d "$SWARMUI_PATH/Data" ]; then
        echo "Seeding it from the shared Data directory..."
        cp -a "$SWARMUI_PATH/Data/." "$SWARM_DATA_DIR/"
    fi
    EXTRA_ARGS="--data_dir $SWARM_DATA_DIR"
fi

echo "Server: $SWARMUI_HOST:$SWARMUI_PORT"
echo "Using SwarmUI's launch-linux.sh script"
echo "=============================================================================="
echo ""

# Start SwarmUI with official launch script
# --launch_mode none: Don't open browser
# --host 0.0.0.0: Listen on all interfaces
# --port: Custom port
exec ./launch-linux.sh \
    --launch_mode none \
    --host "$SWARMUI_HOST" \
    --port "$SWARMUI_PORT" \
    $EXTRA_ARGS 2>&1
