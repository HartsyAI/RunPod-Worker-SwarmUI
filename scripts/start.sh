#!/bin/bash
# SwarmUI Startup Script for RunPod Serverless
# Checks for existing installation on network volume, installs if needed, then starts SwarmUI

set -e

echo "=============================================================================="
echo "SwarmUI RunPod Serverless - Startup"
echo "=============================================================================="

# Configuration
VOLUME_PATH="${VOLUME_PATH:-/runpod-volume}"
SWARMUI_PATH="$VOLUME_PATH/SwarmUI"
MODELS_PATH="$VOLUME_PATH/Models"
SWARMUI_PORT="${SWARMUI_PORT:-7801}"
SWARMUI_HOST="${SWARMUI_HOST:-0.0.0.0}"

echo "Volume Path: $VOLUME_PATH"
echo "SwarmUI Path: $SWARMUI_PATH"
echo "Models Path: $MODELS_PATH"
echo "=============================================================================="

# Check if network volume is mounted
if [ ! -d "$VOLUME_PATH" ]; then
    echo "ERROR: Network volume not mounted at $VOLUME_PATH"
    echo "Please attach a network volume to your serverless endpoint"
    exit 1
fi

echo "Network volume detected at $VOLUME_PATH"

# Function to install SwarmUI
install_swarmui() {
    echo "=============================================================================="
    echo "Installing SwarmUI (first-time setup)"
    echo "=============================================================================="
    
    cd "$VOLUME_PATH"
    
    # Clone SwarmUI repository
    echo "Cloning SwarmUI repository..."
    git clone https://github.com/mcmonkeyprojects/SwarmUI.git "$SWARMUI_PATH"
    
    cd "$SWARMUI_PATH"
    
    # Build SwarmUI
    echo "Building SwarmUI..."
    dotnet build src/SwarmUI.csproj --configuration Release -o ./bin
    
    # Create necessary directories
    mkdir -p "$SWARMUI_PATH/Data"
    mkdir -p "$SWARMUI_PATH/Output"
    mkdir -p "$SWARMUI_PATH/dlbackend"
    
    # Install ComfyUI backend
    echo "Installing ComfyUI backend..."
    if [ -f "$SWARMUI_PATH/launchtools/comfy-install-linux.sh" ]; then
        chmod +x "$SWARMUI_PATH/launchtools/comfy-install-linux.sh"
        bash "$SWARMUI_PATH/launchtools/comfy-install-linux.sh"
    else
        echo "ERROR: ComfyUI installer not found"
        exit 1
    fi
    
    echo "SwarmUI installation complete!"
}

# Function to configure SwarmUI
configure_swarmui() {
    echo "=============================================================================="
    echo "Configuring SwarmUI"
    echo "=============================================================================="
    
    # Link Models directory to volume
    if [ ! -L "$SWARMUI_PATH/Models" ]; then
        rm -rf "$SWARMUI_PATH/Models" 2>/dev/null || true
        ln -sf "$MODELS_PATH" "$SWARMUI_PATH/Models"
        echo "Linked Models directory to volume"
    fi
    
    # Create models directory structure if it doesn't exist
    mkdir -p "$MODELS_PATH/Stable-Diffusion"
    mkdir -p "$MODELS_PATH/Loras"
    mkdir -p "$MODELS_PATH/VAE"
    mkdir -p "$MODELS_PATH/Embeddings"
    mkdir -p "$MODELS_PATH/ControlNet"
    
    # Configure settings
    SETTINGS_FILE="$SWARMUI_PATH/Data/Settings.fds"
    if [ ! -f "$SETTINGS_FILE" ]; then
        echo "Creating settings file..."
        cat > "$SETTINGS_FILE" << EOF
{
  "Network": {
    "Host": "$SWARMUI_HOST",
    "Port": $SWARMUI_PORT
  },
  "Paths": {
    "ModelRoot": "$SWARMUI_PATH/Models",
    "OutputPath": "$SWARMUI_PATH/Output",
    "DataPath": "$SWARMUI_PATH/Data"
  },
  "DefaultUser": {
    "Settings": {
      "ServerSettings": {
        "AutomaticUpdates": false
      }
    }
  }
}
EOF
    fi
}

# Function to start SwarmUI
start_swarmui() {
    echo "=============================================================================="
    echo "Starting SwarmUI Server"
    echo "=============================================================================="
    
    cd "$SWARMUI_PATH"
    
    # Start SwarmUI
    echo "Launching SwarmUI on $SWARMUI_HOST:$SWARMUI_PORT"
    exec dotnet bin/SwarmUI.dll \
        --host "$SWARMUI_HOST" \
        --port "$SWARMUI_PORT" \
        --no-browser \
        --skip-update
}

# Main execution flow
main() {
    # Check if SwarmUI is already installed
    if [ -d "$SWARMUI_PATH" ] && [ -f "$SWARMUI_PATH/bin/SwarmUI.dll" ]; then
        echo "SwarmUI installation found on network volume"
        echo "Skipping installation, using existing setup"
    else
        echo "SwarmUI not found on network volume"
        install_swarmui
    }
    
    # Configure SwarmUI
    configure_swarmui
    
    # Start SwarmUI
    start_swarmui
}

# Run main function
main
