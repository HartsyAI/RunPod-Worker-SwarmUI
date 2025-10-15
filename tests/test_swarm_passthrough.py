#!/usr/bin/env python3
"""Test SwarmUI API pass-through functionality."""

import argparse
import base64
import os
import sys
from pathlib import Path
from typing import Dict, Any

import requests
from dotenv import load_dotenv

load_dotenv()

ENV_ENDPOINT = "RUNPOD_ENDPOINT_ID"
ENV_API_KEY = "RUNPOD_API_TOKEN"


def call_swarm_api(endpoint: str, api_key: str, method: str, path: str,
                   payload: Dict[str, Any] = None, timeout: int = 600) -> Dict[str, Any]:
    """Call SwarmUI API through RunPod handler.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        method: HTTP method (GET, POST)
        path: SwarmUI API path
        payload: Request payload
        timeout: Request timeout
        
    Returns:
        Response JSON
    """
    url = f"https://api.runpod.ai/v2/{endpoint}/runsync"
    
    request_payload = {
        "input": {
            "action": "swarm_api",
            "method": method,
            "path": path,
            "timeout": timeout
        }
    }
    
    if payload:
        request_payload["input"]["payload"] = payload
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=request_payload, headers=headers, timeout=timeout + 30)
    response.raise_for_status()
    
    return response.json()


def test_get_session(endpoint: str, api_key: str) -> bool:
    """Test GetNewSession API.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        
    Returns:
        True if successful, False otherwise
    """
    print("\n" + "=" * 80)
    print("Testing SwarmUI GetNewSession")
    print("=" * 80 + "\n")
    
    try:
        result = call_swarm_api(
            endpoint,
            api_key,
            "POST",
            "/API/GetNewSession",
            timeout=30
        )
        
        output = result.get("output", {})
        
        if not output.get("success", False):
            error = output.get("error", "Unknown error")
            print(f"✗ API call failed: {error}")
            return False
        
        response = output.get("response", {})
        session_id = response.get("session_id")
        
        if session_id:
            print(f"✓ Got session ID: {session_id[:16]}...")
            print(f"  Version: {response.get('version', 'N/A')}")
            return True
        else:
            print("✗ No session_id in response")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_list_models(endpoint: str, api_key: str) -> bool:
    """Test ListModels API.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        
    Returns:
        True if successful, False otherwise
    """
    print("\n" + "=" * 80)
    print("Testing SwarmUI ListModels")
    print("=" * 80 + "\n")
    
    try:
        # First get a session
        session_result = call_swarm_api(
            endpoint,
            api_key,
            "POST",
            "/API/GetNewSession",
            timeout=30
        )
        
        session_output = session_result.get("output", {})
        if not session_output.get("success"):
            print("✗ Failed to get session")
            return False
        
        session_id = session_output.get("response", {}).get("session_id")
        
        # List models
        result = call_swarm_api(
            endpoint,
            api_key,
            "POST",
            "/API/ListModels",
            payload={
                "session_id": session_id,
                "path": "",
                "depth": 2,
                "subtype": "Stable-Diffusion",
                "allowRemote": True
            },
            timeout=60
        )
        
        output = result.get("output", {})
        
        if not output.get("success", False):
            error = output.get("error", "Unknown error")
            print(f"✗ API call failed: {error}")
            return False
        
        response = output.get("response", {})
        files = response.get("files", [])
        folders = response.get("folders", [])
        
        print(f"✓ Found {len(files)} models in {len(folders)} folders")
        
        if files:
            print("\nFirst 5 models:")
            for f in files[:5]:
                print(f"  - {f}")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def test_generate_image(endpoint: str, api_key: str, 
                       prompt: str = "a simple test image",
                       output_dir: str = "output") -> bool:
    """Test GenerateText2Image API.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        prompt: Image prompt
        output_dir: Directory to save images
        
    Returns:
        True if successful, False otherwise
    """
    print("\n" + "=" * 80)
    print("Testing SwarmUI GenerateText2Image")
    print("=" * 80 + "\n")
    
    try:
        # Get session
        session_result = call_swarm_api(
            endpoint,
            api_key,
            "POST",
            "/API/GetNewSession",
            timeout=30
        )
        
        session_output = session_result.get("output", {})
        if not session_output.get("success"):
            print("✗ Failed to get session")
            return False
        
        session_id = session_output.get("response", {}).get("session_id")
        
        print(f"Prompt: {prompt}")
        print("Generating image...")
        
        # Generate image
        result = call_swarm_api(
            endpoint,
            api_key,
            "POST",
            "/API/GenerateText2Image",
            payload={
                "session_id": session_id,
                "prompt": prompt,
                "negative_prompt": "",
                "model": "OfficialStableDiffusion/sd_xl_base_1.0",
                "width": 1024,
                "height": 1024,
                "steps": 20,
                "cfg_scale": 7.0,
                "images": 1
            },
            timeout=600
        )
        
        output = result.get("output", {})
        
        if not output.get("success", False):
            error = output.get("error", "Unknown error")
            print(f"✗ Generation failed: {error}")
            return False
        
        response = output.get("response", {})
        images = response.get("images", [])
        
        if not images:
            print("✗ No images returned")
            return False
        
        print(f"✓ Generated {len(images)} image(s)")
        
        # Note: SwarmUI returns image paths, not base64 data
        # External app would need to fetch these separately
        print("\nImage paths:")
        for img_path in images:
            print(f"  - {img_path}")
        
        print("\nNote: Image paths are relative to SwarmUI server.")
        print("External app should fetch these via SwarmUI's file serving endpoint.")
        
        return True
        
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Test SwarmUI API pass-through functionality'
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
        '--prompt',
        default='a beautiful mountain landscape',
        help='Image generation prompt'
    )
    parser.add_argument(
        '--output',
        default='output',
        help='Output directory for images'
    )
    parser.add_argument(
        '--skip-generation',
        action='store_true',
        help='Skip image generation test'
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
    
    print("\n" + "=" * 80)
    print("SwarmUI API Pass-Through Tests")
    print("=" * 80)
    print(f"\nEndpoint: {args.endpoint}")
    
    # Run tests
    session_ok = test_get_session(args.endpoint, args.api_key)
    models_ok = test_list_models(args.endpoint, args.api_key)
    
    if args.skip_generation:
        generate_ok = True
        print("\n(Skipping generation test)")
    else:
        generate_ok = test_generate_image(
            args.endpoint,
            args.api_key,
            args.prompt,
            args.output
        )
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80 + "\n")
    
    results = [
        ("GetNewSession", session_ok),
        ("ListModels", models_ok),
        ("GenerateText2Image", generate_ok if not args.skip_generation else None)
    ]
    
    for name, passed in results:
        if passed is None:
            print(f"○ SKIP - {name}")
        elif passed:
            print(f"✓ PASS - {name}")
        else:
            print(f"✗ FAIL - {name}")
    
    all_passed = all(r[1] for r in results if r[1] is not None)
    
    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
