# SwarmUI RunPod Serverless Worker

**Minimal, production-ready serverless handler for SwarmUI on RunPod.**

This project provides a lightweight wrapper that starts SwarmUI on RunPod Serverless and exposes its API for external applications to use. The handler does minimal work—it just ensures SwarmUI is ready and forwards API requests.

---

## Key Features

- ✅ **Minimal Handler**: ~200 lines vs 700+ in typical implementations
- ✅ **Official Scripts**: Uses SwarmUI's own install/launch scripts
- ✅ **Pass-Through Design**: External apps call SwarmUI API directly
- ✅ **Fast Warm Starts**: 60-90 seconds after first install
- ✅ **Persistent Storage**: Network volume preserves models/config
- ✅ **Production Ready**: Health checks, keepalive, graceful shutdown

---

## Architecture Overview

```
External App (Your Code)
    ↓
RunPod API Endpoint
    ↓
Handler (this project)
    ↓ forwards requests to
SwarmUI API (localhost:7801)
```

**The handler's only jobs:**
1. Wait for SwarmUI to start and backends to be ready
2. Provide `/ready`, `/health` endpoints
3. Forward SwarmUI API requests from your app
4. Handle `/keepalive` and `/shutdown` signals

**Your external app:**
- Starts the worker via RunPod API
- Polls `/ready` until SwarmUI is available
- Makes SwarmUI API calls (generate images, list models, etc.)
- Sends `/shutdown` when done

---

## Quick Start

### 1. Prerequisites

- RunPod account with credits
- Network volume (100GB+ recommended)
- Python 3.11+ for local testing

### 2. Deploy to RunPod

**Option A: Use Published Template** (recommended)
1. Go to [RunPod Serverless](https://runpod.io/console/serverless)
2. Create endpoint from template: `swarmui-serverless` (or your published template)
3. Attach network volume
4. Deploy

**Option B: Build Your Own Image**
```bash
docker build --platform linux/amd64 -t youruser/swarmui-runpod:latest .
docker push youruser/swarmui-runpod:latest
```

### 3. Trigger First Install

First run takes 20-30 minutes to install SwarmUI + ComfyUI:

```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure .env
cp .env.example .env
# Edit .env with your RUNPOD_ENDPOINT_ID and RUNPOD_API_TOKEN

# Trigger installation
python scripts/trigger_install.py
```

Subsequent cold starts take only 60-90 seconds.

### 4. Test the Worker

```bash
# Test health endpoints
python tests/test_health.py

# Test SwarmUI API pass-through
python tests/test_swarm_passthrough.py --prompt "a beautiful landscape"
```

---

## Usage from External App

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

# 1. Start worker and wait for ready
print("Starting worker...")
ready = False
while not ready:
    response = requests.post(
        BASE_URL,
        json={"input": {"action": "ready"}},
        headers=headers,
        timeout=120
    )
    result = response.json()
    ready = result.get("output", {}).get("ready", False)
    
    if not ready:
        print("Waiting for SwarmUI to start...")
        time.sleep(15)

print("✓ Worker ready!")

# 2. Get SwarmUI session
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

# 3. Generate image
response = requests.post(
    BASE_URL,
    json={
        "input": {
            "action": "swarm_api",
            "method": "POST",
            "path": "/API/GenerateText2Image",
            "payload": {
                "session_id": session_id,
                "prompt": "a beautiful mountain landscape",
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
images = result["output"]["response"]["images"]
print(f"Generated {len(images)} image(s)")

# 4. Shutdown when done (optional)
requests.post(
    BASE_URL,
    json={"input": {"action": "shutdown"}},
    headers=headers,
    timeout=30
)
```

### C# Example

```csharp
using System.Net.Http.Json;
using System.Text.Json;

public class SwarmUIClient
{
    public string EndpointId { get; set; }
    public string ApiKey { get; set; }
    public HttpClient Http { get; set; }
    
    public string BaseUrl => $"https://api.runpod.ai/v2/{EndpointId}/runsync";
    
    public SwarmUIClient(string endpointId, string apiKey)
    {
        EndpointId = endpointId;
        ApiKey = apiKey;
        Http = new HttpClient();
        Http.DefaultRequestHeaders.Add("Authorization", $"Bearer {ApiKey}");
        Http.Timeout = TimeSpan.FromSeconds(120);
    }
    
    public async Task<bool> WaitForReadyAsync()
    {
        Console.WriteLine("Starting worker...");
        
        while (true)
        {
            var payload = new
            {
                input = new { action = "ready" }
            };
            
            var response = await Http.PostAsJsonAsync(BaseUrl, payload);
            var result = await response.Content.ReadFromJsonAsync<JsonDocument>();
            
            var ready = result.RootElement
                .GetProperty("output")
                .GetProperty("ready")
                .GetBoolean();
            
            if (ready)
            {
                Console.WriteLine("✓ Worker ready!");
                return true;
            }
            
            Console.WriteLine("Waiting for SwarmUI...");
            await Task.Delay(15000);
        }
    }
    
    public async Task<string> GetSessionIdAsync()
    {
        var payload = new
        {
            input = new
            {
                action = "swarm_api",
                method = "POST",
                path = "/API/GetNewSession"
            }
        };
        
        var response = await Http.PostAsJsonAsync(BaseUrl, payload);
        var result = await response.Content.ReadFromJsonAsync<JsonDocument>();
        
        return result.RootElement
            .GetProperty("output")
            .GetProperty("response")
            .GetProperty("session_id")
            .GetString();
    }
    
    public async Task<List<string>> GenerateImageAsync(
        string sessionId,
        string prompt,
        string model = "OfficialStableDiffusion/sd_xl_base_1.0")
    {
        var payload = new
        {
            input = new
            {
                action = "swarm_api",
                method = "POST",
                path = "/API/GenerateText2Image",
                payload = new
                {
                    session_id = sessionId,
                    prompt = prompt,
                    model = model,
                    width = 1024,
                    height = 1024,
                    steps = 30,
                    cfg_scale = 7.5,
                    images = 1
                },
                timeout = 600
            }
        };
        
        Http.Timeout = TimeSpan.FromSeconds(630);
        
        var response = await Http.PostAsJsonAsync(BaseUrl, payload);
        var result = await response.Content.ReadFromJsonAsync<JsonDocument>();
        
        var images = result.RootElement
            .GetProperty("output")
            .GetProperty("response")
            .GetProperty("images")
            .EnumerateArray()
            .Select(x => x.GetString())
            .ToList();
        
        return images;
    }
}

// Usage
var client = new SwarmUIClient("your-endpoint", "your-key");
await client.WaitForReadyAsync();

var sessionId = await client.GetSessionIdAsync();
var images = await client.GenerateImageAsync(
    sessionId,
    "a beautiful mountain landscape"
);

Console.WriteLine($"Generated {images.Count} image(s)");
```

---

## Handler API Reference

All requests go through RunPod's `/runsync` endpoint with an `action` parameter.

### `ready` - Check if SwarmUI is ready

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
    "session_id": "abc123...",
    "version": "0.6.5-Beta",
    "api_url": "http://127.0.0.1:7801"
  }
}
```

### `health` - Quick health check

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
    "healthy": true
  }
}
```

### `keepalive` - Keep worker warm

**Request:**
```json
{
  "input": {
    "action": "keepalive",
    "duration": 300,
    "interval": 30
  }
}
```

**Response:**
```json
{
  "output": {
    "success": true,
    "pings": 10,
    "failures": 0,
    "duration": 300,
    "interval": 30
  }
}
```

### `swarm_api` - Forward SwarmUI API request

**Request:**
```json
{
  "input": {
    "action": "swarm_api",
    "method": "POST",
    "path": "/API/GenerateText2Image",
    "payload": {
      "session_id": "abc123",
      "prompt": "your prompt",
      "model": "OfficialStableDiffusion/sd_xl_base_1.0",
      "width": 1024,
      "height": 1024,
      "steps": 30
    },
    "timeout": 600
  }
}
```

**Response:**
```json
{
  "output": {
    "success": true,
    "response": {
      "images": ["Output/path/to/image.png"],
      "seed": 12345
    }
  }
}
```

### `shutdown` - Signal graceful shutdown

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
    "message": "Shutdown acknowledged"
  }
}
```

---

## SwarmUI API Documentation

See [SwarmUI API Documentation](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/API.md) for full API reference.

**Common endpoints:**
- `/API/GetNewSession` - Get session ID
- `/API/ListModels` - List available models
- `/API/GenerateText2Image` - Generate images
- `/API/DescribeModel` - Get model metadata
- `/API/DoModelDownloadWS` - Download models

---

## Environment Variables

### Container Runtime (set in RunPod endpoint config)

| Variable | Default | Description |
|----------|---------|-------------|
| `SWARMUI_HOST` | `0.0.0.0` | Bind address |
| `SWARMUI_PORT` | `7801` | API port |
| `SWARMUI_API_URL` | `http://127.0.0.1:7801` | Internal API URL |
| `VOLUME_PATH` | `/runpod-volume` | Network volume mount |
| `STARTUP_TIMEOUT` | `1800` | Max wait for startup (seconds) |

### Local Testing (set in `.env` file)

| Variable | Description |
|----------|-------------|
| `RUNPOD_ENDPOINT_ID` | Your RunPod endpoint ID |
| `RUNPOD_API_TOKEN` | Your RunPod API token |

---

## File Structure

```
/
├── Dockerfile                    # Container image definition
├── requirements.txt              # Python dependencies
├── .env.example                  # Environment variables template
├── scripts/
│   ├── start.sh                  # SwarmUI startup script
│   └── trigger_install.py        # First-time install helper
├── src/
│   └── rp_handler.py             # Minimal RunPod handler (~200 lines)
├── tests/
│   ├── test_health.py            # Health endpoint tests
│   └── test_swarm_passthrough.py # SwarmUI API tests
└── docs/
    ├── ARCHITECTURE.md           # Detailed architecture
    ├── QUICKSTART.md             # Quick start guide
    └── API.md                    # Complete API reference
```

---

## Development

### Running Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your endpoint credentials

# Run health tests
python tests/test_health.py

# Run API tests
python tests/test_swarm_passthrough.py

# Run specific test
python tests/test_swarm_passthrough.py --prompt "custom prompt"
```

### Building Image

```bash
# Build for AMD64
docker build --platform linux/amd64 -t youruser/swarmui-runpod:latest .

# Push to registry
docker push youruser/swarmui-runpod:latest
```

---

## Cold Start Times

**First Run (initial install):**
- Download SwarmUI installer: ~5s
- Install SwarmUI: ~3 minutes
- Install ComfyUI: ~15 minutes
- Build & start: ~3 minutes
- **Total: 20-30 minutes**

**Subsequent Runs:**
- Launch existing SwarmUI: ~60-90 seconds

---

## Troubleshooting

### Cold start taking too long
- First install: 20-30 minutes is normal
- Check RunPod dashboard logs
- Ensure network volume has 15GB+ free space

### Worker not responding
- Verify endpoint is active in RunPod dashboard
- Check that network volume is attached
- Use `test_health.py` to diagnose

### Generation failures
- Ensure models are loaded (use `test_swarm_passthrough.py --skip-generation` to test API)
- Check SwarmUI logs in container
- Verify model name is correct (use ListModels API)

### Timeout errors
- Increase timeout values in your requests
- Complex generations may need 10+ minutes
- Consider using async `/run` endpoint for long tasks

---

## Support

- **Documentation**: See `docs/` folder
- **Issues**: GitHub Issues
- **SwarmUI**: [SwarmUI Discord](https://discord.gg/q2y38cqjNw)
- **RunPod**: [RunPod Discord](https://discord.gg/runpod)

---

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

## Credits

- **SwarmUI**: [mcmonkeyprojects/SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI)
- **RunPod**: [runpod.io](https://runpod.io)
- 