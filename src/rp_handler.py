"""RunPod Handler for SwarmUI Serverless Worker.

Workflow:
1. Client sends 'wakeup' job via /run — handler returns connection info immediately
2. Client polls GET /status/{jobId} until COMPLETED (no new jobs created)
3. Client sends 'keepalive' job via /run — handler runs blocking ping loop to keep worker alive
4. Client makes direct SwarmUI API calls to the public URL
5. Client cancels keepalive job when done — worker scales down after idle timeout

Action Design:
- wakeup:    Returns immediately with public_url, session_id, worker_id. No blocking.
- keepalive: Blocking ping loop for 'duration' seconds. Keeps the worker alive.
- ready:     Quick check — returns connection info if SwarmUI is up.
- health:    Lightweight HTTP GET health check.
- shutdown:  Acknowledges shutdown signal.

Session Management:
- Session created ONCE at startup and cached globally
- All actions return the same cached session
- Keepalive uses simple HTTP GET (no session needed)
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
    """Simple logging utility with verbose support."""

    @staticmethod
    def header(msg: str) -> None:
        print("\n" + "=" * 80)
        print(msg)
        print("=" * 80 + "\n")

    @staticmethod
    def info(msg: str) -> None:
        print(f"[INFO] {msg}")

    @staticmethod
    def verbose(msg: str) -> None:
        print(f"[VERBOSE] {msg}")

    @staticmethod
    def success(msg: str) -> None:
        print(f"[SUCCESS] {msg}")

    @staticmethod
    def error(msg: str) -> None:
        print(f"[ERROR] {msg}", file=sys.stderr)

    @staticmethod
    def warning(msg: str) -> None:
        print(f"[WARNING] {msg}")


def get_public_url() -> str:
    """Get the public URL where SwarmUI is accessible.

    Returns:
        Public URL in format: https://{worker-id}-{port}.proxy.runpod.net
    """
    url = f"https://{RUNPOD_POD_ID}-{SWARMUI_PORT}.proxy.runpod.net"
    Log.verbose(f"Public URL: {url}")
    return url


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
    Log.verbose(f"SwarmUI request: {method} {url} (timeout: {timeout}s)")

    try:
        if method.upper() == 'GET':
            response = session.get(url, timeout=timeout)
        elif method.upper() == 'POST':
            response = session.post(url, json=payload or {}, timeout=timeout)
        else:
            raise ValueError(f"Unsupported method: {method}")

        Log.verbose(f"SwarmUI response: {response.status_code} ({len(response.content)} bytes)")
        response.raise_for_status()
        return response.json() if response.content else {}

    except Exception as e:
        Log.verbose(f"SwarmUI request failed: {method} {url} -> {e}")
        raise RuntimeError(f"SwarmUI request failed: {e}")


def get_or_create_session() -> tuple[str, str]:
    """Get cached session or create new one if needed.

    Returns:
        Tuple of (session_id, version)

    Raises:
        RuntimeError: If session creation fails after retries
    """
    global CACHED_SESSION_ID, CACHED_VERSION

    if CACHED_SESSION_ID:
        Log.verbose(f"Using cached session: {CACHED_SESSION_ID[:16]}...")
        return CACHED_SESSION_ID, CACHED_VERSION

    Log.info("Creating new SwarmUI session...")

    # Retry session creation in case of transient errors (like LiteDB loops)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            session_info = swarm_request('POST', '/API/GetNewSession', timeout=10)
            CACHED_SESSION_ID = session_info.get('session_id')
            CACHED_VERSION = session_info.get('version', 'unknown')

            if not CACHED_SESSION_ID:
                raise RuntimeError("Failed to get session ID from SwarmUI")

            Log.success(f"Session created: {CACHED_SESSION_ID[:16]}...")
            Log.info(f"Version: {CACHED_VERSION}")

            return CACHED_SESSION_ID, CACHED_VERSION

        except Exception as e:
            if attempt < max_retries - 1:
                Log.warning(f"Session creation attempt {attempt + 1} failed: {e}, retrying...")
                time.sleep(2)
            else:
                Log.error(f"Session creation failed after {max_retries} attempts: {e}")
                raise RuntimeError(f"Failed to create session: {e}")


def keepalive_ping() -> bool:
    """Lightweight keepalive ping using simple HTTP GET.

    Returns:
        True if successful, False otherwise
    """
    try:
        url = f"{SWARMUI_API_URL.rstrip('/')}"
        response = session.get(url, timeout=5, allow_redirects=False)
        alive = response.status_code in [200, 301, 302, 303, 307, 308]
        Log.verbose(f"Keepalive ping: {response.status_code} (alive={alive})")
        return alive
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
            session_info = swarm_request('POST', '/API/GetNewSession', timeout=10)
            session_id = session_info.get('session_id')

            if session_id:
                CACHED_SESSION_ID = session_id
                CACHED_VERSION = session_info.get('version', 'unknown')

                Log.success(f"SwarmUI API ready after {elapsed}s")
                Log.info(f"Version: {CACHED_VERSION}")
                Log.info(f"Session: {CACHED_SESSION_ID[:16]}...")
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


# ──────────────────── Action Handlers ────────────────────


def action_wakeup(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Wake up worker and return connection info immediately.

    This action is NON-BLOCKING. It returns the public URL, session, and worker ID
    as soon as SwarmUI is ready. The client sends a separate 'keepalive' job to
    keep the worker alive for as long as needed.

    Returns:
        Dict with public_url, session_id, worker_id, version
    """
    Log.info("Action: wakeup (non-blocking)")
    try:
        session_id, version = get_or_create_session()
        public_url = get_public_url()

        Log.info(f"Worker ready - returning connection info immediately")
        Log.verbose(f"  public_url: {public_url}")
        Log.verbose(f"  session_id: {session_id[:16]}...")
        Log.verbose(f"  worker_id:  {RUNPOD_POD_ID}")
        Log.verbose(f"  version:    {version}")

        return {
            'success': True,
            'public_url': public_url,
            'session_id': session_id,
            'version': version,
            'worker_id': RUNPOD_POD_ID
        }

    except Exception as e:
        Log.error(f"Wakeup failed: {e}")
        Log.verbose(traceback.format_exc())
        return {
            'success': False,
            'error': str(e)
        }


def action_ready(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Check if SwarmUI is ready and return connection info.

    Returns:
        Dict with ready status and cached session info
    """
    Log.info("Action: ready")
    try:
        session_id, version = get_or_create_session()
        public_url = get_public_url()

        Log.verbose(f"Ready check OK: {public_url}")

        return {
            'ready': True,
            'public_url': public_url,
            'session_id': session_id,
            'version': version,
            'worker_id': RUNPOD_POD_ID
        }

    except Exception as e:
        Log.verbose(f"Ready check failed: {e}")
        return {
            'ready': False,
            'error': str(e)
        }


def action_health(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Quick health check using simple HTTP GET.

    Returns:
        Dict with health status
    """
    Log.info("Action: health")
    try:
        url = f"{SWARMUI_API_URL.rstrip('/')}"
        response = session.get(url, timeout=5, allow_redirects=False)
        healthy = response.status_code in [200, 301, 302, 303, 307, 308]

        Log.verbose(f"Health check: status={response.status_code}, healthy={healthy}")

        return {
            'healthy': healthy,
            'public_url': get_public_url(),
            'worker_id': RUNPOD_POD_ID
        }
    except Exception as e:
        Log.verbose(f"Health check failed: {e}")
        return {
            'healthy': False,
            'error': str(e)
        }


def action_keepalive(job_input: Dict[str, Any]) -> Dict[str, Any]:
    """Keep worker alive by running a blocking ping loop.

    This action is BLOCKING. It runs for 'duration' seconds, pinging SwarmUI
    at 'interval' second intervals. While this job is running, RunPod keeps
    the worker alive. The client cancels this job when it's done with the worker.

    Args:
        job_input: duration (seconds), interval (seconds)

    Returns:
        Dict with keepalive results (only returned when loop ends or job is cancelled)
    """
    duration = int(job_input.get('duration', 3600))
    interval = int(job_input.get('interval', 30))

    if duration <= 0:
        Log.warning("Keepalive rejected: duration must be positive")
        return {
            'success': False,
            'error': 'duration must be positive'
        }

    interval = max(1, interval)

    Log.info(f"Action: keepalive (blocking for {duration}s, ping every {interval}s)")

    pings = 0
    failures = 0
    end_time = time.time() + duration

    while time.time() < end_time:
        if keepalive_ping():
            pings += 1
        else:
            failures += 1

        # Log progress periodically (every 10 pings)
        if (pings + failures) % 10 == 0:
            remaining = int(end_time - time.time())
            Log.verbose(f"Keepalive progress: {pings} ok, {failures} failed, {remaining}s remaining")

        time.sleep(interval)

    Log.info(f"Keepalive complete: {pings} pings, {failures} failures over {duration}s")

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

    Returns:
        Dict with shutdown acknowledgment
    """
    Log.warning("Action: shutdown signal received")
    return {
        'success': True,
        'message': 'Shutdown acknowledged',
        'worker_id': RUNPOD_POD_ID
    }


# ──────────────────── Main Handler ────────────────────


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
        job_id = job.get('id', 'unknown')

        Log.info(f"Handler invoked: action={action}, job_id={job_id}")
        Log.verbose(f"Job input: {job_input}")

        actions = {
            'wakeup': action_wakeup,
            'ready': action_ready,
            'health': action_health,
            'keepalive': action_keepalive,
            'shutdown': action_shutdown,
        }

        if action in actions:
            result = actions[action](job_input)
            Log.verbose(f"Action '{action}' completed, result keys: {list(result.keys())}")
            return result
        else:
            Log.warning(f"Unknown action: {action}")
            return {
                'success': False,
                'error': f'Unknown action: {action}',
                'available_actions': list(actions.keys())
            }

    except Exception as e:
        Log.error(f"Handler error: {e}")
        Log.verbose(traceback.format_exc())
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
