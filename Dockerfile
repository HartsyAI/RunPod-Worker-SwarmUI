# syntax=docker/dockerfile:1.7
#
# Hartsy SwarmUI worker for RunPod (Serverless and Pods).
# Everything provider-neutral (SwarmUI, the backend, the auth gateway, idle release) comes from
# SwarmUI-Worker-Base; this image adds only RunPod's SDK and handler.

ARG BASE_IMAGE=kalebbroo/swarmui-worker-base
ARG BASE_VERSION=1.0.0
ARG BACKEND=comfyui
FROM ${BASE_IMAGE}:${BASE_VERSION}-${BACKEND}

ARG VERSION=dev
ARG REVISION=unknown
LABEL org.opencontainers.image.title="swarmui-worker-runpod" \
      org.opencontainers.image.description="Hartsy SwarmUI worker for RunPod Serverless and Pods" \
      org.opencontainers.image.vendor="Hartsy" \
      org.opencontainers.image.url="https://hartsy.ai" \
      org.opencontainers.image.source="https://github.com/HartsyAI/RunPod-Worker-SwarmUI" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${REVISION}"

COPY --chown=swarm:swarm requirements.txt /opt/worker/requirements.txt
RUN /opt/worker/venv/bin/pip install --no-cache-dir -r /opt/worker/requirements.txt

COPY --chown=swarm:swarm src/handler.py /opt/worker/handler.py
COPY --chown=swarm:swarm scripts/entrypoint.sh /opt/worker/entrypoint.sh

# The SDK prints at DEBUG by default, which logs every streamed output, lease tokens included.
ENV RUNPOD_LOG_LEVEL=INFO \
    WORKER_VERSION=${VERSION}

ENTRYPOINT ["/usr/bin/tini", "--", "/bin/bash", "/opt/worker/entrypoint.sh"]
