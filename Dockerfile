# SwarmUI RunPod Serverless - Minimal Dockerfile
# Uses SwarmUI's official install and launch scripts

# Ubuntu 24.04 base: the sd.cpp prebuilt binaries require glibc 2.38 / GLIBCXX_3.4.32, which 22.04 cannot provide.
FROM nvidia/cuda:12.6.2-cudnn-devel-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV DOTNET_CLI_TELEMETRY_OPTOUT=1
ENV VOLUME_PATH=/runpod-volume
# Port the Vast.ai PyWorker listens on in vast_serverless mode. Unused by the other two modes,
# but exposed unconditionally since one image serves all three - see scripts/entrypoint.sh.
ENV WORKER_PORT=8000
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
# Bake a pre-built SwarmUI into the image
# ==============================================================================
# start.sh copies this to $SWARMUI_PATH on a fresh volume/container instead of git-cloning and
# dotnet-building at container startup - a local file copy takes seconds; a live clone+build
# takes minutes. That gap matters most for Vast.ai Serverless: its workergroups cannot attach a
# volume at all (no such option exists anywhere in Vast's own console for a workergroup, unlike
# RunPod's persistent network volume), so every cold worker used to pay the full clone+build
# cost, and Vast's autoscaler routinely swaps out a not-yet-ready worker for a cheaper candidate
# before that finishes - a serverless endpoint could churn indefinitely without ever reaching
# "ready". This mirrors exactly what SwarmUI's own launch-linux.sh does on first run
# (launchtools/linux-build-logic.sh: `dotnet build src/SwarmUI.csproj --configuration Release
# -o ./src/bin/live_release`), just done once here instead of on every fresh container.
RUN git clone --depth 1 https://github.com/mcmonkeyprojects/SwarmUI /opt/SwarmUI-baked && \
    cd /opt/SwarmUI-baked && \
    dotnet build src/SwarmUI.csproj --configuration Release -o ./src/bin/live_release && \
    git rev-parse HEAD > src/bin/last_build

# ==============================================================================
# Bake the HartsyInference backend in
# ==============================================================================
# SwarmUI with no backend starts fine and then cannot generate anything. RunPod installs its backend
# onto the persistent network volume once and reuses it, but a Vast.ai Serverless workergroup cannot
# attach a volume at all, so a serverless worker gets a bare container every time and anything not in
# the image would be redone on every cold start.
#
# HartsyInference is pure C# in-process, so this costs an extension build and a NuGet package - no
# Python, no venv, no multi-GB torch download, unlike wiring up ComfyUI for the same job.
#
# Built here rather than only cloned, because SwarmUI builds extensions on startup
# (Core/ExtensionsManager.cs BuildExtension) and that build would otherwise land on the first cold
# worker. That code skips building when its exact output file already exists, and names that file
# after the extension's own git HEAD - so TargetName has to carry the same 8-char hash or the worker
# rebuilds anyway and this buys nothing. The final `test` is what catches that drift, loudly, at
# image build time instead of silently costing minutes per worker.
RUN git clone --depth 1 https://github.com/HartsyAI/SwarmUI-HartsyInference-Backend \
        /opt/SwarmUI-baked/src/Extensions/SwarmUI-HartsyInference && \
    cd /opt/SwarmUI-baked && \
    EXT_HASH="$(git -C src/Extensions/SwarmUI-HartsyInference rev-parse HEAD | cut -c1-8)" && \
    DLL="SwarmExtensionSwarmUI-HartsyInference" && \
    dotnet build src/Extensions/SwarmUI-HartsyInference/*.csproj -c Release \
        -o "/opt/SwarmUI-baked/src/bin/extensions/$DLL/" \
        -p:BaseIntermediateOutputPath="/opt/SwarmUI-baked/src/obj/extensions/$DLL/" \
        -p:TargetName="$DLL-$EXT_HASH" && \
    test -f "/opt/SwarmUI-baked/src/bin/extensions/$DLL/$DLL-$EXT_HASH.dll"

# Register an actual backend, because building the extension only registers the backend *type* - it
# does not create a configured backend, and nothing runs the first-run wizard in a container. Without
# this a worker still comes up with an empty backend list and cannot generate.
RUN mkdir -p /opt/SwarmUI-baked/Data && printf '%s\n' \
    '0:' \
    '	type: hartsyinference' \
    '	title: HartsyInference' \
    '	enabled: true' \
    '	settings:' \
    '		ComputeBackend: auto' \
    '		GPU_ID: 0' \
    '		LowVram: Auto' \
    '		OverQueue: 1' \
    '		Previews: true' \
    > /opt/SwarmUI-baked/Data/Backends.fds

# ==============================================================================
# Install Handler Dependencies
# ==============================================================================
COPY requirements.txt /requirements.txt
# One venv for every Python dependency this image needs (rp_handler.py's and vast_worker.py's
# alike), not --break-system-packages against the system Python. That flag plus
# --ignore-installed used to be enough on this base image, but some apt package pulled in a
# newer Debian-managed `cryptography` at some point after this Dockerfile was last verified,
# and any pip install that now needs a different cryptography version (runpod's own dependency
# chain does, and vastai pins one exactly) fails outright: pip can't uninstall a package apt
# installed, since apt doesn't leave the RECORD file pip needs to safely replace it. A venv
# sidesteps the system Python entirely rather than fighting PEP 668 and apt over the same
# package - confirmed broken system-wide in CI even for requirements.txt alone, unrelated to
# vastai specifically.
RUN python3 -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip && \
    /opt/venv/bin/pip install --no-cache-dir -r /requirements.txt && \
    /opt/venv/bin/pip install --no-cache-dir "vastai>=1.6.0" && \
    rm /requirements.txt

# ==============================================================================
# Copy Application Files
# ==============================================================================
COPY src/rp_handler.py /rp_handler.py
COPY src/vast_worker.py /vast_worker.py
COPY scripts/start.sh /start.sh
COPY scripts/entrypoint.sh /entrypoint.sh

# Fix line endings and permissions
RUN dos2unix /start.sh /entrypoint.sh /rp_handler.py /vast_worker.py 2>/dev/null || true && \
    chmod +x /start.sh /entrypoint.sh

# ==============================================================================
# Expose Ports
# ==============================================================================
# SwarmUI itself, plus the Vast.ai PyWorker's port (only listened on in vast_serverless mode).
EXPOSE ${SWARMUI_PORT}
EXPOSE ${WORKER_PORT}

# ============================================================================== 
# Health Check
# ============================================================================== 
HEALTHCHECK --interval=30s --timeout=10s --start-period=1800s --retries=3 \
    CMD curl -f -X POST http://localhost:${SWARMUI_PORT}/API/GetNewSession \
        -H "Content-Type: application/json" \
        -d '{}' || exit 1

# ==============================================================================
# Start SwarmUI, plus a job handler when running as any kind of serverless worker
# ==============================================================================
# The entrypoint picks the mode, so this one image works as a RunPod serverless worker, a plain
# GPU pod, or a Vast.ai Serverless worker, all against the same SwarmUI install on the same
# network volume.
CMD ["/entrypoint.sh"]
