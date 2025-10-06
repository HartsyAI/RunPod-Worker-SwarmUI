#!/bin/bash
# SwarmUI Startup Script for RunPod Serverless
# Leverages SwarmUI's own launch scripts - much simpler!

set -e

echo "=============================================================================="
echo "SwarmUI RunPod Serverless - Startup"
echo "=============================================================================="

# Configuration
VOLUME_PATH="${VOLUME_PATH:-/runpod-volume}"
SWARMUI_PATH="$VOLUME_PATH/SwarmUI"
MODELS_PATH="$VOLUME_PATH/Models"
OUTPUT_PATH="$VOLUME_PATH/Output"
SWARMUI_PORT="${SWARMUI_PORT:-7801}"
SWARMUI_HOST="${SWARMUI_HOST:-0.0.0.0}"

echo "Volume Path: $VOLUME_PATH"
echo "SwarmUI Path: $SWARMUI_PATH"
echo "=============================================================================="

# Check if network volume is mounted
if [ ! -d "$VOLUME_PATH" ]; then
    echo "ERROR: Network volume not mounted at $VOLUME_PATH"
    echo "Please attach a network volume to your serverless endpoint"
    exit 1
fi

echo "✓ Network volume detected"

# Install SwarmUI if not present
if [ ! -d "$SWARMUI_PATH" ]; then
    echo "=============================================================================="
    echo "First-time setup: Installing SwarmUI"
    echo "This will take 10-20 minutes (build + ComfyUI install)"
    echo "=============================================================================="
    
    cd "$VOLUME_PATH"
    
    # Clone SwarmUI
    echo "Cloning SwarmUI repository..."
    git clone https://github.com/mcmonkeyprojects/SwarmUI.git
    
    cd "$SWARMUI_PATH"
    
    # Create Model/Output directories and symlink them
    echo "Setting up Models and Output directories..."
    mkdir -p "$MODELS_PATH"
    mkdir -p "$OUTPUT_PATH"
    rm -rf Models Output 2>/dev/null || true
    ln -sf "$MODELS_PATH" Models
    ln -sf "$OUTPUT_PATH" Output
    
    echo "✓ SwarmUI cloned and directories configured"
else
    echo "✓ SwarmUI installation found, using existing setup"
    
    cd "$SWARMUI_PATH"
    
    # Ensure symlinks exist
    if [ ! -L "Models" ]; then
        rm -rf Models 2>/dev/null || true
        ln -sf "$MODELS_PATH" Models
    fi
    if [ ! -L "Output" ]; then
        rm -rf Output 2>/dev/null || true
        ln -sf "$OUTPUT_PATH" Output
    fi
fi

# Navigate to SwarmUI directory
cd "$SWARMUI_PATH"

echo "=============================================================================="
echo "Starting SwarmUI"
echo "=============================================================================="

# Use SwarmUI's own launch script with serverless parameters
# The launch script will:
# 1. Build SwarmUI if not built (first run)
# 2. Install ComfyUI backend if not present (first run)
# 3. Start the SwarmUI server
#
# launch_mode none = don't try to open browser
# host and port for serverless environment
exec ./launch-linux.sh \
    --launch_mode none \
    --host "$SWARMUI_HOST" \
    --port "$SWARMUI_PORT"
