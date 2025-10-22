# Direct URL Workflow Guide

Complete walkthrough of using the SwarmUI RunPod Serverless worker with direct URL access.

---

## Overview

This worker provides **direct access** to SwarmUI's API running on a RunPod serverless worker. Instead of routing requests through a handler, you get a public URL and make SwarmUI API calls directly.

```
┌──────────────────┐
│  Your App        │
└────────┬─────────┘
         │
         │ (1) Send "wakeup"
         ↓
┌──────────────────┐
│  RunPod Gateway  │
└────────┬─────────┘
         │
         │ (2) Start worker
         ↓
┌──────────────────────────────────┐
│  Worker Container                 │
│  ┌────────────────────────────┐ │
│  │  SwarmUI (port 7801)       │ │
│  │  https://xxx-7801.proxy... │ │
│  └────────────────────────────┘ │
│  ┌────────────────────────────┐ │
│  │  Handler                   │ │
│  │  - Returns public URL      │ │
│  │  - Keeps worker alive      │ │
│  └────────────────────────────┘ │
└──────────────────────────────────┘
         │
         │ (3) Returns public URL
         ↓
┌──────────────────┐
│  Your App        │
│  Makes direct    │
│  SwarmUI calls   │
└──────────────────┘
```

---

## Step-by-Step Workflow

### Step 1: Deploy the Endpoint

**One-time setup** - Deploy the worker to RunPod Serverless.

1. Go to [RunPod Serverless](https://runpod.io/console/serverless)
2. Create new endpoint
3. Use Docker image: `youruser/swarmui-runpod:latest`
4. Attach network volume (100GB+)
5. Configure:
   - GPU: RTX 4090 (24GB) or A100 (40GB+)
   - Active Workers: 0
   - Max Workers: 3
   - Idle Timeout: 120s
   - FlashBoot: Enabled

**Cost:** ~$0.89/hour for RTX 4090 (only when running)

---

### Step 2: Wake Up the Worker

Send a `wakeup` request to start the worker and get the public URL.

**Request:**
```python
import requests

endpoint_id = "your-endpoint-id"
api_key = "your-api-key"

# Start wakeup in background thread (blocks for duration)
import threading

def wakeup_worker():
    response = requests.post(
        f"https://api.runpod.ai/v2/{endpoint_id}/runsync",
        json={
            "input": {
                "action": "wakeup",
                "duration": 3600,  # Keep alive for 1 hour
                "interval": 30      # Ping every 30 seconds
            }
        },
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=3700
    )
    return response.json()

thread = threading.Thread(target=wakeup_worker, daemon=True)
thread.start()
```

**Why background thread?**
- The `wakeup` request blocks for the full duration (1 hour in this case)
- It keeps the worker alive by pinging SwarmUI every 30 seconds
- Running in background lets you make API calls while it's active

**Alternative: Use ready check**
```python
import time

# Give worker time to start
time.sleep(90)

# Check if ready and get URL
response = requests.post(
    f"https://api.runpod.ai/v2/{endpoint_id}/runsync",
    json={"input": {"action": "ready"}},
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=120
)

result = response.json()["output"]
if result.get("ready"):
    public_url = result["public_url"]
    print(f"SwarmUI URL: {public_url}")
```

**Cold start timing:**
- First run: 20-30 minutes (installs SwarmUI + ComfyUI)
- Subsequent runs: 60-90 seconds (launches existing installation)

---

### Step 3: Get the Public URL

The handler returns a public URL in this format:
```
https://{worker-id}-7801.proxy.runpod.net
```

**From wakeup response:**
```python
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

**From ready response:**
```python
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

**Save this URL** - you'll use it for all SwarmUI API calls.

---

### Step 4: Get a SwarmUI Session

Before generating images, you need a session ID from SwarmUI.

```python
# Direct call to SwarmUI (no handler involved)
response = requests.post(
    f"{public_url}/API/GetNewSession",
    json={},
    headers={"Content-Type": "application/json"},
    timeout=30
)

session_data = response.json()
session_id = session_data["session_id"]
print(f"Session: {session_id[:16]}...")
```

**Response:**
```json
{
    "session_id": "9D3534E30DA38499DE782BC38211976A58555AA6",
    "user_id": "local",
    "output_append_user": true,
    "version": "0.6.5-Beta",
    "server_id": "058716b5-c6f5-49ed-9ca3-be20d82e4c5f"
}
```

**Session management:**
- Sessions expire after inactivity
- Create one session per workflow
- Reuse session for multiple generations
- If you get `invalid_session_id` error, get a new session

---

### Step 5: List Available Models (Optional)

Check which models are loaded.

```python
response = requests.post(
    f"{public_url}/API/ListModels",
    json={
        "session_id": session_id,
        "path": "",                    # Root folder
        "depth": 2,                    # Subfolder depth
        "subtype": "Stable-Diffusion", # Model type
        "allowRemote": true            # Include remote models
    },
    headers={"Content-Type": "application/json"},
    timeout=60
)

models_data = response.json()
files = models_data.get("files", [])
folders = models_data.get("folders", [])

print(f"Found {len(files)} models in {len(folders)} folders")
for model in files[:5]:
    print(f"  - {model}")
```

**Common model subtypes:**
- `Stable-Diffusion` - Base models (SDXL, Flux, SD 1.5)
- `LoRA` - LoRA adapters
- `VAE` - VAE models
- `ControlNet` - ControlNet models
- `Wildcards` - Prompt wildcards

---

### Step 6: Generate Images

Now you can generate images using SwarmUI's full API.

```python
response = requests.post(
    f"{public_url}/API/GenerateText2Image",
    json={
        "session_id": session_id,
        "prompt": "a beautiful mountain landscape at sunset, photorealistic, 8k",
        "negative_prompt": "blurry, low quality, distorted, ugly",
        "model": "OfficialStableDiffusion/sd_xl_base_1.0",
        "width": 1024,
        "height": 1024,
        "steps": 30,
        "cfg_scale": 7.5,
        "seed": -1,     # -1 for random
        "images": 1     # Number of images
    },
    headers={"Content-Type": "application/json"},
    timeout=600
)

result = response.json()
images = result.get("images", [])
print(f"Generated {len(images)} image(s)")
for img_path in images:
    print(f"  - {img_path}")
```

**Response:**
```json
{
    "images": [
        "Output/2024-10/image-abc123.png"
    ],
    "seed": 1234567890
}
```

**Common parameters:**
- `prompt` - What to generate
- `negative_prompt` - What to avoid
- `model` - Model identifier
- `width` / `height` - Image dimensions (multiples of 64)
- `steps` - Generation steps (20-50 typical)
- `cfg_scale` - Prompt guidance (7-12 typical)
- `seed` - Random seed (-1 for random)
- `images` - Number of images to generate

See [SwarmUI API docs](docs/SWARMUI_API.md) for complete parameter list.

---

### Step 7: Retrieve Generated Images

Images are saved to SwarmUI's Output directory. You can retrieve them via:

**Option 1: Direct image URL**
```python
# Images are served at: {public_url}/{image_path}
image_url = f"{public_url}/{images[0]}"
response = requests.get(image_url, timeout=30)

# Save to file
with open("generated.png", "wb") as f:
    f.write(response.content)
```

**Option 2: View URL**
```python
# SwarmUI provides a View URL
view_url = f"{public_url}/View/local/raw/{images[0].split('/')[-1]}"
```

---

### Step 8: Generate Multiple Images

You can make multiple generation calls using the same session.

```python
prompts = [
    "a serene ocean sunset",
    "a cyberpunk city at night",
    "a peaceful forest path"
]

for prompt in prompts:
    response = requests.post(
        f"{public_url}/API/GenerateText2Image",
        json={
            "session_id": session_id,
            "prompt": prompt,
            "model": "OfficialStableDiffusion/sd_xl_base_1.0",
            "width": 512,
            "height": 512,
            "steps": 20,
            "images": 1
        },
        timeout=300
    )
    
    result = response.json()
    images = result.get("images", [])
    print(f"✓ {prompt}: {images[0] if images else 'failed'}")
```

**Batch generation:**
```python
# Generate 4 images at once
response = requests.post(
    f"{public_url}/API/GenerateText2Image",
    json={
        "session_id": session_id,
        "prompt": "a beautiful landscape",
        "model": "OfficialStableDiffusion/sd_xl_base_1.0",
        "width": 1024,
        "height": 1024,
        "steps": 30,
        "images": 4  # Generate 4 images
    },
    timeout=1200  # Longer timeout for batch
)
```

---

### Step 9: Shutdown When Done

Signal that you're done and the worker can shut down.

```python
requests.post(
    f"https://api.runpod.ai/v2/{endpoint_id}/runsync",
    json={"input": {"action": "shutdown"}},
    headers={"Authorization": f"Bearer {api_key}"},
    timeout=30
)
```

**What happens:**
- Handler acknowledges shutdown
- Worker continues until keepalive expires
- RunPod auto-scales down worker after idle timeout

**Note:** Shutdown is optional - worker will auto-shutdown after keepalive duration expires.

---

## Complete Workflow Example

```python
import requests
import threading
import time

# Configuration
ENDPOINT_ID = "your-endpoint-id"
API_KEY = "your-api-key"

# Step 1: Start worker in background
def wakeup_worker():
    requests.post(
        f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync",
        json={
            "input": {
                "action": "wakeup",
                "duration": 3600,
                "interval": 30
            }
        },
        headers={"Authorization": f"Bearer {API_KEY}"},
        timeout=3700
    )

thread = threading.Thread(target=wakeup_worker, daemon=True)
thread.start()

# Step 2: Wait for worker to be ready
print("Waiting for worker...")
time.sleep(90)

while True:
    try:
        response = requests.post(
            f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync",
            json={"input": {"action": "ready"}},
            headers={"Authorization": f"Bearer {API_KEY}"},
            timeout=60
        )
        result = response.json()["output"]
        if result.get("ready"):
            public_url = result["public_url"]
            print(f"✓ Worker ready: {public_url}")
            break
    except Exception as e:
        print(f"  Waiting... {e}")
    time.sleep(15)

# Step 3: Get session
response = requests.post(f"{public_url}/API/GetNewSession", json={})
session_id = response.json()["session_id"]
print(f"✓ Session: {session_id[:16]}...")

# Step 4: Generate images
prompts = [
    "a mountain landscape",
    "an ocean sunset",
    "a forest path"
]

for prompt in prompts:
    print(f"Generating: {prompt}")
    response = requests.post(
        f"{public_url}/API/GenerateText2Image",
        json={
            "session_id": session_id,
            "prompt": prompt,
            "model": "OfficialStableDiffusion/sd_xl_base_1.0",
            "width": 512,
            "height": 512,
            "steps": 20,
            "images": 1
        },
        timeout=300
    )
    images = response.json().get("images", [])
    print(f"  ✓ {images[0] if images else 'failed'}")

# Step 5: Shutdown
requests.post(
    f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync",
    json={"input": {"action": "shutdown"}},
    headers={"Authorization": f"Bearer {API_KEY}"},
    timeout=30
)
print("✓ Shutdown complete")
```

---

## Advanced Patterns

### Pattern 1: Long-Running Session

For interactive applications that need the worker active for extended periods:

```python
# Start with 2-hour keepalive
public_url = start_worker(duration=7200)  # 2 hours

# Use for interactive generation
while user_active:
    prompt = get_user_input()
    images = generate(public_url, session_id, prompt)
    display_images(images)
    
# Extend if needed
extend_keepalive(duration=3600)  # Add 1 more hour
```

### Pattern 2: Scheduled Generation

For automated/scheduled image generation:

```python
# Cron job or scheduled task
public_url = start_worker(duration=600)  # 10 minutes
session_id = get_session(public_url)

# Generate daily images
for prompt in daily_prompts:
    generate(public_url, session_id, prompt)

shutdown()
```

### Pattern 3: On-Demand Scaling

For variable workload:

```python
# Start worker only when needed
if queue.has_pending_jobs():
    public_url = start_worker(duration=1800)  # 30 minutes
    session_id = get_session(public_url)
    
    # Process queue
    while queue.has_jobs() and time_remaining():
        job = queue.pop()
        images = generate(public_url, session_id, job.prompt)
        queue.complete(job, images)
    
    shutdown()
```

---

## Troubleshooting

### Worker not starting
**Problem:** Ready check times out

**Solutions:**
- First run takes 20-30 minutes (SwarmUI installation)
- Check RunPod dashboard logs
- Verify network volume has 15GB+ free space
- Increase wait time for first run

### Can't access public URL
**Problem:** URL returns connection refused

**Solutions:**
- Verify worker is still alive (within keepalive duration)
- Check URL format: `https://{worker-id}-7801.proxy.runpod.net`
- Try ready check to get current URL
- Ensure keepalive is still running

### Generation failures
**Problem:** Requests timeout or return errors

**Solutions:**
- Increase timeout (600s minimum for complex generations)
- Verify model is loaded: call ListModels
- Check prompt/parameters are valid
- Reduce steps/resolution for faster generation

### Invalid session errors
**Problem:** `invalid_session_id` error

**Solutions:**
- Get a new session: `GetNewSession`
- Sessions expire after ~1 hour of inactivity
- One session per workflow is recommended

---

## Best Practices

**✅ Do:**
- Run wakeup in background thread
- Reuse sessions for multiple generations
- Set appropriate keepalive duration
- Monitor costs via RunPod dashboard
- Use shutdown when completely done
- Handle errors gracefully

**❌ Don't:**
- Block main thread with wakeup request
- Create new session for every generation
- Use excessive keepalive duration
- Forget to shutdown (costs add up)
- Assume worker is ready immediately
- Use hardcoded worker URLs (they change)

---

## Next Steps

- **[Client Usage Guide](CLIENT.md)** - Using the pre-built Python client
- **[SwarmUI API Reference](SWARMUI_API.md)** - Complete API documentation
- **[Back to README](../README.md)** - Project overview

---

## Support

- **GitHub Issues:** Bug reports and feature requests
- **[SwarmUI Discord](https://discord.gg/q2y38cqjNw):** SwarmUI-specific help
- **[RunPod Discord](https://discord.gg/runpod):** RunPod platform support
