"""Minimal CLI helpers for exercising RunPod model management actions."""

import argparse
import json
import os
from typing import Any, Dict

import requests
from dotenv import load_dotenv


load_dotenv()

ENV_ENDPOINT = "RUNPOD_ENDPOINT_ID"
ENV_API_KEY = "RUNPOD_API_TOKEN"


def call_runpod(endpoint: str, api_key: str, action: str, **payload: Any) -> Dict[str, Any]:
    if not endpoint:
        raise ValueError(f"Missing endpoint ID. Set {ENV_ENDPOINT} or pass --endpoint.")
    if not api_key:
        raise ValueError(f"Missing API key. Set {ENV_API_KEY} or pass --api-key.")

    url = f"https://api.runpod.ai/v2/{endpoint}/runsync"
    body = {"input": {"action": action, **payload}}
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, json=body, headers=headers, timeout=90)
    response.raise_for_status()
    return response.json()


def pretty_print(title: str, data: Dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description="RunPod model management helper")
    parser.add_argument("--endpoint", default=os.getenv(ENV_ENDPOINT), help="RunPod endpoint ID")
    parser.add_argument("--api-key", default=os.getenv(ENV_API_KEY), help="RunPod API token")

    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List available models")
    list_parser.add_argument("--path", default="", help="Path prefix inside storage")
    list_parser.add_argument("--depth", type=int, default=2, help="Traversal depth")
    list_parser.add_argument("--subtype", default="Stable-Diffusion")
    list_parser.add_argument("--allow-remote", action="store_true", default=True)
    list_parser.add_argument("--no-remote", dest="allow_remote", action="store_false")
    list_parser.add_argument("--sort-by")
    list_parser.add_argument("--sort-reverse", action="store_true")
    list_parser.add_argument("--data-images", action="store_true")

    describe_parser = subparsers.add_parser("describe", help="Describe a specific model")
    describe_parser.add_argument("model_name", help="Model identifier")
    describe_parser.add_argument("--subtype", default="Stable-Diffusion")

    download_parser = subparsers.add_parser("download", help="Trigger a model download")
    download_parser.add_argument("url", help="Source URL")
    download_parser.add_argument("model_name", help="Destination model name")
    download_parser.add_argument("--model-type", default="Stable-Diffusion")
    download_parser.add_argument("--metadata", help="Optional metadata JSON string")

    edit_parser = subparsers.add_parser("edit", help="Edit model metadata")
    edit_parser.add_argument("model_name")
    edit_parser.add_argument("--subtype", default="Stable-Diffusion")
    edit_parser.add_argument("--metadata", required=True, help="Metadata JSON payload")

    keep_alive_parser = subparsers.add_parser("keep-alive", help="Keep worker warm")
    keep_alive_parser.add_argument("--duration", type=int, default=300)
    keep_alive_parser.add_argument("--interval", type=int, default=30)

    args = parser.parse_args()
    metadata_payload: Dict[str, Any]

    if args.command == "list":
        result = call_runpod(
            args.endpoint,
            args.api_key,
            "list_models",
            path=args.path,
            depth=args.depth,
            subtype=args.subtype,
            allow_remote=args.allow_remote,
            sort_by=args.sort_by,
            sort_reverse=args.sort_reverse,
            data_images=args.data_images,
        )
        pretty_print("MODELS", result)
        return

    if args.command == "describe":
        result = call_runpod(
            args.endpoint,
            args.api_key,
            "describe_model",
            model_name=args.model_name,
            subtype=args.subtype,
        )
        pretty_print("MODEL DETAILS", result)
        return

    if args.command == "download":
        metadata_payload = json.loads(args.metadata) if args.metadata else None
        result = call_runpod(
            args.endpoint,
            args.api_key,
            "download_model",
            url=args.url,
            model_name=args.model_name,
            model_type=args.model_type,
            metadata=metadata_payload,
        )
        pretty_print("DOWNLOAD", result)
        return

    if args.command == "edit":
        metadata_payload = json.loads(args.metadata)
        result = call_runpod(
            args.endpoint,
            args.api_key,
            "edit_model_metadata",
            model_name=args.model_name,
            subtype=args.subtype,
            metadata=metadata_payload,
        )
        pretty_print("EDIT", result)
        return

    if args.command == "keep-alive":
        result = call_runpod(
            args.endpoint,
            args.api_key,
            "keep_alive",
            duration_seconds=args.duration,
            interval_seconds=args.interval,
        )
        pretty_print("KEEP ALIVE", result)


if __name__ == "__main__":
    main()
