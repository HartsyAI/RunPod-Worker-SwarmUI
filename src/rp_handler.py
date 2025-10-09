"""RunPod Handler for SwarmUI Serverless Worker.

Handles model management and image generation requests with SwarmUI integration.
"""

import os
import time
import base64
import json
import traceback
from typing import Dict, Any, Optional, Union, List, Tuple

import requests
import runpod
from dotenv import load_dotenv

load_dotenv()

# Configuration
SWARMUI_API_URL = os.getenv('SWARMUI_API_URL', 'http://127.0.0.1:7801')
GENERATION_TIMEOUT = int(os.getenv('GENERATION_TIMEOUT', '600'))
STARTUP_TIMEOUT = int(os.getenv('STARTUP_TIMEOUT', '1800'))
CHECK_INTERVAL = 10
HUGGINGFACE_TOKEN = os.getenv('HUGGINGFACE_API_TOKEN')

# Setup session with retries
session = requests.Session()
session.mount('http://', requests.adapters.HTTPAdapter(
    max_retries=requests.adapters.Retry(
        total=10,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
))
session.mount('https://', requests.adapters.HTTPAdapter(
    max_retries=requests.adapters.Retry(
        total=10,
        backoff_factor=0.3,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
))
session.headers.update({
    'User-Agent': 'SwarmUI-RunPod-Worker/1.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json'
})


def _build_url(path: str) -> str:
    """Build a full URL for SwarmUI API requests."""

    if path.startswith('http://') or path.startswith('https://'):
        return path

    return f"{SWARMUI_API_URL.rstrip('/')}/{path.lstrip('/')}"


def swarm_post(path: str,
               payload: Dict[str, Any],
               *,
               timeout: int = 30,
               headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Send a POST request to a SwarmUI API endpoint and return the JSON payload."""

    response = session.post(
        _build_url(path),
        json=payload,
        timeout=timeout,
        headers=headers
    )
    response.raise_for_status()
    if not response.content:
        return {}
    return response.json()


def _model_operation_error(operation: str, error: Exception) -> Dict[str, Any]:
    """Normalize model management errors."""

    error_message = str(error)
    details: Optional[Union[str, Dict[str, Any]]] = None

    response = getattr(error, 'response', None)
    if response is not None:
        try:
            payload = response.json()
            details = payload
            error_message = payload.get('error', error_message)
        except ValueError:
            details = response.text

    return {
        'success': False,
        'error': f"Failed to {operation}",
        'details': details or error_message
    }


def fetch_image_as_base64(image_path: str) -> Optional[str]:
    """Fetch an image from SwarmUI and return a base64 data URI."""

    if not image_path:
        return None

    if image_path.startswith('data:'):
        return image_path

    try:
        url = _build_url(image_path)
        response = session.get(url, timeout=30)
        response.raise_for_status()
        image_bytes = response.content
        extension = image_path.split('.')[-1].lower()
        mime_type = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'webp': 'image/webp',
            'gif': 'image/gif'
        }.get(extension, 'image/png')

        encoded = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{encoded}"
    except Exception as err:
        print(f"WARNING: Failed to fetch image '{image_path}': {err}")
        return None


def list_models_action(path: str = '',
                      depth: int = 2,
                      subtype: str = 'Stable-Diffusion',
                      allow_remote: bool = True,
                      sort_by: Optional[str] = None,
                      sort_reverse: Optional[bool] = None,
                      data_images: Optional[bool] = None,
                      session_id: Optional[str] = None) -> Dict[str, Any]:
    """List available models via SwarmUI."""

    if session_id is None:
        session_id = get_session_id()
        if not session_id:
            return {
                'success': False,
                'error': 'Failed to obtain session for list_models request'
            }

    payload: Dict[str, Any] = {
        'path': path,
        'depth': depth,
        'subtype': subtype,
        'allowRemote': allow_remote,
        'session_id': session_id
    }

    if sort_by is not None:
        payload['sortBy'] = sort_by
    if sort_reverse is not None:
        payload['sortReverse'] = sort_reverse
    if data_images is not None:
        payload['dataImages'] = data_images

    try:
        data = swarm_post('/API/ListModels', payload)
        return {
            'success': True,
            'models': data.get('files', []),
            'folders': data.get('folders', [])
        }
    except Exception as err:
        return _model_operation_error('list models', err)


def describe_model_action(model_name: str,
                          subtype: str = 'Stable-Diffusion') -> Dict[str, Any]:
    """Describe a specific model via SwarmUI."""

    payload = {
        'modelName': model_name,
        'subtype': subtype
    }

    try:
        data = swarm_post('/API/DescribeModel', payload)
        return {
            'success': True,
            'model': data.get('model', {})
        }
    except Exception as err:
        return _model_operation_error(f'describe model {model_name}', err)


def download_model_action(url: str,
                          model_name: str,
                          model_type: str = 'Stable-Diffusion',
                          metadata: Optional[Union[Dict[str, Any], str]] = None) -> Dict[str, Any]:
    """Trigger a remote model download."""

    metadata_payload: Optional[str]
    if metadata is None:
        metadata_payload = None
    elif isinstance(metadata, str):
        metadata_payload = metadata
    else:
        metadata_payload = json.dumps(metadata)

    payload = {
        'url': url,
        'type': model_type,
        'name': model_name,
        'metadata': metadata_payload
    }

    headers: Optional[Dict[str, str]] = None
    if 'huggingface.co' in url and HUGGINGFACE_TOKEN:
        headers = {
            **session.headers,
            'Authorization': f'Bearer {HUGGINGFACE_TOKEN}'
        }

    try:
        data = swarm_post('/API/DoModelDownloadWS', payload, timeout=300, headers=headers)
        return {
            'success': True,
            'message': 'Download started',
            'data': data
        }
    except Exception as err:
        return _model_operation_error('download model', err)


def edit_model_metadata_action(model_name: str,
                               metadata: Dict[str, Any],
                               subtype: str = 'Stable-Diffusion') -> Dict[str, Any]:
    """Update metadata for a model via SwarmUI."""

    if not isinstance(metadata, dict):
        return {
            'success': False,
            'error': 'metadata must be a JSON object'
        }

    required_fields = [
        'title',
        'author',
        'type',
        'description',
        'standard_width',
        'standard_height',
        'usage_hint',
        'date',
        'license',
        'trigger_phrase',
        'prediction_type',
        'tags'
    ]
    missing_fields = [field for field in required_fields if field not in metadata]
    if missing_fields:
        return {
            'success': False,
            'error': f"Missing required metadata fields: {', '.join(missing_fields)}"
        }

    payload = {
        'model': model_name,
        'subtype': subtype,
        **metadata
    }

    try:
        swarm_post('/API/EditModelMetadata', payload)
        return {
            'success': True,
            'message': 'Metadata updated successfully'
        }
    except Exception as err:
        return _model_operation_error('edit model metadata', err)


def keep_worker_alive_action(duration_seconds: int,
                             interval_seconds: int = CHECK_INTERVAL) -> Dict[str, Any]:
    """Keep the worker warm by periodically pinging SwarmUI for a duration."""

    if duration_seconds <= 0:
        return {
            'success': False,
            'error': 'duration_seconds must be positive'
        }

    interval_seconds = max(1, interval_seconds)
    end_time = time.time() + duration_seconds
    pings = 0
    last_error: Optional[str] = None

    while time.time() < end_time:
        try:
            swarm_post('/API/GetNewSession', {}, timeout=10)
            pings += 1
            last_error = None
        except Exception as err:
            last_error = str(err)

        time.sleep(interval_seconds)

    result: Dict[str, Any] = {
        'success': last_error is None,
        'pings': pings,
        'duration': duration_seconds,
        'interval': interval_seconds
    }

    if last_error:
        result['last_error'] = last_error

    return result


def prepare_text2image_payload(job_input: Dict[str, Any], session_id: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Prepare payload for /API/GenerateText2Image based on job input."""

    raw_input = job_input.get('raw_input') or job_input.get('rawInput')
    if raw_input is not None and not isinstance(raw_input, dict):
        raise ValueError('raw_input must be a mapping if provided')

    if raw_input is not None:
        raw_input = dict(raw_input)

    control_keys = {
        'action',
        'install_only',
        'raw_input',
        'rawInput',
        'interval',
        'duration',
        'session_id'
    }

    if raw_input is None:
        raw_input = {
            key: value
            for key, value in job_input.items()
            if key not in control_keys and key not in {'images'}
        }

    images_requested = job_input.get('images')
    if images_requested is None and 'images' in raw_input:
        images_requested = raw_input['images']
        raw_input = {k: v for k, v in raw_input.items() if k != 'images'}

    if images_requested is None:
        images_count = 1
    else:
        try:
            images_count = int(images_requested)
        except (TypeError, ValueError):
            raise ValueError('images must be an integer')

    raw_input.setdefault('prompt', job_input.get('prompt', 'a beautiful landscape'))
    raw_input.setdefault('model', job_input.get('model', 'OfficialStableDiffusion/sd_xl_base_1.0'))

    payload: Dict[str, Any] = {
        'session_id': session_id,
        'images': images_count
    }

    extra_metadata = job_input.get('extra_metadata')
    if extra_metadata is not None:
        payload['extra_metadata'] = extra_metadata

    payload.update(raw_input)

    return payload, raw_input


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
    """Wait for SwarmUI to become responsive and ready for generation."""

    print("=" * 80)
    print("Waiting for SwarmUI to be ready...")
    print("=" * 80)
    print(f"URL: {SWARMUI_API_URL}")
    print(f"Max wait: {max_wait_seconds}s")
    print()

    start_time = time.time()
    max_attempts = max(1, max_wait_seconds // CHECK_INTERVAL)

    for attempt in range(max_attempts):
        elapsed = int(time.time() - start_time)

        try:
            session_info = swarm_post('/API/GetNewSession', {}, timeout=10)
            session_id = session_info.get('session_id')

            if session_id:
                try:
                    test_payload, _ = prepare_text2image_payload({
                        'images': 0,
                        'prompt': 'warmup',
                        'model': 'OfficialStableDiffusion/sd_xl_base_1.0',
                        'steps': 1,
                        'width': 512,
                        'height': 512
                    }, session_id)
                except ValueError:
                    test_payload = {
                        'session_id': session_id,
                        'images': 0,
                        'prompt': 'warmup',
                        'model': 'OfficialStableDiffusion/sd_xl_base_1.0',
                        'steps': 1,
                        'width': 512,
                        'height': 512
                    }

                try:
                    swarm_post('/API/GenerateText2Image', test_payload, timeout=10)
                    print()
                    print(f"✓ SwarmUI ready after {elapsed}s!")
                    print(f"  Version: {session_info.get('version', 'unknown')}")
                    return True
                except Exception as err:
                    print(f"  [{elapsed:4d}s] Backend warming: {err}")
            else:
                print(f"  [{elapsed:4d}s] Waiting for valid session...")

        except Exception as err:
            print(f"  [{elapsed:4d}s] Connecting: {err}")

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
    """Generate images using SwarmUI's /API/GenerateText2Image route."""

    if job_input.get('install_only'):
        print("Install-only warm-up requested; ensuring SwarmUI service is ready...")

        if not wait_for_service(SWARMUI_API_URL):
            return {
                'success': False,
                'error': 'SwarmUI service not ready during install warm-up'
            }

        session_id = get_session_id()
        if not session_id:
            return {
                'success': False,
                'error': 'Failed to obtain session during install warm-up'
            }

        return {
            'success': True,
            'status': 'install_ready',
            'message': 'SwarmUI responded successfully to install-only warm-up',
            'session_id': session_id
        }

    session_id = get_session_id()
    if not session_id:
        return {'success': False, 'error': 'Failed to create SwarmUI session'}

    try:
        request_payload, raw_input = prepare_text2image_payload(job_input, session_id)
    except ValueError as err:
        return {'success': False, 'error': str(err)}

    images_requested = request_payload.get('images', 1)

    prompt = raw_input.get('prompt')
    model = raw_input.get('model')
    steps = raw_input.get('steps')
    width = raw_input.get('width')
    height = raw_input.get('height')

    print()
    print("=" * 80)
    print("Generating Image")
    print("=" * 80)
    if prompt:
        print(f"Prompt: '{str(prompt)[:60]}...'")
    if model:
        print(f"Model: {model}")
    if width and height:
        print(f"Size: {width}x{height}")
    if steps is not None:
        print(f"Steps: {steps}")
    print(f"Images: {images_requested}")
    print()

    try:
        result = swarm_post('/API/GenerateText2Image', request_payload, timeout=GENERATION_TIMEOUT)
    except requests.exceptions.Timeout:
        return {'success': False, 'error': f'Generation timed out after {GENERATION_TIMEOUT}s'}
    except Exception as err:
        return {'success': False, 'error': f'Request failed: {err}'}

    error_msg = result.get('error') or result.get('error_id')
    if error_msg:
        print(f"ERROR: {error_msg}")
        return {'success': False, 'error': error_msg, 'details': result}

    image_paths = result.get('images', [])
    if not image_paths:
        return {'success': False, 'error': 'No images generated', 'details': result}

    images: List[str] = []
    for img_path in image_paths:
        img_data = fetch_image_as_base64(img_path)
        if img_data:
            images.append(img_data)

    if not images:
        return {'success': False, 'error': 'Failed to fetch generated images', 'details': result}

    print(f"✓ Successfully returned {len(images)} image(s)")

    return {
        'success': True,
        'images': images,
        'metadata': {
            'seed': result.get('seed'),
            'raw_input': raw_input,
            'images_requested': images_requested
        }
    }

def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """RunPod handler - entry point for all requests.
    
    Args:
        job: Dictionary containing the job input with 'action' and other parameters
        
    Returns:
        Dict containing the result of the requested action
    """
    try:
        job_input = job.get('input', {})
        action = job_input.get('action', 'generate')
        
        # Model management actions
        if action == 'list_models':
            return list_models_action(
                path=job_input.get('path', ''),
                depth=job_input.get('depth', 2),
                subtype=job_input.get('subtype', 'Stable-Diffusion'),
                allow_remote=job_input.get('allow_remote', True),
                sort_by=job_input.get('sort_by'),
                sort_reverse=job_input.get('sort_reverse'),
                data_images=job_input.get('data_images')
            )
            
        elif action == 'describe_model':
            if 'model_name' not in job_input:
                return {
                    'success': False,
                    'error': 'model_name is required for describe_model action'
                }
            return describe_model_action(
                model_name=job_input['model_name'],
                subtype=job_input.get('subtype', 'Stable-Diffusion')
            )
            
        elif action == 'download_model':
            if 'url' not in job_input or 'model_name' not in job_input:
                return {
                    'success': False,
                    'error': 'url and model_name are required for download_model action'
                }
            return download_model_action(
                url=job_input['url'],
                model_name=job_input['model_name'],
                model_type=job_input.get('model_type', 'Stable-Diffusion'),
                metadata=job_input.get('metadata')
            )
            
        elif action == 'edit_model_metadata':
            if 'model_name' not in job_input or 'metadata' not in job_input:
                return {
                    'success': False,
                    'error': 'model_name and metadata are required for edit_model_metadata action'
                }
            return edit_model_metadata_action(
                model_name=job_input['model_name'],
                metadata=job_input['metadata'],
                subtype=job_input.get('subtype', 'Stable-Diffusion')
            )

        elif action == 'keep_alive':
            duration = job_input.get('duration_seconds', job_input.get('duration', 60))
            interval = job_input.get('interval_seconds', job_input.get('interval', CHECK_INTERVAL))
            try:
                duration_int = int(duration)
                interval_int = int(interval)
            except (TypeError, ValueError):
                return {
                    'success': False,
                    'error': 'duration and interval must be integers'
                }

            return keep_worker_alive_action(duration_int, interval_int)

        # Image generation action (legacy)
        elif action == 'generate':
            return generate_image(job_input)

        # Unknown action
        else:
            return {
                'success': False,
                'error': f'Unknown action: {action}',
                'available_actions': [
                    'list_models',
                    'describe_model',
                    'download_model',
                    'edit_model_metadata',
                    'generate'
                ]
            }
            
    except KeyError as e:
        return {
            'success': False,
            'error': f'Missing required parameter: {str(e)}',
            'traceback': traceback.format_exc()
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Handler error: {str(e)}',
            'traceback': traceback.format_exc()
        }
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
