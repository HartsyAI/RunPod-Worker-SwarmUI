# SwarmUI Worker for RunPod

Run [SwarmUI](https://github.com/mcmonkeyprojects/SwarmUI) generations on RunPod GPUs, on demand. This image is the RunPod worker used by the [Cloud Backends](https://github.com/HartsyAI/SwarmUI-CloudBackends) SwarmUI extension. The extension starts workers when you generate, sends generations straight to them, and lets them shut themselves down when idle. Under load it scales out to as many workers as you allow.

It is built on [SwarmUI-Worker-Base](https://github.com/HartsyAI/SwarmUI-Worker-Base), which provides SwarmUI, the generation backend, an authenticated gateway, and idle release. This repo adds RunPod's SDK and job handler.

## Images

`hartsy/swarmui-worker-runpod:<version>-<backend>` on Docker Hub:

| Backend | Tag example | Notes |
|---|---|---|
| ComfyUI | `2.0.0-comfyui` | Full ComfyUI backend. The widest model support. |
| HartsyInference | `2.0.0-hartsyinference` | Hartsy's pure C# backend. A smaller image and a faster cold start. |

Pin a release version in production. `edge-<backend>` tracks `main`.

## How it works

- **Serverless:** each worker is held by one **lease** job. The lease streams the worker's address and a fresh access token, then keeps running while SwarmUI is in use. Once no generation has run for the idle window, the lease ends and RunPod scales the worker down. When every worker is busy, another queued lease makes RunPod start a new worker, up to the endpoint's Max Workers.
- **Pods:** the worker runs until you stop the pod, behind the same gateway with a fixed token.
- **Security:** SwarmUI never listens on a public port. RunPod's proxy URL is public, so the gateway refuses any request without the current token. Serverless tokens are per lease and stop working the moment the lease ends.

## Serverless setup

1. **Network volume.** Create one in the data center you want, and put your models in `Models/` at its root: `Models/Stable-Diffusion`, `Models/Lora`, `Models/VAE`, and so on (SwarmUI's standard layout). Volumes from version 1 of this image (`SwarmUI/Models/`) are detected and used as they are.
2. **Endpoint.** Create a **Queue**-type serverless endpoint from `hartsy/swarmui-worker-runpod:<version>-<backend>`:

   | Setting | Value |
   |---|---|
   | Container disk | 30 GB (ComfyUI) or 15 GB (HartsyInference) |
   | Network volume | the volume from step 1 |
   | GPU | 16 GB VRAM or more (24 GB for large models) |
   | CUDA version | 12.8 or newer |
   | Active workers | 0 (scales to zero) |
   | Max workers | the most workers you want running at once |
   | Execution timeout | above the lease limit, e.g. 4200 seconds for the default 3600-second lease |
   | Idle timeout | 5 seconds (the default; the lease already covers idle time) |
   | FlashBoot | on |
   | Environment | optional, see [Configuration](#configuration) |

3. **Cloud Backends.** In SwarmUI, add a **Cloud Backends** backend, enable RunPod Serverless, and enter the endpoint ID. Put your RunPod API key in User Settings. Set **Max Workers** on the card to how far it may scale (at most the endpoint's Max workers).

Then generate as usual. The first generation starts a worker. The next ones go straight to it while it's up.

## Pod setup

The Cloud Backends extension creates, starts, and stops pods for you (RunPod GPU Pods section of the card). It sets the pod's token and volume automatically.

To run one by hand: create a pod from the same image, attach your network volume, expose port **7801 as HTTP**, and set `SWARMUI_WORKER_TOKEN` to a random value of at least 32 characters. Connect SwarmUI to it with a **Swarm API** backend at `https://<pod-id>-7801.proxy.runpod.net`, with `AuthorizationHeader` set to `Bearer <token>`.

## Configuration

These are environment variables on the endpoint or pod. The defaults suit most setups.

| Variable | Default | Meaning |
|---|---|---|
| `SWARMUI_IDLE_SECONDS` | `120` | How long a worker may sit with no generation before it shuts down. Lower saves money; higher avoids cold starts between bursts. |
| `SWARMUI_STARTUP_GRACE_SECONDS` | `600` | How long a new worker waits for its first generation. |
| `SWARMUI_MAX_LEASE_SECONDS` | `3600` | Longest a single lease lasts. Keep the endpoint's execution timeout above it. |
| `SWARMUI_MODEL_ROOT` | detected on the volume | Where the models are. |
| `SWARMUI_WORKER_TOKEN` | *(none)* | **Pods only.** Serverless workers refuse to start with it set, because each lease must get its own token. |
| `SWARM_MODE` | `auto` | `serverless` or `pod`. Detected from `RUNPOD_ENDPOINT_ID`. |

The base image's full list is in the [SwarmUI-Worker-Base README](https://github.com/HartsyAI/SwarmUI-Worker-Base#configuration).

## Job API

The Cloud Backends extension is the intended client. The protocol, for reference:

- `{"input": {"action": "lease"}}` is an async job. Read `GET /v2/<endpoint>/stream/<job_id>`. The first output is `{"success": true, "public_url": ..., "token": ..., "worker_id": ..., "protocol": 2, "idle_seconds": ..., "max_lease_seconds": ...}`. The job completes with `{"released": true, "reason": ...}` when the worker goes idle. Cancelling the job ends the lease at once.
- `{"input": {"action": "health"}}` returns the worker version and protocol.

Send requests to `public_url` with `Authorization: Bearer <token>`. HTTP responses through RunPod's proxy are limited to 100 seconds, so run generations over SwarmUI's WebSocket API (SwarmUI's own Swarm API backend does this).

## Upgrading from version 1

Version 1 installed SwarmUI and ComfyUI onto the network volume, and ran SwarmUI unauthenticated on the proxy URL. Version 2 bakes both into the image and reads only models from the volume.

- Your models keep working where they are.
- ComfyUI custom nodes installed on the volume aren't loaded. Everything the image needs is built in and pinned.
- Version 2 needs a Cloud Backends version with lease support. Older versions of the extension can't use it.

## Development

```bash
PYTHONPATH=../SwarmUI-Worker-Base/src python -m pytest tests
# Until base images are published, build the base locally first (CI does the same):
git clone https://github.com/HartsyAI/SwarmUI-Worker-Base ../SwarmUI-Worker-Base
docker build --build-arg BACKEND=comfyui -t hartsy/swarmui-worker-base:source-comfyui ../SwarmUI-Worker-Base
docker build --build-arg BACKEND=comfyui --build-arg BASE_VERSION=source -t swarmui-worker-runpod:local .
bash tests/smoke/smoke.sh swarmui-worker-runpod:local
```

## License

MIT, see [LICENSE](LICENSE).
