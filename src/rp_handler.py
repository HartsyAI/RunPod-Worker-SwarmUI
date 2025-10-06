"""RunPod Handler for SwarmUI Serverless Worker.

Manages SwarmUI readiness, proxies generation requests, and returns base64 images.
Professional implementation following best practices.
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
SERVICE_WAIT_INTERVAL = int(os.getenv('SERVICE_WAIT_INTERVAL', '5'))
STARTUP_TIMEOUT = int(os.getenv('STARTUP_TIMEOUT', '900'))
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
    print(f"Waiting for SwarmUI service at {url}")
    print(f"Maximum wait time: {STARTUP_TIMEOUT}s ({max_attempts} attempts @ {SERVICE_WAIT_INTERVAL}s interval)")

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
            print(f"Attempt {attempt + 1}/{max_attempts}: Service not ready... ({type(e).__name__})")
            
        except Exception as e:
            print(f"Unexpected error while waiting for service: {e}")
        
        if attempt < max_attempts - 1:
            time.sleep(SERVICE_WAIT_INTERVAL)
    
    print(f"ERROR: SwarmUI service failed to start after {max_attempts} attempts")
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
        image_path: Path returned by SwarmUI API (e.g., "View/local/raw/...")
        
    Returns:
        dict: Image data with filename, type, and base64 data, or None if failed
    """
    try:
        # Construct full URL - image_path already includes the path
        img_url = f"{SWARMUI_API_URL}/{image_path}"
        
        print(f"Fetching image from: {img_url}")
        
        response = session.get(img_url, timeout=30)
        response.raise_for_status()
        
        # Convert to base64
        img_base64 = base64.b64encode(response.content).decode('utf-8')
        
        # Extract filename from path
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
    
    print(f"Generating image with prompt: '{prompt[:60]}...'")
    print(f"Model: {model}, Size: {width}x{height}, Steps: {steps}")
    
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
        print("=" * 80)
        print("SwarmUI Handler - Processing Request")
        print("=" * 80)
        
        job_input = job.get('input', {})
        
        if not job_input:
            return {"error": "No input provided"}
        
        # Generate image
        result = generate_image(job_input)
        
        print("✓ Request completed")
        print("=" * 80)
        
        return result
        
    except Exception as e:
        print(f"ERROR: Handler error: {e}")
        return {"error": f"Handler error: {str(e)}"}


# Initialize - wait for SwarmUI to be ready
if __name__ == "__main__":
    print("=" * 80)
    print("SwarmUI RunPod Serverless Worker")
    print("=" * 80)
    
    # Wait for SwarmUI to start
    if not wait_for_service(SWARMUI_API_URL):
        print("FATAL: SwarmUI service failed to start")
        exit(1)
    
    print("✓ Starting RunPod serverless handler...")
    runpod.serverless.start({"handler": handler})
