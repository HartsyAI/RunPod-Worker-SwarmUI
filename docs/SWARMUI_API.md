# SwarmUI API Reference

Complete reference for SwarmUI's API endpoints with examples for direct URL access.

---

## Overview

SwarmUI provides a full-capability REST API for image generation and server management. Once you have the public worker URL, you can call any SwarmUI API endpoint directly.

**Base URL format:**
```
https://{worker-id}-7801.proxy.runpod.net/API/{endpoint}
```

**📖 Related Documentation:**
- **[Setup Guide](SETUP.md)** - First-time deployment
- **[Workflow Guide](WORKFLOW.md)** - Complete workflow walkthrough  
- **[Client Usage Guide](CLIENT.md)** - Python client examples
- **[Back to README](README.md)** - Project overview

**Official SwarmUI Documentation:**
- [SwarmUI API Docs](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/API.md)
- [API Routes Documentation](https://github.com/mcmonkeyprojects/SwarmUI/tree/master/docs/APIRoutes)

---

## Quick Reference

### Essential Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/API/GetNewSession` | POST | Get session ID (required for all other calls) |
| `/API/GenerateText2Image` | POST | Generate images from text prompts |
| `/API/ListModels` | POST | List available models |
| `/API/DescribeModel` | POST | Get detailed model information |
| `/API/DoModelDownloadWS` | WebSocket | Download models from URLs |

**💡 See [WORKFLOW.md](WORKFLOW.md) for complete usage examples**

---

## Authentication & Sessions

### GetNewSession

**Must be called first** - all other endpoints require a `session_id`.

**Request:**
```bash
curl -X POST https://abc123-7801.proxy.runpod.net/API/GetNewSession \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Python:**
```python
import requests

response = requests.post(
    f"{public_url}/API/GetNewSession",
    json={},
    headers={"Content-Type": "application/json"}
)

data = response.json()
session_id = data["session_id"]
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

**Session Management:**
- Sessions expire after ~1 hour of inactivity
- Create one session per workflow
- Reuse session for multiple requests
- If you get `invalid_session_id` error, get a new session

**💡 See [CLIENT.md](CLIENT.md) for session management best practices**

---

## Image Generation

### GenerateText2Image

Generate images from text prompts.

**Request:**
```bash
curl -X POST https://abc123-7801.proxy.runpod.net/API/GenerateText2Image \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "YOUR_SESSION_ID",
    "prompt": "a beautiful mountain landscape",
    "negative_prompt": "blurry, low quality",
    "model": "OfficialStableDiffusion/sd_xl_base_1.0",
    "width": 1024,
    "height": 1024,
    "steps": 30,
    "cfg_scale": 7.5,
    "seed": -1,
    "images": 1
  }'
```

**Python:**
```python
response = requests.post(
    f"{public_url}/API/GenerateText2Image",
    json={
        "session_id": session_id,
        "prompt": "a beautiful mountain landscape at sunset",
        "negative_prompt": "blurry, low quality, distorted",
        "model": "OfficialStableDiffusion/sd_xl_base_1.0",
        "width": 1024,
        "height": 1024,
        "steps": 30,
        "cfg_scale": 7.5,
        "seed": -1,
        "images": 1
    },
    timeout=600
)

result = response.json()
images = result.get("images", [])
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

**Parameters:**

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `session_id` | string | Yes | - | Session ID from GetNewSession |
| `prompt` | string | Yes | - | Text description of desired image |
| `negative_prompt` | string | No | "" | What to avoid in the image |
| `model` | string | Yes | - | Model identifier (see ListModels) |
| `width` | integer | No | 1024 | Image width (multiple of 64) |
| `height` | integer | No | 1024 | Image height (multiple of 64) |
| `steps` | integer | No | 30 | Generation steps (20-50 typical) |
| `cfg_scale` | float | No | 7.5 | Prompt guidance (7-12 typical) |
| `seed` | integer | No | -1 | Random seed (-1 for random) |
| `images` | integer | No | 1 | Number of images to generate |
| `sampler` | string | No | - | Sampler name |
| `scheduler` | string | No | - | Scheduler name |
| `init_image` | string | No | - | Base64 init image for img2img |
| `init_image_creativity` | float | No | 0.6 | How much to change init image |

**Image Dimensions:**
- Must be multiples of 64
- SDXL recommended: 1024x1024, 1216x832, 832x1216
- SD 1.5 recommended: 512x512, 768x512, 512x768
- Larger sizes = longer generation time

**Steps:**
- 15-20: Fast, lower quality
- 25-35: Balanced (recommended)
- 40-50: High quality, slower

**CFG Scale:**
- 5-7: More creative, less faithful to prompt
- 7-9: Balanced (recommended)
- 10-15: Very faithful to prompt, less creative

**Timing:**
- First generation: ~40 seconds (10s model load + 30s generation)
- Subsequent generations: ~30 seconds (model already loaded)

**💡 See [WORKFLOW.md](WORKFLOW.md) for complete generation examples**

---

### GenerateText2ImageWS

WebSocket version with progress updates and preview images.

**Connection:**
```javascript
const ws = new WebSocket(
    `wss://abc123-7801.proxy.runpod.net/API/GenerateText2ImageWS`
);

ws.onopen = () => {
    ws.send(JSON.stringify({
        session_id: session_id,
        prompt: "a mountain landscape",
        model: "OfficialStableDiffusion/sd_xl_base_1.0",
        width: 1024,
        height: 1024,
        steps: 30
    }));
};

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.progress) {
        console.log(`Progress: ${data.progress}%`);
    }
    
    if (data.preview_image) {
        // Display preview image
        displayImage(data.preview_image);
    }
    
    if (data.images) {
        // Final images ready
        console.log("Complete:", data.images);
    }
};
```

---

## Model Management

### ListModels

List available models on the server.

**Request:**
```python
response = requests.post(
    f"{public_url}/API/ListModels",
    json={
        "session_id": session_id,
        "path": "",                    # Root folder ("" or specific path)
        "depth": 2,                    # Subfolder depth to search
        "subtype": "Stable-Diffusion", # Model type
        "allowRemote": true            # Include remote models
    }
)

data = response.json()
files = data.get("files", [])
folders = data.get("folders", [])
```

**Model Subtypes:**
- `Stable-Diffusion` - Base models (SDXL, Flux, SD 1.5)
- `LoRA` - LoRA adapters
- `VAE` - VAE models
- `ControlNet` - ControlNet models
- `Embedding` - Text embeddings
- `Wildcards` - Prompt wildcards

**Response:**
```json
{
    "files": [
        "OfficialStableDiffusion/sd_xl_base_1.0",
        "OfficialStableDiffusion/sd_xl_refiner_1.0",
        "BFL/flux1-dev-fp8",
        "BFL/flux1-schnell-fp8"
    ],
    "folders": [
        "OfficialStableDiffusion",
        "BFL",
        "StabilityAI"
    ]
}
```

**Note:** Listing models reads from disk and does NOT load backends or use GPU. This is a fast, inexpensive operation.

**💡 See [CLIENT.md](CLIENT.md) for model listing examples**

---

### DescribeModel

Get detailed metadata for a specific model.

**Request:**
```python
response = requests.post(
    f"{public_url}/API/DescribeModel",
    json={
        "session_id": session_id,
        "model_name": "OfficialStableDiffusion/sd_xl_base_1.0",
        "subtype": "Stable-Diffusion"
    }
)

model_info = response.json()["model"]
```

**Response:**
```json
{
    "model": {
        "name": "sd_xl_base_1.0",
        "title": "Stable Diffusion XL Base 1.0",
        "author": "Stability AI",
        "description": "Base SDXL model for 1024x1024 generation",
        "preview_image": "data:image/jpg;base64,...",
        "loaded": true,
        "architecture": "stable-diffusion-xl-v1-base",
        "class": "Stable-Diffusion",
        "standard_width": 1024,
        "standard_height": 1024,
        "license": "CreativeML Open RAIL++-M",
        "date": "2023-07-26",
        "usage_hint": "Use for high quality 1024x1024 image generation",
        "tags": ["sdxl", "base", "1024x1024"],
        "is_supported_model_format": true,
        "local": true
    }
}
```

---

### DoModelDownloadWS

Download a model from a URL (WebSocket with progress).

**Connection:**
```python
import websocket
import json

ws = websocket.create_connection(
    f"wss://abc123-7801.proxy.runpod.net/API/DoModelDownloadWS"
)

ws.send(json.dumps({
    "session_id": session_id,
    "url": "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
    "type": "Stable-Diffusion",
    "name": "my-custom-model"
}))

while True:
    msg = json.loads(ws.recv())
    
    if msg.get("progress"):
        print(f"Progress: {msg['progress']}%")
    
    if msg.get("success"):
        print("Download complete!")
        break
    
    if msg.get("error"):
        print(f"Error: {msg['error']}")
        break
```

**💡 See [SETUP.md](SETUP.md) for model upload methods**

---

## Advanced Features

### User Settings

**Get Settings:**
```python
response = requests.post(
    f"{public_url}/API/GetUserSettings",
    json={"session_id": session_id}
)

settings = response.json()["settings"]
```

**Edit Settings:**
```python
response = requests.post(
    f"{public_url}/API/EditUserSettings",
    json={
        "session_id": session_id,
        "setting_id": "value"
    }
)
```

---

### Batch Operations

**Generate Multiple Images:**
```python
# Single request, multiple images
response = requests.post(
    f"{public_url}/API/GenerateText2Image",
    json={
        "session_id": session_id,
        "prompt": "a landscape",
        "model": "OfficialStableDiffusion/sd_xl_base_1.0",
        "width": 1024,
        "height": 1024,
        "steps": 30,
        "images": 4  # Generate 4 images
    },
    timeout=1200
)
```

---

### Image-to-Image Generation

**Using init_image parameter:**
```python
import base64

# Load and encode image
with open("input.png", "rb") as f:
    image_data = base64.b64encode(f.read()).decode()

response = requests.post(
    f"{public_url}/API/GenerateText2Image",
    json={
        "session_id": session_id,
        "prompt": "same image but at sunset",
        "model": "OfficialStableDiffusion/sd_xl_base_1.0",
        "width": 1024,
        "height": 1024,
        "steps": 30,
        "init_image": f"data:image/png;base64,{image_data}",
        "init_image_creativity": 0.6  # 0-1, higher = more changes
    },
    timeout=600
)
```

---

## Error Handling

### Common Errors

**invalid_session_id:**
```json
{
    "error_id": "invalid_session_id",
    "error": "Session ID is invalid or expired"
}
```

**Solution:** Get a new session with `GetNewSession`

**Model not found:**
```json
{
    "error": "Model 'xyz' not found"
}
```

**Solution:** Check available models with `ListModels`

**Backend not ready:**
```json
{
    "error": "No backends available"
}
```

**Solution:** Wait for backends to load (happens on first generation)

---

### Error Handling Pattern

```python
import requests

try:
    response = requests.post(
        f"{public_url}/API/GenerateText2Image",
        json={...},
        timeout=600
    )
    response.raise_for_status()
    
    result = response.json()
    
    # Check for SwarmUI errors
    if "error" in result or "error_id" in result:
        error_id = result.get("error_id")
        error_msg = result.get("error", "Unknown error")
        
        if error_id == "invalid_session_id":
            # Get new session and retry
            session_id = get_new_session()
            # retry...
        else:
            print(f"SwarmUI error: {error_msg}")
    else:
        # Success
        images = result.get("images", [])
        
except requests.exceptions.Timeout:
    print("Request timed out")
except requests.exceptions.HTTPError as e:
    print(f"HTTP error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

---

## Complete API Endpoints

### Generation
- `/API/GenerateText2Image` - Generate images from text
- `/API/GenerateText2ImageWS` - WebSocket version with progress
- `/API/InterruptAll` - Cancel all running generations

### Models
- `/API/ListModels` - List available models
- `/API/DescribeModel` - Get model details
- `/API/DoModelDownloadWS` - Download model from URL
- `/API/ListLoadedModels` - List currently loaded models
- `/API/DeleteModel` - Delete a model

### Session & User
- `/API/GetNewSession` - Create new session
- `/API/GetUserSettings` - Get user settings
- `/API/EditUserSettings` - Update user settings

### Admin (if enabled)
- `/API/ChangeServerSettings` - Modify server settings
- `/API/ListBackends` - List backend status
- `/API/RestartBackend` - Restart a backend

**For complete API documentation:**
- [Official SwarmUI API Docs](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/API.md)
- [BasicAPIFeatures](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/APIRoutes/BasicAPIFeatures.md)
- [ModelsAPI](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/APIRoutes/ModelsAPI.md)
- [AdminAPI](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/APIRoutes/AdminAPI.md)
- [ComfyUIWebAPI](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/APIRoutes/ComfyUIWebAPI.md)

---

## Performance Tips

**Optimize Speed:**
- Use smaller dimensions (512x512 vs 1024x1024)
- Reduce steps (20 vs 50)
- Use faster models (SDXL Turbo, Flux Schnell)
- Use efficient samplers (DPM++ 2M Karras)

**Optimize Quality:**
- Increase steps (40-50)
- Use higher CFG scale (8-12)
- Use detailed prompts
- Use appropriate negative prompts
- Use higher resolutions

**Optimize Costs:**
- Batch multiple generations in one request
- Reuse sessions
- Use appropriate step counts
- Monitor generation times

**💡 See [CLIENT.md](CLIENT.md) for performance optimization examples**

---

## Best Practices

**✅ Do:**
- Get a session before making API calls
- Reuse sessions for multiple requests
- Handle `invalid_session_id` errors gracefully
- Set appropriate timeouts for long generations
- Check model availability with ListModels

**❌ Don't:**
- Skip GetNewSession call
- Create new session for every request
- Use excessively high step counts
- Ignore error responses
- Assume models are always loaded

---

## Timing Reference

### Model Listing
- Time: <1 second
- Cost: ~$0.0001 (negligible)
- GPU: Not used (disk read only)

### First Generation (Backend Load)
- Model load: ~10 seconds
- Generation: ~30 seconds
- Total: ~40 seconds
- Cost: ~$0.01 (RTX 4090)

### Subsequent Generations
- Time: ~30 seconds
- Cost: ~$0.008 (RTX 4090)

### Session Creation
- Time: <1 second
- Cost: Negligible

**💡 See [WORKFLOW.md](WORKFLOW.md) for complete timing breakdown**

---

## Next Steps

- **[Workflow Guide](WORKFLOW.md)** - Complete workflow walkthrough
- **[Client Usage Guide](CLIENT.md)** - Using the Python client
- **[Setup Guide](SETUP.md)** - First-time deployment
- **[Back to README](README.md)** - Project overview

---

## External Resources

**Official SwarmUI Documentation:**
- [Main Repository](https://github.com/mcmonkeyprojects/SwarmUI)
- [API Documentation](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/API.md)
- [Basic Usage Guide](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/Basic%20Usage.md)
- [Model Support](https://github.com/mcmonkeyprojects/SwarmUI/blob/master/docs/Model%20Support.md)

**Community:**
- [SwarmUI Discord](https://discord.gg/q2y38cqjNw)
- [GitHub Discussions](https://github.com/mcmonkeyprojects/SwarmUI/discussions)
- [GitHub Issues](https://github.com/mcmonkeyprojects/SwarmUI/issues)

---

## Support

- **GitHub Issues:** Bug reports and feature requests
- **[SwarmUI Discord](https://discord.gg/q2y38cqjNw):** SwarmUI-specific help
- **[RunPod Discord](https://discord.gg/runpod):** RunPod platform support
