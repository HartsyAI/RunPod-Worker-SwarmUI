# Running this image as a GPU Pod

This image runs as both a RunPod **serverless worker** and a plain **GPU pod**, against the same SwarmUI installation on the same network volume. One SwarmUI, one model library, two ways to rent a GPU.

## How the mode is chosen

`/entrypoint.sh` picks the mode at container start:

| Mode | What runs | When it is chosen |
|---|---|---|
| `serverless` | SwarmUI in the background, the RunPod job handler in the foreground | `RUNPOD_ENDPOINT_ID` is set, which RunPod does only for serverless workers |
| `pod` | SwarmUI in the foreground, no job handler | Anything else |

Set `SWARM_MODE` to `serverless` or `pod` to force it, or leave it unset (or `auto`) to detect.

### Why the mode matters

RunPod supervises the container's foreground process. In serverless that has to be the job handler, since that is what receives jobs. In a pod there are no jobs, so the handler exits immediately, and because it was the foreground process the container exits with it. Nothing is left listening on the SwarmUI port and RunPod's HTTP proxy answers **404**.

That is exactly what a serverless-only image does when you deploy it as a pod, and it looks like a networking problem rather than a process one.

## Deploying as a pod

1. Create a pod from `kalebbroo/swarmui-runpod:latest`, **in the same data center as your network volume**, since a volume only attaches to a pod beside it.
2. Attach the network volume at `/runpod-volume`.
3. Expose port **7801 as an http port**. RunPod's proxy only routes to ports declared http, and it will serve SwarmUI at `https://{podId}-7801.proxy.runpod.net`.
4. Environment: the defaults are correct. Set `VOLUME_PATH` only if your volume is mounted elsewhere.

The SwarmUI-CloudBackends extension can do all of this for you: enable `AutoCreate` on a RunPod Pods backend, point it at this image and your network volume, and it creates, starts, stops and reuses the pod on its own.

> RunPod's proxy applies **no authentication of its own**. Anyone who knows the pod ID and port can reach that SwarmUI. Do not put anything sensitive on a pod you would not expose publicly.

## Sharing one install between instances

The volume holds the SwarmUI install, the Python environments and your models, and sharing those is the point of this setup. They are read-mostly and safe to share.

`Data/` is the exception. SwarmUI keeps users, model metadata, settings and backend configuration there, and the user and metadata stores are LiteDB files. **LiteDB expects a single process**, so two SwarmUI instances writing one `Data/` over a network volume can corrupt it.

| Situation | What to do |
|---|---|
| One instance at a time (a pod, or serverless with max workers 1) | Nothing. Share `Data/`, which keeps your configured backends and settings. |
| A pod and serverless workers running together, or serverless scaled past one worker | Set `SWARM_DATA_DIR` per instance, for example `/runpod-volume/instances/$RUNPOD_POD_ID/Data`. |

`SWARM_DATA_DIR` is seeded from the shared `Data/` the first time it is used, so the instance starts with your existing backends rather than as an empty SwarmUI with no backend configured at all. Models are not in `Data/`, so they stay shared either way.

If you have serverless max workers above 1 today and have never set `SWARM_DATA_DIR`, those workers are already sharing one `Data/`. That is worth fixing before it bites.
