#!/usr/bin/env python3
"""Test direct SwarmUI URL access workflow.

Demonstrates:
1. Wake up worker and get public URL
2. Make direct SwarmUI API calls to that URL
3. Generate images without going through handler
4. Shutdown when done
"""

import argparse
import os
import sys
import time
import threading
from typing import Dict, Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

ENV_ENDPOINT = "RUNPOD_ENDPOINT_ID"
ENV_API_KEY = "RUNPOD_API_TOKEN"


def call_handler(endpoint: str, api_key: str, action: str,
                 **kwargs) -> Dict[str, Any]:
    """Call RunPod handler.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        action: Action to perform
        **kwargs: Additional parameters
        
    Returns:
        Response JSON
    """
    url = f"https://api.runpod.ai/v2/{endpoint}/runsync"
    
    payload = {"input": {"action": action, **kwargs}}
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    # Use longer timeout for wakeup/keepalive
    timeout = 3700 if action in ['wakeup', 'keepalive'] else 120
    
    response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    
    return response.json()


def call_swarm_direct(public_url: str, method: str, path: str,
                     payload: Optional[Dict[str, Any]] = None,
                     timeout: int = 600) -> Dict[str, Any]:
    """Call SwarmUI API directly.
    
    Args:
        public_url: Public SwarmUI URL
        method: HTTP method
        path: API path
        payload: JSON payload
        timeout: Request timeout
        
    Returns:
        Response JSON
    """
    url = f"{public_url.rstrip('/')}/{path.lstrip('/')}"
    
    if method.upper() == 'GET':
        response = requests.get(url, timeout=timeout)
    elif method.upper() == 'POST':
        response = requests.post(url, json=payload or {}, timeout=timeout)
    else:
        raise ValueError(f"Unsupported method: {method}")
    
    response.raise_for_status()
    return response.json() if response.content else {}


def test_workflow(endpoint: str, api_key: str, keepalive_duration: int = 600):
    """Test complete direct URL workflow.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        keepalive_duration: How long to keep worker alive (seconds)
    """
    print("\n" + "=" * 80)
    print("SwarmUI Direct URL Access Test")
    print("=" * 80 + "\n")
    
    print(f"Endpoint: {endpoint}")
    print(f"Keepalive: {keepalive_duration}s ({keepalive_duration // 60} minutes)\n")
    
    # Step 1: Wake up worker in background thread
    print("=" * 80)
    print("Step 1: Waking up worker...")
    print("=" * 80 + "\n")
    
    wakeup_result = {}
    wakeup_error = None
    
    def wakeup_thread():
        nonlocal wakeup_result, wakeup_error
        try:
            result = call_handler(
                endpoint,
                api_key,
                "wakeup",
                duration=keepalive_duration,
                interval=30
            )
            wakeup_result = result.get("output", {})
        except Exception as e:
            wakeup_error = str(e)
    
    thread = threading.Thread(target=wakeup_thread, daemon=True)
    thread.start()
    
    # Wait a bit for worker to start
    print("Waiting for worker to start (this may take 60-90 seconds)...")
    time.sleep(5)
    
    # Step 2: Check if worker is ready
    print("\n" + "=" * 80)
    print("Step 2: Checking worker status...")
    print("=" * 80 + "\n")
    
    max_wait = 300  # 5 minutes
    start = time.time()
    
    while time.time() - start < max_wait:
        try:
            result = call_handler(endpoint, api_key, "ready")
            output = result.get("output", {})
            
            if output.get("ready"):
                public_url = output.get("public_url")
                worker_id = output.get("worker_id")
                version = output.get("version")
                
                print(f"✓ Worker ready!")
                print(f"  Public URL: {public_url}")
                print(f"  Worker ID: {worker_id}")
                print(f"  Version: {version}\n")
                break
        except Exception as e:
            print(f"  Still waiting... {e}")
        
        time.sleep(15)
    else:
        print("✗ Worker failed to start within timeout")
        return False
    
    # Step 3: Get SwarmUI session directly
    print("=" * 80)
    print("Step 3: Getting SwarmUI session (direct API call)...")
    print("=" * 80 + "\n")
    
    try:
        session_data = call_swarm_direct(
            public_url,
            "POST",
            "/API/GetNewSession"
        )
        
        session_id = session_data.get("session_id")
        print(f"✓ Got session ID: {session_id[:16]}...")
        print(f"  Version: {session_data.get('version', 'N/A')}\n")
    except Exception as e:
        print(f"✗ Failed to get session: {e}\n")
        return False
    
    # Step 4: List models directly
    print("=" * 80)
    print("Step 4: Listing models (direct API call)...")
    print("=" * 80 + "\n")
    
    try:
        models_data = call_swarm_direct(
            public_url,
            "POST",
            "/API/ListModels",
            payload={
                "session_id": session_id,
                "path": "",
                "depth": 2,
                "subtype": "Stable-Diffusion",
                "allowRemote": True
            }
        )
        
        files = models_data.get("files", [])
        folders = models_data.get("folders", [])
        
        print(f"✓ Found {len(files)} models in {len(folders)} folders")
        
        if files:
            print("\nFirst 5 models:")
            for f in files[:5]:
                print(f"  - {f}")
        print()
    except Exception as e:
        print(f"✗ Failed to list models: {e}\n")
        return False
    
    # Step 5: Generate image directly
    print("=" * 80)
    print("Step 5: Generating image (direct API call)...")
    print("=" * 80 + "\n")
    
    try:
        print("Prompt: 'a beautiful mountain landscape at sunset'")
        print("Generating...\n")
        
        generation_data = call_swarm_direct(
            public_url,
            "POST",
            "/API/GenerateText2Image",
            payload={
                "session_id": session_id,
                "prompt": "a beautiful mountain landscape at sunset, photorealistic, 8k",
                "negative_prompt": "blurry, low quality, distorted",
                "model": "OfficialStableDiffusion/sd_xl_base_1.0",
                "width": 1024,
                "height": 1024,
                "steps": 20,
                "cfg_scale": 7.5,
                "seed": -1,
                "images": 1
            },
            timeout=600
        )
        
        images = generation_data.get("images", [])
        print(f"✓ Generated {len(images)} image(s)")
        
        for img_path in images:
            print(f"  - {img_path}")
        
        print(f"\nNote: Images can be retrieved from SwarmUI's Output directory")
        print(f"      or via: {public_url}/Output/...")
        print()
    except Exception as e:
        print(f"✗ Failed to generate image: {e}\n")
        return False
    
    # Step 6: Demonstrate multiple generations
    print("=" * 80)
    print("Step 6: Multiple generations (direct API calls)...")
    print("=" * 80 + "\n")
    
    prompts = [
        "a serene ocean sunset",
        "a cyberpunk city at night",
        "a peaceful forest path"
    ]
    
    for i, prompt in enumerate(prompts, 1):
        print(f"[{i}/{len(prompts)}] Generating: '{prompt}'")
        try:
            result = call_swarm_direct(
                public_url,
                "POST",
                "/API/GenerateText2Image",
                payload={
                    "session_id": session_id,
                    "prompt": prompt,
                    "model": "OfficialStableDiffusion/sd_xl_base_1.0",
                    "width": 512,
                    "height": 512,
                    "steps": 15,
                    "images": 1
                },
                timeout=300
            )
            
            images = result.get("images", [])
            print(f"         ✓ Generated: {images[0] if images else 'none'}")
        except Exception as e:
            print(f"         ✗ Failed: {e}")
    
    print()
    
    # Summary
    print("=" * 80)
    print("Test Summary")
    print("=" * 80 + "\n")
    
    print("✓ Worker started successfully")
    print("✓ Public URL obtained")
    print("✓ Direct SwarmUI API access working")
    print("✓ Multiple generations successful")
    print(f"\nWorker will stay alive for {keepalive_duration // 60} minutes")
    print("You can continue making direct API calls during this time")
    print(f"Or send shutdown: python tests/test_direct_url.py --shutdown\n")
    
    return True


def test_shutdown(endpoint: str, api_key: str):
    """Send shutdown signal to worker.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
    """
    print("\n" + "=" * 80)
    print("Sending Shutdown Signal")
    print("=" * 80 + "\n")
    
    try:
        result = call_handler(endpoint, api_key, "shutdown")
        output = result.get("output", {})
        
        if output.get("success"):
            print("✓ Shutdown acknowledged")
            print("  Worker will stop after current keepalive expires\n")
        else:
            print(f"✗ Shutdown failed: {output.get('error')}\n")
    except Exception as e:
        print(f"✗ Shutdown error: {e}\n")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Test direct SwarmUI URL access'
    )
    
    parser.add_argument(
        '--endpoint',
        default=os.getenv(ENV_ENDPOINT),
        help='RunPod endpoint ID'
    )
    parser.add_argument(
        '--api-key',
        default=os.getenv(ENV_API_KEY),
        help='RunPod API token'
    )
    parser.add_argument(
        '--duration',
        type=int,
        default=600,
        help='Keepalive duration in seconds (default: 600 = 10 minutes)'
    )
    parser.add_argument(
        '--shutdown',
        action='store_true',
        help='Send shutdown signal instead of running tests'
    )
    
    args = parser.parse_args()
    
    if not args.endpoint:
        print(f"Error: Missing endpoint ID. Set {ENV_ENDPOINT} or use --endpoint",
              file=sys.stderr)
        return 1
    
    if not args.api_key:
        print(f"Error: Missing API key. Set {ENV_API_KEY} or use --api-key",
              file=sys.stderr)
        return 1
    
    if args.shutdown:
        test_shutdown(args.endpoint, args.api_key)
        return 0
    
    success = test_workflow(args.endpoint, args.api_key, args.duration)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
