# Quick Start Guide

Get SwarmUI running on RunPod Serverless in under 30 minutes.

---

## Prerequisites

- RunPod account with credits
- Network volume (100GB+) in same region as target GPU
- Python 3.11+ for local testing
- Basic understanding of API calls

---

## Step 1: Create Network Volume

1. Go to [RunPod Storage](https://runpod.io/console/storage)
2. Click "**+ New Network Volume**"
3. Configure:
   - **Name**: `swarmui-models`
   - **Size**: `100 GB` (minimum)
   - **Region**: Match your GPU region (e.g., `EU-RO-1`)
4. Click "Create"

**Cost:** ~$7/month for 100GB

---

## Step 2: Deploy Serverless Endpoint

### Option A: Use Published Template (Recommended)

1. Go to [RunPod Serverless](https://runpod.io/console/serverless)
2. Click "**+ New Endpoint**"
3. Select template: `swarmui-serverless`
4. Configure:
   - **Name**: `my-swarmui`
   - **GPU Type**: RTX 4090 (24GB) or A100 (40GB+)
   - **Network Volume**: Select your volume
   - **Active Workers**: `0`
   - **Max Workers**: `3`
   - **Idle Timeout**: `120` seconds
   - **FlashBoot**: Enabled
5. Click "Deploy"

### Option B: Deploy Custom Image

```bash
# Clone repository
git clone https://github.com/youruser/runpod-worker-swarmui.git
cd runpod-worker-swarmui

# Build image
docker build --platform linux/amd64 -t youruser/swarmui-runpod:latest .

# Push to registry
docker push youruser/swarmui-runpod:latest
```

Then create endpoint using your custom image URL.

---

## Step 3: Configure Local Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env

# Edit .env with your credentials
nano .env
```

Add your endpoint details to `.env`:
```bash
RUNPOD_ENDPOINT_ID=your-endpoint-id-here
RUNPOD_API_TOKEN=your-api-token-here
```

Get these from RunPod dashboard:
- **Endpoint ID**: In endpoint URL or settings
- **API Token**: Settings → API Keys

---

## Step 4: Trigger First Installation

First run installs SwarmUI + ComfyUI (20-30 minutes):

```bash
python scripts/trigger_install.py
```

**Expected output:**
```
================================================================================
Triggering SwarmUI Installation
================================================================================

Endpoint: abc123xyz
Max wait: 1800s (30 minutes)

Note: First install takes 20-30 minutes
      Subsequent starts take 60-90 seconds

[  145s] Waiting: Not ready
[  160s] Waiting: Backend warming
[  175s] Waiting: Backend warming
...
✓ SwarmUI ready after 1247s (20 minutes)
  Version: 0.6.5-Beta
  Session: abc123def456...
```

**What's happening:**
1. Downloading SwarmUI installer
2. Cloning SwarmUI repository
3. Installing ComfyUI backend
4. Downloading PyTorch (~2GB)
5. Building and starting SwarmUI

**Subsequent cold starts:** Only 60-90 seconds!

---

## Step 5: Test the Worker

### Quick Health Check

```bash
python tests/test_health.py
```

**Expected output:**
```
================================================================================
Testing Health Endpoint
================================================================================

✓ Health check passed

================================================================================
Testing Ready Endpoint
================================================================================

✓ SwarmUI is ready
  Session ID: abc123...
  Version: 0.6.5-Beta
  API URL: http://127.0.0.1:7801

================================================================================
Testing Keepalive Endpoint (30s)
================================================================================

Starting keepalive for 30s...
✓ Keepalive completed in 30.2s
  Pings: 3
  Failures: 0

================================================================================
Test Summary
================================================================================

✓ PASS - Health
✓ PASS - Ready
✓ PASS - Keepalive

✓ All tests passed!
```

### Test SwarmUI API

```bash
python tests/test_swarm_passthrough.py --prompt "a beautiful mountain landscape"
```

**Expected output:**
```
================================================================================
Testing SwarmUI GetNewSession
================================================================================

✓ Got session ID: abc123def456...
  Version: 0.6.5-Beta

================================================================================
Testing SwarmUI ListModels
================================================================================

✓ Found 2 models in 3 folders

First 5 models:
  - OfficialStableDiffusion/sd_xl_base_1.0
  - OfficialStableDiffusion/sd_xl_refiner_1.0

================================================================================
Testing SwarmUI GenerateText2Image
================================================================================

Prompt: a beautiful mountain landscape
Generating image...
✓ Generated 1 image(s)

Image paths:
  - Output/2024-10/abc123.png

Note: Image paths are relative to SwarmUI server.
External app should fetch these via SwarmUI's file serving endpoint.

================================================================================
Test Summary
================================================================================

✓ PASS - GetNewSession
✓ PASS - ListModels
✓ PASS - GenerateText2Image

✓ All tests passed!
```

---

## Step 6: Use from Your App

### Python Example

```python
import requests
import time

# Configuration
ENDPOINT_ID = "your-endpoint-id"
API_KEY = "your-api-key"
BASE_URL = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

# 1. Wait for worker ready
print("Starting worker...")
while True:
    response = requests.post(
        BASE_URL,
        json={"input": {"action": "ready"}},
        headers=headers,
        timeout=120
    )
    result = response.json()
    if result.get("output", {}).get("ready"):
        print("✓ Worker ready!")
        break
    print("Waiting...")
    time.sleep(15)

# 2. Get session
response = requests.post(
    BASE_URL,
    json={
        "input": {
            "action": "swarm_api",
            "method": "POST",
            "path": "/API/GetNewSession"
        }
    },
    headers=headers,
    timeout=30
)
session_id = response.json()["output"]["response"]["session_id"]
print(f"Session: {session_id[:16]}...")

# 3. Generate image
print("Generating image...")
response = requests.post(
    BASE_URL,
    json={
        "input": {
            "action": "swarm_api",
            "method": "POST",
            "path": "/API/GenerateText2Image",
            "payload": {
                "session_id": session_id,
                "prompt": "a serene lake at sunset, photorealistic",
                "model": "OfficialStableDiffusion/sd_xl_base_1.0",
                "width": 1024,
                "height": 1024,
                "steps": 30,
                "cfg_scale": 7.5,
                "images": 1
            },
            "timeout": 600
        }
    },
    headers=headers,
    timeout=630
)

result = response.json()
if result.get("output", {}).get("success"):
    images = result["output"]["response"]["images"]
    print(f"✓ Generated {len(images)} image(s)")
    for img_path in images:
        print(f"  - {img_path}")
else:
    error = result.get("output", {}).get("error", "Unknown error")
    print(f"✗ Generation failed: {error}")

# 4. Keep worker warm (optional)
print("Keeping worker warm for 5 minutes...")
requests.post(
    BASE_URL,
    json={
        "input": {
            "action": "keepalive",
            "duration": 300,
            "interval": 30
        }
    },
    headers=headers,
    timeout=330
)
print("✓ Keepalive complete")

# 5. Shutdown (optional)
requests.post(
    BASE_URL,
    json={"input": {"action": "shutdown"}},
    headers=headers,
    timeout=30
)
print("✓ Shutdown acknowledged")
```

### C# Example

```csharp
using System.Net.Http.Json;
using System.Text.Json;

var endpointId = "your-endpoint-id";
var apiKey = "your-api-key";
var baseUrl = $"https://api.runpod.ai/v2/{endpointId}/runsync";

var http = new HttpClient();
http.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiKey}");
http.Timeout = TimeSpan.FromSeconds(120);

// 1. Wait for ready
Console.WriteLine("Starting worker...");
while (true)
{
    var readyResponse = await http.PostAsJsonAsync(baseUrl, new
    {
        input = new { action = "ready" }
    });
    
    var readyResult = await readyResponse.Content.ReadFromJsonAsync<JsonDocument>();
    var ready = readyResult.RootElement
        .GetProperty("output")
        .GetProperty("ready")
        .GetBoolean();
    
    if (ready)
    {
        Console.WriteLine("✓ Worker ready!");
        break;
    }
    
    Console.WriteLine("Waiting...");
    await Task.Delay(15000);
}

// 2. Get session
var sessionResponse = await http.PostAsJsonAsync(baseUrl, new
{
    input = new
    {
        action = "swarm_api",
        method = "POST",
        path = "/API/GetNewSession"
    }
});

var sessionResult = await sessionResponse.Content.ReadFromJsonAsync<JsonDocument>();
var sessionId = sessionResult.RootElement
    .GetProperty("output")
    .GetProperty("response")
    .GetProperty("session_id")
    .GetString();

Console.WriteLine($"Session: {sessionId.Substring(0, 16)}...");

// 3. Generate image
Console.WriteLine("Generating image...");
http.Timeout = TimeSpan.FromSeconds(630);

var generateResponse = await http.PostAsJsonAsync(baseUrl, new
{
    input = new
    {
        action = "swarm_api",
        method = "POST",
        path = "/API/GenerateText2Image",
        payload = new
        {
            session_id = sessionId,
            prompt = "a serene lake at sunset, photorealistic",
            model = "OfficialStableDiffusion/sd_xl_base_1.0",
            width = 1024,
            height = 1024,
            steps = 30,
            cfg_scale = 7.5,
            images = 1
        },
        timeout = 600
    }
});

var generateResult = await generateResponse.Content.ReadFromJsonAsync<JsonDocument>();
var success = generateResult.RootElement
    .GetProperty("output")
    .GetProperty("success")
    .GetBoolean();

if (success)
{
    var images = generateResult.RootElement
        .GetProperty("output")
        .GetProperty("response")
        .GetProperty("images")
        .EnumerateArray()
        .Select(x => x.GetString())
        .ToList();
    
    Console.WriteLine($"✓ Generated {images.Count} image(s)");
    foreach (var img in images)
    {
        Console.WriteLine($"  - {img}");
    }
}
```

---

## Common Workflows

### Batch Generation

Generate multiple images in one session:

```python
# Get session once
session_id = get_session()

# Generate multiple images
for prompt in prompts:
    response = call_swarm_api(
        "POST",
        "/API/GenerateText2Image",
        {
            "session_id": session_id,
            "prompt": prompt,
            # ... other params
        }
    )
```

### Keep Worker Warm

For interactive applications:

```python
# Start keepalive in background
import threading

def keepalive_loop():
    while True:
        call_endpoint("keepalive", {"duration": 300})

thread = threading.Thread(target=keepalive_loop, daemon=True)
thread.start()

# Now use worker interactively
# Worker stays warm as long as keepalive runs
```

### Scheduled Generation

Cron job example:

```bash
#!/bin/bash
# daily-generation.sh

# Start worker
python -c "
import requests
BASE_URL='https://api.runpod.ai/v2/$ENDPOINT_ID/runsync'
headers={'Authorization': 'Bearer $API_KEY'}

# Wait for ready
while True:
    r = requests.post(BASE_URL, json={'input': {'action': 'ready'}}, headers=headers, timeout=120)
    if r.json().get('output', {}).get('ready'):
        break
    time.sleep(15)

# Generate
# ... your generation code
"
```

Add to crontab:
```bash
0 2 * * * /path/to/daily-generation.sh
```

---

## Troubleshooting

### Worker Not Starting

**Symptoms:**
- `trigger_install.py` times out
- Health check fails

**Solutions:**
1. Check RunPod dashboard logs
2. Verify network volume is attached
3. Ensure volume has 15GB+ free space
4. Try increasing `--max-wait` timeout

### Generation Failures

**Symptoms:**
- "No backends available"
- "Model not found"
- Timeout errors

**Solutions:**
1. Verify backends are ready: `test_health.py`
2. List available models: `test_swarm_passthrough.py --skip-generation`
3. Check model name spelling
4. Increase timeout for complex generations

### Slow Performance

**Symptoms:**
- Generation takes 5+ minutes
- Frequent timeouts

**Solutions:**
1. Use appropriate GPU:
   - SDXL: RTX 4090 (24GB)
   - Flux: A100 40GB+
2. Reduce steps/resolution
3. Use quantized models (GGUF)
4. Enable FlashBoot

### High Costs

**Symptoms:**
- Unexpected billing
- Workers running when not in use

**Solutions:**
1. Set appropriate idle timeout
2. Use keepalive only when needed
3. Send shutdown signal when done
4. Monitor active workers in dashboard

---

## Next Steps

- **Read API Reference**: `docs/API.md`
- **Understand Architecture**: `docs/ARCHITECTURE.md`
- **Explore SwarmUI Features**: [SwarmUI Docs](https://github.com/mcmonkeyprojects/SwarmUI)
- **Join Community**:
  - [SwarmUI Discord](https://discord.gg/q2y38cqjNw)
  - [RunPod Discord](https://discord.gg/runpod)

---

## Summary

You now have:
- ✅ SwarmUI running on RunPod Serverless
- ✅ Tested health and API endpoints
- ✅ Working code examples
- ✅ Understanding of common workflows

**Total setup time:** ~30 minutes (including first install)

**Per-job workflow:**
1. Start worker (60-90s on warm start)
2. Get session
3. Generate images
4. Shutdown or keepalive

**Cost:** ~$0.01-0.03 per image (RTX 4090, including idle time)

Happy generating! 🎨
