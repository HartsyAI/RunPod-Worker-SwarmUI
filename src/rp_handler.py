"""RunPod Handler for SwarmUI Serverless Worker.

Minimal pass-through handler that:
1. Waits for SwarmUI to start and backends to be ready
2. Provides health/ready endpoints
3. Forwards SwarmUI API requests
4. Handles keepalive and shutdown signals
"""

import os
import sys
import time
import traceback
from typing import Dict, Any, Optional

import requests
import runpod

# Configuration
SWARMUI_API_URL = os.getenv('SWARMUI_API_URL', 'http://127.0.0.1:7801')
STARTUP_TIMEOUT = int(os.getenv('STARTUP_TIMEOUT', '1800'))
CHECK_INTERVAL = 10

# Setup session with retries
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    max_retries=requests.adapters.Retry(
        total=5,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
)
session.mount('http://', adapter)
session.mount('https://', adapter)
session.headers.update({
    'User-Agent': 'SwarmUI-RunPod-Worker/2.0',
    'Content-Type': 'application/json'
})


class Log:
    """Simple logging utility."""
    
    @staticmethod
    def header(msg: str) -> None:
        print("\n" + "=" * 80)
        print(msg)
        print("=" * 80 + "\n")
    
    @staticmethod
    def info(msg: str) -> None:
        print(f"[INFO] {msg}")
    
    @staticmethod
    def success(msg: str) -> None:
        print(f"[SUCCESS] ✓ {msg}")
    
    @staticmethod
    def error(msg: str) -> None:
        print(f"[ERROR] ✗ {msg}", file=sys.stderr)
    
    @staticmethod
    def warning(msg: str) -> None:
        print(f"[WARNING] ⚠ {msg}")


def build_url(path: str) -> str:
    """Build full URL for SwarmUI API request."""
    if path.startswith('http'):
        return path
    base = SWARMUI_API_URL.rstrip('/')
    path = path.lstrip('/')
    return f"{base}/{path}"


def swarm_request(method: str, path: str, payload: Optional[Dict[str, Any]] = None, 
                  timeout: int = 30) -> Dict[str, Any]:
    """Make HTTP request to SwarmUI API.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API path (e.g., '/API/GetNewSession')
        payload: JSON payload for POST requests
        timeout: Request timeout in seconds
        
    Returns:
        Dict containing response JSON
        
    Raises:
        requests.RequestException: On request failure
    """
    url = build_url(path)
    
    if method.upper() == 'GET':
        response = session.get(url, timeout=timeout)
    elif method.upper() == 'POST':
        response = session.post(url, json=payload or {}, timeout=timeout)
    else:
        raise ValueError(f"Unsupported HTTP method: {method}")
    
    response.raise_for_status()
    
    if not response.content:
        return {}
    
    return response.json()


def get_session_id() -> Optional[str]:
    """Get a new SwarmUI session ID.
    
    Returns:
        Session ID string or None if failed
    """
    try:
        data = swarm_request('POST', '/API/GetNewSession')
        session_id = data.get('session_id')
        
        if session_id:
            Log.info(f"Session: {session_id[:16]}...")
            return session_id
        
        Log.error("No session_id in response")
        return None
        
    except Exception as e:
        Log.error(f"Failed to get session: {e}")
        return None


def check_backend_ready() -> bool:
    """Check if SwarmUI backend is ready for generation.
    
    Returns:
        True if backend ready, False otherwise
    """
    try:
        session_id = get_session_id()
        if not session_id:
            return False
        
        # Test with minimal generation request
        test_payload = {
            'session_id': session_id,
            'images': 0,  # Don't actually generate
            'prompt': 'warmup',
            'model': 'OfficialStableDiffusion/sd_xl_base_1.0',
            'steps': 1,
            'width': 512,
            'height': 512
        }
        
        swarm_request('POST', '/API/GenerateText2Image', test_payload, timeout=10)
        return True
        
    except Exception:
        return False


def wait_for_swarmui_ready(max_wait_seconds: int = STARTUP_TIMEOUT) -> bool:
    """Wait for SwarmUI to become ready for generation.
    
    Args:
        max_wait_seconds: Maximum time to wait
        
    Returns:
        True if ready, False if timeout
    """
    Log.header("Waiting for SwarmUI to be ready")
    Log.info(f"URL: {SWARMUI_API_URL}")
    Log.info(f"Max wait: {max_wait_seconds}s")
    
    start_time = time.time()
    max_attempts = max(1, max_wait_seconds // CHECK_INTERVAL)
    
    for attempt in range(max_attempts):
        elapsed = int(time.time() - start_time)
        
        try:
            session_info = swarm_request('POST', '/API/GetNewSession', timeout=10)
            session_id = session_info.get('session_id')
            
            if session_id:
                if check_backend_ready():
                    Log.success(f"SwarmUI ready after {elapsed}s")
                    version = session_info.get('version', 'unknown')
                    Log.info(f"Version: {version}")
                    return True
                else:
                    Log.info(f"[{elapsed:4d}s] Backend warming up...")
            else:
                Log.info(f"[{elapsed:4d}s] Waiting for valid session...")
                
        except Exception as e:
            Log.info(f"[{elapsed:4d}s] Connecting: {e}")
        
        if elapsed >= max_wait_seconds:
            break
        
        time.sleep(CHECK_INTERVAL)
    
    Log.error(f"SwarmUI not ready after {max_wait_seconds}s")
    return False


def action_ready(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Check if SwarmUI is ready and return status info.
    
    Args:
        job_input: Job input (unused)
        
    Returns:
        Dict with ready status and SwarmUI info
    """
    try:
        session_info = swarm_request('POST', '/API/GetNewSession', timeout=10)
        session_id = session_info.get('session_id')
        
        if not session_id:
            return {
                'ready': False,
                'error': 'No session available'
            }
        
        backend_ready = check_backend_ready()
        
        return {
            'ready': backend_ready,
            'session_id': session_id,
            'version': session_info.get('version', 'unknown'),
            'api_url': SWARMUI_API_URL
        }
        
    except Exception as e:
        return {
            'ready': False,
            'error': str(e)
        }


def action_health(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Quick health check.
    
    Args:
        job_input: Job input (unused)
        
    Returns:
        Dict with health status
    """
    try:
        swarm_request('POST', '/API/GetNewSession', timeout=5)
        return {'healthy': True}
    except Exception as e:
        return {'healthy': False, 'error': str(e)}


def action_keepalive(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Keep worker warm by pinging SwarmUI.
    
    Args:
        job_input: Must contain 'duration' (seconds) and optional 'interval' (seconds)
        
    Returns:
        Dict with keepalive results
    """
    duration = job_input.get('duration', 60)
    interval = job_input.get('interval', CHECK_INTERVAL)
    
    try:
        duration = int(duration)
        interval = int(interval)
    except (TypeError, ValueError):
        return {
            'success': False,
            'error': 'duration and interval must be integers'
        }
    
    if duration <= 0:
        return {
            'success': False,
            'error': 'duration must be positive'
        }
    
    interval = max(1, interval)
    end_time = time.time() + duration
    pings = 0
    failures = 0
    
    Log.info(f"Keeping alive for {duration}s (interval: {interval}s)")
    
    while time.time() < end_time:
        try:
            swarm_request('POST', '/API/GetNewSession', timeout=10)
            pings += 1
        except Exception:
            failures += 1
        
        time.sleep(interval)
    
    return {
        'success': True,
        'pings': pings,
        'failures': failures,
        'duration': duration,
        'interval': interval
    }


def action_swarm_api(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Forward request to SwarmUI API.
    
    Args:
        job_input: Must contain:
            - method: HTTP method (GET, POST)
            - path: SwarmUI API path (e.g., '/API/GenerateText2Image')
            - payload: Optional JSON payload for POST requests
            - timeout: Optional request timeout (default: 600s)
            
    Returns:
        Dict containing SwarmUI API response
    """
    method = job_input.get('method', 'POST')
    path = job_input.get('path')
    payload = job_input.get('payload')
    timeout = job_input.get('timeout', 600)
    
    if not path:
        return {
            'success': False,
            'error': 'path is required'
        }
    
    try:
        timeout = int(timeout)
    except (TypeError, ValueError):
        return {
            'success': False,
            'error': 'timeout must be an integer'
        }
    
    try:
        response = swarm_request(method, path, payload, timeout)
        return {
            'success': True,
            'response': response
        }
    except requests.exceptions.Timeout:
        return {
            'success': False,
            'error': f'Request timed out after {timeout}s'
        }
    except requests.exceptions.HTTPError as e:
        return {
            'success': False,
            'error': f'HTTP {e.response.status_code}: {e.response.text}'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def action_shutdown(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Signal graceful shutdown.
    
    Args:
        job_input: Job input (unused)
        
    Returns:
        Dict with shutdown acknowledgment
    """
    Log.warning("Shutdown signal received")
    return {
        'success': True,
        'message': 'Shutdown acknowledged'
    }


def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """RunPod handler - routes to action handlers.
    
    Args:
        job: RunPod job containing 'input' with 'action' key
        
    Returns:
        Dict containing action result
    """
    try:
        job_input = job.get('input', {})
        action = job_input.get('action', 'ready')
        
        Log.info(f"Action: {action}")
        
        if action == 'ready':
            return action_ready(job_input)
        elif action == 'health':
            return action_health(job_input)
        elif action == 'keepalive':
            return action_keepalive(job_input)
        elif action == 'swarm_api':
            return action_swarm_api(job_input)
        elif action == 'shutdown':
            return action_shutdown(job_input)
        else:
            return {
                'success': False,
                'error': f'Unknown action: {action}',
                'available_actions': ['ready', 'health', 'keepalive', 'swarm_api', 'shutdown']
            }
            
    except Exception as e:
        Log.error(f"Handler error: {e}")
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


if __name__ == "__main__":
    Log.header("SwarmUI RunPod Serverless Worker")
    
    if not wait_for_swarmui_ready():
        Log.error("SwarmUI failed to start")
        Log.error("Check container logs for errors")
        sys.exit(1)
    
    Log.header("System Ready - Starting RunPod Handler")
    
    runpod.serverless.start({"handler": handler})
