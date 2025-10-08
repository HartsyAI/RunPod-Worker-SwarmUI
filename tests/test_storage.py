"""Utility to list models stored in the RunPod S3 volume."""

import os
from pathlib import Path
from typing import Dict, Iterable, List

import boto3
from botocore.config import Config
from dotenv import load_dotenv


load_dotenv()

ENV_ENDPOINT = "RUNPOD_ENDPOINT_URL"
ENV_ACCESS_KEY = "RUNPOD_ACCESS_KEY"
ENV_SECRET_KEY = "RUNPOD_SECRET_ACCESS_KEY"
ENV_REGION = "RUNPOD_TRAINING_STORAGE_REGION"
ENV_BUCKET = "RUNPOD_TRAINING_STORAGE_VOLUME_ID"

MODEL_PREFIX = "Models/"
MODEL_SUFFIXES = {".safetensors", ".ckpt", ".pt", ".bin"}


def get_s3_client():
    endpoint_url = os.getenv(ENV_ENDPOINT)
    access_key = os.getenv(ENV_ACCESS_KEY)
    secret_key = os.getenv(ENV_SECRET_KEY)
    region = os.getenv(ENV_REGION)

    if not all([endpoint_url, access_key, secret_key, region]):
        missing = [
            ENV_ENDPOINT,
            ENV_ACCESS_KEY,
            ENV_SECRET_KEY,
            ENV_REGION,
        ]
        raise EnvironmentError(f"Missing S3 configuration. Ensure {missing} are set.")

    return boto3.client(
        "s3",
        endpoint_url=endpoint_url.rstrip("/"),
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region.lower(),
        config=Config(signature_version="s3v4"),
    )


def format_model_path(key: str) -> str:
    path = Path(key)
    parts = path.parts
    if not parts or parts[0] != MODEL_PREFIX.rstrip("/"):
        return key
    stem = path.stem
    return "/".join((*parts[1:-1], stem))


def list_models() -> List[Dict[str, object]]:
    bucket = os.getenv(ENV_BUCKET)
    if not bucket:
        raise EnvironmentError(f"Missing bucket name. Set {ENV_BUCKET}.")

    client = get_s3_client()
    paginator = client.get_paginator("list_objects_v2")

    results: List[Dict[str, object]] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=MODEL_PREFIX):
        for entry in page.get("Contents", []):
            key = entry["Key"]
            if not any(key.endswith(suffix) for suffix in MODEL_SUFFIXES):
                continue
            results.append(
                {
                    "path": format_model_path(key),
                    "full_path": key,
                    "size_mb": entry["Size"] / (1024 * 1024),
                    "last_modified": entry["LastModified"].isoformat(),
                }
            )

    return results


def print_models(models: Iterable[Dict[str, object]]) -> None:
    models = list(models)
    if not models:
        print("No models found.")
        return

    print("Models found:\n")
    for entry in models:
        print(f"- {entry['path']}")
        print(f"  full_path: {entry['full_path']}")
        print(f"  size_mb: {entry['size_mb']:.2f}")
        print(f"  last_modified: {entry['last_modified']}")
        print()


if __name__ == "__main__":
    try:
        print_models(list_models())
    except Exception as error:  # pragma: no cover - CLI convenience
        print(f"Error: {error}")