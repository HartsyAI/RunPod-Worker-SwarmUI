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
    
    cd "$VOLUME_PATH"
    
    # Download SwarmUI install script
    echo "Downloading SwarmUI installer..."
    wget -q https://github.com/mcmonkeyprojects/SwarmUI/releases/download/0.6.5-Beta/install-linux.sh -O install-linux.sh
    chmod +x install-linux.sh
    
    # Run SwarmUI installer
    echo "Running SwarmUI installer (this will clone and setup SwarmUI)..."
    ./install-linux.sh
    
    if [ ! -d "$SWARMUI_PATH" ]; then
        echo "ERROR: SwarmUI installation failed - directory not created"
        exit 1
    fi
    
    echo "✓ SwarmUI installed successfully"
    
    # Install ComfyUI Backend
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
    --port "$SWARMUI_PORT" 2>&1
