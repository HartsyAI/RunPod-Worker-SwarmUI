# SwarmUI RunPod Serverless Dockerfile
# Based on official RunPod worker-comfyui pattern

FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1

# RunPod environment
ENV VOLUME_PATH=/runpod-volume
ENV SWARMUI_PORT=7801
ENV SWARMUI_HOST=0.0.0.0

WORKDIR /

# ============================================================================== 
# Install System Dependencies
# ============================================================================== 
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Core tools
        wget \
        curl \
        ca-certificates \
        apt-transport-https \
        gnupg \
        # Build tools
        build-essential \
        git \
        # Python
        python3.11 \
        python3.11-venv \
        python3.11-dev \
        python3-pip \
        # Image processing
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
    && \
    # Install .NET 8 SDK
    wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update && \
    apt-get install -y dotnet-sdk-8.0 && \
    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# ============================================================================== 
# Install RunPod Python Dependencies
# ============================================================================== 
COPY builder/requirements.txt /requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir -r /requirements.txt && \
    rm /requirements.txt

# ============================================================================== 
# Copy Application Files
# ============================================================================== 
COPY src/rp_handler.py /rp_handler.py
COPY start.sh /start.sh
RUN chmod +x /start.sh

# ============================================================================== 
# Expose Port
# ============================================================================== 
EXPOSE ${SWARMUI_PORT}

# ============================================================================== 
# Start Script (runs in background) and Handler (runs in foreground)
# ============================================================================== 
CMD ["/bin/bash", "-c", "/start.sh & python3 -u /rp_handler.py"]
