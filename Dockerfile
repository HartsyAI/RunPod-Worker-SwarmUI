# SwarmUI RunPod Serverless - Simplified Dockerfile
# Uses SwarmUI's official install and launch scripts

FROM nvidia/cuda:12.1.0-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
ENV VOLUME_PATH=/runpod-volume
ENV SWARMUI_PORT=7801
ENV SWARMUI_HOST=0.0.0.0

WORKDIR /

# ============================================================================== 
# Install System Dependencies (SwarmUI Prerequisites)
# ============================================================================== 
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        # Core utilities
        wget \
        curl \
        ca-certificates \
        git \
        dos2unix \
        # Python 3.11 (required by SwarmUI)
        python3.11 \
        python3.11-venv \
        python3.11-dev \
        python3-pip \
        python3-full \
        # Build tools
        build-essential \
        # Image processing
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
    && \
    # Install .NET 8 SDK (required by SwarmUI)
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

# Verify Python has pip
RUN python3.11 -m pip --version

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
COPY src/rp_handler.py /rp_handler.py
COPY scripts/start.sh /start.sh

# Fix line endings and permissions
RUN dos2unix /start.sh /rp_handler.py 2>/dev/null || true && \
    chmod +x /start.sh

# ============================================================================== 
# Expose SwarmUI Port
# ============================================================================== 
EXPOSE ${SWARMUI_PORT}

# ============================================================================== 
# Health Check
# ============================================================================== 
HEALTHCHECK --interval=30s --timeout=10s --start-period=1800s --retries=3 \
    CMD curl -f -X POST http://localhost:${SWARMUI_PORT}/API/GetNewSession \
        -H "Content-Type: application/json" \
        -d '{}' || exit 1

# ============================================================================== 
# Start SwarmUI and RunPod Handler
# ============================================================================== 
CMD ["/bin/bash", "-c", "/start.sh & python3 -u /rp_handler.py"]
