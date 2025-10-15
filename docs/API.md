# Deployment Checklist – RunPod Worker SwarmUI

Use this checklist before publishing the worker as a public RunPod template.

---

## ✅ Prerequisites

- [ ] RunPod account with sufficient credits.
- [ ] Network volume created in the same region as your target GPUs.
- [ ] Optional Docker Hub repository if you maintain a custom image.
- [ ] Local environment with Python 3.11+ (for smoke tests).

---

## 📁 Repository Sanity Check

- [ ] `Dockerfile` builds the container (installs dependencies, copies `scripts/start.sh`, `src/rp_handler.py`).
- [ ] `scripts/start.sh` matches the current boot flow described in `docs/ARCHITECTURE.md`.
- [ ] `src/rp_handler.py` contains inline model helpers and keep-alive action.
- [ ] `builder/requirements.txt` lists handler dependencies (requests, runpod, python-dotenv, etc.).
- [ ] `tests/` directory includes:
  - `tests/test_endpoint.py`
  - `tests/test_model_management.py`
  - `tests/test_storage.py`
  - `tests/test_handler.py`
- [ ] `.env.example` reflects required environment variables (RunPod API, S3, Hugging Face token, timeouts).
- [ ] `docs/` folder updated (`ARCHITECTURE.md`, `SETUP.md`, `QUICKSTART.md`, this checklist).

---

## 🌐 Network Volume & Models

- [ ] Volume size ≥ 100 GB (adjust based on model catalog).
- [ ] Region aligns with the GPU region used in the endpoint.
- [ ] Optional: preload base models using the S3 credentials or a temporary pod.
- [ ] Confirm folder structure on volume matches SwarmUI expectations (e.g., `Models/Stable-Diffusion/...`).

---

## 🐳 Image Build & Registry (if applicable)

- [ ] `docker build --platform linux/amd64 -t youruser/runpod-worker-swarmui:tag .`
- [ ] `docker push youruser/runpod-worker-swarmui:tag`
- [ ] Template or README references the correct image/tag.

GitHub Actions workflow (optional):

- [ ] CI pipeline builds and publishes on push/main.
- [ ] Secrets configured (e.g., `DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`).

---

## ⚙️ Endpoint Deployment

- [ ] Create or update RunPod Serverless endpoint.
- [ ] Attach the correct network volume.
- [ ] Recommended config validated:
  - GPU: RTX 4090 (24 GB) or A100 40 GB/80 GB.
  - Active Workers: `0` (scale from cold starts).
  - Max Workers: ≥ `2`.
  - Idle Timeout: `120` seconds.
  - FlashBoot enabled.
- [ ] Environment variables appended (from `.env.example` as needed).
- [ ] First deployment observed until SwarmUI finishes installation (expect 20–30 minutes).

---

## 🧪 Functional Verification

After deployment, export the required env vars locally or update `.env`, then run:

- [ ] `python tests/test_endpoint.py --prompt "deployment checklist"`
- [ ] `python tests/test_model_management.py list`
- [ ] `python tests/test_model_management.py keep-alive --duration 180`
- [ ] `python tests/test_storage.py`
- [ ] `python -m unittest tests.test_handler`

Confirm outputs match expectations (images saved, models listed, keep-alive success message, tests green).

---

## 🧷 Template Metadata (for public release)

- [ ] Template name, description, and instructions updated in RunPod dashboard.
- [ ] Link to documentation (`docs/QUICKSTART.md`, `docs/SETUP.md`) added.
- [ ] Pricing and GPU recommendations clearly stated.

---

## 🛟 Troubleshooting Ready

- [ ] Logs explain cold start phases (SwarmUI install, ComfyUI install, ready message).
- [ ] `docs/SETUP.md` includes troubleshooting steps that mirror current behavior.
- [ ] Error messages in `src/rp_handler.py` are helpful (model metadata validation, missing parameters, etc.).

---

## 📣 Final Steps

- [ ] Share template link, documentation, and usage instructions.
- [ ] Monitor first few deployments for unexpected issues or user feedback.

Once every item is checked, your worker is ready for public consumption. 🎉
