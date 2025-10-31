# SwarmUI RunPod Serverless - Direct URL Access

**Wake up a SwarmUI worker, get a public URL, and make direct API calls.**

This serverless worker exposes SwarmUI on a public URL so you can access its API directly without routing through the handler.

---

## 📚 Documentation

**Getting Started:**
1. **[Setup Guide](SETUP.md)** ⭐ Start here for first-time deployment
2. **[Workflow Guide](WORKFLOW.md)** - Complete step-by-step workflow walkthrough
3. **[Client Usage Guide](CLIENT.md)** - Using the Python client class
4. **[SwarmUI API Reference](SWARMUI_API.md)** - Complete API documentation

**Quick links:**
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Handler API](#handler-api)
- [Complete Example](#complete-example)
- [Testing](#testing)

---

## How It Works

```
1. Send "wakeup" request to RunPod
   ↓
2. Worker starts and returns public URL
   ↓
3. Make direct SwarmUI API calls to that URL
   ↓
4. Handler keeps worker alive by pinging SwarmUI
   ↓
5. Send "shutdown" when done (or let keepalive expire)
```

**Public URL format:**
```
https://{worker-id}-7801.proxy.runpod.net
```

You can access SwarmUI directly at this URL while the worker is alive.

**💡 For complete workflow details, see the [Workflow Guide](WORKFLOW.md)**

---

## Quick Start

### 1. Deploy Endpoint

**⚠️ Important for First Setup:**
Use a **cheap GPU** for initial installation (takes 20-30 minutes). You can change to more powerful GPUs later.

Recommended for first setup:
- **RTX 4000 Ada** (20GB) - ~$0.39/hour
- **RTX A4000** (16GB) - ~$0.45/hour

For production use (after setup):
- **RTX 4090** (24GB) - ~$0.89/hour - Good for SDXL
- **A100 40GB** - ~$1.89/hour - Good for Flux

**Setup Steps:**

1. Go to [RunPod Serverless](https://runpod.io/console/serverless)
2. Create endpoint with this Docker image: `youruser/swarmui-runpod:latest`
3. Attach a network volume (100GB+)
4. Configure:
   - GPU: **RTX 4000 Ada** (for initial setup)
   - Active Workers: 0
   - Max Workers: 3
   - Idle Timeout: 120s
   - FlashBoot: Enabled

**💡 For complete setup instructions, see the [Setup Guide](SETUP.md)**

### 2. First-Time Installation (20-30 minutes)

**The first run installs SwarmUI and requires manual ComfyUI installation:**

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your endpoint ID and API key

# Start first installation
python trigger_install.py
```

**What happens:**
1. Worker starts and installs SwarmUI (~5 minutes)
2. Script shows public URL
3. **You must manually open the URL in browser**
4. **Click "Install ComfyUI" and accept terms in SwarmUI UI**
5. Wait for ComfyUI installation to complete (~15-20 minutes)

**⚠️ Known Issue: ComfyUI Install Hangs**

If the ComfyUI installation appears to hang:
1. Set logs to **Debug** in SwarmUI UI to check status
2. If truly stuck, restart the worker via RunPod dashboard
3. Run `python trigger_install.py` again
4. Repeat ComfyUI installation until it completes

This is a known issue (likely RunPod network related). Usually succeeds within 2-3 attempts.

**After first installation is complete:**
- SwarmUI + ComfyUI stored on network volume
- Future starts take only 60-90 seconds
- You can change to more powerful GPU in RunPod settings

### 3. Wake Up Worker

**After initial setup, normal usage:**

```python
import requests

endpoint_id = "your-endpoint-id"
api_key = "your-api-key"

# Wake up worker (keeps alive for 1 hour)
response = requests.post(
    f"https://api.runpod.ai/v2/{endpoint_id}/runsync",
    json={
        "input": {
            "action": "wakeup",
            "duration": 3600,  # 1 hour
            "interval": 30      # ping every 30s
        }
    },
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=3700
)

result = response.json()["output"]
public_url = result["public_url"]
print(f"SwarmUI URL: {public_url}")
```

**Note:** The wakeup request blocks for the full duration (1 hour in this case) to keep the worker alive. Start it in a background thread if needed.

**💡 Want a simpler way? Check out the [Client Usage Guide](CLIENT.md) for a ready-to-use Python class**

### 4. Make Direct SwarmUI API Calls

```python
# Get session
response = requests.post(f"{public_url}/API/GetNewSession")
session_id = response.json()["session_id"]

# Generate image
response = requests.post(
    f"{public_url}/API/GenerateText2Image",
    json={
        "session_id": session_id,
        "prompt": "a beautiful mountain landscape",
        "model": "OfficialStableDiffusion/sd_xl_base_1.0",
        "width": 1024,
        "height": 1024,
        "steps": 30
    },
    timeout=600
)

images = response.json()["images"]
print(f"Generated: {images}")
```

**💡 For all available SwarmUI endpoints, see the [SwarmUI API Reference](SWARMUI_API.md)**

### 5. Shutdown When Done

```python
requests.post(
    f"https://api.runpod.ai/v2/{endpoint_id}/runsync",
    json={"input": {"action": "shutdown"}},
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=30
)
```

---

## Complete Example

See `example_client.py` for a reusable client class:

```python
from example_client import SwarmUIClient

# Initialize
client = SwarmUIClient("your-endpoint", "your-key")

# Wake up and get URL
public_url = client.wakeup(duration=3600)  # 1 hour

# Get session
session_id = client.get_session(public_url)

# Generate images
images = client.generate_image(
    public_url,
    session_id,
    "a serene ocean sunset",
    width=1024,
    height=1024,
    steps=30
)

# Shutdown
client.shutdown()
```

**💡 This example uses our pre-built client. For manual implementation details, see the [Workflow Guide](WORKFLOW.md)**

---

## Handler API

The handler provides simple actions for worker management. All responses include worker status and public URL.

### `wakeup` - Start Worker and Get URL

**Request:**
```json
{
  "input": {
    "action": "wakeup",
    "duration": 3600,
    "interval": 30
  }
}
```

**Response:**
```json
{
  "output": {
    "success": true,
    "public_url": "https://abc123-7801.proxy.runpod.net",
    "session_id": "def456...",
    "version": "0.6.5-Beta",
    "worker_id": "abc123",
    "keepalive": {
      "duration": 3600,
      "pings": 120,
      "failures": 0
    }
  }
}
```

**Notes:**
- Request blocks for full duration (keeps worker alive)
- Run in background thread if needed
- Worker auto-shuts down after duration expires

### `ready` - Check Status

**Request:**
```json
{
  "input": {
    "action": "ready"
  }
}
```

**Response:**
```json
{
  "output": {
    "ready": true,
    "public_url": "https://abc123-7801.proxy.runpod.net",
    "session_id": "def456...",
    "version": "0.6.5-Beta",
    "worker_id": "abc123"
  }
}
```

### `health` - Quick Health Check

**Request:**
```json
{
  "input": {
    "action": "health"
  }
}
```

**Response:**
```json
{
  "output": {
    "healthy": true,
    "public_url": "https://abc123-7801.proxy.runpod.net",
    "worker_id": "abc123"
  }
}
```

### `keepalive` - Extend Worker Lifetime

**Request:**
```json
{
  "input": {
    "action": "keepalive",
    "duration": 1800,
    "interval": 30
  }
}
```

**Response:**
```json
{
  "output": {
    "success": true,
    "public_url": "https://abc123-7801.proxy.runpod.net",
    "worker_id": "abc123",
    "pings": 60,
    "failures": 0,
    "duration": 1800,
    "interval": 30
  }
}
```

### `shutdown` - Signal Shutdown

**Request:**
```json
{
  "input": {
    "action": "shutdown"
  }
}
```

**Response:**
```json
{
  "output": {
    "success": true,
    "message": "Shutdown acknowledged",
    "worker_id": "abc123"
  }
}
```

---

## SwarmUI API Reference

Once you have the public URL, you can use any SwarmUI API endpoint:

### Common Endpoints

**GetNewSession:**
```bash
curl -X POST https://abc123-7801.proxy.runpod.net/API/GetNewSession \
  -H "Content-Type: application/json" \
  -d '{}'
```

**ListModels:**
```bash
curl -X POST https://abc123-7801.proxy.runpod.net/API/ListModels \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session",
    "path": "",
    "depth": 2,
    "subtype": "Stable-Diffusion"
  }'
```

**GenerateText2Image:**
```bash
curl -X POST https://abc123-7801.proxy.runpod.net/API/GenerateText2Image \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session",
    "prompt": "a mountain landscape",
    "model": "OfficialStableDiffusion/sd_xl_base_1.0",
    "width": 1024,
    "height": 1024,
    "steps": 30
  }'
```

**Full API documentation:** [SwarmUI API Docs](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/API.md)

**💡 For detailed parameter descriptions and more endpoints, see our [SwarmUI API Reference](SWARMUI_API.md)**

---

## Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your credentials

# Run complete workflow test
python test_direct_url.py --duration 600  # 10 minutes

# Send shutdown
python test_direct_url.py --shutdown
```

---

## Cold Start Times

**First Run (initial install):**
- SwarmUI installation: ~5 minutes
- ComfyUI installation: ~15-20 minutes (requires manual installation in UI)
- **Total: 20-30 minutes** (stored on network volume, only happens once)

**Subsequent Runs:**
- Worker startup: 60-90 seconds
- Almost instant if within idle timeout (120s)

---

## Workflow Patterns

### One-Off Generation

```python
# Wake up, generate, shutdown
public_url = client.wakeup(duration=600)  # 10 minutes
session_id = client.get_session(public_url)
images = client.generate_image(public_url, session_id, "prompt")
client.shutdown()
```

### Interactive Session

```python
# Wake up for 1 hour
public_url = client.wakeup(duration=3600)
session_id = client.get_session(public_url)

# Generate multiple images
for prompt in prompts:
    images = client.generate_image(public_url, session_id, prompt)
    process_images(images)

# Extend if needed
client._call_handler("keepalive", duration=1800, timeout=1900)

# Shutdown when done
client.shutdown()
```

### Background Worker

```python
import threading

# Start long-running keepalive in background
def keep_alive():
    client._call_handler("wakeup", duration=7200, timeout=7300)  # 2 hours

thread = threading.Thread(target=keep_alive, daemon=True)
thread.start()

# Get URL from ready check
time.sleep(90)  # Wait for worker to start
result = client._call_handler("ready")
public_url = result["public_url"]

# Use public_url for the next 2 hours
# Worker will auto-shutdown after 2 hours
```

---

## Cost Optimization

**Tips:**
- Use appropriate keepalive duration (don't over-allocate)
- Use cheap GPU (RTX 4000 Ada ~$0.39/hour) for initial setup
- Use appropriate GPU for workload:
  - RTX 4090 (~$0.89/hour) for SDXL
  - A100 40GB (~$1.89/hour) for Flux
- Shutdown explicitly when done
- Monitor active workers in RunPod dashboard

**Example costs:**
- Initial setup (30 min on RTX 4000 Ada): ~$0.20
- 10-minute session (RTX 4090): ~$0.15
- 1-hour session (RTX 4090): ~$0.89
- 5 images @ 30s each (RTX 4090): ~$0.03

---

## Troubleshooting

### Worker not starting
- Check logs in RunPod dashboard
- Verify network volume has 15GB+ free space
- First install takes 20-30 minutes

### ComfyUI installation hangs
- Set logs to **Debug** in SwarmUI UI
- Check status in debug logs
- If stuck, restart worker via RunPod dashboard
- Run installation again (usually works within 2-3 attempts)
- This is a known issue, likely network-related

### Can't access public URL
- Verify worker is still alive (within keepalive duration)
- Check URL format: `https://{worker-id}-7801.proxy.runpod.net`
- Try ready check to get current URL

### Generation timeouts
- Increase request timeout (600s minimum)
- Reduce steps/resolution for faster generation
- Use faster models (SDXL Turbo, Flux Schnell)

### High costs
- Check for orphaned workers
- Reduce keepalive duration
- Always send shutdown when done

---

## Architecture

```
Your Application
    ↓ (1) Wakeup request
RunPod API Gateway
    ↓ (2) Start worker if needed
Worker Container
    ├─ start.sh (launches SwarmUI)
    └─ rp_handler.py (keeps alive, returns URL)
         ↓ (3) Returns public URL
Your Application
    ↓ (4) Direct SwarmUI API calls
https://{worker-id}-7801.proxy.runpod.net
    ↓ (5) SwarmUI processes requests
    └─ Returns generated images
```

---

## Files

```
/
├── rp_handler.py                  # Handler with direct URL support
├── start.sh                        # SwarmUI startup script
├── trigger_install.py              # First-time installation helper
├── test_direct_url.py              # Complete workflow test
├── example_client.py               # Reusable Python client
├── SETUP.md                        # Complete setup guide
├── WORKFLOW.md                     # Step-by-step workflow
├── CLIENT.md                       # Client usage guide
├── SWARMUI_API.md                  # Complete API reference
├── Dockerfile                      # Container image
├── requirements.txt                # Python dependencies
└── .env.example                    # Environment template
```

---

## 📖 Complete Documentation

Ready to dive deeper? Here's your learning path:

### 1. **[Setup Guide](SETUP.md)** ⭐ Start here!
First-time deployment walkthrough:
- Creating RunPod account
- Setting up network volume
- Deploying the endpoint
- First-time installation process
- Troubleshooting installation issues

### 2. **[Workflow Guide](WORKFLOW.md)**
Complete step-by-step walkthrough:
- How to wake up workers
- Getting public URLs
- Making direct SwarmUI API calls
- Batch generation patterns
- Error handling and troubleshooting

### 3. **[Client Usage Guide](CLIENT.md)**
Using our Python client class:
- Quick start examples
- API reference for all methods
- Advanced usage patterns
- Error handling
- Performance tips

### 4. **[SwarmUI API Reference](SWARMUI_API.md)**
Complete SwarmUI API documentation:
- All available endpoints
- Request/response formats
- Parameter descriptions
- Code examples
- Links to official docs

---

## Support

- **Issues:** GitHub Issues
- **SwarmUI:** [SwarmUI Discord](https://discord.gg/q2y38cqjNw)
- **RunPod:** [RunPod Discord](https://discord.gg/runpod)

---

## License

MIT - See [LICENSE](LICENSE) file for details.

---

## Credits

- **SwarmUI:** [mcmonkeyprojects/SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI)
- **RunPod:** [runpod.io](https://runpod.io)
