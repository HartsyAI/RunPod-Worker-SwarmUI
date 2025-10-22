#!/usr/bin/env python3
"""Simple SwarmUI client for direct URL access.

Usage:
    from client import SwarmUIClient
    
    client = SwarmUIClient(endpoint_id, api_key)
    public_url = client.wakeup(duration=3600)  # 1 hour
    
    # Now use public_url for direct SwarmUI API calls
    session_id = client.get_session(public_url)
    images = client.generate_image(public_url, session_id, "a mountain")
    
    client.shutdown()  # When done
"""

import time
import threading
from typing import Dict, Any, Optional

import requests


class SwarmUIClient:
    """Client for managing SwarmUI workers on RunPod.
    
    This client handles:
    1. Waking up workers and getting public URLs
    2. Making direct SwarmUI API calls
    3. Shutting down workers when done
    """
    
    def __init__(self, endpoint_id: str, api_key: str):
        """Initialize client.
        
        Args:
            endpoint_id: RunPod endpoint ID
            api_key: RunPod API token
        """
        self.endpoint_id = endpoint_id
        self.api_key = api_key
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}/runsync"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        self.public_url: Optional[str] = None
        self._wakeup_thread: Optional[threading.Thread] = None
    
    def _call_handler(self, action: str, timeout: int = 120, **kwargs) -> Dict[str, Any]:
        """Call RunPod handler.
        
        Args:
            action: Action to perform
            timeout: Request timeout
            **kwargs: Additional parameters
            
        Returns:
            Response output
        """
        payload = {"input": {"action": action, **kwargs}}
        
        response = requests.post(
            self.base_url,
            json=payload,
            headers=self.headers,
            timeout=timeout
        )
        response.raise_for_status()
        
        return response.json().get("output", {})
    
    def wakeup(self, duration: int = 3600, wait: bool = True) -> str:
        """Wake up worker and get public URL.
        
        Args:
            duration: How long to keep worker alive (seconds)
            wait: Whether to wait for worker to be ready
            
        Returns:
            Public SwarmUI URL
            
        Raises:
            RuntimeError: If worker fails to start
        """
        print(f"Waking up worker (keepalive: {duration}s)...")
        
        # Start wakeup in background thread (it blocks for duration)
        def _wakeup():
            self._call_handler("wakeup", timeout=duration + 100, duration=duration)
        
        self._wakeup_thread = threading.Thread(target=_wakeup, daemon=True)
        self._wakeup_thread.start()
        
        if wait:
            # Wait for worker to be ready
            max_wait = 300  # 5 minutes
            start = time.time()
            
            while time.time() - start < max_wait:
                try:
                    result = self._call_handler("ready", timeout=30)
                    
                    if result.get("ready"):
                        self.public_url = result.get("public_url")
                        print(f"✓ Worker ready: {self.public_url}")
                        return self.public_url
                        
                except Exception:
                    pass
                
                time.sleep(10)
            
            raise RuntimeError("Worker failed to start within timeout")
        
        return ""
    
    def shutdown(self):
        """Signal worker to shutdown.
        
        Note: Worker will shutdown after current keepalive expires.
        """
        print("Sending shutdown signal...")
        try:
            result = self._call_handler("shutdown", timeout=30)
            if result.get("success"):
                print("✓ Shutdown acknowledged")
        except Exception as e:
            print(f"✗ Shutdown error: {e}")
    
    def call_swarm(self, public_url: str, method: str, path: str,
                   payload: Optional[Dict[str, Any]] = None,
                   timeout: int = 600) -> Dict[str, Any]:
        """Call SwarmUI API directly.
        
        Args:
            public_url: Public SwarmUI URL
            method: HTTP method (GET, POST)
            path: API path (e.g., /API/GetNewSession)
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
    
    def get_session(self, public_url: str) -> str:
        """Get SwarmUI session ID.
        
        Args:
            public_url: Public SwarmUI URL
            
        Returns:
            Session ID
        """
        result = self.call_swarm(public_url, "POST", "/API/GetNewSession")
        return result["session_id"]
    
    def list_models(self, public_url: str, session_id: str) -> Dict[str, Any]:
        """List available models.
        
        Args:
            public_url: Public SwarmUI URL
            session_id: SwarmUI session ID
            
        Returns:
            Dict with files and folders
        """
        return self.call_swarm(
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
    
    def generate_image(self, public_url: str, session_id: str, prompt: str,
                      **kwargs) -> list:
        """Generate images.
        
        Args:
            public_url: Public SwarmUI URL
            session_id: SwarmUI session ID
            prompt: Image prompt
            **kwargs: Additional SwarmUI parameters
            
        Returns:
            List of image paths
        """
        payload = {
            "session_id": session_id,
            "prompt": prompt,
            "negative_prompt": kwargs.get("negative_prompt", ""),
            "model": kwargs.get("model", "OfficialStableDiffusion/sd_xl_base_1.0"),
            "width": kwargs.get("width", 1024),
            "height": kwargs.get("height", 1024),
            "steps": kwargs.get("steps", 30),
            "cfg_scale": kwargs.get("cfg_scale", 7.5),
            "seed": kwargs.get("seed", -1),
            "images": kwargs.get("images", 1)
        }
        
        result = self.call_swarm(
            public_url,
            "POST",
            "/API/GenerateText2Image",
            payload=payload,
            timeout=600
        )
        
        return result.get("images", [])


def example_usage():
    """Example usage of SwarmUI client."""
    import os
    
    # Configuration
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "your-endpoint-id")
    api_key = os.getenv("RUNPOD_API_TOKEN", "your-api-key")
    
    # Initialize client
    client = SwarmUIClient(endpoint_id, api_key)
    
    # Wake up worker (keeps alive for 1 hour)
    public_url = client.wakeup(duration=3600)
    
    # Get session
    session_id = client.get_session(public_url)
    print(f"Session: {session_id[:16]}...")
    
    # List models
    models = client.list_models(public_url, session_id)
    print(f"Found {len(models.get('files', []))} models")
    
    # Generate images
    prompts = [
        "a beautiful mountain landscape",
        "a serene ocean sunset",
        "a peaceful forest path"
    ]
    
    for i, prompt in enumerate(prompts, 1):
        print(f"\n[{i}/{len(prompts)}] Generating: {prompt}")
        images = client.generate_image(
            public_url,
            session_id,
            prompt,
            width=512,
            height=512,
            steps=20
        )
        print(f"         Generated: {images[0] if images else 'none'}")
    
    # Shutdown when done
    print("\nShutting down...")
    client.shutdown()
    
    print("\n✓ Complete!")


if __name__ == "__main__":
    example_usage()
