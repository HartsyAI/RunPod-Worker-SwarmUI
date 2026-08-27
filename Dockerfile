# SwarmUI RunPod Serverless - Minimal Dockerfile
# Uses SwarmUI's official install and launch scripts

# Ubuntu 24.04 base: the sd.cpp prebuilt binaries require glibc 2.38 / GLIBCXX_3.4.32, which 22.04 cannot provide.
FROM nvidia/cuda:12.6.2-cudnn-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
ENV VOLUME_PATH=/runpod-volume
ENV SWARMUI_PORT=7801
ENV SWARMUI_HOST=0.0.0.0

WORKDIR /

# ============================================================================== 
# Install System Dependencies
# ============================================================================== 
# deadsnakes PPA provides python3.11 on 24.04 (which defaults to python3.12).
RUN apt-get update && \
    apt-get install -y --no-install-recommends software-properties-common gnupg && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt-get update && \
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
        # Build tools
        build-essential \
        # Image processing
        libglib2.0-0 \
        libgl1 \
        libgomp1 \
        # Vulkan loader (required by the sd.cpp Vulkan backend binary)
        libvulkan1 \
    && \
    # Cleanup
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set Python 3.11 as default
RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 && \
    update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

# ==============================================================================
# Install .NET 10 SDK
# ==============================================================================
# SwarmUI's own launcher treats .NET 8 as legacy and installs .NET 10, so shipping
# 10 here keeps the image aligned with it. Without this, that launcher would pause
# 15 seconds and download a second .NET into the network volume on a cold start.
#
# SwarmUI targets net8.0 but builds with <RollForward>Major</RollForward>, so it
# runs on the .NET 10 runtime; a separate .NET 8 runtime is not needed.
#
# Installed with Microsoft's official script rather than apt, because Ubuntu 24.04
# packages .NET 8 natively and adding the Microsoft feed on noble conflicts with it.
ENV DOTNET_ROOT=/usr/share/dotnet
ENV PATH="${DOTNET_ROOT}:${DOTNET_ROOT}/tools:${PATH}"
# The SDK install already brings Microsoft.AspNetCore.App, so it is not fetched separately.
RUN wget https://dot.net/v1/dotnet-install.sh -O /tmp/dotnet-install.sh && \
    chmod +x /tmp/dotnet-install.sh && \
    /tmp/dotnet-install.sh --channel 10.0 --install-dir "$DOTNET_ROOT" && \
    rm /tmp/dotnet-install.sh && \
    ln -sf "$DOTNET_ROOT/dotnet" /usr/bin/dotnet && \
    dotnet --list-sdks

# ============================================================================== 
# Install Handler Dependencies
# ============================================================================== 
COPY requirements.txt /requirements.txt
# 24.04: --ignore-installed avoids uninstalling the Debian-managed pip (no RECORD file);
# --break-system-packages opts out of PEP 668 for this system-wide install.
RUN python3 -m pip install --no-cache-dir --break-system-packages --ignore-installed --upgrade pip && \
    python3 -m pip install --no-cache-dir --break-system-packages -r /requirements.txt && \
    rm /requirements.txt

# ============================================================================== 
# Copy Application Files
# ============================================================================== 
COPY src/rp_handler.py /rp_handler.py
COPY scripts/start.sh /start.sh
COPY scripts/entrypoint.sh /entrypoint.sh

# Fix line endings and permissions
RUN dos2unix /start.sh /entrypoint.sh /rp_handler.py 2>/dev/null || true && \
    chmod +x /start.sh /entrypoint.sh

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
# Start SwarmUI, and the RunPod job handler only when running as a serverless worker
# ==============================================================================
# The entrypoint picks the mode, so this one image works as both a serverless worker
# and a plain GPU pod against the same SwarmUI install on the same network volume.
CMD ["/entrypoint.sh"]
