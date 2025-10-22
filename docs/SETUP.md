# Complete Setup Guide

Comprehensive first-time setup instructions for deploying SwarmUI on RunPod Serverless.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create RunPod Account](#create-runpod-account)
3. [Create Network Volume](#create-network-volume)
4. [Deploy Container Image](#deploy-container-image)
5. [Configure Environment](#configure-environment)
6. [Trigger First Installation](#trigger-first-installation)
7. [Upload Models (Optional)](#upload-models-optional)
8. [Test the Deployment](#test-the-deployment)
9. [Next Steps](#next-steps)

---

## Prerequisites

**Required:**
- Credit card or payment method for RunPod
- Python 3.11+ (for testing)
- Git
- Basic command line knowledge

**Optional:**
- Docker (if building custom images)
- Docker Hub account (for publishing images)

**Estimated setup time:**
- Account creation: 5 minutes
- Deployment: 10 minutes
- First installation: 20-30 minutes
- **Total: ~45 minutes**

---

## Create RunPod Account

### Step 1: Sign Up

1. Go to [RunPod](https://runpod.io)
2. Click **"Sign Up"** or **"Get Started"**
3. Create account with:
   - Email + password, OR
   - Google account, OR
   - GitHub account

### Step 2: Add Payment Method

1. Go to [Billing](https://runpod.io/console/user/billing)
2. Click **"Add Payment Method"**
3. Enter credit card details
4. Add initial credits (minimum $10 recommended)

**Pricing:**
- RTX 4090: ~$0.89/hour (~$0.015/minute)
- A100 40GB: ~$1.89/hour
- Network volume: ~$0.07/GB/month

**Tip:** Start with $25-50 credits for testing.

### Step 3: Get API Key

1. Go to [Settings → API Keys](https://runpod.io/console/user/settings)
2. Click **"+ API Key"**
3. Name it: `swarmui-worker`
4. Copy the key and **save it securely**

**⚠️ Important:** You can only see the API key once. Store it safely!

---

## Create Network Volume

Network volumes store SwarmUI installation, models, and generated images across worker restarts.

### Step 1: Create Volume

1. Go to [Storage](https://runpod.io/console/storage)
2. Click **"+ New Network Volume"**
3. Configure:
   - **Name:** `swarmui-models`
   - **Size:** `100 GB` (minimum)
   - **Region:** Choose based on GPU availability:
     - `US-OR-1` (US West)
     - `US-TX-3` (US Central)  
     - `EU-RO-1` (Europe)
     - `US-GA-1` (US East)
4. Click **"Create"**
5. Wait ~1 minute for provisioning

### Step 2: Note Volume Details

After creation, note:
- **Volume ID** (e.g., `abc123xyz`)
- **Region** (must match your GPU region)

**Cost:** ~$7/month for 100GB storage

### Storage Requirements

| Content | Size |
|---------|------|
| SwarmUI + ComfyUI | ~10 GB |
| SDXL Model | ~7 GB |
| Flux Model | ~24 GB |
| Generated Images (1000) | ~5 GB |
| **Recommended** | **100-200 GB** |

**Tip:** You can always expand the volume later if needed.

---

## Deploy Container Image

### Option A: Use Published Image (Recommended)

If using a public template or pre-built image:

1. Go to [Serverless](https://runpod.io/console/serverless)
2. Click **"+ New Endpoint"**
3. Choose **"Use a Template"** (if available)
4. Or select **"Docker Image"** and enter: `youruser/swarmui-runpod:latest`

### Option B: Build Your Own Image

**Local build:**
```bash
# Clone repository
git clone https://github.com/youruser/runpod-worker-swarmui.git
cd runpod-worker-swarmui

# Build for AMD64 (RunPod architecture)
docker build --platform linux/amd64 -t youruser/swarmui-runpod:latest .

# Push to Docker Hub
docker login
docker push youruser/swarmui-runpod:latest
```

**Note your image URL:** `youruser/swarmui-runpod:latest`

---

## Configure Environment

### Step 1: Create Endpoint

1. Go to [Serverless](https://runpod.io/console/serverless)
2. Click **"+ New Endpoint"**
3. Configure:

**Basic Settings:**
- **Name:** `swarmui-worker`
- **Docker Image:** Your image URL from previous step
- **Docker Command:** Leave empty (uses CMD from Dockerfile)

**GPU Configuration:**
- **GPU Type:** 
  - RTX 4090 (24GB) - Good for SDXL ($0.89/hr)
  - A100 40GB - Good for Flux ($1.89/hr)
  - A100 80GB - For large models ($3.19/hr)
- **Active Workers:** `0` (cold start on demand)
- **Max Workers:** `3`
- **Idle Timeout:** `120` seconds
- **FlashBoot:** ✅ Enabled (faster cold starts)

**Storage:**
- **Container Disk:** `15 GB` (for installation)
- **Network Volume:** Select your volume from Step 2

**Advanced:**
- **Execution Timeout:** `3600` seconds (1 hour)
- **Request Timeout:** `3600` seconds

### Step 2: Add Environment Variables (Optional)

Click **"Environment Variables"** and add:

```
SWARMUI_HOST=0.0.0.0
SWARMUI_PORT=7801
STARTUP_TIMEOUT=1800
```

**Note:** These are optional - defaults work fine.

### Step 3: Deploy

1. Review configuration
2. Click **"Deploy"**
3. Wait for deployment (~1 minute)
4. Note your **Endpoint ID** (e.g., `abc123xyz`)

**Your endpoint URL will be:**
```
https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync
```

---

## Trigger First Installation

First run downloads and installs SwarmUI + ComfyUI to network volume.

### Step 1: Configure Local Environment

```bash
# Clone repository (if not already done)
git clone https://github.com/youruser/runpod-worker-swarmui.git
cd runpod-worker-swarmui

# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env with your credentials
nano .env  # or your preferred editor
```

Add to `.env`:
```bash
RUNPOD_ENDPOINT_ID=your-endpoint-id-here
RUNPOD_API_TOKEN=your-api-key-here
```

### Step 2: Start Installation

```bash
python scripts/trigger_install.py
```

**Expected output:**
```
================================================================================
SwarmUI RunPod Serverless - Installation Trigger
================================================================================

Endpoint: abc123xyz
Max wait: 1800s (30 minutes)

Note: First install takes 20-30 minutes
      Subsequent starts take 60-90 seconds

[  145s] Waiting: Not ready
[  160s] Waiting: Backend warming
...
✓ SwarmUI ready after 1247s (20 minutes)
```

**What's happening:**
1. Downloads SwarmUI installer (~5s)
2. Clones SwarmUI repository (~30s)
3. Installs SwarmUI (~2 min)
4. Downloads PyTorch (~3 min)
5. Installs ComfyUI (~5 min)
6. Builds and starts SwarmUI (~3 min)

**Total time: 20-30 minutes** (first run only!)

### Troubleshooting Installation

**Timeout after 30 minutes:**
- Check RunPod dashboard logs
- Verify network volume has 15GB+ free space
- Ensure container disk is 15GB+
- Try again - sometimes network is slow

**Connection errors:**
- Verify endpoint ID is correct
- Check API key is valid
- Ensure endpoint is active in dashboard

---

## Upload Models (Optional)

SwarmUI includes default models, but you may want to add custom ones.

### Method 1: Via Temporary Pod (Recommended for large models)

**Best for:** Bulk uploads, large models (5GB+)

1. Go to [Pods](https://runpod.io/console/pods)
2. Deploy cheap GPU pod (e.g., RTX 3070)
3. Attach your network volume
4. SSH into pod
5. Upload models:

```bash
cd /workspace  # Network volume mount point
mkdir -p Models/Stable-Diffusion/CustomModels

# Download model
wget https://huggingface.co/YOUR_USER/YOUR_MODEL/resolve/main/model.safetensors \
  -O Models/Stable-Diffusion/CustomModels/my-model.safetensors

# Verify
ls -lh Models/Stable-Diffusion/
```

6. Stop pod when done

**Directory structure:**
```
Models/
├── Stable-Diffusion/
│   ├── OfficialStableDiffusion/
│   └── CustomModels/
│       └── my-model.safetensors
├── LoRA/
├── VAE/
└── ControlNet/
```

### Method 2: Via SwarmUI API (Recommended for single models)

**Best for:** Downloading from URLs, automated setups

```python
import requests

# After worker is running
response = requests.post(
    f"{public_url}/API/DoModelDownloadWS",
    json={
        "url": "https://huggingface.co/...",
        "type": "Stable-Diffusion",
        "name": "my-custom-model"
    }
)
```

### Method 3: Via RunPod S3 API (Advanced)

**Best for:** Automated deployments, CI/CD

Requires S3 credentials from volume settings. See RunPod documentation.

---

## Test the Deployment

### Test 1: Health Check

```bash
python tests/test_direct_url.py --duration 600
```

**Expected:**
- ✓ Worker starts (60-90s)
- ✓ Public URL obtained
- ✓ Direct SwarmUI calls work
- ✓ Image generation successful

### Test 2: Simple Generation

```python
from examples.client import SwarmUIClient

client = SwarmUIClient("your-endpoint", "your-key")

# Wake up worker
public_url = client.wakeup(duration=600)  # 10 minutes
session_id = client.get_session(public_url)

# Generate test image
images = client.generate_image(
    public_url,
    session_id,
    "a beautiful sunset over mountains",
    width=512,
    height=512,
    steps=20
)

print(f"Success! Generated: {images[0]}")

client.shutdown()
```

### Test 3: Verify Models

```python
# List available models
models = client.list_models(public_url, session_id)
print(f"Available models: {len(models.get('files', []))}")
```

---

## Cost Estimates

**Initial Setup:**
- Free (just account creation)

**First Run:**
- ~20-30 minutes installation
- RTX 4090: ~$0.45-0.75
- A100: ~$0.95-1.40

**Per Generation:**
- 1024x1024, 30 steps, RTX 4090: ~$0.01
- 512x512, 20 steps, RTX 4090: ~$0.003

**Monthly Costs (if used daily):**
- Network volume (100GB): ~$7/month
- GPU usage (1 hour/day): ~$27/month
- **Total: ~$34/month**

**Tips to reduce costs:**
- Use appropriate idle timeout
- Shutdown when done
- Use smaller resolutions for testing
- Use faster models (SDXL Turbo, Flux Schnell)

---

## Common Issues

### Issue: "No GPU available"
**Solution:**
- Try different region
- Change GPU type
- Check RunPod status page
- Try off-peak hours

### Issue: "Network volume not found"
**Solution:**
- Verify volume is in same region as GPU
- Check volume is created and active
- Reattach volume to endpoint

### Issue: "Out of memory"
**Solution:**
- Use smaller model
- Reduce batch size
- Use appropriate GPU (SDXL needs 24GB+)
- Try quantized models (GGUF)

### Issue: "Cannot access public URL"
**Solution:**
- Verify worker is still alive
- Check keepalive duration hasn't expired
- Get fresh URL with `ready` check
- Review RunPod logs

---

## Security Best Practices

**✅ Do:**
- Keep API keys secret
- Use environment variables
- Rotate API keys periodically
- Monitor usage in dashboard
- Set spending limits

**❌ Don't:**
- Commit API keys to git
- Share endpoint URLs publicly
- Leave workers running indefinitely
- Use root credentials

---

## Next Steps

Now that your worker is deployed:

1. **[Workflow Guide](WORKFLOW.md)** - Learn the complete workflow
2. **[Client Usage Guide](CLIENT.md)** - Use the Python client
3. **[SwarmUI API Reference](SWARMUI_API.md)** - Explore all endpoints

**Ready to generate?**
```python
from examples.client import SwarmUIClient

client = SwarmUIClient("your-endpoint", "your-key")
public_url = client.wakeup(duration=3600)
session_id = client.get_session(public_url)

images = client.generate_image(
    public_url,
    session_id,
    "your amazing prompt here!"
)

print(f"Generated: {images[0]}")
```

---

## Support

**Need help?**
- **GitHub Issues:** Bug reports and features
- **[SwarmUI Discord](https://discord.gg/q2y38cqjNw):** SwarmUI questions
- **[RunPod Discord](https://discord.gg/runpod):** RunPod platform help

**Documentation:**
- [RunPod Documentation](https://docs.runpod.io)
- [SwarmUI Documentation](https://github.com/mcmonkeyprojects/SwarmUI/tree/master/docs)

---

## Summary

You now have:
- ✅ RunPod account with credits
- ✅ Network volume configured
- ✅ Serverless endpoint deployed
- ✅ SwarmUI installed and tested
- ✅ Working code examples

**First run:** 20-30 minutes  
**Warm starts:** 60-90 seconds  
**Cost per image:** ~$0.01 (RTX 4090)

**Ready to build! 🚀**
