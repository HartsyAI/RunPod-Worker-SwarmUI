#!/usr/bin/env python3
"""Quick smoke test for the RunPod SwarmUI endpoint."""

import argparse
import base64
import json
import os
from pathlib import Path
from typing import Any, Dict

import requests
from dotenv import load_dotenv


load_dotenv()

ENV_ENDPOINT = "RUNPOD_ENDPOINT_ID"
ENV_API_KEY = "RUNPOD_API_TOKEN"


def call_runsync(endpoint: str, api_key: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://api.runpod.ai/v2/{endpoint}/runsync"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, json={"input": payload}, headers=headers, timeout=600)
    response.raise_for_status()
    return response.json()


def save_base64_images(images: Any, output_dir: Path) -> None:
    output_dir.mkdir(exist_ok=True)
    for idx, item in enumerate(images):
        if not isinstance(item, dict):
            continue
        if item.get("type") != "base64":
            continue
        data = item.get("data")
        if not data:
            continue
        filename = item.get("filename", f"image_{idx}.png")
        try:
            with open(output_dir / filename, "wb") as handle:
                handle.write(base64.b64decode(data))
        except Exception as err:
            print(f"Failed to write {filename}: {err}")


def build_payload(prompt: str, model: str, width: int, height: int) -> Dict[str, Any]:
    return {
        "action": "generate",
        "prompt": prompt,
        "negative_prompt": "",
        "model": model,
        "width": width,
        "height": height,
        "steps": 20,
        "cfg_scale": 7.0,
        "images": 1,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync image generation smoke test")
    parser.add_argument("--endpoint", default=os.getenv(ENV_ENDPOINT), help="RunPod endpoint ID")
    parser.add_argument("--api-key", default=os.getenv(ENV_API_KEY), help="RunPod API token")
    parser.add_argument("--prompt", default="A vivid nebula in outer space", help="Prompt text")
    parser.add_argument("--model", default="OfficialStableDiffusion/sd_xl_base_1.0", help="Model name")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1024)
    parser.add_argument("--output", default="output", help="Directory for images")

    args = parser.parse_args()

    if not args.endpoint:
        raise ValueError(f"Missing endpoint ID. Set {ENV_ENDPOINT} or pass --endpoint.")
    if not args.api_key:
        raise ValueError(f"Missing API key. Set {ENV_API_KEY} or pass --api-key.")

    payload = build_payload(args.prompt, args.model, args.width, args.height)
    print("Submitting generation request...")
    result = call_runsync(args.endpoint, args.api_key, payload)

    print("Response:")
    print(json.dumps(result, indent=2, sort_keys=True))

    output = result.get("output") or {}
    images = output.get("images")
    if images:
        save_base64_images(images, Path(args.output))
        print(f"Saved {len(images)} image(s) to {args.output}")


if __name__ == "__main__":
    main()
