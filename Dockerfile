# SwarmUI RunPod Serverless - Simplified using official SwarmUI scripts
FROM nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
ENV VOLUME_PATH=/runpod-volume
ENV SWARMUI_PORT=7801
ENV SWARMUI_HOST=0.0.0.0

WORKDIR /

# ============================================================================== 
# Install SwarmUI Prerequisites
# ============================================================================== 
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        wget \
        curl \
        git \
        python3.11 \
        python3.11-venv \
        python3.11-dev \
        python3-pip \
        build-essential \
        ca-certificates \
        dos2unix \
        libglib2.0-0 \
        libgl1 \
    && \
    # Install .NET 8 SDK
    wget https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O packages-microsoft-prod.deb && \
    dpkg -i packages-microsoft-prod.deb && \
    rm packages-microsoft-prod.deb && \
    apt-get update && \
    apt-get install -y dotnet-sdk-8.0 && \
    # Set Python 3.11 as default
    update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1 && \
    # Verify installations
    python3 --version && \
    python3 -m pip --version && \
    dotnet --version && \
    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ============================================================================== 
# Install RunPod Handler Dependencies
# ============================================================================== 
COPY builder/requirements.txt /requirements.txt
RUN python3 -m pip install --no-cache-dir --upgrade pip && \
    python3 -m pip install --no-cache-dir -r /requirements.txt && \
    rm /requirements.txt

# ============================================================================== 
# Copy Application Files
# ============================================================================== 
COPY scripts/start.sh /start.sh
COPY src/rp_handler.py /rp_handler.py

RUN dos2unix /start.sh /rp_handler.py 2>/dev/null || true && \
    chmod +x /start.sh

# ============================================================================== 
# Expose SwarmUI Port
# ============================================================================== 
EXPOSE ${SWARMUI_PORT}

# ============================================================================== 
# Start SwarmUI and Handler
# ============================================================================== 
CMD ["/bin/bash", "-c", "/start.sh & python3 -u /rp_handler.py"]
