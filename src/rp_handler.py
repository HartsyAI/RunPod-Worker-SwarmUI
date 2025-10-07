"""RunPod Handler for SwarmUI Serverless Worker.

Enhanced version that waits for ComfyUI backend installation and readiness.
"""

import os
import time
import base64
import requests
import runpod
from typing import Dict, Any, Optional, List
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration
SWARMUI_API_URL = os.getenv('SWARMUI_API_URL', 'http://127.0.0.1:7801')
GENERATION_TIMEOUT = int(os.getenv('GENERATION_TIMEOUT', '600'))
SERVICE_WAIT_INTERVAL = int(os.getenv('SERVICE_WAIT_INTERVAL', '10'))
BACKEND_WAIT_INTERVAL = int(os.getenv('BACKEND_WAIT_INTERVAL', '15'))
STARTUP_TIMEOUT = int(os.getenv('STARTUP_TIMEOUT', '1800'))  # 30 min for first install
MAX_RETRY_ATTEMPTS = max(1, STARTUP_TIMEOUT // max(1, SERVICE_WAIT_INTERVAL))

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


def wait_for_service(url: str, max_attempts: int = MAX_RETRY_ATTEMPTS) -> bool:
    """Wait for SwarmUI service to become available.
    
    Args:
        url: The base URL of the SwarmUI service
        max_attempts: Maximum number of attempts to check
        
    Returns:
        bool: True if service is ready, False otherwise
    """
    print("=" * 80)
    print("STEP 1: Waiting for SwarmUI Service")
    print("=" * 80)
    print(f"Target: {url}")
    print(f"Max wait: {STARTUP_TIMEOUT}s ({max_attempts} attempts @ {SERVICE_WAIT_INTERVAL}s)")
    print()

    for attempt in range(max_attempts):
        try:
            response = session.post(
                f"{url}/API/GetNewSession",
                json={},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'session_id' in data:
                    print(f"✓ SwarmUI service is ready!")
                    print(f"  Version: {data.get('version', 'unknown')}")
                    print(f"  Server ID: {data.get('server_id', 'unknown')}")
                    return True
            
        except requests.exceptions.RequestException as e:
            elapsed = attempt * SERVICE_WAIT_INTERVAL
            print(f"  [{elapsed:4d}s] Waiting... ({type(e).__name__})")
            
        except Exception as e:
            print(f"  Unexpected error: {e}")
        
        if attempt < max_attempts - 1:
            time.sleep(SERVICE_WAIT_INTERVAL)
    
    print(f"ERROR: SwarmUI service failed to start after {STARTUP_TIMEOUT}s")
    return False


def wait_for_backend(url: str, max_wait_seconds: int = 1200) -> bool:
    """Wait for at least one backend to be available.
    
    ComfyUI backend may take 5-15 minutes to install on first run.
    
    Args:
        url: The base URL of the SwarmUI service
        max_wait_seconds: Maximum seconds to wait for backend
        
    Returns:
        bool: True if backend is ready, False otherwise
    """
    print()
    print("=" * 80)
    print("STEP 2: Waiting for ComfyUI Backend Installation & Startup")
    print("=" * 80)
    print("This may take 5-15 minutes on first run (ComfyUI installation)")
    print("Subsequent runs should be ready in 30-90 seconds")
    print()
    
    start_time = time.time()
    max_attempts = max_wait_seconds // BACKEND_WAIT_INTERVAL
    
    for attempt in range(max_attempts):
        elapsed = int(time.time() - start_time)
        
        try:
            # Method 1: Try to list backends (requires POST!)
            response = session.post(
                f"{url}/API/ListBackends",
                json={},
                timeout=10
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    backends = data.get('backends', [])
                    
                    # Look for enabled and running backends
                    available_backends = [
                        b for b in backends 
                        if b.get('status') in ['running', 'ready', 'loaded']
                    ]
                    
                    if available_backends:
                        print()
                        print(f"✓ Backend ready after {elapsed}s!")
                        print(f"  Available backends: {len(available_backends)}")
                        for backend in available_backends:
                            print(f"    - {backend.get('title', 'Unknown')}: {backend.get('status')}")
                        return True
                    
                    # Show status of all backends
                    if backends:
                        status_msg = ", ".join([
                            f"{b.get('title', 'Unknown')}: {b.get('status', 'unknown')}"
                            for b in backends
                        ])
                        print(f"  [{elapsed:4d}s] {status_msg}")
                    else:
                        print(f"  [{elapsed:4d}s] No backends configured yet...")
                        
                except (ValueError, KeyError) as e:
                    print(f"  [{elapsed:4d}s] Backend API returned invalid data, retrying...")
                    
            elif response.status_code == 400:
                # Bad request - API format might have changed
                print(f"  [{elapsed:4d}s] ListBackends returned 400, trying alternative check...")
                
                # Method 2: Try to get a session and check for backend errors
                try:
                    test_response = session.post(
                        f"{url}/API/GetNewSession",
                        json={},
                        timeout=10
                    )
                    
                    if test_response.status_code == 200:
                        # If we can get a session, try a simple generation to test backend
                        test_gen = session.post(
                            f"{url}/API/GenerateText2Image",
                            json={
                                "session_id": test_response.json().get('session_id'),
                                "prompt": "test",
                                "images": 0  # Don't actually generate
                            },
                            timeout=5
                        )
                        
                        # If we get anything other than "no backends", consider it ready
                        if test_gen.status_code == 200:
                            result = test_gen.json()
                            if 'error' not in result or 'No backends available' not in str(result.get('error', '')):
                                print(f"✓ Backend ready after {elapsed}s! (confirmed via test)")
                                return True
                            else:
                                print(f"  [{elapsed:4d}s] Still no backends available...")
                                
                except Exception:
                    pass  # Ignore errors in fallback check
                    
            else:
                print(f"  [{elapsed:4d}s] ListBackends returned {response.status_code}")
            
        except requests.exceptions.RequestException as e:
            print(f"  [{elapsed:4d}s] Checking backends... ({type(e).__name__})")
        except Exception as e:
            print(f"  [{elapsed:4d}s] Error: {type(e).__name__}")
        
        if elapsed >= max_wait_seconds:
            break
            
        time.sleep(BACKEND_WAIT_INTERVAL)
    
    print()
    print(f"ERROR: No backends available after {max_wait_seconds}s")
    print()
    print("Troubleshooting:")
    print("  1. Check SwarmUI logs for backend installation errors")
    print("  2. First run needs 5-15 minutes for ComfyUI installation")
    print("  3. Ensure sufficient disk space (15GB+ for container)")
    print("  4. Verify Settings.fds has backend configuration")
    return False


def get_session_id() -> Optional[str]:
    """Request a new SwarmUI session identifier.
    
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
        
        data = response.json()
        session_id = data.get("session_id")
        
        if session_id:
            print(f"✓ Obtained session ID: {session_id[:16]}...")
            return session_id
        else:
            print("ERROR: No session_id in response")
            return None
            
    except Exception as e:
        print(f"ERROR: Failed to get session ID: {e}")
        return None


def fetch_image_as_base64(image_path: str) -> Optional[Dict[str, str]]:
    """Fetch an image from SwarmUI and convert to base64.
    
    Args:
        image_path: Path returned by SwarmUI API
        
    Returns:
        dict: Image data with filename, type, and base64 data, or None if failed
    """
    try:
        img_url = f"{SWARMUI_API_URL}/{image_path}"
        print(f"Fetching image from: {img_url}")
        
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
        print(f"ERROR: Failed to fetch image from {image_path}: {e}")
        return None


def generate_image(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an image using SwarmUI API.
    
    Args:
        job_input: Dictionary containing generation parameters
        
    Returns:
        dict: Generation result with images or error
    """
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
    print("STEP 3: Generating Image")
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
        
        # Check for errors in response
        if 'error' in result or 'error_id' in result:
            error_msg = result.get('error', result.get('error_id', 'Unknown error'))
            print(f"ERROR: SwarmUI returned error: {error_msg}")
            return {"error": error_msg}
        
        # Extract image paths from response
        if 'images' in result and len(result['images']) > 0:
            print(f"✓ Generation complete, fetching {len(result['images'])} image(s)...")
            
            images = []
            for img_path in result['images']:
                img_data = fetch_image_as_base64(img_path)
                if img_data:
                    images.append(img_data)
                else:
                    print(f"WARNING: Failed to fetch image: {img_path}")
            
            if len(images) == 0:
                return {"error": "Failed to fetch any generated images"}
            
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
        
        print("ERROR: No images in SwarmUI response")
        return {"error": "No images generated by SwarmUI"}
        
    except requests.exceptions.Timeout:
        return {"error": f"Generation request timed out after {GENERATION_TIMEOUT}s"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """RunPod handler function - entry point for all requests.
    
    Args:
        job: Dictionary containing job input and metadata
        
    Returns:
        dict: Result or error
    """
    try:
        print()
        print("=" * 80)
        print("SwarmUI RunPod Serverless - Processing Request")
        print("=" * 80)
        
        job_input = job.get('input', {})
        
        if not job_input:
            return {"error": "No input provided"}
        
        # Generate image
        result = generate_image(job_input)
        
        print()
        print("=" * 80)
        print("✓ Request Completed")
        print("=" * 80)
        
        return result
        
    except Exception as e:
        print(f"ERROR: Handler error: {e}")
        return {"error": f"Handler error: {str(e)}"}


# Initialize - wait for SwarmUI AND backend to be ready
if __name__ == "__main__":
    print("=" * 80)
    print("SwarmUI RunPod Serverless Worker - Initialization")
    print("=" * 80)
    print()
    
    # Step 1: Wait for SwarmUI server to start
    if not wait_for_service(SWARMUI_API_URL):
        print()
        print("FATAL: SwarmUI service failed to start")
        exit(1)
    
    # Step 2: Wait for ComfyUI backend to install and start
    if not wait_for_backend(SWARMUI_API_URL):
        print()
        print("FATAL: No backends available after timeout")
        print("Check container logs for installation errors")
        exit(1)
    
    print()
    print("=" * 80)
    print("✓ System Ready - Starting RunPod Handler")
    print("=" * 80)
    print()
    
    runpod.serverless.start({"handler": handler})
    