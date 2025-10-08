#!/bin/bash
# SwarmUI Startup - Uses official SwarmUI installation scripts
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

# Verify network volume is mounted
if [ ! -d "$VOLUME_PATH" ]; then
    echo "ERROR: Network volume not mounted at $VOLUME_PATH"
    echo "Please attach a RunPod network volume to this endpoint"
    exit 1
fi

echo "✓ Network volume detected"

# First-time installation using official SwarmUI installer
if [ ! -d "$SWARMUI_PATH" ]; then
    echo "=============================================================================="
    echo "First-Time Setup: Installing SwarmUI"
    echo "=============================================================================="
    echo "This will take 10-20 minutes (download, build, ComfyUI installation)"
    echo ""
    
    cd "$VOLUME_PATH"
    
    # Download official installer
    echo "Downloading SwarmUI installer..."
    wget -q https://github.com/mcmonkeyprojects/SwarmUI/releases/download/0.6.5-Beta/install-linux.sh -O install-linux.sh
    chmod +x install-linux.sh
    
    echo "Running SwarmUI installer..."
    echo "(This installs SwarmUI and will prompt for ComfyUI installation)"
    echo ""
    
    # Run installer - it will create the SwarmUI directory
    ./install-linux.sh
    
    if [ ! -d "$SWARMUI_PATH" ]; then
        echo "ERROR: SwarmUI installation failed - directory not created"
        exit 1
    fi
    
    echo ""
    echo "✓ SwarmUI installed successfully"
    
    # Create Models and Output directories on volume
    mkdir -p "$VOLUME_PATH/Models/Stable-Diffusion"
    mkdir -p "$VOLUME_PATH/Models/Loras"
    mkdir -p "$VOLUME_PATH/Models/VAE"
    mkdir -p "$VOLUME_PATH/Output"
    
    # Symlink to volume storage
    cd "$SWARMUI_PATH"
    rm -rf Models Output 2>/dev/null || true
    ln -sf "$VOLUME_PATH/Models" Models
    ln -sf "$VOLUME_PATH/Output" Output
    
    echo "✓ Storage directories configured"
else
    echo "✓ SwarmUI found at $SWARMUI_PATH"
    
    # Ensure symlinks exist
    cd "$SWARMUI_PATH"
    if [ ! -L "Models" ]; then
        rm -rf Models 2>/dev/null || true
        ln -sf "$VOLUME_PATH/Models" Models
    fi
    if [ ! -L "Output" ]; then
        rm -rf Output 2>/dev/null || true
        ln -sf "$VOLUME_PATH/Output" Output
    fi
fi

# Launch SwarmUI using official launch script
echo "=============================================================================="
echo "Launching SwarmUI Server"
echo "=============================================================================="
echo "Using official launch-linux.sh script"
echo "This will:"
echo "  - Build SwarmUI if needed"
echo "  - Install ComfyUI backend if needed (first run: 5-10 minutes)"
echo "  - Start SwarmUI server on $SWARMUI_HOST:$SWARMUI_PORT"
echo "  - Auto-start ComfyUI backend"
echo "=============================================================================="
echo ""

cd "$SWARMUI_PATH"

# Make sure launch script is executable
chmod +x launch-linux.sh

# Launch SwarmUI with serverless-friendly settings
# --launch_mode none: Don't open browser
# --host 0.0.0.0: Listen on all interfaces for RunPod routing
# --port: Our configured port
exec ./launch-linux.sh \
    --launch_mode none \
    --host "$SWARMUI_HOST" \
    --port "$SWARMUI_PORT"
