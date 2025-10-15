# Architecture Documentation

This document explains the design decisions, data flow, and internals of the SwarmUI RunPod Serverless worker.

---

## Design Philosophy

**Minimal handler, maximum flexibility.**

This project follows a "thin wrapper" philosophy:
- Handler does the minimum necessary work
- SwarmUI's official scripts handle installation
- External apps control generation logic
- Pass-through design for SwarmUI API

### Why This Approach?

**Previous problems with "fat" handlers:**
- ❌ 700+ lines of model management code
- ❌ Complex image encoding/decoding
- ❌ Tight coupling to specific SwarmUI features
- ❌ Difficult to update when SwarmUI changes
- ❌ Business logic mixed with infrastructure

**Benefits of "thin" handler:**
- ✅ ~200 lines, easy to understand
- ✅ External app has full control
- ✅ Works with any SwarmUI feature
- ✅ Easy to update (just change SwarmUI version)
- ✅ Clean separation of concerns

---

## Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      External Application                    │
│              (Your Python/C#/JS code)                        │
└───────────────────┬─────────────────────────────────────────┘
                    │ HTTPS
                    ↓
┌─────────────────────────────────────────────────────────────┐
│                    RunPod API Gateway                        │
│           https://api.runpod.ai/v2/{endpoint}                │
└───────────────────┬─────────────────────────────────────────┘
                    │ Internal routing
                    ↓
┌─────────────────────────────────────────────────────────────┐
│                   RunPod Handler Container                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  rp_handler.py                                       │   │
│  │  - Wait for SwarmUI ready                           │   │
│  │  - Provide health/ready endpoints                   │   │
│  │  - Forward SwarmUI API requests                     │   │
│  │  - Handle keepalive/shutdown                        │   │
│  └────────────────┬────────────────────────────────────┘   │
│                   │ HTTP (localhost)                        │
│                   ↓                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  SwarmUI (localhost:7801)                           │   │
│  │  - Image generation                                 │   │
│  │  - Model management                                 │   │
│  │  - Backend coordination                             │   │
│  └────────────────┬────────────────────────────────────┘   │
│                   │                                          │
│                   ↓                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ComfyUI Backend                                    │   │
│  │  - GPU inference                                    │   │
│  │  - Model loading                                    │   │
│  └─────────────────────────────────────────────────────┘   │
└───────────────────┬─────────────────────────────────────────┘
                    │ Reads/writes
                    ↓
┌─────────────────────────────────────────────────────────────┐
│              RunPod Network Volume                           │
│  /runpod-volume/                                            │
│  ├── SwarmUI/          (installed by official scripts)     │
│  ├── Models/           (user models)                        │
│  └── Output/           (generated images)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Request Flow

### 1. Worker Startup

```
Container Start
    ↓
start.sh executes
    ↓
Check if /runpod-volume/SwarmUI exists
    ↓
┌─────────── First Run ─────────────┐  ┌── Subsequent Runs ──┐
│                                   │  │                      │
│ Download install-linux.sh         │  │ SwarmUI exists       │
│        ↓                          │  │        ↓             │
│ Run install-linux.sh              │  │ Skip install         │
│   (clone SwarmUI)                 │  │                      │
│        ↓                          │  │                      │
│ Run comfy-install-linux.sh        │  │                      │
│   (install ComfyUI)               │  │                      │
│        ↓                          │  │                      │
│ 20-30 minutes                     │  │ ~10 seconds          │
└─────────┬─────────────────────────┘  └──────┬───────────────┘
          │                                     │
          └──────────────┬──────────────────────┘
                         ↓
            Run launch-linux.sh
              (start SwarmUI)
                         ↓
            rp_handler.py starts
                         ↓
          wait_for_swarmui_ready()
            (poll until ready)
                         ↓
            RunPod Handler Running
```

### 2. External App Request Flow

```
External App
    ↓
POST /v2/{endpoint}/runsync
    {
      "input": {
        "action": "ready"
      }
    }
    ↓
RunPod Gateway
    ↓
handler(job)
    ↓
action_ready(job_input)
    ↓
swarm_request('POST', '/API/GetNewSession')
    ↓
SwarmUI @ localhost:7801
    ↓
Response: {session_id: "abc123"}
    ↓
Handler returns to RunPod Gateway
    ↓
External App receives:
    {
      "output": {
        "ready": true,
        "session_id": "abc123",
        "version": "0.6.5-Beta"
      }
    }
```

### 3. SwarmUI API Pass-Through

```
External App builds SwarmUI payload:
    {
      "session_id": "abc123",
      "prompt": "mountain landscape",
      "model": "sd_xl_base_1.0",
      "width": 1024,
      "height": 1024
    }
    ↓
POST /v2/{endpoint}/runsync
    {
      "input": {
        "action": "swarm_api",
        "method": "POST",
        "path": "/API/GenerateText2Image",
        "payload": { ... },
        "timeout": 600
      }
    }
    ↓
Handler receives job
    ↓
action_swarm_api(job_input)
    ↓
swarm_request(
    method='POST',
    path='/API/GenerateText2Image',
    payload={...},
    timeout=600
)
    ↓
POST http://localhost:7801/API/GenerateText2Image
    ↓
SwarmUI processes request
    ↓
ComfyUI generates image
    ↓
SwarmUI returns:
    {
      "images": ["Output/2024-10/image.png"],
      "seed": 12345
    }
    ↓
Handler wraps response:
    {
      "success": true,
      "response": { ... }
    }
    ↓
External App receives response
```

---

## Data Persistence

All persistent data lives on the RunPod network volume:

```
/runpod-volume/
├── SwarmUI/
│   ├── bin/                    # Built .NET binaries
│   ├── Data/                   # Settings, configs
│   │   ├── Settings.fds        # User settings
│   │   └── Models/             # Model metadata
│   ├── dlbackend/              # Backend installations
│   │   └── ComfyUI/
│   │       ├── models/         # ComfyUI models (symlinked)
│   │       └── custom_nodes/
│   ├── launchtools/            # Installation scripts
│   ├── Models/                 # Shared model directory
│   │   ├── Stable-Diffusion/
│   │   ├── Loras/
│   │   ├── VAE/
│   │   └── ControlNet/
│   ├── Output/                 # Generated images
│   └── src/                    # SwarmUI source
└── install-linux.sh            # Cached installer (first run)
```

**Why this structure?**
- SwarmUI's official scripts create this layout
- Models are shared between SwarmUI and ComfyUI via symlinks
- Settings persist across restarts
- Generated images can be retrieved later

**Network Volume Benefits:**
- ✅ Models downloaded once, reused by all workers
- ✅ Settings preserved across restarts
- ✅ Fast warm starts (60-90s vs 20-30 min)
- ✅ Multiple workers share the same models

---

## Handler Design

### Core Principles

1. **Do minimal work**: Just coordinate, don't process
2. **Trust SwarmUI**: Let it handle its own features
3. **Be transparent**: Pass-through requests/responses
4. **Fail gracefully**: Return errors, don't crash

### Handler Responsibilities

**✅ What the handler DOES:**
- Wait for SwarmUI to start
- Verify backends are ready
- Provide health/ready status
- Forward SwarmUI API requests
- Handle keepalive pings
- Accept shutdown signals

**❌ What the handler DOESN'T do:**
- Parse generation payloads
- Encode/decode images
- Manage models
- Validate SwarmUI requests
- Transform responses

### Why Pass-Through?

**Alternative: Handler parses everything**
```python
def generate_image(job_input):
    # Extract and validate 20+ parameters
    prompt = job_input.get('prompt')
    model = job_input.get('model')
    width = validate_width(job_input.get('width'))
    # ... 15 more fields
    
    # Build SwarmUI payload
    swarm_payload = {
        'session_id': get_session(),
        'prompt': prompt,
        # ... 20 more mappings
    }
    
    # Call SwarmUI
    response = swarm_post('/API/GenerateText2Image', swarm_payload)
    
    # Parse response
    images = response.get('images', [])
    
    # Fetch and encode images
    encoded = []
    for img_path in images:
        img_data = fetch_and_encode(img_path)
        encoded.append(img_data)
    
    return {'images': encoded}
```

**Problems:**
- ❌ 50+ lines per action
- ❌ Must update handler for new SwarmUI features
- ❌ Couples handler to SwarmUI internals
- ❌ Handler duplicates SwarmUI validation

**Our approach: Pass-through**
```python
def action_swarm_api(job_input):
    method = job_input.get('method', 'POST')
    path = job_input.get('path')
    payload = job_input.get('payload')
    timeout = job_input.get('timeout', 600)
    
    try:
        response = swarm_request(method, path, payload, timeout)
        return {'success': True, 'response': response}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

**Benefits:**
- ✅ 10 lines
- ✅ Works with ANY SwarmUI endpoint
- ✅ External app controls everything
- ✅ No handler updates needed

---

## Scalability

### Horizontal Scaling

RunPod automatically scales workers based on queue depth:

```
Queue Depth = 0  →  0 workers (cold)
Queue Depth = 1  →  1 worker spins up
Queue Depth = 5  →  5 workers spin up
Workers idle    →  Scale down after timeout
```

**Each worker:**
- Has its own SwarmUI instance
- Shares the network volume (models)
- Processes one job at a time
- Independent session management

### Network Volume Considerations

**✅ Safe for concurrent access:**
- Reading models
- Reading shared configs
- SwarmUI's Data/ directory (uses file locking)

**⚠️ Potential conflicts:**
- Writing to Output/ simultaneously
- Model downloads from multiple workers
- Editing shared settings

**Mitigation:**
- SwarmUI handles file locking
- Output files have unique names (timestamp + random)
- Model downloads are atomic operations

---

## Cold Start Optimization

### Why First Start is Slow

**Installation breakdown (20-30 min total):**
1. Download `install-linux.sh`: ~5s
2. Clone SwarmUI repo: ~30s
3. Run first-time setup: ~2 min
4. Install ComfyUI:
   - Download PyTorch (2GB): ~3 min
   - Install dependencies: ~5 min
   - Download ComfyUI: ~1 min
   - Build environment: ~5 min
5. Build SwarmUI:
   - Restore .NET packages: ~1 min
   - Compile: ~2 min
6. First launch: ~3 min

### Why Warm Starts are Fast

**Warm start breakdown (60-90s total):**
1. Check SwarmUI exists: instant
2. Run `launch-linux.sh`: ~10s
3. SwarmUI starts: ~20s
4. Load configs: ~5s
5. Backend warmup: ~30s
6. Ready check: ~10s

**Optimization techniques:**
- Network volume caches everything
- Pre-compiled binaries
- Model metadata cached
- Backend settings preserved
- No downloads needed

---

## Error Handling

### Handler Error Philosophy

**Fail gracefully, return useful errors.**

```python
# ✅ Good: Return error, don't crash
def action_swarm_api(job_input):
    try:
        response = swarm_request(...)
        return {'success': True, 'response': response}
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': f'Request timed out after {timeout}s'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

# ❌ Bad: Let it crash
def action_swarm_api(job_input):
    response = swarm_request(...)
    return response  # Crashes handler on error
```

### Error Types

**Network errors:**
- Timeout waiting for SwarmUI
- SwarmUI not responding
- Connection refused

**SwarmUI errors:**
- Invalid model name
- Missing backend
- Generation failed
- Out of memory

**Handler errors:**
- Missing parameters
- Invalid action
- Malformed payload

**All errors return:**
```json
{
  "success": false,
  "error": "Human-readable error message"
}
```

---

## Security Considerations

### RunPod Isolation

- Each worker runs in isolated container
- Network volume is private to your account
- No direct port exposure (RunPod gateway only)
- API key required for all requests

### SwarmUI Security

- Runs on localhost only (`0.0.0.0` bind, but firewalled)
- No authentication (not needed, internal only)
- File access limited to network volume

### Best Practices

**✅ Do:**
- Use RunPod API keys (keep secret)
- Validate inputs in external app
- Set reasonable timeouts
- Monitor costs

**❌ Don't:**
- Expose endpoint URLs publicly
- Share API keys
- Skip input validation
- Run untrusted payloads

---

## Performance Characteristics

### Typical Latencies

**Cold start (first run):**
- Installation: 20-30 minutes
- Ready check: 30 seconds

**Warm start:**
- Launch: 60-90 seconds
- Ready check: 10 seconds

**API calls:**
- Health check: <1 second
- Get session: <1 second
- List models: 1-3 seconds
- Generate SDXL 1024x1024 (20 steps): 10-20 seconds
- Generate Flux (20 steps): 30-60 seconds

### Cost Optimization

**Strategies:**
1. **Use keepalive**: Keep worker warm between requests
2. **Batch requests**: Process multiple images per session
3. **Shared volume**: Reuse models across workers
4. **Right-size GPU**: SDXL needs 24GB, Flux needs 40GB+
5. **Idle timeout**: Set based on usage pattern

**Example cost calculation:**
- RTX 4090 (24GB): $0.89/hour
- Idle timeout: 120 seconds
- Average job: 30 seconds
- Idle cost: $0.03 per job
- Generation cost: $0.007 per image

---

## Future Extensibility

### Adding New Features

**Handler side (rare):**
- New lifecycle actions (warmup, status)
- Enhanced logging
- Metrics collection
- Custom health checks

**External app side (common):**
- New SwarmUI features (just use new API paths)
- Custom workflows
- Model management
- Batch processing

### Example: Adding Image-to-Image

**No handler changes needed!**

External app just calls different endpoint:
```python
response = requests.post(
    BASE_URL,
    json={
        "input": {
            "action": "swarm_api",
            "method": "POST",
            "path": "/API/GenerateImage2Image",  # Different path
            "payload": {
                # Image-to-image params
            }
        }
    }
)
```

Handler automatically forwards it.

---

## Testing Strategy

### Unit Tests (Handler)

```python
# Test health check
def test_action_health():
    result = action_health({})
    assert 'healthy' in result

# Test error handling
def test_swarm_api_missing_path():
    result = action_swarm_api({})
    assert result['success'] is False
    assert 'path is required' in result['error']
```

### Integration Tests (Full Stack)

```bash
# Test health endpoint
python tests/test_health.py

# Test SwarmUI pass-through
python tests/test_swarm_passthrough.py
```

### Production Monitoring

**Key metrics:**
- Cold start time
- Warm start time
- Request success rate
- Average generation time
- Error rate by type

---

## Comparison: Before vs After

### Before (Fat Handler)

**Files:**
- `rp_handler.py`: 700+ lines
- Multiple test files
- Model management code
- Image encoding logic
- Complex routing

**Problems:**
- Hard to maintain
- Tight coupling to SwarmUI
- Duplicate validation logic
- Complex error handling
- Must update for new features

### After (Thin Handler)

**Files:**
- `rp_handler.py`: ~200 lines
- Simple test files
- No business logic
- Pass-through only
- Simple routing

**Benefits:**
- Easy to maintain
- Loose coupling
- No duplication
- Simple errors
- Works with all features

---

## Summary

**Key takeaways:**

1. **Minimal handler**: Only coordinate, don't process
2. **Pass-through design**: Let external app control everything
3. **Official scripts**: Use SwarmUI's own installation
4. **Network volume**: Persist everything between runs
5. **Clean separation**: Infrastructure vs business logic

**Result:** Production-ready, maintainable, flexible serverless worker in ~200 lines.
