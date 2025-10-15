#!/usr/bin/env python3
"""Trigger first-time SwarmUI installation on RunPod Serverless.

First run takes 20-30 minutes for SwarmUI + ComfyUI installation.
Subsequent runs take 60-90 seconds.

Usage:
    python scripts/trigger_install.py --endpoint YOUR_ENDPOINT --api-key YOUR_KEY
"""

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


def call_endpoint(endpoint: str, api_key: str, action: str = "ready",
                  timeout: int = 120) -> Dict[str, Any]:
    """Call RunPod endpoint.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        action: Action to perform
        timeout: Request timeout
        
    Returns:
        Response JSON
    """
    url = f"https://api.runpod.ai/v2/{endpoint}/runsync"
    
    payload = {"input": {"action": action}}
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=timeout)
    response.raise_for_status()
    
    return response.json()


def wait_for_ready(endpoint: str, api_key: str, max_wait: int = 1800) -> bool:
    """Wait for SwarmUI to be ready.
    
    Args:
        endpoint: RunPod endpoint ID
        api_key: RunPod API token
        max_wait: Maximum wait time in seconds
        
    Returns:
        True if ready, False if timeout
    """
    print("\n" + "=" * 80)
    print("Triggering SwarmUI Installation")
    print("=" * 80 + "\n")
    
    print(f"Endpoint: {endpoint}")
    print(f"Max wait: {max_wait}s ({max_wait // 60} minutes)")
    print("\nNote: First install takes 20-30 minutes")
    print("      Subsequent starts take 60-90 seconds\n")
    
    start_time = time.time()
    check_interval = 15
    
    while True:
        elapsed = int(time.time() - start_time)
        
        try:
            result = call_endpoint(endpoint, api_key, "ready", timeout=60)
            output = result.get("output", {})
            
            if output.get("ready", False):
                print(f"\n✓ SwarmUI ready after {elapsed}s ({elapsed // 60} minutes)")
                print(f"  Version: {output.get('version', 'N/A')}")
                print(f"  Session: {output.get('session_id', 'N/A')[:16]}...")
                return True
            else:
                error = output.get("error", "Not ready")
                print(f"[{elapsed:5d}s] Waiting: {error}", end="\r")
                
        except requests.exceptions.Timeout:
            print(f"[{elapsed:5d}s] Request timeout (normal during install)", end="\r")
        except Exception as e:
            print(f"[{elapsed:5d}s] Error: {str(e)[:50]}", end="\r")
        
        if elapsed >= max_wait:
            print(f"\n\n✗ Timeout after {max_wait}s")
            print("\nPossible issues:")
            print("  - First install takes longer than expected")
            print("  - Check RunPod dashboard logs for errors")
            print("  - Ensure network volume has 15GB+ free space")
            return False
        
        time.sleep(check_interval)


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Trigger SwarmUI installation and wait for ready',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        '--endpoint',
        default=os.getenv(ENV_ENDPOINT),
        required=not os.getenv(ENV_ENDPOINT),
        help='RunPod endpoint ID'
    )
    parser.add_argument(
        '--api-key',
        default=os.getenv(ENV_API_KEY),
        required=not os.getenv(ENV_API_KEY),
        help='RunPod API token'
    )
    parser.add_argument(
        '--max-wait',
        type=int,
        default=1800,
        help='Maximum wait time in seconds (default: 1800 = 30 min)'
    )
    
    args = parser.parse_args()
    
    print("\n" + "=" * 80)
    print("SwarmUI RunPod Serverless - Installation Trigger")
    print("=" * 80)
    
    if wait_for_ready(args.endpoint, args.api_key, args.max_wait):
        print("\n" + "=" * 80)
        print("✓ Installation Complete - Worker Ready")
        print("=" * 80)
        print("\nNext steps:")
        print("  1. Test with: python tests/test_health.py")
        print("  2. Test API: python tests/test_swarm_passthrough.py")
        print("  3. Use SwarmUI API through your external app\n")
        return 0
    else:
        print("\n" + "=" * 80)
        print("✗ Installation Failed or Timed Out")
        print("=" * 80)
        print("\nCheck RunPod dashboard logs for details\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
