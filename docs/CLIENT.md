# Client Usage Guide

Complete guide to using the `SwarmUIClient` Python class for easy integration.

---

## Overview

The `SwarmUIClient` class (in `example_client.py`) provides a simple, reusable interface for managing SwarmUI workers and making direct API calls.

**Features:**
- ✅ Automatic worker wake-up and URL retrieval
- ✅ Background keepalive management
- ✅ Direct SwarmUI API access helpers
- ✅ Clean session management
- ✅ Error handling

**📖 Related Documentation:**
- **[Setup Guide](SETUP.md)** - First-time deployment
- **[Workflow Guide](WORKFLOW.md)** - Complete workflow walkthrough
- **[SwarmUI API Reference](SWARMUI_API.md)** - Complete API docs

---

## Installation

The client is included in the repository:

```bash
# Clone repository
git clone https://github.com/youruser/runpod-worker-swarmui.git
cd runpod-worker-swarmui

# Install dependencies
pip install -r requirements.txt

# Use the client
from example_client import SwarmUIClient
```

**Dependencies:**
- `requests` - HTTP client
- Python 3.7+

---

## Quick Start

```python
from example_client import SwarmUIClient

# Initialize
client = SwarmUIClient(
    endpoint_id="your-endpoint-id",
    api_key="your-api-key"
)

# Wake up worker (keeps alive for 1 hour)
public_url = client.wakeup(duration=3600)

# Get session
session_id = client.get_session(public_url)

# Generate image
images = client.generate_image(
    public_url,
    session_id,
    "a beautiful mountain landscape"
)

print(f"Generated: {images}")

# Shutdown when done
client.shutdown()
```

---

## API Reference

### Constructor

```python
SwarmUIClient(endpoint_id: str, api_key: str)
```

**Parameters:**
- `endpoint_id` - Your RunPod endpoint ID
- `api_key` - Your RunPod API token

**Returns:** SwarmUIClient instance

**Example:**
```python
client = SwarmUIClient("abc123xyz", "your-api-key")
```

---

### wakeup()

Start the worker and get the public URL.

```python
wakeup(duration: int = 3600, wait: bool = True) -> str
```

**Parameters:**
- `duration` - How long to keep worker alive (seconds)
- `wait` - Whether to wait for worker to be ready

**Returns:** Public SwarmUI URL

**Raises:** RuntimeError if worker fails to start

**Example:**
```python
# Start worker, wait until ready
public_url = client.wakeup(duration=3600)  # 1 hour
# Returns: "https://abc123-7801.proxy.runpod.net"

# Start worker, don't wait
public_url = client.wakeup(duration=7200, wait=False)  # 2 hours
```

**How it works:**
1. Starts wakeup request in background thread (blocks for `duration`)
2. If `wait=True`, polls ready endpoint until worker is available
3. Returns public URL once worker responds
4. Background thread continues keepalive for full duration

**Timing:**
- First run (after initial setup): 60-90 seconds
- Subsequent runs: 60-90 seconds
- `wait=True` adds polling time (~5-90s depending on state)

---

### shutdown()

Signal worker to shutdown.

```python
shutdown() -> None
```

**Parameters:** None

**Returns:** None

**Example:**
```python
client.shutdown()
# Prints: "✓ Shutdown acknowledged"
```

**Note:** Worker will shutdown after keepalive expires, not immediately.

---

### call_swarm()

Make a direct call to SwarmUI API.

```python
call_swarm(
    public_url: str,
    method: str,
    path: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 600
) -> Dict[str, Any]
```

**Parameters:**
- `public_url` - Public SwarmUI URL from wakeup()
- `method` - HTTP method ("GET" or "POST")
- `path` - API path (e.g., "/API/GetNewSession")
- `payload` - JSON payload for POST requests
- `timeout` - Request timeout (seconds)

**Returns:** Response JSON

**Raises:** requests.HTTPError on failure

**Example:**
```python
# Get session
result = client.call_swarm(
    public_url,
    "POST",
    "/API/GetNewSession"
)
session_id = result["session_id"]

# List models
result = client.call_swarm(
    public_url,
    "POST",
    "/API/ListModels",
    payload={
        "session_id": session_id,
        "path": "",
        "depth": 2,
        "subtype": "Stable-Diffusion"
    }
)
models = result.get("files", [])
```

**💡 See [SWARMUI_API.md](SWARMUI_API.md) for all available endpoints**

---

### get_session()

Get a SwarmUI session ID.

```python
get_session(public_url: str) -> str
```

**Parameters:**
- `public_url` - Public SwarmUI URL

**Returns:** Session ID string

**Example:**
```python
session_id = client.get_session(public_url)
# Returns: "9D3534E30DA38499DE782BC38211976A58555AA6"
```

---

### list_models()

List available models.

```python
list_models(public_url: str, session_id: str) -> Dict[str, Any]
```

**Parameters:**
- `public_url` - Public SwarmUI URL
- `session_id` - SwarmUI session ID

**Returns:** Dict with `files` (list of models) and `folders` (list of folders)

**Example:**
```python
result = client.list_models(public_url, session_id)
models = result.get("files", [])
folders = result.get("folders", [])

print(f"Found {len(models)} models in {len(folders)} folders")
for model in models:
    print(f"  - {model}")
```

**Note:** Listing models reads from disk and does not load backends or use GPU.

---

### generate_image()

Generate images using SwarmUI.

```python
generate_image(
    public_url: str,
    session_id: str,
    prompt: str,
    **kwargs
) -> List[str]
```

**Parameters:**
- `public_url` - Public SwarmUI URL
- `session_id` - SwarmUI session ID
- `prompt` - Image generation prompt
- `**kwargs` - Additional SwarmUI parameters

**Supported kwargs:**
- `negative_prompt` - Negative prompt (default: "")
- `model` - Model name (default: "OfficialStableDiffusion/sd_xl_base_1.0")
- `width` - Image width (default: 1024)
- `height` - Image height (default: 1024)
- `steps` - Generation steps (default: 30)
- `cfg_scale` - CFG scale (default: 7.5)
- `seed` - Random seed (default: -1 for random)
- `images` - Number of images (default: 1)

**Returns:** List of image paths

**Example:**
```python
# Simple generation
images = client.generate_image(
    public_url,
    session_id,
    "a mountain landscape"
)

# With custom parameters
images = client.generate_image(
    public_url,
    session_id,
    "a cyberpunk city at night",
    negative_prompt="blurry, low quality",
    width=512,
    height=512,
    steps=20,
    cfg_scale=8.0,
    seed=42,
    images=4
)

print(f"Generated {len(images)} image(s)")
for img in images:
    print(f"  - {img}")
```

**Timing:**
- First generation: ~40 seconds (10s model load + 30s generation)
- Subsequent generations: ~30 seconds (model already loaded)

**💡 See [SWARMUI_API.md](SWARMUI_API.md) for detailed parameter descriptions**

---

## Complete Usage Examples

### Example 1: Simple Generation

```python
from example_client import SwarmUIClient

# Initialize
client = SwarmUIClient("your-endpoint", "your-key")

# Wake up and generate
public_url = client.wakeup(duration=600)  # 10 minutes
session_id = client.get_session(public_url)

images = client.generate_image(
    public_url,
    session_id,
    "a serene ocean sunset"
)

print(f"Generated: {images[0]}")

# Shutdown
client.shutdown()
```

### Example 2: Batch Generation

```python
from example_client import SwarmUIClient

client = SwarmUIClient("your-endpoint", "your-key")

# Wake up for 30 minutes
public_url = client.wakeup(duration=1800)
session_id = client.get_session(public_url)

# Generate multiple images
prompts = [
    "a mountain landscape",
    "an ocean sunset",
    "a forest path",
    "a desert dune",
    "a snowy peak"
]

for prompt in prompts:
    images = client.generate_image(
        public_url,
        session_id,
        prompt,
        width=512,
        height=512,
        steps=20
    )
    print(f"✓ {prompt}: {images[0]}")

client.shutdown()
```

### Example 3: Interactive Session

```python
from example_client import SwarmUIClient
import time

client = SwarmUIClient("your-endpoint", "your-key")

# Start long session
public_url = client.wakeup(duration=3600)  # 1 hour
session_id = client.get_session(public_url)

# List available models
models = client.list_models(public_url, session_id)
print(f"Available models: {len(models.get('files', []))}")

# Interactive generation loop
while True:
    prompt = input("\nEnter prompt (or 'quit'): ")
    if prompt.lower() == 'quit':
        break
    
    print("Generating...")
    images = client.generate_image(
        public_url,
        session_id,
        prompt
    )
    print(f"✓ Generated: {images[0]}")

client.shutdown()
print("Session ended")
```

### Example 4: Custom Parameters

```python
from example_client import SwarmUIClient

client = SwarmUIClient("your-endpoint", "your-key")
public_url = client.wakeup(duration=1200)  # 20 minutes
session_id = client.get_session(public_url)

# High quality generation
images = client.generate_image(
    public_url,
    session_id,
    "a photorealistic portrait, studio lighting, 8k",
    negative_prompt="cartoon, drawing, painting, blur, low quality",
    width=1024,
    height=1024,
    steps=50,
    cfg_scale=7.5,
    seed=42,  # Fixed seed for reproducibility
    images=1
)

# Fast generation
images = client.generate_image(
    public_url,
    session_id,
    "a quick sketch of a cat",
    width=512,
    height=512,
    steps=15,  # Fewer steps for speed
    cfg_scale=6.0,
    images=1
)

client.shutdown()
```

### Example 5: Error Handling

```python
from example_client import SwarmUIClient
import requests

client = SwarmUIClient("your-endpoint", "your-key")

try:
    # Wake up worker
    print("Starting worker...")
    public_url = client.wakeup(duration=600, wait=True)
    print(f"✓ Worker ready: {public_url}")
    
    # Get session
    session_id = client.get_session(public_url)
    print(f"✓ Session: {session_id[:16]}...")
    
    # Generate image
    images = client.generate_image(
        public_url,
        session_id,
        "a beautiful landscape"
    )
    print(f"✓ Generated: {images[0]}")
    
except RuntimeError as e:
    print(f"✗ Worker startup failed: {e}")
except requests.HTTPError as e:
    print(f"✗ API call failed: {e}")
except Exception as e:
    print(f"✗ Unexpected error: {e}")
finally:
    # Always try to shutdown
    try:
        client.shutdown()
    except:
        pass
```

---

## Advanced Usage

### Custom SwarmUI API Calls

The client provides a generic `call_swarm()` method for any SwarmUI API endpoint:

```python
# Describe a specific model
model_info = client.call_swarm(
    public_url,
    "POST",
    "/API/DescribeModel",
    payload={
        "session_id": session_id,
        "model_name": "OfficialStableDiffusion/sd_xl_base_1.0",
        "subtype": "Stable-Diffusion"
    }
)

# Get user settings
settings = client.call_swarm(
    public_url,
    "POST",
    "/API/GetUserSettings",
    payload={"session_id": session_id}
)

# Download a model
download_result = client.call_swarm(
    public_url,
    "POST",
    "/API/DoModelDownloadWS",
    payload={
        "session_id": session_id,
        "url": "https://huggingface.co/...",
        "type": "Stable-Diffusion",
        "name": "my-custom-model"
    },
    timeout=1800  # 30 minutes for large models
)
```

**💡 See [SWARMUI_API.md](SWARMUI_API.md) for complete API reference**

---

### Extending Keepalive

If your workflow takes longer than expected, you can manually extend keepalive:

```python
# Start with 30 minutes
public_url = client.wakeup(duration=1800)

# Do work...
# Takes longer than expected...

# Extend by another 30 minutes
client._call_handler("keepalive", duration=1800, interval=30, timeout=1900)
```

---

### Multiple Concurrent Workers

For parallel processing, start multiple workers:

```python
# Start multiple workers
workers = []
for i in range(3):
    client = SwarmUIClient(f"endpoint-{i}", api_key)
    url = client.wakeup(duration=3600, wait=True)
    session = client.get_session(url)
    workers.append((client, url, session))

# Distribute work
for i, prompt in enumerate(prompts):
    client, url, session = workers[i % len(workers)]
    images = client.generate_image(url, session, prompt)
    print(f"Worker {i % len(workers)}: {images[0]}")

# Shutdown all
for client, _, _ in workers:
    client.shutdown()
```

---

## Best Practices

**✅ Do:**
- Initialize one client per endpoint
- Reuse `public_url` and `session_id` for multiple calls
- Set appropriate `duration` based on workload
- Handle exceptions gracefully
- Always call `shutdown()` when done

**❌ Don't:**
- Create new client for every request
- Hardcode public URLs (they change per worker)
- Use excessive keepalive durations
- Ignore errors from API calls
- Forget to shutdown (costs accumulate)

---

## Troubleshooting

### Import Error

**Problem:** `ModuleNotFoundError: No module named 'example_client'`

**Solution:**
```python
# Add project root to path
import sys
sys.path.append('/path/to/runpod-worker-swarmui')

from example_client import SwarmUIClient
```

Or copy `example_client.py` to your project:
```bash
cp example_client.py your_project/swarm_client.py
```

### Timeout on wakeup()

**Problem:** `RuntimeError: Worker failed to start within timeout`

**Solutions:**
- First run takes 60-90 seconds after initial setup
- Check RunPod dashboard for errors
- Verify network volume has space
- Try `wait=False` and poll manually

### Session Expired

**Problem:** `invalid_session_id` error

**Solution:**
```python
# Get new session
session_id = client.get_session(public_url)
```

Sessions expire after ~1 hour of inactivity.

---

## Performance Tips

**Optimize generation speed:**
- Use smaller dimensions (512x512 vs 1024x1024)
- Reduce steps (20 vs 50)
- Use faster models (SDXL Turbo, Flux Schnell)
- Generate multiple images per request (batch)

**Optimize costs:**
- Set appropriate keepalive duration
- Shutdown when done
- Use keepalive for interactive sessions only
- Monitor active workers in RunPod dashboard

**Optimize quality:**
- Increase steps (40-50)
- Use higher CFG scale (8-12)
- Use specific seeds for consistency
- Add detailed prompts and negative prompts

---

## Next Steps

- **[Workflow Guide](WORKFLOW.md)** - Complete workflow walkthrough
- **[SwarmUI API Reference](SWARMUI_API.md)** - Full API documentation
- **[Setup Guide](SETUP.md)** - First-time deployment
- **[Back to README](README.md)** - Project overview

---

## Support

- **GitHub Issues:** Bug reports and feature requests
- **[SwarmUI Discord](https://discord.gg/q2y38cqjNw):** SwarmUI-specific help
- **[RunPod Discord](https://discord.gg/runpod):** RunPod platform support
