"""RunPod Handler for SwarmUI Serverless Worker.

Manages SwarmUI readiness, proxies generation requests, and returns base64 images.
"""

import os
import time
import requests
import runpod
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configuration
SWARMUI_API_URL = os.getenv('SWARMUI_API_URL', 'http://127.0.0.1:7801')
TIMEOUT = int(os.getenv('GENERATION_TIMEOUT', '600'))
WAIT_INTERVAL_SECONDS = int(os.getenv('SERVICE_WAIT_INTERVAL', '5'))
STARTUP_TIMEOUT = int(os.getenv('STARTUP_TIMEOUT', '900'))
MAX_RETRY_ATTEMPTS = max(1, STARTUP_TIMEOUT // max(1, WAIT_INTERVAL_SECONDS))

# Setup session with retries
session = requests.Session()
retries = Retry(
    total=10,
    backoff_factor=0.1,
    status_forcelist=[502, 503, 504],
)
session.mount('http://', HTTPAdapter(max_retries=retries))
session.mount('https://', HTTPAdapter(max_retries=retries))


def wait_for_service(url, max_attempts=MAX_RETRY_ATTEMPTS):
    """
    Wait for SwarmUI service to become available.
    
    Args:
        url: The URL to check
        
    Returns:
        bool: True if service is ready, False otherwise
    """
    print(f"Waiting for SwarmUI service at {url}")
    print(f"Maximum wait time: {STARTUP_TIMEOUT}s ({MAX_RETRY_ATTEMPTS} attempts, interval {WAIT_INTERVAL_SECONDS}s)")

    for attempt in range(max_attempts):
        try:
            response = session.get(f"{url}/API/GetNewSession", timeout=10)
            if response.status_code == 200:
                print("SwarmUI service is ready!")
                return True
        except requests.exceptions.RequestException as e:
            print(
                f"Attempt {attempt + 1}/{max_attempts}: Service not ready yet... ({e})"
            )
            time.sleep(WAIT_INTERVAL_SECONDS)
        except Exception as e:
            print(f"Unexpected error while waiting for service: {e}")
    print(f"ERROR: SwarmUI service failed to start after {max_attempts} attempts")
    return False


def get_session_id():
    """Request a new SwarmUI session identifier."""
    try:
        response = session.post(
            f"{SWARMUI_API_URL}/API/GetNewSession",
            json={},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        return data.get("session_id")
    except Exception as e:
        print(f"Error getting session ID: {e}")
        return None


def generate_image(job_input):
    """
    Generate an image using SwarmUI API.
    
    Args:
        job_input: Dictionary containing generation parameters
        
    Returns:
        dict: Generation result or error
    """
    # Get session ID
    session_id = get_session_id()
    if not session_id:
        return {"error": "Failed to create SwarmUI session"}
    
    # Extract parameters with defaults
    prompt = job_input.get('prompt', 'a beautiful landscape')
    negative_prompt = job_input.get('negative_prompt', '')
    model = job_input.get('model', 'OfficialStableDiffusion/sd_xl_base_1.0')
    width = job_input.get('width', 1024)
    height = job_input.get('height', 1024)
    steps = job_input.get('steps', 30)
    cfg_scale = job_input.get('cfg_scale', 7.5)
    seed = job_input.get('seed', -1)
    images_count = job_input.get('images', 1)
    
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
    
    print(f"Generating image with prompt: '{prompt}'")
    print(f"Model: {model}, Size: {width}x{height}, Steps: {steps}")
    
    try:
        # Send generation request
        response = session.post(
            f"{SWARMUI_API_URL}/API/GenerateText2Image",
            json=swarm_request,
            timeout=TIMEOUT
        )
        response.raise_for_status()
        result = response.json()
        
        # Check for errors in response
        if 'error' in result:
            return {"error": result['error']}
        
        # Extract image data
        if 'images' in result and len(result['images']) > 0:
            # SwarmUI returns image paths, we need to fetch them
            images = []
            for img_path in result['images']:
                img_url = f"{SWARMUI_API_URL}{img_path}"
                try:
                    img_response = session.get(img_url, timeout=30)
                    img_response.raise_for_status()
                    
                    # Convert to base64
                    import base64
                    img_base64 = base64.b64encode(img_response.content).decode('utf-8')
                    
                    images.append({
                        "filename": img_path.split('/')[-1],
                        "type": "base64",
                        "data": img_base64
                    })
                except Exception as e:
                    print(f"Error fetching image from {img_url}: {e}")
            
            return {
                "images": images,
                "parameters": {
                    "prompt": prompt,
                    "model": model,
                    "seed": result.get('seed', seed),
                    "width": width,
                    "height": height,
                    "steps": steps
                }
            }
        
        return {"error": "No images generated"}
        
    except requests.exceptions.Timeout:
        return {"error": "Generation request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": f"Request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}


def handler(job):
    """
    RunPod handler function - entry point for all requests.
    
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
        
        print("Request completed")
        print("=" * 80)
        
        return result
        
    except Exception as e:
        print(f"Handler error: {e}")
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
    
    print("Starting RunPod serverless handler...")
    runpod.serverless.start({"handler": handler})
