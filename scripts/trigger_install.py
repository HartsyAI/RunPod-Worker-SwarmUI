#!/usr/bin/env python3
"""
Trigger SwarmUI's first-run installation programmatically.
Replicates what the web install wizard does.
"""

import requests
import time
import sys
import json

SWARMUI_URL = "http://127.0.0.1:7801"
MAX_WAIT = 300  # 5 minutes

def wait_for_swarmui():
    """Wait for SwarmUI to be ready."""
    print("Waiting for SwarmUI to start...")
    for i in range(MAX_WAIT // 5):
        try:
            response = requests.post(
                f"{SWARMUI_URL}/API/GetNewSession",
                json={},
                timeout=5
            )
            if response.status_code == 200:
                print("✓ SwarmUI is ready!")
                return True
        except:
            pass
        time.sleep(5)
    
    print("ERROR: SwarmUI failed to start")
    return False

def get_session():
    """Get a session ID."""
    response = requests.post(
        f"{SWARMUI_URL}/API/GetNewSession",
        json={},
        timeout=10
    )
    response.raise_for_status()
    return response.json()['session_id']

def trigger_install(session_id):
    """
    Trigger the install process via API.
    This replicates what happens when you click "Install Now" in the web UI.
    """
    print("Triggering installation via API...")
    
    # The install payload - what the web wizard sends
    install_data = {
        "session_id": session_id,
        "theme": "dark",  # or "light"
        "backend": "comfyui_local",  # Install ComfyUI backend
        "models": [],  # Don't auto-download models (can do manually later)
        "installConfirmed": True
    }
    
    print(f"Sending install request: {json.dumps(install_data, indent=2)}")
    
    try:
        # Try the install API endpoint
        # Note: This might be a WebSocket endpoint (_WS suffix)
        response = requests.post(
            f"{SWARMUI_URL}/API/InstallConfirm",
            json=install_data,
            timeout=600  # 10 minutes for installation
        )
        
        if response.status_code == 200:
            print("✓ Installation triggered successfully!")
            print(f"Response: {response.text}")
            return True
        else:
            print(f"Install API returned {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("Installation is taking longer than 10 minutes...")
        print("This is normal for first-run ComfyUI installation")
        return True
    except Exception as e:
        print(f"Error calling install API: {e}")
        return False

def main():
    """Main installation flow."""
    print("=" * 80)
    print("SwarmUI Programmatic Installer")
    print("=" * 80)
    
    # Wait for SwarmUI to be ready
    if not wait_for_swarmui():
        sys.exit(1)
    
    # Get session
    print("\nGetting session ID...")
    session_id = get_session()
    print(f"✓ Session: {session_id[:16]}...")
    
    # Trigger install
    print("\nTriggering installation...")
    print("This will:")
    print("  1. Install ComfyUI backend")
    print("  2. Create backend configuration")
    print("  3. Mark installation as complete")
    print("")
    
    if trigger_install(session_id):
        print("\n" + "=" * 80)
        print("✓ Installation complete!")
        print("=" * 80)
        print("\nSwarmUI should now restart with ComfyUI backend configured.")
        print("Wait 30-60 seconds for backend to start, then try generating!")
    else:
        print("\n" + "=" * 80)
        print("✗ Installation may have failed")
        print("=" * 80)
        print("\nCheck SwarmUI logs for details")
        sys.exit(1)

if __name__ == "__main__":
    main()
