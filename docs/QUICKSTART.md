# Quick Start

Launch the SwarmUI RunPod Serverless worker, verify image generation, and exercise model management in under an hour.

---

## 1. Prerequisites

- **RunPod account** with funds for serverless GPU time.
- **Network volume** ready (100 GB+ recommended). See `docs/SETUP.md` if you still need to create one.
- **Python 3.11+** and `pip` installed locally for the test scripts.
- Optional: Docker Hub account if you plan to publish your own image.

---

## 2. Clone and Install Local Requirements

```bash
git clone https://github.com/YOUR_USERNAME/runpod-worker-swarmui.git
cd runpod-worker-swarmui
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r builder/requirements.txt
```

Copy `.env.example` to `.env` and fill in the environment variables that apply to your workflow (RunPod endpoint ID, API token, S3 credentials, Hugging Face token, etc.).

---

## 3. Build or Use the Container Image

### Option A – Use the published image

If you are consuming an existing template/image, note its repository (for example `youruser/runpod-worker-swarmui:latest`) and skip to deployment.

### Option B – Build the image locally

```bash
docker build --platform linux/amd64 -t youruser/runpod-worker-swarmui:latest .
docker push youruser/runpod-worker-swarmui:latest
```

---

## 4. Deploy the Serverless Endpoint

1. Open [RunPod Serverless](https://runpod.io/console/serverless/user/endpoints) and create a new endpoint.
2. Select the template or Docker image from step 3.
3. Attach your network volume and confirm it resides in the same region as your target GPU.
4. Recommended launch settings:
   - **GPU:** RTX 4090 (24 GB) for SDXL, A100 40 GB+ for Flux or larger models.
   - **Active Workers:** `0` (let the service scale from cold starts).
   - **Max Workers:** `2–3` initially.
   - **Idle Timeout:** `120` seconds.
   - **FlashBoot:** Enabled (reduces cold start time).
5. Save and deploy. First installation (SwarmUI + ComfyUI) can take 20–30 minutes; watch logs for progress.

---

## 5. Configure Local Environment Variables

With the endpoint running, export the required variables or rely on the `.env` file you populated earlier. For PowerShell:

```powershell
$env:RUNPOD_ENDPOINT_ID = "YOUR_ENDPOINT_ID"
$env:RUNPOD_API_TOKEN = "YOUR_RUNPOD_API_TOKEN"
$env:RUNPOD_ENDPOINT_URL = "https://s3api-REGION.runpod.io/"
$env:RUNPOD_ACCESS_KEY = "YOUR_S3_ACCESS_KEY"
$env:RUNPOD_SECRET_ACCESS_KEY = "YOUR_S3_SECRET_KEY"
$env:RUNPOD_TRAINING_STORAGE_REGION = "REGION"
$env:RUNPOD_TRAINING_STORAGE_VOLUME_ID = "YOUR_VOLUME_ID"
$env:HUGGINGFACE_API_TOKEN = "YOUR_HF_TOKEN"
```

Adjust for your shell as needed. These values let the provided scripts talk to both the RunPod API and your S3-compatible storage.

---

## 6. Run Smoke Tests

### Image generation

```bash
python tests/test_endpoint.py --prompt "first light on the horizon"
```

Images are saved to `output/` on success.

### Model management

List available models, describe metadata, trigger downloads, or keep a worker warm:

```bash
python tests/test_model_management.py list
python tests/test_model_management.py describe OfficialStableDiffusion/sd_xl_base_1.0
python tests/test_model_management.py keep-alive --duration 300 --interval 30
```

These commands rely on the environment variables from step 5 when flags are omitted.

### Storage inventory (optional)

```bash
python tests/test_storage.py
```

This prints a table of models currently stored in your RunPod volume via the S3 API.

---

## 7. Connect Local SwarmUI (Optional)

1. Launch SwarmUI on your workstation (CPU-only is fine).
2. Go to **Server → Backends → Add Backend**.
3. Choose **Swarm-API-Backend** and configure:
   - **Address:** `https://api.runpod.io/v2/YOUR_ENDPOINT_ID/swarmui`
   - **Title:** `RunPod Cloud GPU`
   - **API Key:** leave blank unless you added authentication.
4. Save. The backend turns green once the serverless worker is awake. Generate an image from the local UI to confirm routing.

---

## 8. Next Steps

- Walk through the full `docs/SETUP.md` for advanced deployment, model upload, and troubleshooting guidance.
- Follow `docs/DEPLOYMENT_CHECKLIST.md` prior to publishing a public template.
- Review `docs/ARCHITECTURE.md` to understand the boot process and extensibility points.

Happy generating! 🎨
