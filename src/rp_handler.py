"""RunPod Handler for SwarmUI Serverless Worker.

Simplified version that uses SwarmUI's built-in installation and backend management.
SwarmUI's launch-linux.sh handles ComfyUI installation automatically.
"""

import os
import time
import base64
import requests
import runpod
from typing import Dict, Any, Optional
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration
SWARMUI_API_URL = os.getenv('SWARMUI_API_URL', 'http://127.0.0.1:7801')
GENERATION_TIMEOUT = int(os.getenv('GENERATION_TIMEOUT', '600'))
STARTUP_TIMEOUT = int(os.getenv('STARTUP_TIMEOUT', '1800'))

# Setup session with retries
session = requests.Session()
retries = Retry(
    total=10,
    backoff_factor=0.3,
    status_forcelist=[502, 503, 504],
    allowed_methods=["GET", "POST"]
)
session.mount('http://', HTTPAdapter(max_retries=retries))


def wait_for_swarmui_ready(max_wait_seconds: int = STARTUP_TIMEOUT) -> bool:
    """Wait for SwarmUI server and ComfyUI backend to be fully ready.
    
    SwarmUI's launch-linux.sh automatically installs and starts ComfyUI.
    We just need to wait until the backend is running.
    
    Args:
        max_wait_seconds: Maximum time to wait
        
    Returns:
        bool: True if ready, False if timeout
    """
    print("=" * 80)
    print("Waiting for SwarmUI and ComfyUI Backend")
    print("=" * 80)
    print(f"Target: {SWARMUI_API_URL}")
    print(f"Max wait: {max_wait_seconds}s")
    print("")
    print("First run: 10-20 minutes (SwarmUI build + ComfyUI installation)")
    print("Subsequent runs: 30-90 seconds (just startup)")
    print("=" * 80)
    print("")
    
    start_time = time.time()
    check_interval = 10
    last_status = None
    
    while time.time() - start_time < max_wait_seconds:
        elapsed = int(time.time() - start_time)
        
        try:
            # Try to get a session - this is the simplest health check
            response = session.post(
                f"{SWARMUI_API_URL}/API/GetNewSession",
                json={},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                session_id = data.get('session_id')
                
                if session_id:
                    # SwarmUI is responding, now check if backend is ready
                    backend_response = session.post(
                        f"{SWARMUI_API_URL}/API/ListBackends",
                        json={"session_id": session_id},
                        timeout=10
                    )
                    
                    if backend_response.status_code == 200:
                        backends = backend_response.json().get('backends', [])
                        
                        # Check for running backends
                        running_backends = [
                            b for b in backends 
                            if b.get('status') in ['running', 'ready', 'loaded']
                        ]
                        
                        if running_backends:
                            print("")
                            print("=" * 80)
                            print(f"✓ System Ready! (took {elapsed}s)")
                            print("=" * 80)
                            print(f"SwarmUI Version: {data.get('version', 'unknown')}")
                            print(f"Available Backends: {len(running_backends)}")
                            for backend in running_backends:
                                print(f"  - {backend.get('title', 'Unknown')}: {backend.get('status')}")
                            print("=" * 80)
                            return True
                        
                        # Show backend status
                        if backends:
                            status_msg = ", ".join([
                                f"{b.get('title', 'Unknown')}: {b.get('status', 'unknown')}"
                                for b in backends
                            ])
                            if status_msg != last_status:
                                print(f"[{elapsed:4d}s] Backends: {status_msg}")
                                last_status = status_msg
                        else:
                            if last_status != "installing":
                                print(f"[{elapsed:4d}s] SwarmUI ready, waiting for ComfyUI installation...")
                                last_status = "installing"
                    else:
                        # Backend API not ready yet
                        if last_status != "swarmui_starting":
                            print(f"[{elapsed:4d}s] SwarmUI starting, backends not ready yet...")
                            last_status = "swarmui_starting"
            else:
                # SwarmUI not responding yet
                if last_status != "waiting":
                    print(f"[{elapsed:4d}s] Waiting for SwarmUI server...")
                    last_status = "waiting"
                    
        except requests.exceptions.RequestException:
            if last_status != "connecting":
                print(f"[{elapsed:4d}s] Connecting to SwarmUI...")
                last_status = "connecting"
        except Exception as e:
            print(f"[{elapsed:4d}s] Unexpected error: {type(e).__name__}")
        
        time.sleep(check_interval)
    
    print("")
    print("=" * 80)
    print(f"ERROR: System not ready after {max_wait_seconds}s")
    print("=" * 80)
    print("")
    print("Troubleshooting:")
    print("  1. Check container logs for errors")
    print("  2. First run needs 10-20 minutes for full installation")
    print("  3. Ensure network volume has sufficient space (50GB+)")
    print("  4. Verify .NET 8 SDK and Python 3.11 are installed")
    return False


def get_session_id() -> Optional[str]:
    """Get a SwarmUI session ID.
    
    Returns:
        str: Session ID if successful, None otherwise
    """
    try:
        response = session.post(
            f"{SWARMUI_API_URL}/API/GetNewSession",
            json={},
            timeout=30
        )
        response.raise_for_status()
        
        session_id = response.json().get("session_id")
        if session_id:
            print(f"✓ Session ID: {session_id[:16]}...")
            return session_id
        
        print("ERROR: No session_id in response")
        return None
        
    except Exception as e:
        print(f"ERROR: Failed to get session: {e}")
        return None


def fetch_image_as_base64(image_path: str) -> Optional[Dict[str, str]]:
    """Fetch image from SwarmUI and encode as base64.
    
    Args:
        image_path: Path returned by SwarmUI API
        
    Returns:
        dict: Image data with filename and base64 encoding
    """
    try:
        img_url = f"{SWARMUI_API_URL}/{image_path}"
        response = session.get(img_url, timeout=30)
        response.raise_for_status()
        
        img_base64 = base64.b64encode(response.content).decode('utf-8')
        filename = image_path.split('/')[-1]
        
        return {
            "filename": filename,
            "type": "base64",
            "data": img_base64
        }
        
    except Exception as e:
        print(f"ERROR: Failed to fetch image {image_path}: {e}")
        return None


def generate_image(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Generate image using SwarmUI API.
    
    Args:
        job_input: Generation parameters
        
    Returns:
        dict: Result with images or error
    """
    # Get session
    session_id = get_session_id()
    if not session_id:
        return {"error": "Failed to create SwarmUI session"}
    
    # Extract parameters with defaults
    prompt = job_input.get('prompt', 'a beautiful landscape')
    negative_prompt = job_input.get('negative_prompt', '')
    model = job_input.get('model', 'OfficialStableDiffusion/sd_xl_base_1.0')
    width = int(job_input.get('width', 1024))
    height = int(job_input.get('height', 1024))
    steps = int(job_input.get('steps', 30))
    cfg_scale = float(job_input.get('cfg_scale', 7.5))
    seed = int(job_input.get('seed', -1))
    images_count = int(job_input.get('images', 1))
    
    # Build request
    swarm_request = {
        "session_id": session_id,
        "prompt": prompt,
        "negativeprompt": negative_prompt,
        "model": model,
        "width": width,
        "height": height,
        "steps": steps,
        "cfgscale": cfg_scale,
        "seed": seed,
        "images": images_count,
        "donotsave": False
    }
    
    print("")
    print("=" * 80)
    print("Generating Image")
    print("=" * 80)
    print(f"Prompt: {prompt[:60]}{'...' if len(prompt) > 60 else ''}")
    print(f"Model: {model}")
    print(f"Size: {width}x{height}, Steps: {steps}, CFG: {cfg_scale}")
    print("=" * 80)
    print("")
    
    try:
        # Generate
        response = session.post(
            f"{SWARMUI_API_URL}/API/GenerateText2Image",
            json=swarm_request,
            timeout=GENERATION_TIMEOUT
        )
        response.raise_for_status()
        
        result = response.json()
        
        # Check for errors
        if 'error' in result or 'error_id' in result:
            error_msg = result.get('error', result.get('error_id', 'Unknown error'))
            print(f"ERROR: SwarmUI error: {error_msg}")
            return {"error": error_msg}
        
        # Fetch images
        if 'images' in result and len(result['images']) > 0:
            print(f"✓ Generated {len(result['images'])} image(s), fetching...")
            
            images = []
            for img_path in result['images']:
                img_data = fetch_image_as_base64(img_path)
                if img_data:
                    images.append(img_data)
            
            if not images:
                return {"error": "Failed to fetch generated images"}
            
            print(f"✓ Successfully returned {len(images)} image(s)")
            
            return {
                "images": images,
                "parameters": {
                    "prompt": prompt,
                    "negative_prompt": negative_prompt,
                    "model": model,
                    "seed": result.get('seed', seed),
                    "width": width,
                    "height": height,
                    "steps": steps,
                    "cfg_scale": cfg_scale
                }
            }
        
        print("ERROR: No images in response")
        return {"error": "No images generated"}
        
    except requests.exceptions.Timeout:
        return {"error": f"Generation timeout after {GENERATION_TIMEOUT}s"}
    except Exception as e:
        return {"error": f"Generation failed: {str(e)}"}


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """RunPod handler - entry point for all requests.
    
    Args:
        job: Job data with input parameters
        
    Returns:
        dict: Result or error
    """
    try:
        print("")
        print("=" * 80)
        print("SwarmUI RunPod Serverless - New Request")
        print("=" * 80)
        
        job_input = job.get('input', {})
        if not job_input:
            return {"error": "No input provided"}
        
        result = generate_image(job_input)
        
        print("")
        print("=" * 80)
        print("✓ Request Complete")
        print("=" * 80)
        
        return result
        
    except Exception as e:
        print(f"ERROR: Handler error: {e}")
        return {"error": f"Handler error: {str(e)}"}


# Initialize - wait for SwarmUI and ComfyUI to be ready
if __name__ == "__main__":
    print("")
    print("=" * 80)
    print("SwarmUI RunPod Serverless Worker")
    print("=" * 80)
    print("")
    
    if not wait_for_swarmui_ready():
        print("")
        print("FATAL: SwarmUI failed to start")
        print("Check container logs for details")
        exit(1)
    
    print("")
    print("=" * 80)
    print("Starting RunPod Handler")
    print("=" * 80)
    print("Ready to accept generation requests")
    print("=" * 80)
    print("")
    
    runpod.serverless.start({"handler": handler})
