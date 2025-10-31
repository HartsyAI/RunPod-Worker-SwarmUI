# Complete Setup Guide

Comprehensive first-time setup instructions for deploying SwarmUI on RunPod Serverless.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Create RunPod Account](#create-runpod-account)
3. [Create Network Volume](#create-network-volume)
4. [Deploy Container Image](#deploy-container-image)
5. [Configure Environment](#configure-environment)
6. [First-Time Installation](#first-time-installation)
7. [Upload Models (Optional)](#upload-models-optional)
8. [Test the Deployment](#test-the-deployment)
9. [Next Steps](#next-steps)

---

## Prerequisites

**Required:**
- Credit card or payment method for RunPod
- Python 3.7+ (for testing)
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
- RTX 4000 Ada (20GB): ~$0.39/hour - **Recommended for initial setup**
- RTX 4090 (24GB): ~$0.89/hour - Good for SDXL production
- A100 40GB: ~$1.89/hour - Good for Flux production
- Network volume: ~$0.07/GB/month

**Tip:** Start with $25-50 credits for testing. Initial setup costs ~$0.20 if using RTX 4000 Ada.

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

**⚠️ IMPORTANT: For first-time setup, use a cheap GPU:**

- **GPU Type:** **RTX 4000 Ada (20GB)** or **RTX A4000 (16GB)**
  - These cost ~$0.39-0.45/hour
  - First installation takes 20-30 minutes
  - Initial setup cost: ~$0.20
  
**After installation is complete, you can change to production GPUs:**
- **RTX 4090 (24GB)** - ~$0.89/hr - Good for SDXL
- **A100 40GB** - ~$1.89/hr - Good for Flux
- **A100 80GB** - ~$3.19/hr - For large models

**Other Settings:**
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

## First-Time Installation

**⚠️ CRITICAL: First run requires manual ComfyUI installation**

The initial setup has two phases:
1. Automatic SwarmUI installation (~5 minutes)
2. Manual ComfyUI installation via UI (~15-20 minutes)

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
python trigger_install.py
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

[   45s] Waiting: Not ready
[   60s] Waiting: Backend warming
...
✓ SwarmUI ready after 320s (5 minutes)
  Version: 0.6.5-Beta
  Session: 9D3534E30DA3...
```

**Phase 1: Automatic SwarmUI Installation (~5 minutes)**

What happens automatically:
1. Downloads SwarmUI installer
2. Clones SwarmUI repository
3. Installs SwarmUI
4. Downloads PyTorch
5. Starts SwarmUI server

When you see "SwarmUI ready", the script will show you the public URL:
```
================================================================================
✓ Installation Complete - Worker Ready
================================================================================

Public URL: https://abc123-7801.proxy.runpod.net

IMPORTANT: You must manually install ComfyUI:
1. Open the URL above in your browser
2. Click "Install ComfyUI Backend"
3. Accept the terms and conditions
4. Wait for installation to complete (15-20 minutes)
```

### Step 3: Manual ComfyUI Installation

**⚠️ REQUIRED: You must do this step manually**

1. **Open the public URL in your browser:**
   ```
   https://abc123-7801.proxy.runpod.net
   ```

2. **You will see SwarmUI interface**
   - Look for "Install ComfyUI" button or prompt
   - Click the button

3. **Accept Terms:**
   - Read and accept ComfyUI terms and conditions
   - Click "Install" or "Accept and Install"

4. **Wait for installation:**
   - Installation takes 15-20 minutes
   - Progress will show in the UI
   - **DO NOT close the browser or stop the worker**

5. **Set Logs to Debug (Recommended):**
   - In SwarmUI, go to Settings
   - Find "Log Level" setting
   - Set to **"Debug"**
   - This helps diagnose if installation hangs

### Step 4: Monitor Installation

**Check installation progress:**
- SwarmUI UI will show progress bars
- Check RunPod dashboard logs for detailed output
- Debug logs show exactly what's happening

**Installation steps (visible in logs):**
```
[INFO] Starting ComfyUI installation...
[INFO] Downloading ComfyUI...
[INFO] Installing Python packages...
[INFO] Installing PyTorch...
[INFO] Building ComfyUI...
[INFO] Testing ComfyUI...
[SUCCESS] ComfyUI installation complete!
```

### Step 5: Handle Installation Issues

**⚠️ Known Issue: ComfyUI Installation Sometimes Hangs**

**Symptoms:**
- Progress bar stops moving for >5 minutes
- No new logs appearing
- UI becomes unresponsive

**Solution:**

1. **Check if truly stuck:**
   - Look at debug logs in SwarmUI UI
   - Check RunPod dashboard logs
   - Wait at least 5 minutes (downloads can be slow)

2. **If stuck, restart the worker:**
   - Go to RunPod dashboard
   - Find your active worker
   - Click "Terminate" or "Stop"
   - Wait for worker to stop

3. **Run installation again:**
   ```bash
   python trigger_install.py
   ```
   - Open public URL again
   - Install ComfyUI again
   - Usually works within 2-3 attempts

**Why this happens:**
- Likely RunPod network issue
- Large file downloads timing out
- PyTorch install sometimes gets stuck
- Not your fault - it's a known issue

**Tips:**
- Try at different times of day
- US regions tend to be more stable
- Debug logs help identify exactly where it's stuck

### Step 6: Verify Installation

**After ComfyUI installation completes:**

1. **SwarmUI should show:**
   - "ComfyUI Backend: Active"
   - Green status indicator
   - Models available in dropdown

2. **Test generation:**
   - Enter a simple prompt: "a red ball"
   - Select a model (SDXL Base)
   - Click Generate
   - Should work within 30-60 seconds

3. **Check logs:**
   ```
   [SUCCESS] Backend initialized
   [SUCCESS] Model loaded: sd_xl_base_1.0
   [INFO] Generation started
   [SUCCESS] Image generated
   ```

**If test generation works, installation is complete! 🎉**

### Installation Complete

**What you now have:**
- ✅ SwarmUI installed on network volume
- ✅ ComfyUI backend installed and working
- ✅ Default models available
- ✅ Future startups take only 60-90 seconds

**Next steps:**
1. Change GPU to more powerful one (RTX 4090 or A100)
2. Upload custom models (optional)
3. Test with your SwarmUI extension
4. Start generating!

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
python test_direct_url.py --duration 600
```

**Expected:**
- ✓ Worker starts (60-90s after initial setup)
- ✓ Public URL obtained
- ✓ Direct SwarmUI calls work
- ✓ Image generation successful

### Test 2: Simple Generation

```python
from example_client import SwarmUIClient

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

**First Installation (RTX 4000 Ada):**
- ~30 minutes × $0.39/hr = ~$0.20

**After Setup (Normal Usage):**

**Per Generation:**
- 1024x1024, 30 steps, RTX 4090: ~$0.01
- 512x512, 20 steps, RTX 4090: ~$0.003

**Monthly Costs (if used daily):**
- Network volume (100GB): ~$7/month
- GPU usage (1 hour/day, RTX 4090): ~$27/month
- **Total: ~$34/month**

**Tips to reduce costs:**
- Use appropriate idle timeout
- Shutdown when done
- Use smaller resolutions for testing
- Use faster models (SDXL Turbo, Flux Schnell)
- Use RTX 4000 Ada instead of RTX 4090 when possible

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

### Issue: "ComfyUI installation hangs"
**Solution:**
- Set logs to Debug in SwarmUI UI
- Check what step it's stuck on
- Wait at least 5 minutes (downloads are slow)
- Restart worker and try again
- Usually works within 2-3 attempts

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
from example_client import SwarmUIClient

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
- ✅ SwarmUI + ComfyUI installed and tested
- ✅ Working code examples

**First installation:** 20-30 minutes  
**Warm starts:** 60-90 seconds  
**Cost per image:** ~$0.01 (RTX 4090)

**Ready to build! 🚀**
