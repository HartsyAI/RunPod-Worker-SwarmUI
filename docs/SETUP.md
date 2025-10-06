# Setup Guide - SwarmUI RunPod Serverless

Comprehensive guide for deploying and using SwarmUI on RunPod Serverless.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [RunPod Setup](#runpod-setup)
3. [Network Volume Creation](#network-volume-creation)
4. [Endpoint Deployment](#endpoint-deployment)
5. [Uploading Models](#uploading-models)
6. [Connecting Local SwarmUI](#connecting-local-swarmui)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### Requirements

- RunPod account with funds
- Local SwarmUI installation (for using as remote backend)
- Basic understanding of APIs and endpoints

### Recommended Knowledge

- Docker basics (if building custom images)
- SSH/FTP for file transfers (for model uploads)
- Command line familiarity

## RunPod Setup

### Step 1: Create RunPod Account

1. Go to [RunPod.io](https://runpod.io)
2. Sign up for an account
3. Add credits to your account (minimum $10 recommended)

### Step 2: Generate API Key (Optional)

If you plan to use authentication:

1. Go to Settings → API Keys
2. Click "Generate API Key"
3. Copy and save securely
4. Use this key when connecting from local SwarmUI

## Network Volume Creation

Network volumes store your models persistently across workers.

### Why Use Network Volumes?

- **Persistent Storage**: Models persist between worker restarts
- **Faster Cold Starts**: Workers don't re-download models
- **Cost Efficient**: Pay for storage, not repeated downloads
- **Shared Across Workers**: Multiple workers access same models

### Create Network Volume

1. Navigate to [RunPod Storage](https://runpod.io/console/storage)
2. Click **"+ New Network Volume"**
3. Configure:
   - **Name**: `swarmui-models` (or your preferred name)
   - **Size**: 
     - 50GB minimum (basic models)
     - 100GB recommended (multiple SD/SDXL models)
     - 500GB+ (extensive collection with Flux, etc.)
   - **Datacenter**: Choose based on:
     - GPU availability in that region
     - Your location (for upload speed)
     - Recommended: `EU-RO-1` or `US-GA` for high availability
4. Click **"Create"**
5. Wait for provisioning (~1 minute)

### Cost Calculation

Network volume pricing: $0.07/GB/month (first 1TB)

Examples:
- 50GB = $3.50/month
- 100GB = $7.00/month
- 500GB = $35.00/month

## Endpoint Deployment

### Option A: One-Click Deploy (Recommended)

1. Click the "Deploy to RunPod" button in README
2. Skip to "Configure Endpoint" below

### Option B: Manual Deployment

1. Go to [RunPod Serverless](https://runpod.io/console/serverless)
2. Click **"+ New Endpoint"**
3. Search for "SwarmUI" in community templates
4. Click **"Deploy"**

### Configure Endpoint

#### Basic Configuration

**Endpoint Name**: `swarmui-production`
- Choose a descriptive name
- You can have multiple endpoints (dev, prod, etc.)

**Select GPU**:
- **RTX 4090 (24GB)**: Best cost/performance for SDXL
- **RTX A6000 (48GB)**: For multiple large models
- **A100 (40GB/80GB)**: Maximum performance, higher cost

GPU Selection Tips:
```
SD 1.5 models → RTX 4090 (24GB) sufficient
SDXL models → RTX 4090 (24GB) recommended
Flux models → A100 (40GB) or better
Multiple models loaded → A100 (80GB)
```

#### Scaling Configuration

**Active Workers**:
- `0` = Cost-effective (cold start ~30-60s)
- `1` = Always-on (instant response, continuous billing)
- `2+` = High traffic (parallel processing)

**Max Workers**:
- Start with `2-3`
- Increase based on usage patterns
- Each worker can handle 1 generation at a time

**Idle Timeout**:
- `60s` = Aggressive cost savings
- `120s` = Balanced
- `300s` = Maximum availability

**Scale Type**:
- **Queue Delay** (recommended for most)
- **Request Count** (for predictable load)

#### Storage Configuration

**Select Network Volume**:
- Choose your created network volume
- IMPORTANT: Must be in same datacenter as GPU selection

**Container Disk**:
- `10GB` minimum (SwarmUI + ComfyUI)
- `15GB` recommended (with custom nodes)

#### Advanced Configuration

**Environment Variables** (optional):
```bash
# Auto-download default models on first start
AUTO_DOWNLOAD_MODELS=true

# Custom ComfyUI arguments
COMFY_ARGS=--highvram

# Startup timeout (increase if slow downloads)
STARTUP_TIMEOUT=600
```

### Deploy

1. Review all settings
2. Click **"Deploy"**
3. Wait for deployment (~2-3 minutes)

### Monitor First Startup

First startup takes 5-15 minutes:

1. Go to your endpoint
2. Click **"Logs"** tab
3. Watch for:
   ```
   SwarmUI Startup Script
   Installing ComfyUI backend...
   Starting SwarmUI server...
   SwarmUI is ready!
   ```

Common first-start delays:
- ComfyUI installation: 3-5 minutes
- Python dependencies: 2-3 minutes
- Model downloads: 5-10 minutes (if enabled)

## Uploading Models

### Method 1: Using a Pod (Recommended for Large Uploads)

1. **Start a GPU Pod**:
   - Go to GPU Cloud → Secure Cloud
   - Deploy any pod with your network volume attached
   - Choose low-cost GPU (doesn't matter for uploads)

2. **Connect via SSH**:
   ```bash
   ssh root@<pod-ssh-address>
   ```

3. **Navigate to volume**:
   ```bash
   cd /workspace
   # Your network volume is mounted here in Pods
   ```

4. **Upload models**:
   ```bash
   # Using wget
   cd Models/Stable-Diffusion
   wget https://huggingface.co/model/url/file.safetensors
   
   # Using curl
   curl -L -o model.safetensors https://url
   ```

5. **Organize models**:
   ```
   /workspace/Models/
   ├── Stable-Diffusion/
   │   ├── sd_xl_base_1.0.safetensors
   │   └── sd_xl_refiner_1.0.safetensors
   ├── Loras/
   │   └── my_lora.safetensors
   ├── VAE/
   │   └── vae-ft-mse-840000.safetensors
   └── ControlNet/
       └── control_v11p_sd15_openpose.pth
   ```

6. **Stop Pod** when done (to save costs)

### Method 2: Using S3-Compatible API

RunPod provides S3 API for direct uploads:

1. **Get S3 credentials**:
   - Go to your network volume settings
   - Find S3 endpoint and credentials

2. **Use AWS CLI**:
   ```bash
   aws configure --profile runpod
   # Enter credentials from volume settings
   
   aws s3 cp model.safetensors \
     s3://your-volume/Models/Stable-Diffusion/ \
     --profile runpod \
     --endpoint-url=https://your-endpoint
   ```

3. **Or use GUI tools**:
   - Cyberduck (Mac/Windows)
   - WinSCP (Windows)
   - FileZilla (any OS)

### Recommended Models

#### Essential Models (50-100GB)
```
Stable Diffusion XL Base 1.0 (6.9GB)
└─ https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0

Stable Diffusion XL Refiner 1.0 (6.1GB)
└─ https://huggingface.co/stabilityai/stable-diffusion-xl-refiner-1.0

SD 1.5 (4.2GB) - for compatibility
└─ https://huggingface.co/runwayml/stable-diffusion-v1-5
```

## Connecting Local SwarmUI

### Step 1: Get Endpoint URL

From your RunPod endpoint page:
```
Endpoint ID: abc123xyz
Your URL: https://api.runpod.io/v2/abc123xyz/
```

### Step 2: Add Backend to Local SwarmUI

1. Open local SwarmUI in browser
2. Navigate to **Server → Backends**
3. Click **"Add Backend"**
4. Select backend type: **"Swarm-API-Backend"**

### Step 3: Configure Backend

**Backend Configuration**:
```
Title: RunPod Cloud GPU
Backend Type: Swarm-API-Backend
Address: https://api.runpod.io/v2/YOUR_ENDPOINT_ID/swarmui
Port: (leave default 7801)
API Key: (leave empty unless you configured authentication)
```

**IMPORTANT**: 
- Add `/swarmui` to the end of the URL
- Complete URL example: `https://api.runpod.io/v2/abc123xyz/swarmui`

### Step 4: Save and Test

1. Click **"Save"**
2. Backend status should show green (may take 30-60s for cold start)
3. If red, check endpoint logs on RunPod

### Step 5: Set as Default (Optional)

To always use RunPod backend:
1. Go to **Server → Server Settings**
2. Find "Default Backend"
3. Select your RunPod backend

## Testing

### Test 1: Health Check

In local SwarmUI Backends page:
- RunPod backend should show "Connected" status
- If not, wait 60s for cold start

### Test 2: Simple Generation

1. Go to **Generate** tab
2. Enter prompt: `a beautiful landscape`
3. Click **Generate**
4. First generation: 30-90s (cold start + model load)
5. Second generation: 5-15s (depending on GPU)

### Test 3: Model Loading

1. Try different models
2. First load of each model will be slow
3. Subsequent uses should be fast (model cached in VRAM)

### Test 4: Batch Generation

1. Set **Image Count** to 4
2. Generate
3. Should see parallel processing (if max workers > 1)

## Troubleshooting

### Issue: Backend Shows Red/Disconnected

**Cause**: Worker not started or starting
**Solution**:
1. Wait 60s for cold start
2. Check endpoint logs for errors
3. Verify network volume is attached
4. Try triggering with a test request

### Issue: "Connection Refused"

**Cause**: Incorrect URL or worker not running
**Solution**:
1. Verify URL has `/swarmui` at end
2. Check endpoint is active (not paused)
3. Verify endpoint ID is correct
4. Test endpoint directly: `curl https://api.runpod.io/v2/YOUR_ID/health`

### Issue: Very Slow First Generation

**Cause**: This is normal for cold starts
**Expected Times**:
- Worker start: 30-60s
- Model download (first time): 5-10min
- Model load to VRAM: 10-30s

**Solutions**:
- Use 1 active worker for always-on
- Pre-download models to network volume
- Increase idle timeout

### Issue: "Out of Memory" Errors

**Cause**: Model too large for GPU VRAM
**Solutions**:
1. Use larger GPU (A100 40GB/80GB)
2. Reduce image resolution
3. Use fewer attention/upscale steps
4. Don't load multiple large models simultaneously

### Issue: Models Not Found

**Cause**: Models not in correct path
**Solution**:
1. Check models are in: `/runpod-volume/Models/Stable-Diffusion/`
2. Not in subdirectories
3. Use Pod to verify file paths
4. Check file permissions

### Issue: High Costs

**Analysis**:
```
If bills are high, check:
- Are workers idling? (should be 0 active workers)
- Is idle timeout too long? (reduce to 60-120s)
- Are you using expensive GPUs unnecessarily?
```

**Cost Optimization**:
1. Set active workers to 0
2. Use smallest GPU that fits your models
3. Shorter idle timeout (60-120s)
4. Batch generations together
5. Use network volume (avoid redownloads)

### Issue: Request Timeouts

**Cause**: Generation taking too long for serverless timeout
**Solution**:
1. Reduce steps/resolution
2. Use faster samplers (DPM++ 2M, Euler A)
3. For very long generations, consider GPU Pods instead

## Advanced Topics

### Multiple Endpoints

You can have multiple endpoints for different purposes:
```
Endpoint 1: swarmui-sdxl (RTX 4090, SDXL only)
Endpoint 2: swarmui-flux (A100 40GB, Flux models)
Endpoint 3: swarmui-dev (testing)
```

Add each as separate backend in local SwarmUI.

### Custom Docker Image

To build your own image with pre-installed models:

1. Fork this repository
2. Modify Dockerfile to include models
3. Build: `docker build -t youruser/swarmui-custom .`
4. Push: `docker push youruser/swarmui-custom`
5. Deploy endpoint with your custom image

### Monitoring and Logs

**View Real-Time Logs**:
1. Go to endpoint page
2. Click "Logs" tab
3. See all worker activity

**Metrics to Monitor**:
- Request queue depth
- Active workers
- GPU utilization
- Cost per hour
- Cold start frequency

### Backup and Migration

**Backup Network Volume**:
1. Start a Pod with volume attached
2. SSH into Pod
3. Use `tar` or `rsync` to backup:
   ```bash
   tar -czf models-backup.tar.gz /workspace/Models/
   ```

**Migrate to New Volume**:
1. Create new volume
2. Start Pod with both volumes
3. Copy data: `cp -r /old-volume/* /new-volume/`

## Support

### Getting Help

1. **Check logs first**: Most issues show up in logs
2. **SwarmUI Discord**: [Join here](https://discord.gg/q2y38cqjNw)
3. **RunPod Discord**: [Join here](https://discord.gg/runpod)
4. **GitHub Issues**: Report bugs or request features

### Useful Links

- [SwarmUI Documentation](https://github.com/mcmonkeyprojects/SwarmUI/tree/master/docs)
- [RunPod Documentation](https://docs.runpod.io)
- [ComfyUI GitHub](https://github.com/comfyanonymous/ComfyUI)

---

**Next Steps**: Once everything is working, consider optimizing your setup and exploring advanced SwarmUI features!
