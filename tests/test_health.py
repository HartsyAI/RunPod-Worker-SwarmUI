#!/usr/bin/env python3
"""Test health and readiness endpoints."""

import argparse
import os
import sys
import time
from typing import Dict, Any

import requests
from dotenv import load_dotenv

load_dotenv()

ENV_ENDPOINT = "RUNPOD_ENDPOINT_ID"
ENV_API_KEY = "RUNPOD_API_TOKEN"


def call_endpoint(endpoint: str, api_key: str, action: str, 
                  extra_input: Dict[str, Any] = None) -> Dict[str, Any]:
    """Call RunPod endpoint with action.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        action: Action to perform
        extra_input: Additional input parameters
        
    Returns:
        Response JSON
    """
    url = f"https://api.runpod.ai/v2/{endpoint}/runsync"
    
    payload = {"input": {"action": action}}
    if extra_input:
        payload["input"].update(extra_input)
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=120)
    response.raise_for_status()
    
    return response.json()


def test_health(endpoint: str, api_key: str) -> bool:
    """Test health endpoint.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        
    Returns:
        True if healthy, False otherwise
    """
    print("\n" + "=" * 80)
    print("Testing Health Endpoint")
    print("=" * 80 + "\n")
    
    try:
        result = call_endpoint(endpoint, api_key, "health")
        output = result.get("output", {})
        
        healthy = output.get("healthy", False)
        
        if healthy:
            print("✓ Health check passed")
            return True
        else:
            error = output.get("error", "Unknown error")
            print(f"✗ Health check failed: {error}")
            return False
            
    except Exception as e:
        print(f"✗ Health check error: {e}")
        return False


def test_ready(endpoint: str, api_key: str) -> bool:
    """Test ready endpoint.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        
    Returns:
        True if ready, False otherwise
    """
    print("\n" + "=" * 80)
    print("Testing Ready Endpoint")
    print("=" * 80 + "\n")
    
    try:
        result = call_endpoint(endpoint, api_key, "ready")
        output = result.get("output", {})
        
        ready = output.get("ready", False)
        
        if ready:
            print("✓ SwarmUI is ready")
            print(f"  Session ID: {output.get('session_id', 'N/A')}")
            print(f"  Version: {output.get('version', 'N/A')}")
            print(f"  API URL: {output.get('api_url', 'N/A')}")
            return True
        else:
            error = output.get("error", "Not ready")
            print(f"✗ SwarmUI not ready: {error}")
            return False
            
    except Exception as e:
        print(f"✗ Ready check error: {e}")
        return False


def test_keepalive(endpoint: str, api_key: str, duration: int = 30) -> bool:
    """Test keepalive endpoint.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        duration: Duration in seconds
        
    Returns:
        True if successful, False otherwise
    """
    print("\n" + "=" * 80)
    print(f"Testing Keepalive Endpoint ({duration}s)")
    print("=" * 80 + "\n")
    
    try:
        print(f"Starting keepalive for {duration}s...")
        start = time.time()
        
        result = call_endpoint(
            endpoint, 
            api_key, 
            "keepalive",
            {"duration": duration, "interval": 10}
        )
        
        elapsed = time.time() - start
        output = result.get("output", {})
        
        success = output.get("success", False)
        
        if success:
            print(f"✓ Keepalive completed in {elapsed:.1f}s")
            print(f"  Pings: {output.get('pings', 0)}")
            print(f"  Failures: {output.get('failures', 0)}")
            return True
        else:
            error = output.get("error", "Unknown error")
            print(f"✗ Keepalive failed: {error}")
            return False
            
    except Exception as e:
        print(f"✗ Keepalive error: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Test SwarmUI health and readiness endpoints'
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
        '--keepalive-duration',
        type=int,
        default=30,
        help='Duration for keepalive test (seconds)'
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
    print("SwarmUI Health Tests")
    print("=" * 80)
    print(f"\nEndpoint: {args.endpoint}")
    
    # Run tests
    health_ok = test_health(args.endpoint, args.api_key)
    ready_ok = test_ready(args.endpoint, args.api_key)
    keepalive_ok = test_keepalive(args.endpoint, args.api_key, args.keepalive_duration)
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80 + "\n")
    
    results = [
        ("Health", health_ok),
        ("Ready", ready_ok),
        ("Keepalive", keepalive_ok)
    ]
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status} - {name}")
    
    all_passed = all(r[1] for r in results)
    
    if all_passed:
        print("\n✓ All tests passed!")
        return 0
    else:
        print("\n✗ Some tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())