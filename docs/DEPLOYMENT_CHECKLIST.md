# Deployment Checklist - SwarmUI RunPod Serverless

Complete checklist for deploying SwarmUI on RunPod Serverless.

## Prerequisites

- [ ] RunPod account created
- [ ] Credit added to RunPod account (minimum $10)
- [ ] Docker Hub account (for custom builds)
- [ ] GitHub account (optional, for GitHub deployment)

## File Structure Checklist

Your repository should have these files:

```
runpod-swarmui-serverless/
├── README.md                      # Landing page
├── Dockerfile                     # Container build instructions
├── start.sh                       # SwarmUI bootstrap script
├── src/
│   └── rp_handler.py             # RunPod handler (entry point)
├── builder/
│   └── requirements.txt          # Python dependencies for handler
├── test_input.json                # Sample payload for local tests
├── test_endpoint.py               # RunPod endpoint tester
├── docs/
│   ├── QUICKSTART.md             # Condensed deployment steps
│   ├── SETUP.md                  # Detailed setup & troubleshooting
│   └── DEPLOYMENT_CHECKLIST.md   # This checklist
├── LICENSE                        # MIT license
├── .gitignore                     # Git ignore file
├── .runpodignore                  # Files excluded from builds
└── (optional)
    ├── .env.example              # Example environment variables
    └── .github/workflows/*       # CI/CD automation
```

## Network Volume Setup

### Step 1: Create Network Volume

- [ ] Navigate to [RunPod Storage](https://runpod.io/console/storage)
- [ ] Click "+ New Network Volume"
- [ ] Configure:
  - Name: `swarmui-models`
  - Size: 100GB minimum (500GB recommended)
  - Datacenter: Choose based on GPU availability
- [ ] Click "Create"
- [ ] Wait for provisioning (~1 minute)

### Step 2: Upload Models (Optional but Recommended)

**Option A: Using a Temporary Pod**
- [ ] Go to GPU Cloud → Deploy Pod
- [ ] Select any GPU with your network volume attached
- [ ] Connect via SSH
- [ ] Navigate to `/workspace` (network volume mount point in Pods)
- [ ] Create directory structure:
  ```bash
  mkdir -p Models/Stable-Diffusion
  mkdir -p Models/Loras
  mkdir -p Models/VAE
  ```
- [ ] Upload models:
  ```bash
  cd Models/Stable-Diffusion
  wget https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors
  ```
- [ ] Terminate Pod when done

**Option B: Let First Run Download** (slower)
- [ ] SwarmUI will auto-install ComfyUI on first run
- [ ] Models can be downloaded through SwarmUI UI later

## Docker Image Build

### Option 1: GitHub Actions (Recommended)

- [ ] Fork this repository
- [ ] Add GitHub Secrets:
  - `DOCKERHUB_USERNAME`: Your Docker Hub username
- [ ] GitHub Actions will automatically build and push

### Option 2: Manual Build

- [x] Clone repository locally
- [x] Build image:
  ```bash
  docker build --platform linux/amd64 -t yourusername/swarmui-runpod:latest .
  ```
- [ ] Push to Docker Hub:
  ```bash
  docker push yourusername/swarmui-runpod:latest
  ```
{{ ... }}

- [x] Open local SwarmUI
- [x] Go to Server → Backends
- [x] Click "Add Backend"
- [x] Configure:
- [x] Click "Save"
- [x] Backend shows "Connected" (may take 60s)
s**: `https://api.runpod.io/v2/YOUR_ENDPOINT_ID`
  - **Title**: "RunPod Cloud GPU"
- [x] Click "Save"
- [x] Backend shows "Connected" (may take 60s)

### Test from Local SwarmUI
{{ ... }}
- [ ] Generate tab
- [ ] Enter prompt: "test image"
- [ ] Click Generate
- [ ] First generation: 60-90s (cold start)
- [ ] Second generation: 5-15s (warm)
- [ ] Image appears in gallery

## Cost Optimization Verification

- [ ] Active workers = 0 (no idle costs)
- [ ] Idle timeout = 120s or less
- [ ] Worker shuts down after timeout
- [ ] No unexpected charges

## Troubleshooting Checklist

### If Endpoint Won't Start

- [ ] Check logs for errors
- [ ] Verify network volume is attached
- [ ] Verify Docker image exists and is accessible
- [ ] Try redeploying endpoint

### If First Start Times Out

- [ ] Check container disk size (15GB minimum)
- [ ] Increase startup timeout in logs
- [ ] Check network volume has space
- [ ] Verify .NET and Python are installing correctly

### If Models Not Found

- [ ] Verify models are in `/runpod-volume/Models/Stable-Diffusion/`
- [ ] Check model file names match SwarmUI expectations
- [ ] Use Pod to verify file structure

### If Connection Refused from Local SwarmUI

- [ ] Verify endpoint URL is correct
- [ ] Check endpoint is active
- [ ] Trigger endpoint with test script first
- [ ] Check if authentication is needed

## Earning Credits (Template Creator Program)

### Eligibility

- [ ] Template must accumulate 1 day of total runtime
- [ ] Template must be published
- [ ] Users must use your template

### How to Earn

- [ ] Publish your template publicly
- [ ] Share template link with community
- [ ] Earn 1% of runtime spend from users
- [ ] Monitor earnings in RunPod dashboard

### Maximize Earnings

- [ ] Create good documentation
- [ ] Make template easy to use
- [ ] Support users with issues
- [ ] Share in SwarmUI Discord
- [ ] Write tutorials/guides

## Next Steps

Once everything is working:

- [ ] Optimize your workflow
- [ ] Add more models to network volume
- [ ] Experiment with different GPUs
- [ ] Set up monitoring/alerts
- [ ] Document your custom configurations
- [ ] Share your setup with community

## Support Resources

- **SwarmUI Discord**: [Join](https://discord.gg/q2y38cqjNw)
- **RunPod Discord**: [Join](https://discord.gg/runpod)
- **GitHub Issues**: [Report](https://github.com/YOUR_USERNAME/runpod-swarmui-serverless/issues)
- **Documentation**: See SETUP.md and ARCHITECTURE.md

---

**Completion**: When all items are checked, your SwarmUI serverless setup is complete!
