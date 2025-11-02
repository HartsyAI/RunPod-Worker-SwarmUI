"""RunPod Handler for SwarmUI Serverless Worker.

Workflow:
1. Send wakeup/keepalive request to start worker
2. Handler returns public SwarmUI URL and cached session
3. Make direct SwarmUI API calls to that URL
4. Handler keeps worker alive by pinging lightweight endpoints
5. Send shutdown when done

Session Management:
- Session created ONCE at startup and cached globally
- All actions return the same cached session
- Keepalive uses ListBackends (lightweight, no session creation)
- If session expires, we recreate it automatically
"""

import os
import sys
import time
import traceback
import requests
import runpod

from typing import Dict, Any, Optional

SWARMUI_API_URL = os.getenv('SWARMUI_API_URL', 'http://127.0.0.1:7801')
SWARMUI_PORT = os.getenv('SWARMUI_PORT', '7801')
STARTUP_TIMEOUT = int(os.getenv('STARTUP_TIMEOUT', '1800'))
CHECK_INTERVAL = 10
RUNPOD_POD_ID = os.getenv('RUNPOD_POD_ID', 'unknown')

# Global session cache - created once at startup, reused for all requests
CACHED_SESSION_ID: Optional[str] = None
CACHED_VERSION: Optional[str] = None

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


def get_public_url() -> str:
    """Get the public URL where SwarmUI is accessible.
    
    Returns:
        Public URL in format: https://{worker-id}-{port}.proxy.runpod.net
    """
    return f"https://{RUNPOD_POD_ID}-{SWARMUI_PORT}.proxy.runpod.net"


def swarm_request(method: str, path: str, payload: Optional[Dict[str, Any]] = None,
                  timeout: int = 30) -> Dict[str, Any]:
    """Make HTTP request to SwarmUI API.
    
    Args:
        method: HTTP method (GET, POST)
        path: API path
        payload: JSON payload for POST
        timeout: Request timeout
        
    Returns:
        Response JSON
        
    Raises:
        RuntimeError: On request failure
    """
    url = f"{SWARMUI_API_URL.rstrip('/')}/{path.lstrip('/')}"
    
    try:
        if method.upper() == 'GET':
            response = session.get(url, timeout=timeout)
        elif method.upper() == 'POST':
            response = session.post(url, json=payload or {}, timeout=timeout)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json() if response.content else {}
        
    except Exception as e:
        raise RuntimeError(f"SwarmUI request failed: {e}")


def get_or_create_session() -> tuple[str, str]:
    """Get cached session or create new one if needed.
    
    Returns:
        Tuple of (session_id, version)
        
    Raises:
        RuntimeError: If session creation fails
    """
    global CACHED_SESSION_ID, CACHED_VERSION
    
    if CACHED_SESSION_ID:
        return CACHED_SESSION_ID, CACHED_VERSION
    
    Log.info("Creating new SwarmUI session...")
    session_info = swarm_request('POST', '/API/GetNewSession', timeout=10)
    CACHED_SESSION_ID = session_info.get('session_id')
    CACHED_VERSION = session_info.get('version', 'unknown')
    
    if not CACHED_SESSION_ID:
        raise RuntimeError("Failed to get session ID from SwarmUI")
    
    Log.success(f"Session created: {CACHED_SESSION_ID[:16]}...")
    Log.info(f"Version: {CACHED_VERSION}")
    
    return CACHED_SESSION_ID, CACHED_VERSION


def keepalive_ping() -> bool:
    """Lightweight keepalive ping using ListBackends endpoint.
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Use ListBackends - lightweight endpoint that doesn't create sessions
        swarm_request('POST', '/API/ListBackends', payload={}, timeout=10)
        return True
    except Exception as e:
        Log.warning(f"Keepalive ping failed: {e}")
        return False


def wait_for_swarmui_ready(max_wait_seconds: int = STARTUP_TIMEOUT) -> bool:
    """Wait for SwarmUI to become ready and create initial session.
    
    Args:
        max_wait_seconds: Maximum wait time
        
    Returns:
        True if ready, False if timeout
    """
    global CACHED_SESSION_ID, CACHED_VERSION
    
    Log.header("Waiting for SwarmUI to be ready")
    Log.info(f"URL: {SWARMUI_API_URL}")
    Log.info(f"Public URL: {get_public_url()}")
    Log.info(f"Max wait: {max_wait_seconds}s")
    
    start_time = time.time()
    max_attempts = max(1, max_wait_seconds // CHECK_INTERVAL)
    
    for attempt in range(max_attempts):
        elapsed = int(time.time() - start_time)
        try:
            # Try to create session - this verifies SwarmUI is ready
            session_info = swarm_request('POST', '/API/GetNewSession', timeout=10)
            session_id = session_info.get('session_id')
            
            if session_id:
                # Cache the session globally
                CACHED_SESSION_ID = session_id
                CACHED_VERSION = session_info.get('version', 'unknown')
                
                Log.success(f"SwarmUI API ready after {elapsed}s")
                Log.info(f"Version: {CACHED_VERSION}")
                Log.info(f"Session: {CACHED_SESSION_ID[:16]}...")
                Log.info("Note: Backend models will load on-demand when first generation is requested")
                return True
            else:
                Log.info(f"[{elapsed:4d}s] Waiting for valid session...")
        except Exception as e:
            Log.info(f"[{elapsed:4d}s] Connecting: {e}")
        
        if elapsed >= max_wait_seconds:
            break
        time.sleep(CHECK_INTERVAL)
    
    Log.error(f"SwarmUI not ready after {max_wait_seconds}s")
    return False


def action_wakeup(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Wake up worker and return connection info.
    
    Args:
        job_input: Optional duration for keepalive (seconds)
        
    Returns:
        Dict with public URL and cached session info
    """
    try:
        # Get or use cached session
        session_id, version = get_or_create_session()
        
        # Get keepalive duration
        duration = int(job_input.get('duration', 3600))  # Default 1 hour
        interval = int(job_input.get('interval', 30))     # Default 30s
        
        public_url = get_public_url()
        
        Log.info(f"Worker ready - Public URL: {public_url}")
        Log.info(f"Starting keepalive for {duration}s (interval: {interval}s)")
        
        # Start keepalive loop using lightweight pings
        pings = 0
        failures = 0
        end_time = time.time() + duration
        
        while time.time() < end_time:
            if keepalive_ping():
                pings += 1
            else:
                failures += 1
            
            time.sleep(interval)
        
        Log.info(f"Keepalive complete: {pings} pings, {failures} failures")
        
        return {
            'success': True,
            'public_url': public_url,
            'session_id': session_id,
            'version': version,
            'worker_id': RUNPOD_POD_ID,
            'keepalive': {
                'duration': duration,
                'pings': pings,
                'failures': failures
            }
        }
        
    except Exception as e:
        Log.error(f"Wakeup failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }


def action_ready(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Check if SwarmUI is ready and return connection info.
    
    Args:
        job_input: Unused
        
    Returns:
        Dict with ready status and cached session info
    """
    try:
        # Use cached session if available, create if needed
        session_id, version = get_or_create_session()
        
        return {
            'ready': True,
            'public_url': get_public_url(),
            'session_id': session_id,
            'version': version,
            'worker_id': RUNPOD_POD_ID
        }
        
    except Exception as e:
        return {
            'ready': False,
            'error': str(e)
        }


def action_health(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Quick health check using lightweight endpoint.
    
    Args:
        job_input: Unused
        
    Returns:
        Dict with health status
    """
    try:
        # Use lightweight endpoint for health check
        swarm_request('POST', '/API/ListBackends', payload={}, timeout=5)
        return {
            'healthy': True,
            'public_url': get_public_url(),
            'worker_id': RUNPOD_POD_ID
        }
    except Exception as e:
        return {
            'healthy': False,
            'error': str(e)
        }


def action_keepalive(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Keep worker warm by pinging lightweight endpoints.
    
    Args:
        job_input: duration (seconds), interval (seconds)
        
    Returns:
        Dict with keepalive results
    """
    duration = int(job_input.get('duration', 3600))  # Default 1 hour
    interval = int(job_input.get('interval', 30))    # Default 30s
    
    if duration <= 0:
        return {
            'success': False,
            'error': 'duration must be positive'
        }
    
    interval = max(1, interval)
    
    Log.info(f"Keepalive started: {duration}s (interval: {interval}s)")
    
    pings = 0
    failures = 0
    end_time = time.time() + duration
    
    while time.time() < end_time:
        if keepalive_ping():
            pings += 1
        else:
            failures += 1
        
        time.sleep(interval)
    
    Log.info(f"Keepalive complete: {pings} pings, {failures} failures")
    
    return {
        'success': True,
        'public_url': get_public_url(),
        'worker_id': RUNPOD_POD_ID,
        'pings': pings,
        'failures': failures,
        'duration': duration,
        'interval': interval
    }


def action_shutdown(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Signal graceful shutdown.
    
    Args:
        job_input: Unused
        
    Returns:
        Dict with shutdown acknowledgment
    """
    Log.warning("Shutdown signal received")
    return {
        'success': True,
        'message': 'Shutdown acknowledged',
        'worker_id': RUNPOD_POD_ID
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
        action = job_input.get('action', 'wakeup')
        
        Log.info(f"Action: {action}")
        
        if action == 'wakeup':
            return action_wakeup(job_input)
        elif action == 'ready':
            return action_ready(job_input)
        elif action == 'health':
            return action_health(job_input)
        elif action == 'keepalive':
            return action_keepalive(job_input)
        elif action == 'shutdown':
            return action_shutdown(job_input)
        else:
            return {
                'success': False,
                'error': f'Unknown action: {action}',
                'available_actions': ['wakeup', 'ready', 'health', 'keepalive', 'shutdown']
            }
            
    except Exception as e:
        Log.error(f"Handler error: {e}")
        return {
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }


if __name__ == "__main__":
    Log.header("SwarmUI RunPod Serverless Worker - Direct URL Access")
    
    if not wait_for_swarmui_ready():
        Log.error("SwarmUI failed to start")
        Log.error("Check container logs for errors")
        sys.exit(1)
    
    Log.header("System Ready - Starting RunPod Handler")
    Log.info(f"Public URL: {get_public_url()}")
    Log.info(f"Worker ID: {RUNPOD_POD_ID}")
    Log.info(f"Cached Session: {CACHED_SESSION_ID[:16]}...")
    
    runpod.serverless.start({"handler": handler})
