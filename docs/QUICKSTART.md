# Quick Start

Get SwarmUI generating images on RunPod Serverless in less than 15 minutes.

---

## 1. Prepare Accounts & Tools

- **RunPod Account** – add at least $10 in credits.
- **Docker Hub Account** – optional if you want to publish custom images.
- **GitHub Account** – optional for CI/CD.
- **Python 3.11+** – required for the `test_endpoint.py` script.

---

## 2. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/runpod-swarmui-serverless.git
cd runpod-swarmui-serverless
```

If you forked the project, replace `YOUR_USERNAME` with your GitHub handle.

---

## 3. Build or Pull the Container Image

### Option A – Use a published image

Update the README badge and template configuration with the Docker image you want to use (for example `youruser/swarmui-runpod:latest`).

### Option B – Build locally

```bash
docker build --platform linux/amd64 -t youruser/swarmui-runpod:latest .
docker push youruser/swarmui-runpod:latest
```

---

## 4. Create a RunPod Network Volume

1. Navigate to [RunPod Storage](https://runpod.io/console/storage).
2. Click **“+ New Network Volume.”**
3. Allocate **at least 100 GB** (more if you plan to host many models or custom nodes).
4. Choose a data center that matches the GPU region you intend to deploy in.
5. Wait for provisioning to complete (≈1 minute).

> **Tip:** Upload models now using a temporary pod so your first serverless cold start is faster. See `docs/SETUP.md` for detailed model upload steps.

---

## 5. Deploy the Serverless Endpoint

1. Go to [RunPod Serverless](https://runpod.io/console/serverless/user/endpoints).
2. Click **“+ New Endpoint.”**
3. Select your SwarmUI template (or provide the Docker image name).
4. Attach the network volume created in the previous step.
5. Recommended configuration:
   - **GPU:** RTX 4090 (24 GB) or A100 (40 GB/80 GB) depending on model size.
   - **Active Workers:** `0` (cost efficient).
   - **Max Workers:** `3`.
   - **Idle Timeout:** `120` seconds.
   - **FlashBoot:** Enabled.
6. Deploy and monitor logs. First-time installation can take **20–30 minutes** while SwarmUI and ComfyUI are installed to the volume.

---

## 6. Test the Endpoint

1. Grab your RunPod API key from the RunPod dashboard.
2. Run the helper script:

```bash
python test_endpoint.py \
  --endpoint YOUR_ENDPOINT_ID \
  --api-key YOUR_RUNPOD_API_KEY
```

3. The script saves generated images to the local `output/` directory.

For asynchronous testing, add the `--async` flag. Example prompts and more troubleshooting tips live in `docs/SETUP.md`.

---

## 7. Connect Your Local SwarmUI

1. Launch SwarmUI locally (no GPUs required).
2. Navigate to **Server → Backends**.
3. Add a **SwarmAPI Backend** using:
   - **URL:** `https://api.runpod.io/v2/YOUR_ENDPOINT_ID`
   - **Title:** `RunPod Cloud GPU`
4. Generate an image to confirm that your local UI forwards jobs to RunPod.

---

## 8. Next Steps

- Review the full deployment checklist in `docs/DEPLOYMENT_CHECKLIST.md`.
- Explore deeper configuration and automation in `docs/SETUP.md`.
- Read `docs/ARCHITECTURE.md` to understand how the worker bootstraps SwarmUI and ComfyUI.
- Open an issue or PR if you find a bug or want to contribute.

Happy generating! 🎨
