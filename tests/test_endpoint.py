#!/usr/bin/env python3
"""
Test script for SwarmUI RunPod Serverless Endpoint

Usage:
    python test_endpoint.py --endpoint YOUR_ENDPOINT_ID --api-key YOUR_API_KEY
"""

import argparse
import requests
import json
import time
import base64
from pathlib import Path


def test_runsync(endpoint_id, api_key, prompt=None):
    """
    Test the /runsync endpoint (synchronous, waits for completion).
    
    Args:
        endpoint_id: RunPod endpoint ID
        api_key: RunPod API key
        prompt: Custom prompt (optional)
    """
    url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
    
    # Prepare request
    payload = {
        "input": {
            "prompt": prompt or "a beautiful mountain landscape at sunset, highly detailed, 4k",
            "negative_prompt": "blurry, low quality, distorted",
            "model": "OfficialStableDiffusion/sd_xl_base_1.0",
            "width": 1024,
            "height": 1024,
            "steps": 30,
            "cfg_scale": 7.5,
            "seed": -1,
            "images": 1
        }
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("=" * 80)
    print("Testing SwarmUI RunPod Endpoint (Synchronous)")
    print("=" * 80)
    print(f"Endpoint ID: {endpoint_id}")
    print(f"URL: {url}")
    print(f"Prompt: {payload['input']['prompt']}")
    print("=" * 80)
    print("\nSending request (this may take 30-90 seconds for cold start)...")
    
    try:
        start_time = time.time()
        
        response = requests.post(url, json=payload, headers=headers, timeout=600)
        response.raise_for_status()
        
        elapsed = time.time() - start_time
        
        result = response.json()
        
        print(f"\n✓ Request completed in {elapsed:.2f} seconds")
        print("\nResponse:")
        print(json.dumps(result, indent=2))
        
        # Save images if present
        if 'output' in result and 'images' in result['output']:
            save_images(result['output']['images'])
        
        return result
        
    except requests.exceptions.Timeout:
        print("\n✗ Request timed out (took longer than 600 seconds)")
        print("  This might indicate a cold start issue or slow model loading")
        return None
    except requests.exceptions.HTTPError as e:
        print(f"\n✗ HTTP Error: {e}")
        print(f"  Response: {e.response.text}")
        return None
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return None


def test_run_async(endpoint_id, api_key, prompt=None):
    """
    Test the /run endpoint (asynchronous, returns job ID immediately).
    
    Args:
        endpoint_id: RunPod endpoint ID
        api_key: RunPod API key
        prompt: Custom prompt (optional)
    """
    run_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    
    payload = {
        "input": {
            "prompt": prompt or "a beautiful mountain landscape at sunset, highly detailed, 4k",
            "negative_prompt": "blurry, low quality, distorted",
            "model": "OfficialStableDiffusion/sd_xl_base_1.0",
            "width": 1024,
            "height": 1024,
            "steps": 30,
            "cfg_scale": 7.5,
            "seed": -1,
            "images": 1
        }
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    print("=" * 80)
    print("Testing SwarmUI RunPod Endpoint (Asynchronous)")
    print("=" * 80)
    print(f"Endpoint ID: {endpoint_id}")
    print(f"Prompt: {payload['input']['prompt']}")
    print("=" * 80)
    
    try:
        # Submit job
        print("\nSubmitting job...")
        response = requests.post(run_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        
        job_data = response.json()
        job_id = job_data.get('id')
        
        print(f"✓ Job submitted successfully")
        print(f"  Job ID: {job_id}")
        print(f"  Status: {job_data.get('status', 'UNKNOWN')}")
        
        # Poll for status
        status_url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
        
        print("\nPolling for job completion...")
        max_attempts = 120  # 10 minutes max
        attempt = 0
        
        while attempt < max_attempts:
            time.sleep(5)
            attempt += 1
            
            status_response = requests.get(status_url, headers=headers, timeout=30)
            status_response.raise_for_status()
            
            status_data = status_response.json()
            status = status_data.get('status', 'UNKNOWN')
            
            print(f"  [{attempt * 5}s] Status: {status}")
            
            if status == 'COMPLETED':
                print(f"\n✓ Job completed successfully")
                print("\nResult:")
                print(json.dumps(status_data, indent=2))
                
                # Save images if present
                if 'output' in status_data and 'images' in status_data['output']:
                    save_images(status_data['output']['images'])
                
                return status_data
            
            if status == 'FAILED':
                print(f"\n✗ Job failed")
                print(f"  Error: {status_data.get('error', 'Unknown error')}")
                return status_data
            
            if status not in ['IN_QUEUE', 'IN_PROGRESS']:
                print(f"\n? Unknown status: {status}")
        
        print(f"\n✗ Job did not complete within {max_attempts * 5} seconds")
        return None
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return None


def save_images(images):
    """
    Save base64 images to files.
    
    Args:
        images: List of image objects with base64 data
    """
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    
    print(f"\nSaving images to '{output_dir}' directory...")
    
    for i, img in enumerate(images):
        if img.get('type') == 'base64':
            filename = img.get('filename', f'image_{i}.png')
            filepath = output_dir / filename
            
            try:
                img_data = base64.b64decode(img['data'])
                with open(filepath, 'wb') as f:
                    f.write(img_data)
                print(f"  ✓ Saved: {filepath}")
            except Exception as e:
                print(f"  ✗ Failed to save {filename}: {e}")


def main():
    parser = argparse.ArgumentParser(description='Test SwarmUI RunPod Serverless Endpoint')
    parser.add_argument('--endpoint', required=True, help='RunPod endpoint ID')
    parser.add_argument('--api-key', required=True, help='RunPod API key')
    parser.add_argument('--prompt', help='Custom prompt (optional)')
    parser.add_argument('--async', action='store_true', dest='use_async', help='Use async /run endpoint instead of /runsync')
    
    args = parser.parse_args()
    
    if args.use_async:
        result = test_run_async(args.endpoint, args.api_key, args.prompt)
    else:
        result = test_runsync(args.endpoint, args.api_key, args.prompt)
    
    if result:
        print("\n" + "=" * 80)
        print("Test completed successfully!")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("Test failed!")
        print("=" * 80)
        exit(1)
if __name__ == "__main__":
    main()
