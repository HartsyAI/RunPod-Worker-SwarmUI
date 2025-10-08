"""RunPod Handler for SwarmUI Serverless Worker - Simplified Version

Uses SwarmUI's official install and launch scripts.
Just waits for readiness and handles generation requests.
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
CHECK_INTERVAL = 10

# Setup session with retries
session = requests.Session()
retries = Retry(
    total=10,
    backoff_factor=0.3,
    status_forcelist=[502, 503, 504],
    allowed_methods=["GET", "POST"]
)
session.mount('http://', HTTPAdapter(max_retries=retries))
session.mount('https://', HTTPAdapter(max_retries=retries))


def wait_for_service(url: str, max_attempts: Optional[int] = None) -> bool:
    """Wait briefly for a SwarmUI endpoint to respond."""

    attempts = max_attempts or max(1, STARTUP_TIMEOUT // CHECK_INTERVAL)

    for attempt in range(attempts):
        try:
            response = session.post(f"{url}/API/GetNewSession", json={}, timeout=10)
            if response.status_code == 200 and "session_id" in response.json():
                return True
        except requests.exceptions.RequestException:
            pass

        time.sleep(CHECK_INTERVAL)

    return False


def wait_for_swarmui_ready(max_wait_seconds: int = STARTUP_TIMEOUT) -> bool:
    """Wait for SwarmUI API to be ready and have a backend available.
    
    Args:
        max_wait_seconds: Maximum seconds to wait
        
    Returns:
        bool: True if ready, False if timeout
    """
    print("=" * 80)
    print("Waiting for SwarmUI to be ready...")
    print("=" * 80)
    print(f"URL: {SWARMUI_API_URL}")
    print(f"Max wait: {max_wait_seconds}s")
    print()
    
    start_time = time.time()
    max_attempts = max_wait_seconds // CHECK_INTERVAL
    
    for attempt in range(max_attempts):
        elapsed = int(time.time() - start_time)
        
        try:
            # Try to get a session - this tests if SwarmUI is responsive
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
                    # Try a test generation with 0 images to see if backend exists
                    test_response = session.post(
                        f"{SWARMUI_API_URL}/API/GenerateText2Image",
                        json={
                            "session_id": session_id,
                            "prompt": "test",
                            "model": "OfficialStableDiffusion/sd_xl_base_1.0",
                            "images": 0,
                            "width": 512,
                            "height": 512,
                            "steps": 1
                        },
                        timeout=10
                    )
                    
                    if test_response.status_code == 200:
                        result = test_response.json()
                        error = result.get('error', '')
                        
                        # If no error or error isn't about missing backend, we're good
                        if not error or 'No backends available' not in str(error):
                            print()
                            print(f"✓ SwarmUI ready after {elapsed}s!")
                            print(f"  Version: {data.get('version', 'unknown')}")
                            return True
                        else:
                            print(f"  [{elapsed:4d}s] Backend still starting...")
                    else:
                        print(f"  [{elapsed:4d}s] Testing backend readiness...")
                else:
                    print(f"  [{elapsed:4d}s] Waiting for valid session...")
            else:
                print(f"  [{elapsed:4d}s] Waiting for SwarmUI service...")
                
        except requests.exceptions.RequestException:
            print(f"  [{elapsed:4d}s] Connecting...")
        except Exception as e:
            print(f"  [{elapsed:4d}s] Error: {type(e).__name__}")
        
        if elapsed >= max_wait_seconds:
            break
            
        time.sleep(CHECK_INTERVAL)
    
    print()
    print(f"ERROR: SwarmUI not ready after {max_wait_seconds}s")
    return False


def get_session_id() -> Optional[str]:
    """Get a new SwarmUI session ID.
    
    Returns:
        str: Session ID or None if failed
    """
    try:
        response = session.post(
            f"{SWARMUI_API_URL}/API/GetNewSession",
            json={},
            timeout=30
        )
        response.raise_for_status()
        
        data = response.json()
        session_id = data.get("session_id")

        if session_id:
            print(f"✓ Session ID: {session_id[:16]}...")
            return session_id

        print("ERROR: No session_id in response")
        return None
    except Exception as e:
        print(f"ERROR: Failed to get session: {e}")
        return None


def generate_image(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an image using SwarmUI API.

    Args:
        job_input: Dictionary containing generation parameters

    Returns:
        dict: Generation result with images or error
    """
    # Support install-only warm up to trigger SwarmUI boot without requiring models.
    if job_input.get("install_only"):
        print("Install-only warm-up requested; ensuring SwarmUI service is ready...")

        if not wait_for_service(SWARMUI_API_URL):
            return {"error": "SwarmUI service not ready during install warm-up"}

        session_id = get_session_id()
        if not session_id:
            return {"error": "Failed to obtain session during install warm-up"}

        return {
            "status": "install_ready",
            "message": "SwarmUI responded successfully to install-only warm-up",
            "session_id": session_id,
        }

    # Get session ID
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

    # Build SwarmUI API request
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
    
    print()
    print("=" * 80)
    print("Generating Image")
    print("=" * 80)
    print(f"Prompt: '{prompt[:60]}...'")
    print(f"Model: {model}")
    print(f"Size: {width}x{height}, Steps: {steps}, CFG: {cfg_scale}")
    print()
    
    try:
        # Send generation request
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
            print(f"ERROR: {error_msg}")
            return {"error": error_msg}
        
        # Extract images
        if 'images' in result and len(result['images']) > 0:
            print(f"✓ Generation complete, fetching {len(result['images'])} image(s)...")
            
            images = []
            for img_path in result['images']:
                img_data = fetch_image_as_base64(img_path)
                if img_data:
                    images.append(img_data)
            
            if len(images) == 0:
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
        return {"error": f"Generation timed out after {GENERATION_TIMEOUT}s"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """RunPod handler - entry point for all requests.
    
    Args:
        job: Job with input parameters
        
    Returns:
        dict: Result or error
    """
    try:
        print()
        print("=" * 80)
        print("SwarmUI RunPod Handler - Processing Request")
        print("=" * 80)
        
        job_input = job.get('input', {})
        
        if not job_input:
            return {"error": "No input provided"}
        
        result = generate_image(job_input)
        
        print()
        print("=" * 80)
        print("✓ Request Complete")
        print("=" * 80)
        
        return result
        
    except Exception as e:
        print(f"ERROR: Handler error: {e}")
        return {"error": f"Handler error: {str(e)}"}


# Initialize - wait for SwarmUI to be ready
if __name__ == "__main__":
    print("=" * 80)
    print("SwarmUI RunPod Serverless Worker - Initialization")
    print("=" * 80)
    print()
    
    if not wait_for_swarmui_ready():
        print()
        print("FATAL: SwarmUI failed to start")
        print("Check container logs for errors")
        exit(1)
    
    print()
    print("=" * 80)
    print("✓ System Ready - Starting RunPod Handler")
    print("=" * 80)
    print()
    
    runpod.serverless.start({"handler": handler})
