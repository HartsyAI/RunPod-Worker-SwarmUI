# Setup Guide – RunPod Worker SwarmUI

Comprehensive instructions for provisioning infrastructure, deploying the worker, uploading models, and validating functionality.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create the Network Volume](#create-the-network-volume)
3. [Prepare the Repository](#prepare-the-repository)
4. [Build or Reuse the Container Image](#build-or-reuse-the-container-image)
5. [Deploy the RunPod Endpoint](#deploy-the-runpod-endpoint)
6. [Populate Models](#populate-models)
7. [Environment Variables](#environment-variables)
8. [Validation & Testing](#validation--testing)
9. [Connect Local SwarmUI (Optional)](#connect-local-swarmui-optional)
10. [Troubleshooting](#troubleshooting)
11. [Support & Resources](#support--resources)

---

## Prerequisites

- RunPod account with sufficient credits.
- Access to a RunPod network volume (100 GB minimum recommended).
- Local workstation with:
  - Python 3.11+
  - Docker CLI (if building images yourself)
  - Git
- Optional: Docker Hub (or other registry) credentials for publishing custom images.

---

## Create the Network Volume

1. Visit [RunPod Storage](https://runpod.io/console/storage).
2. Click **“+ New Network Volume.”**
3. Configure:
   - **Name:** `swarmui-models` (or any descriptive name)
   - **Size:** 100 GB+ (increase if you plan to host many models)
   - **Region:** Match the GPU region you intend to deploy in (e.g., `EU-RO-1`, `US-OR-1`).
4. Create and wait for provisioning (≈1 minute).

> **Tip:** Volumes cost ~$0.07/GB/month, so 100 GB ≈ $7/month.

---

## Prepare the Repository

Clone the project and install local dependencies used by the handler and CLI scripts.

```bash
git clone https://github.com/YOUR_USERNAME/runpod-worker-swarmui.git
cd runpod-worker-swarmui
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r builder/requirements.txt
```

Copy `.env.example` to `.env` and fill in values you already have (RunPod tokens, S3 credentials, Hugging Face token). This file is a convenience for local testing; do **not** commit it.

---

## Build or Reuse the Container Image

### Option A – Use an existing published image

If you are consuming the project’s public template, note the image tag (e.g., `youruser/runpod-worker-swarmui:latest`) and skip to [Deploy the RunPod Endpoint](#deploy-the-runpod-endpoint).

### Option B – Build the image locally

```bash
docker build --platform linux/amd64 -t youruser/runpod-worker-swarmui:latest .
docker push youruser/runpod-worker-swarmui:latest
```

Ensure the image tag in your RunPod template or deployment matches the pushed image.

---

## Deploy the RunPod Endpoint

1. Navigate to [RunPod Serverless](https://runpod.io/console/serverless/user/endpoints) and create a new endpoint.
2. Choose the container image (either the published tag or the one you built).
3. Attach your network volume (must be the same region as the GPU).
4. Recommended configuration:
   - **GPU:** RTX 4090 (24 GB) or A100 40 GB/80 GB depending on model footprint.
   - **Active Workers:** `0` (allow cold starts when jobs arrive).
   - **Max Workers:** `2–3` initially.
   - **Idle Timeout:** `120` seconds.
   - **FlashBoot:** Enabled.
   - **Container Disk:** 15 GB (to accommodate SwarmUI + ComfyUI install).
5. Add environment variables as needed (see [Environment Variables](#environment-variables)).
6. Deploy and monitor logs. First-time install downloads SwarmUI and ComfyUI to the network volume and can take 20–30 minutes. You should eventually see log lines indicating SwarmUI readiness.

---

## Populate Models

You can preload models before the first cold start or let SwarmUI download them later.

### Option 1 – Upload via temporary pod

1. Deploy a low-cost GPU pod with the same network volume attached.
2. SSH into the pod and navigate to `/workspace` (network volume mount point for pods).
3. Create directories if needed and download models:

   ```bash
   cd /workspace
   mkdir -p Models/Stable-Diffusion
   cd Models/Stable-Diffusion
   wget https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors
   ```

4. Verify structure resembles:

   ```
   /workspace/Models/
   ├── Stable-Diffusion/
   │   └── sd_xl_base_1.0.safetensors
   ├── Loras/
   ├── VAE/
   └── ControlNet/
   ```

5. Stop the pod to avoid ongoing charges.

### Option 2 – Upload via S3-compatible API

1. Retrieve S3 credentials from the RunPod volume dashboard.
2. Use AWS CLI or a GUI client (Cyberduck, WinSCP, etc.) to upload models directly:

   ```bash
   aws s3 cp sd_xl_base_1.0.safetensors \
     s3://YOUR_VOLUME_ID/Models/Stable-Diffusion/ \
     --endpoint-url https://s3api-REGION.runpod.io/ \
     --profile runpod
   ```

3. Confirm uploaded files in the RunPod storage console or via `tests/test_storage.py` (see [Validation & Testing](#validation--testing)).

---

## Environment Variables

The following variables drive scripts and runtime behavior. Populate them in your `.env`, RunPod endpoint configuration, or shell environment.

| Variable | Description |
|----------|-------------|
| `SWARMUI_API_URL` | Internal URL the handler uses to reach SwarmUI (default `http://127.0.0.1:7801`). |
| `STARTUP_TIMEOUT` | Seconds to wait for SwarmUI readiness on cold start (default `1800`). |
| `GENERATION_TIMEOUT` | Per-image-generation timeout in seconds (default `600`). |
| `HUGGINGFACE_API_TOKEN` | Token used by the handler to authorize gated model downloads. |
| `RUNPOD_ENDPOINT_ID` | Default endpoint ID consumed by test scripts when the flag is omitted. |
| `RUNPOD_API_TOKEN` | RunPod API token for tests and automation. |
| `RUNPOD_ENDPOINT_URL` | S3 endpoint for RunPod storage (e.g., `https://s3api-EU-RO-1.runpod.io/`). |
| `RUNPOD_ACCESS_KEY` / `RUNPOD_SECRET_ACCESS_KEY` | Credentials for RunPod S3 operations. |
| `RUNPOD_TRAINING_STORAGE_REGION` | Region for S3 operations (e.g., `EU-RO-1`). |
| `RUNPOD_TRAINING_STORAGE_VOLUME_ID` | The volume/bucket identifier used for S3 uploads. |
| `RUNPOD_S3_PREFIX` | Optional prefix within the volume when uploading models. |

`scripts/start.sh` additionally respects `SWARMUI_HOST`, `SWARMUI_PORT`, and `VOLUME_PATH` if you need to change default bindings.

---

## Validation & Testing

Once the endpoint is deployed and environment variables are configured locally, run the provided scripts to confirm functionality.

### 1. Image generation smoke test

```bash
python tests/test_endpoint.py --prompt "swarmui worker smoke test"
```

Expected output:
- Job completes without error.
- Response JSON prints to the console.
- Generated images (if any) saved under `output/`.

### 2. Model management CLI

```bash
python tests/test_model_management.py list
python tests/test_model_management.py describe OfficialStableDiffusion/sd_xl_base_1.0
python tests/test_model_management.py keep-alive --duration 300 --interval 30
```

Verify that model lists populate, metadata responses look correct, and keep-alive reports success.

### 3. Storage inventory helper

```bash
python tests/test_storage.py
```

Confirms the S3 credentials are valid and prints a roster of model files.

### 4. Unit tests

```bash
python -m unittest tests.test_handler
```

Ensures handler helper functions behave as expected.

---

## Connect Local SwarmUI (Optional)

1. Launch SwarmUI locally (no GPU required if you only want to relay jobs).
2. Navigate to **Server → Backends** and click **Add Backend**.
3. Select **Swarm-API-Backend** and configure:
   - **Address:** `https://api.runpod.io/v2/YOUR_ENDPOINT_ID/swarmui`
   - **Title:** `RunPod Cloud GPU`
   - **API Key:** leave blank unless you configured authentication.
4. Save and wait up to 60 seconds for the backend to turn green (cold start warm-up).
5. Generate an image from the local UI to confirm traffic is forwarded to RunPod.

---

## Troubleshooting

### Cold start takes too long
- Expect 20–30 minutes the first time while SwarmUI + ComfyUI install on the volume.
- Subsequent starts should be 60–90 seconds.
- Ensure your network volume remains attached and container disk size is ≥15 GB.

### `keep_alive` reports failures
- Verify the endpoint is active and `RUNPOD_API_TOKEN` is valid.
- Review handler logs (`/API/GetNewSession` may return transient errors during boot).

### Model not found / metadata errors
- Confirm model files reside under `/runpod-volume/Models/...` using the correct SwarmUI naming scheme.
- Use `tests/test_model_management.py describe` to inspect available models.

### Request timeouts
- Decrease resolution, steps, or number of images in the generation payload.
- Increase `GENERATION_TIMEOUT` via environment variables if necessary.

### Authentication errors when downloading models
- Ensure `HUGGINGFACE_API_TOKEN` is set for gated models (Flux, SD3.5 GGUF, etc.).
- For manual downloads using `scripts/download_models.py`, supply `--token` or set the env variable.

### Logs unclear or missing
- Check RunPod endpoint logs for combined output from `scripts/start.sh` and `src/rp_handler.py`.
- Add additional logging statements in the handler if publishing a customized template.

---

## Support & Resources

- **Documentation:**
  - `docs/ARCHITECTURE.md` – internals of the worker.
  - `docs/QUICKSTART.md` – condensed version of this guide.
  - `docs/DEPLOYMENT_CHECKLIST.md` – pre-release checklist.
- **Communities:**
  - [SwarmUI Discord](https://discord.gg/q2y38cqjNw)
  - [RunPod Discord](https://discord.gg/runpod)
- **Issue tracking:** open bugs or feature requests via GitHub Issues in this repository.

Happy building! 🎯
