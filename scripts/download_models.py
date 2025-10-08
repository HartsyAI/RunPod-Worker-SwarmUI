#!/usr/bin/env python3
"""Download SwarmUI-compatible model checkpoints into RunPod network storage via S3.

This helper pulls a focused set of five high-priority checkpoints (Flux family
and SDXL tiers) from Hugging Face and streams them directly into your RunPod
network storage bucket using the S3 API credentials. Destinations follow the
``Models/<category>/...`` conventions from the SwarmUI documentation, including
sub-folders for vendor/model families.

Usage examples::

    python scripts/download_models.py --list
    python scripts/download_models.py --only flux-dev flux-schnell --skip-existing
    python scripts/download_models.py --only flux-dev-gguf sd3.5-medium-gguf
    python scripts/download_models.py --token <hf_token>

Environment variables (used as defaults for CLI options)::

    RUNPOD_ENDPOINT_URL
    RUNPOD_ACCESS_KEY
    RUNPOD_SECRET_ACCESS_KEY
    RUNPOD_TRAINING_STORAGE_REGION
    RUNPOD_TRAINING_STORAGE_VOLUME_ID
    HUGGINGFACE_API_TOKEN
"""

from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError
import requests
from requests.exceptions import HTTPError


@dataclass(frozen=True)
class ModelSpec:
    key: str
    name: str
    url: str
    destination: Path
    requires_token: bool = False
    notes: Optional[str] = None


# Curated list (exactly five models aligned with SwarmUI folder rules).
MODEL_SPECS: Dict[str, ModelSpec] = {
    "flux-dev": ModelSpec(
        key="flux-dev",
        name="Flux.1 Dev (fp8)",
        url="https://huggingface.co/Comfy-Org/flux1-dev/resolve/main/flux1-dev-fp8.safetensors?download=true",
        destination=Path("Models/Stable-Diffusion/BFL/Flux/flux1-dev-fp8.safetensors"),
        requires_token=True,
        notes="Standard fp8 checkpoint; license acceptance required on Hugging Face",
    ),
    "flux-schnell": ModelSpec(
        key="flux-schnell",
        name="Flux.1 Schnell (fp8)",
        url="https://huggingface.co/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors?download=true",
        destination=Path("Models/Stable-Diffusion/BFL/Flux/flux1-schnell-fp8.safetensors"),
        requires_token=True,
        notes="Fast 4-step Flux variant; license acceptance required",
    ),
    "sdxl-base": ModelSpec(
        key="sdxl-base",
        name="SDXL Base 1.0",
        url="https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        destination=Path("Models/Stable-Diffusion/SDXL/SDXL-Base/sd_xl_base_1.0.safetensors"),
    ),
    "flux-dev-gguf": ModelSpec(
        key="flux-dev-gguf",
        name="Flux.1 Dev GGUF Q4_K_S",
        url="https://huggingface.co/Comfy-Org/flux1-dev-gguf/resolve/main/flux1-dev-Q4_K_S.gguf?download=true",
        destination=Path("Models/diffusion_models/BFL/Flux/Flux-Dev-Q4_K_S/flux1-dev-Q4_K_S.gguf"),
        requires_token=True,
        notes="Quantized GGUF checkpoint for low-VRAM inference",
    ),
    "sd3.5-medium-gguf": ModelSpec(
        key="sd3.5-medium-gguf",
        name="SD3.5 Medium GGUF Q4_K_S",
        url="https://huggingface.co/Comfy-Org/sd3.5-medium-gguf/resolve/main/sd3.5_medium-Q4_K_S.gguf?download=true",
        destination=Path("Models/diffusion_models/StabilityAI/SD3.5/SD3.5-Medium-Q4_K_S/sd3.5_medium-Q4_K_S.gguf"),
        requires_token=True,
        notes="Requires acceptance of Stability AI Community License on Hugging Face",
    ),
}


def iter_selected_specs(selected_keys: Optional[Iterable[str]]) -> List[ModelSpec]:
    if not selected_keys:
        return list(MODEL_SPECS.values())

    missing = [key for key in selected_keys if key not in MODEL_SPECS]
    if missing:
        raise KeyError(
            "Unknown model keys: " + ", ".join(missing) +
            "\nUse --list to see all available keys."
        )
    return [MODEL_SPECS[key] for key in selected_keys]


def build_headers(token: Optional[str]) -> Dict[str, str]:
    headers: Dict[str, str] = {"User-Agent": "runpod-model-downloader/2.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


class ProgressPrinter:
    def __init__(self, total_bytes: Optional[int], label: str) -> None:
        self.total_bytes = total_bytes or 0
        self.label = label
        self.transferred = 0

    def __call__(self, bytes_amount: int) -> None:
        self.transferred += bytes_amount
        if self.total_bytes:
            percent = self.transferred / self.total_bytes * 100
            total_mb = self.total_bytes / (1 << 20)
            transferred_mb = self.transferred / (1 << 20)
            print(f"    {percent:5.1f}% ({transferred_mb:7.1f} MiB / {total_mb:7.1f} MiB)", end="\r")
        else:
            transferred_gb = self.transferred / (1 << 30)
            print(f"    transferred {transferred_gb:7.2f} GiB", end="\r")


def create_s3_client(endpoint_url: str, region: str, access_key: str, secret_key: str):
    session = boto3.session.Session()
    return session.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def log_existing_objects(s3_client, bucket: str, prefix: str, limit: int = 100) -> None:
    print("Existing objects in network storage (first 100):")
    kwargs = {"Bucket": bucket}
    if prefix:
        kwargs["Prefix"] = prefix.rstrip("/") + "/"

    found = 0
    paginator = s3_client.get_paginator("list_objects_v2")
    try:
        for page in paginator.paginate(**kwargs):
            for obj in page.get("Contents", []):
                size_mb = obj["Size"] / (1 << 20)
                print(f"  - {obj['Key']} ({size_mb:,.2f} MiB)")
                found += 1
                if found >= limit:
                    return
        if found == 0:
            print("  (no files found)")
    except ClientError as exc:
        print(f"  ! Unable to list objects: {exc}")


def upload_spec(
    spec: ModelSpec,
    s3_client,
    bucket: str,
    prefix: str,
    headers: Dict[str, str],
    skip_existing: bool,
) -> None:
    key_suffix = spec.destination.as_posix()
    key = f"{prefix.rstrip('/')}/{key_suffix}" if prefix else key_suffix

    if skip_existing:
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
            print(f"[skip] {spec.key}: s3://{bucket}/{key} already exists")
            return
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code not in {"404", "NoSuchKey", "NotFound"}:
                raise

    print(f"[downloading] {spec.key}: {spec.name}")
    print(f"  source: {spec.url}")
    print(f"  target: s3://{bucket}/{key}")
    if spec.notes:
        print(f"  note: {spec.notes}")

    with requests.get(spec.url, stream=True, headers=headers, timeout=600) as response:
        try:
            response.raise_for_status()
        except HTTPError as exc:
            if spec.requires_token and response.status_code == 401:
                raise RuntimeError(
                    f"Unauthorized when fetching '{spec.key}'. Ensure your HF token"
                    " has access and is passed via --token or HF_TOKEN."
                ) from exc
            raise

        total_bytes = int(response.headers.get("Content-Length") or 0) or None
        progress = ProgressPrinter(total_bytes, spec.key)
        response.raw.decode_content = True

        transfer_config = TransferConfig(
            multipart_threshold=64 * 1024 * 1024,
            multipart_chunksize=32 * 1024 * 1024,
            max_concurrency=4,
        )

        s3_client.upload_fileobj(
            Fileobj=response.raw,
            Bucket=bucket,
            Key=key,
            Config=transfer_config,
            Callback=progress,
        )

    print()
    print(f"[done] {spec.key} → s3://{bucket}/{key}\n")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download curated SwarmUI models into RunPod network storage via S3"
    )
    parser.add_argument(
        "--only",
        nargs="*",
        help="Subset of model keys to download (default: all listed)."
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip uploads when the object already exists in S3.",
    )
    parser.add_argument(
        "--token",
        help="Hugging Face access token (overrides HUGGINGFACE_API_TOKEN environment variable).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available model keys and exit.",
    )
    parser.add_argument(
        "--bucket",
        default=os.environ.get("RUNPOD_TRAINING_STORAGE_VOLUME_ID"),
        help="RunPod network storage volume ID (used as the S3 bucket).",
    )
    parser.add_argument(
        "--prefix",
        default=os.environ.get("RUNPOD_S3_PREFIX", ""),
        help="Optional prefix inside the bucket for storing models.",
    )
    parser.add_argument(
        "--endpoint-url",
        default=os.environ.get("RUNPOD_ENDPOINT_URL"),
        help="RunPod S3 endpoint URL.",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("RUNPOD_TRAINING_STORAGE_REGION", "us-il-1"),
        help="RunPod S3 region.",
    )
    parser.add_argument(
        "--access-key",
        default=os.environ.get("RUNPOD_ACCESS_KEY"),
        help="RunPod S3 access key.",
    )
    parser.add_argument(
        "--secret-key",
        default=os.environ.get("RUNPOD_SECRET_ACCESS_KEY"),
        help="RunPod S3 secret access key.",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)

    if args.list:
        print("Available model keys:")
        for spec in MODEL_SPECS.values():
            token_flag = " (requires HF token)" if spec.requires_token else ""
            print(f"- {spec.key}{token_flag}: {spec.destination} → {spec.url}")
        return 0

    required = {
        "bucket": args.bucket,
        "endpoint_url": args.endpoint_url,
        "access_key": args.access_key,
        "secret_key": args.secret_key,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        print(
            "Missing required configuration: " + ", ".join(missing) +
            "\nProvide via CLI flags or environment variables.",
            file=sys.stderr,
        )
        return 2

    token = args.token or os.environ.get("HUGGINGFACE_API_TOKEN")
    headers = build_headers(token)

    try:
        specs = iter_selected_specs(args.only)
    except KeyError as err:
        print(err, file=sys.stderr)
        return 2

    if not specs:
        print("No model specs selected.")
        return 0

    s3_client = create_s3_client(
        endpoint_url=args.endpoint_url,
        region=args.region,
        access_key=args.access_key,
        secret_key=args.secret_key,
    )

    try:
        s3_client.head_bucket(Bucket=args.bucket)
    except ClientError as exc:
        print(f"Failed to access bucket '{args.bucket}': {exc}", file=sys.stderr)
        return 2

    prefix = args.prefix.strip("/")
    print(f"Using bucket: {args.bucket}")
    if prefix:
        print(f"Using prefix: {prefix}/")

    log_existing_objects(s3_client, args.bucket, prefix)

    for spec in specs:
        try:
            upload_spec(
                spec,
                s3_client,
                bucket=args.bucket,
                prefix=prefix,
                headers=headers,
                skip_existing=args.skip_existing,
            )
        except Exception as exc:  # noqa: BLE001 - continue with next model
            print(f"[error] {spec.key}: {exc}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
