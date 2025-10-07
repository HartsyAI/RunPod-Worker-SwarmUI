#!/bin/bash
# SwarmUI Startup Script for RunPod Serverless
# Manually installs ComfyUI to ensure it's always available

set -e

echo "=============================================================================="
echo "SwarmUI RunPod Serverless - Startup"
echo "=============================================================================="

# Configuration
VOLUME_PATH="${VOLUME_PATH:-/runpod-volume}"
SWARMUI_PATH="$VOLUME_PATH/SwarmUI"
MODELS_PATH="$VOLUME_PATH/Models"
OUTPUT_PATH="$VOLUME_PATH/Output"
COMFY_PATH="$SWARMUI_PATH/dlbackend/ComfyUI"
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

# Install SwarmUI if not present
if [ ! -d "$SWARMUI_PATH" ]; then
    echo "=============================================================================="
    echo "First-time setup: Installing SwarmUI"
    echo "=============================================================================="
    
    cd "$VOLUME_PATH"
    
    echo "Cloning SwarmUI repository..."
    git clone https://github.com/mcmonkeyprojects/SwarmUI.git
    
    cd "$SWARMUI_PATH"
    
    echo "Setting up directories..."
    mkdir -p "$MODELS_PATH/Stable-Diffusion"
    mkdir -p "$MODELS_PATH/Loras"
    mkdir -p "$MODELS_PATH/VAE"
    mkdir -p "$OUTPUT_PATH"
    rm -rf Models Output 2>/dev/null || true
    ln -sf "$MODELS_PATH" Models
    ln -sf "$OUTPUT_PATH" Output
    
    echo "✓ SwarmUI cloned"
else
    echo "✓ SwarmUI found"
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

# Install ComfyUI Backend Using SwarmUI's Official Script
echo "=============================================================================="
echo "ComfyUI Backend Setup"
echo "=============================================================================="

if [ ! -d "$COMFY_PATH" ]; then
    echo "Installing ComfyUI using SwarmUI's official installer..."
    echo "This will take 5-10 minutes (download + PyTorch + dependencies)..."
    
    cd "$SWARMUI_PATH"
    
    # SwarmUI's official ComfyUI installation script
    # Located at launchtools/comfy-install-linux.sh
    INSTALL_SCRIPT="launchtools/comfy-install-linux.sh"
    
    if [ -f "$INSTALL_SCRIPT" ]; then
        echo "Found SwarmUI's official installer: $INSTALL_SCRIPT"
        chmod +x "$INSTALL_SCRIPT"
        
        # Run with 'nv' for NVIDIA GPUs (RunPod uses NVIDIA)
        # This is exactly what SwarmUI does during first-run setup
        bash "$INSTALL_SCRIPT" nv
        
        if [ $? -eq 0 ]; then
            echo "✓ ComfyUI installed successfully"
        else
            echo "ERROR: ComfyUI installation failed"
            echo "Check logs above for details"
            exit 1
        fi
    else
        echo "ERROR: SwarmUI installation script not found at $INSTALL_SCRIPT"
        echo "SwarmUI repository may be incomplete or corrupted"
        echo "Looking for script in current directory..."
        ls -la launchtools/ || echo "launchtools/ directory not found"
        exit 1
    fi
else
    echo "✓ ComfyUI already installed at $COMFY_PATH"
fi

# Configure backend settings
echo "=============================================================================="
echo "Configuring Backend"
echo "=============================================================================="

cd "$SWARMUI_PATH"
mkdir -p Data/Backends

# Create backend configuration file
cat > Data/Backends/ComfyUI-SelfStart-0.fds << 'EOF'
{
  "ID": "ComfyUI-SelfStart-0",
  "Title": "ComfyUI Backend",
  "Type": "comfyui_selfstart",
  "Enabled": true,
  "StartScript": "dlbackend/ComfyUI/main.py",
  "ExtraArgs": "",
  "GPUIDs": "0",
  "MemoryGB": 0,
  "NetworkHost": "127.0.0.1",
  "NetworkPort": 7821,
  "PythonVenvPath": "dlbackend/ComfyUI/venv"
}
EOF

echo "✓ Backend configuration created"

# Build SwarmUI if not built yet
if [ ! -d "bin" ] || [ ! -f "bin/SwarmUI.dll" ]; then
    echo "=============================================================================="
    echo "Building SwarmUI (5-10 minutes)..."
    echo "=============================================================================="
    
    # Make launch script executable
    chmod +x ./launch-linux.sh
    
    # Run build
    ./launch-linux.sh --launch_mode none --build-only || {
        echo "Build with launch script failed, trying dotnet build..."
        dotnet build src/SwarmUI.csproj -c Release -o bin/
    }
    
    echo "✓ Build complete"
fi

echo "=============================================================================="
echo "Starting SwarmUI"
echo "=============================================================================="

if [ ! -d "bin" ] || [ ! -f "bin/SwarmUI.dll" ]; then
    echo "First run - will build and install (15-20 minutes total)"
else
    echo "Existing build - should be ready in 60-90 seconds"
fi

echo "=============================================================================="
echo "SwarmUI Output:"
echo "=============================================================================="

# Start SwarmUI directly with dotnet for better control
exec dotnet bin/SwarmUI.dll \
    --launch_mode none \
    --host "$SWARMUI_HOST" \
    --port "$SWARMUI_PORT" 2>&1
    