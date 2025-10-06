#!/usr/bin/env bash
# Build the SwarmUI RunPod Serverless image and optionally push to a registry.

set -euo pipefail

IMAGE_NAME=${IMAGE_NAME:-swarmui-runpod}
IMAGE_TAG=${IMAGE_TAG:-latest}
PUSH=${PUSH:-false}
REGISTRY=${REGISTRY:-}

FULL_TAG=${IMAGE_NAME}:${IMAGE_TAG}
if [[ -n "${REGISTRY}" ]]; then
  FULL_TAG="${REGISTRY}/${FULL_TAG}"
fi

printf "\n[build-image] Building image %s\n" "${FULL_TAG}"
docker build --platform linux/amd64 -t "${FULL_TAG}" .

if [[ "${PUSH}" == "true" ]]; then
  printf "\n[build-image] Pushing image %s\n" "${FULL_TAG}"
  docker push "${FULL_TAG}"
else
  printf "\n[build-image] Skipping push (set PUSH=true to push).\n"
fi
