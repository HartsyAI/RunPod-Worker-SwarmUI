#!/usr/bin/env python3
"""Trigger first-time SwarmUI installation on RunPod Serverless.

This script wakes up your serverless endpoint and waits for the initial
installation to complete. First run takes 20-30 minutes as it:
  1. Downloads and runs SwarmUI installer
  2. Installs ComfyUI backend
  3. Builds and starts SwarmUI

Subsequent runs will be much faster (60-90 seconds).

Usage:
    # Trigger first install
    python trigger_first_install.py --endpoint YOUR_ENDPOINT_ID --api-key YOUR_API_KEY
    
    # Check if already installed (quick test)
    python trigger_first_install.py --endpoint YOUR_ENDPOINT_ID --api-key YOUR_API_KEY --quick-test
"""

import argparse
import sys
import time
import requests
from typing import Optional, Dict, Any
from datetime import datetime, timedelta


class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def print_header(message: str) -> None:
    """Print a formatted header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{message}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'=' * 80}{Colors.RESET}\n")


def print_success(message: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}✓ {message}{Colors.RESET}")


def print_error(message: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}✗ {message}{Colors.RESET}")


def print_info(message: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}ℹ {message}{Colors.RESET}")


def print_warning(message: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}⚠ {message}{Colors.RESET}")


def trigger_async_install(endpoint_id: str, api_key: str, quick_test: bool = False,
                          model_name: str = "SDXL/sd_xl_base_1.0") -> bool:
    """Trigger installation using async /run endpoint and poll for completion.
    
    Args:
        endpoint_id: RunPod endpoint ID
        api_key: RunPod API key
        quick_test: If True, use minimal timeout for testing if already installed
        
    Returns:
        bool: True if successful, False otherwise
    """
    run_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    
    # Minimal payload - just wake up the service
    payload = {
        "input": {
            "prompt": "test installation trigger",
            "model": model_name,
            "width": 512,
            "height": 512,
            "steps": 1,
            "images": 0  # Don't actually generate an image
        }
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print_header("Triggering SwarmUI Installation")
    print_info(f"Endpoint: {endpoint_id}")
    print_info(f"URL: {run_url}")
    print_info(f"Model: {model_name}")
    
    if quick_test:
        print_warning("Quick test mode - will timeout after 5 minutes")
    else:
        print_warning("First-time install takes 20-30 minutes")
        print_info("You can safely close this script - the install continues in the background")
        print_info("Run again later with --quick-test to check if installation completed")
    
    print()
    
    try:
        # Submit job
        print_info("Submitting wake-up request...")
        start_time = time.time()
        
        response = requests.post(run_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        job_data = response.json()
        job_id = job_data.get('id')
        status = job_data.get('status', 'UNKNOWN')
        
        print_success(f"Request submitted successfully")
        print_info(f"Job ID: {job_id}")
        print_info(f"Initial status: {status}")
        
        # Poll for completion
        status_url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
        
        # Set timeout based on mode
        max_wait = 300 if quick_test else 2400  # 5 min for quick test, 40 min for full install
        check_interval = 10
        max_attempts = max_wait // check_interval
        
        print()
        print_info(f"Polling for completion (max {max_wait // 60} minutes)...")
        print_info("Press Ctrl+C to exit (installation will continue in background)")
        print()
        
        attempt = 0
        last_status = status
        
        while attempt < max_attempts:
            time.sleep(check_interval)
            attempt += 1
            elapsed = int(time.time() - start_time)
            
            try:
                status_response = requests.get(status_url, headers=headers, timeout=30)
                status_response.raise_for_status()
                
                status_data = status_response.json()
                current_status = status_data.get('status', 'UNKNOWN')
                
                # Show status updates
                if current_status != last_status:
                    print_info(f"[{elapsed:4d}s] Status changed: {last_status} → {current_status}")
                    last_status = current_status
                else:
                    # Show progress dots
                    dots = "." * (attempt % 4)
                    print(f"  [{elapsed:4d}s] {current_status:<15} {dots:<3}", end="\r")
                
                # Check for completion
                if current_status == 'COMPLETED':
                    print()  # New line after progress
                    print_success(f"Installation completed in {elapsed}s ({elapsed // 60} minutes)")
                    
                    # Show any output/errors
                    if 'output' in status_data:
                        output = status_data['output']
                        if 'error' in output:
                            print_warning(f"Note: {output['error']}")
                        if 'images' in output:
                            print_success(f"Backend is working! Generated {len(output['images'])} test image(s)")
                    
                    return True
                
                if current_status == 'FAILED':
                    print()  # New line after progress
                    print_error("Installation failed")
                    error = status_data.get('error', 'Unknown error')
                    print_error(f"Error: {error}")
                    
                    # Show helpful hints
                    print()
                    print_info("Common issues:")
                    print_info("  • First install timeout: Normal if >30 min, try --quick-test later")
                    print_info("  • Out of memory: Increase container disk to 15GB+")
                    print_info("  • Network volume: Ensure volume is attached to endpoint")
                    
                    return False
                
                # Check if taking too long
                if elapsed > max_wait:
                    print()  # New line after progress
                    if quick_test:
                        print_warning(f"Quick test timed out after {max_wait}s")
                        print_info("Installation likely still in progress")
                        print_info("Run again without --quick-test to wait for full install")
                    else:
                        print_warning(f"Installation taking longer than expected ({elapsed // 60} minutes)")
                        print_info("This can happen on first run - installation continues in background")
                        print_info("Check RunPod dashboard logs for progress")
                    break
                    
            except requests.exceptions.RequestException as e:
                print()  # New line after progress
                print_warning(f"Network error checking status: {e}")
                print_info("Will retry...")
        
        # If we got here, we timed out but job may still be running
        if last_status in ['IN_QUEUE', 'IN_PROGRESS']:
            print()
            print_warning("Script timeout reached, but installation is still running")
            print_info("Installation continues in the background")
            print_info(f"Check status manually: {status_url}")
            print_info("Or run this script again with --quick-test")
            return True  # Not a failure, just timed out waiting
        
        return False
        
    except requests.exceptions.HTTPError as e:
        print_error(f"HTTP Error: {e}")
        if e.response.status_code == 401:
            print_error("Authentication failed - check your API key")
        elif e.response.status_code == 404:
            print_error("Endpoint not found - check your endpoint ID")
        else:
            print_error(f"Response: {e.response.text}")
        return False
    except requests.exceptions.RequestException as e:
        print_error(f"Request failed: {e}")
        return False
    except KeyboardInterrupt:
        print()
        print_warning("Interrupted by user")
        print_info("Installation continues in the background")
        print_info("Run again with --quick-test to check status")
        return True
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        return False


def check_health(endpoint_id: str, api_key: str) -> bool:
    """Quick health check to see if endpoint is responsive.
    
    Args:
        endpoint_id: RunPod endpoint ID
        api_key: RunPod API key
        
    Returns:
        bool: True if healthy, False otherwise
    """
    health_url = f"https://api.runpod.ai/v2/{endpoint_id}/health"
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print_info("Checking endpoint health...")
    
    try:
        response = requests.get(health_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            print_success("Endpoint is healthy")
            
            # Show workers info if available
            if 'workers' in data:
                workers = data['workers']
                print_info(f"Workers: {workers.get('running', 0)} running, {workers.get('idle', 0)} idle")
            
            return True
        else:
            print_warning(f"Health check returned status {response.status_code}")
            return False
            
    except requests.exceptions.RequestException as e:
        print_warning(f"Health check failed: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Trigger first-time SwarmUI installation on RunPod Serverless',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Trigger first install (wait up to 40 minutes)
  python trigger_first_install.py --endpoint abc123 --api-key YOUR_KEY
  
  # Quick test to check if already installed (5 minute timeout)
  python trigger_first_install.py --endpoint abc123 --api-key YOUR_KEY --quick-test
  
  # Just check endpoint health
  python trigger_first_install.py --endpoint abc123 --api-key YOUR_KEY --health-only

Notes:
  • First install takes 20-30 minutes
  • You can safely exit this script - install continues in background
  • Re-run with --quick-test to check if installation finished
        """
    )
    
    parser.add_argument('--endpoint', required=True, help='RunPod endpoint ID')
    parser.add_argument('--api-key', required=True, help='RunPod API key')
    parser.add_argument('--quick-test', action='store_true',
                        help='Quick test with 5 minute timeout (check if already installed)')
    parser.add_argument('--health-only', action='store_true',
                        help='Only check endpoint health, do not trigger install')
    parser.add_argument('--model', default='SDXL/sd_xl_base_1.0',
                        help='SwarmUI model identifier to use for the warm-up request')
    
    args = parser.parse_args()
    
    print_header("SwarmUI RunPod Serverless - Installation Trigger")
    
    # Health check first
    if args.health_only:
        is_healthy = check_health(args.endpoint, args.api_key)
        return 0 if is_healthy else 1
    
    # Show what we're doing
    if args.quick_test:
        print_info("Mode: Quick test (5 minute timeout)")
        print_info("Use this to check if a previous installation finished")
    else:
        print_info("Mode: Full installation trigger (40 minute timeout)")
        print_info("This will wait for the complete first-time installation")
    
    print()
    
    # Optional: Do health check first
    check_health(args.endpoint, args.api_key)
    print()
    
    # Trigger installation
    start = datetime.now()
    success = trigger_async_install(args.endpoint, args.api_key, args.quick_test, args.model)
    elapsed = datetime.now() - start
    
    print()
    print_header("Summary")
    print_info(f"Total time: {elapsed}")
    
    if success:
        print_success("Installation trigger completed successfully!")
        print()
        print_info("Next steps:")
        print_info("  1. Your SwarmUI serverless endpoint is now ready")
        print_info("  2. Test with: python tests/test_endpoint.py --endpoint YOUR_ID --api-key YOUR_KEY")
        print_info("  3. Connect your local SwarmUI to use it as a remote backend")
        return 0
    else:
        print_error("Installation trigger failed or timed out")
        print()
        print_info("Troubleshooting:")
        print_info("  • Check RunPod dashboard for endpoint logs")
        print_info("  • Verify network volume is attached")
        print_info("  • Ensure container has 15GB+ disk space")
        print_info("  • First install can take 30+ minutes - be patient!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
