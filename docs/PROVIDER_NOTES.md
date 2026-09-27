# Provider research (Phase 0), 2026-09-27

Sources were read directly: the official docs, plus the SDK source from pip wheels `runpod==1.12.0` and `vastai==1.8.2`.

## RunPod

### Queue-based endpoint + lease job (CHOSEN)
- **Streaming is supported for generator handlers.** `runpod/serverless/modules/rp_job.py:196-216`: `is_generator(handler)` streams every yield live through `stream_result`. `return_aggregate_stream: True` also returns the list from `/status`. Docs: https://docs.runpod.io/serverless/workers/handler-functions
- **A running job occupies its worker.** More queued jobs make the scaler add workers.
  - Queue delay scaler: adds workers after a request waits longer than a threshold (default 4s).
  - Request count scaler: `ceil((inQueue + inProgress) / scalerValue)`.
  - Docs: https://docs.runpod.io/serverless/endpoints/endpoint-configurations
- **Endpoint settings:**
  - Max workers: default 3.
  - Idle timeout: default 5s.
  - Execution timeout: default 600s, range 5s to 7 days, and it caps a lease.
  - Job TTL: default 24h.
  - FlashBoot: on by default.
- **The settings can be read by API:** `GET https://rest.runpod.io/v1/endpoints/{id}` returns `workersMax`, `workersMin`, `idleTimeout`, `executionTimeoutMs`, `scalerType`, `scalerValue`, `template.imageName`, `networkVolumeId`. This makes config validation possible.
- **The proxy is public, with no auth.** `https://{podId}-{port}.proxy.runpod.net`. The RunPod docs say to "implement proper authentication in your application". It also has a 100s Cloudflare limit per HTTP response (a 524 after that), so generation must use SwarmUI's WebSocket routes, which SwarmSwarmBackend already does. Docs: https://docs.runpod.io/pods/configuration/expose-ports
- **Pods API:** `POST /pods` has `env` and `name`, but **no label field**. Orphan detection keys off a name prefix plus an env marker.

### Load-balancing endpoint (REJECTED)
- It routes requests directly to workers at `https://<EP>.api.runpod.ai/<path>`, supports WebSockets, and RunPod's API-key bearer auth sits in front of it.
- It's rejected for SwarmUI because:
  1. There's no documented session affinity. SwarmUI keeps its session, loaded model and backend list on one worker, so consecutive requests must reach the same worker.
  2. Each request has a 5.5 min processing limit.
  3. It's unclear whether open WebSockets count as load for scaling. RunPod's own `worker-lb-websocket` ships a `test_scaling.py` to investigate exactly that.
  4. Swarm's backend polling would keep workers busy, so they'd never scale to zero.
- Sources: https://docs.runpod.io/serverless/load-balancing/overview and https://github.com/runpod-workers/worker-lb-websocket

### Official layout to follow
`runpod-workers/worker-template`: `handler.py` (with `handler(event)`, heavy init outside the handler), `requirements.txt` (uv), a Dockerfile `FROM runpod/base`, `test_input.json`, GitHub-integration deploy, and Hub files.

## Vast.ai

### PyWorker + native Sessions (CHOSEN: a provider-native lease)
The `vastai` SDK has first-class sessions, in both the server (`serverless/server/lib/backend.py:297-352`) and the client (`serverless/client/client.py:581`, `start_endpoint_session`).

- **Create:** `/route/` then the worker's `/session/create` with `{lifetime, on_close_route, on_close_payload}` and a `cost`.
- **Load:** the session is recorded as `is_session=True`, and its `cost` counts toward the worker's `cur_load` (`data_types.py:323`) while it's open. The autoscaler sees that worker as busy.
- **Scaling:** `max_sessions` per worker (`worker.py:95`, default 10). Past it, the worker returns 429 and `/route/` has to pick another worker. We set it to 1, so one Swarm slot equals one worker.
- **TTL:** every request made with the `session_id` extends the expiration by `lifetime` (`backend.py:460`). A GC loop closes expired sessions every 5s (`backend.py:995`), and `on_close_route` fires. If SwarmUI crashes, the renewals stop, the session expires, the load drops, and the engine scales down. Nothing is orphaned.
- **Explicit end:** `/session/end`. Health: `/session/health`.
- **Scale-to-zero needs these endpoint settings:** `min_load = 0` and an `inactivity_timeout` above 0. Today our README says Min Load 1, which **never scales to zero**. Other settings: `max_workers` (default 16), `min_workers` (cold/loaded, default 5), `target_util` (0.9), `cold_mult` (3), `max_queue_time`, `target_queue_time`. Docs: https://docs.vast.ai/documentation/serverless/serverless-parameters
- **The TTL adds up.** Each request is `expiration += lifetime` (`backend.py:460`), not `now + lifetime`, so touching on a timer would push the expiry out without bound. Swarm must renew **conditionally**: read `expiration` from the create response or `/session/get` (`backend.py:155`, which does **not** extend; verified), and touch only when `expiration - now < lifetime`. That bounds the overrun to one lifetime.
- **Scale-out is not confirmed yet.** Whether the engine *recruits* a worker depends on `cur_load` against `max_throughput`. `max_throughput` comes from the lifecycle-path benchmark (`backend.py:677-693`, measured as workload/sec, `:795-859`). Our benchmark is a cheap `GetNewSession`, so its perf is huge and a cost-100 session would look like near-0% utilization. Also, `wait_time` excludes `is_session` requests (`data_types.py:313`), so `max_queue_time` never rejects on sessions alone.
  - Fix: calibrate so one session equals full capacity. Either set the benchmark workload, or set the session `cost` to match the measured perf.
  - "Worker at `max_sessions` returns 429, so `/route/` picks another worker" is an inference. The Python client re-routes on `_do_request(retry=True)`, and our C# client must re-route too (a new `request_idx`, a fresh `/route/`).
  - **The first paid Vast test checks this:** two sessions must land on two distinct workers before the slot logic depends on it.
- **Worker token:** the session-create response is fixed by the SDK (`{session_id, expiration}`). So the token and `public_url` come from our own handler route, called with the `session_id`. That call also renews the TTL, so it doubles as the renewal ("touch") call.

## Resulting design, per provider

| | RunPod Serverless | Vast Serverless |
|---|---|---|
| Hold a worker | A lease job from a generator handler. The first yield is `{public_url, token, worker_id}`. | A native session (cost 100, `max_sessions = 1`), then our handler returns `{public_url, token}` |
| Who decides it's idle | The **worker**: the supervisor polls the local `/API/GetGlobalStatus`, with a startup grace and a hard cap | **Swarm**: it renews only when `expiration - now < lifetime` while it's in use, then stops, and the TTL (`lifetime` = IdleSeconds) expires within at most 2× IdleSeconds |
| Scale-out | Another queued lease → the RunPod scaler adds a worker | Another session → the full worker returns 429 → `/route/` picks or recruits another |
| Explicit stop | Cancel the lease job (this kills that worker) | `/session/end` |
| Swarm crash | The worker idles out by itself | The TTL expires |
| Auth | Our token gateway in front of SwarmUI (the proxy is public) | Our token gateway (the public IP and port are open) |
| Config check | `GET /v1/endpoints/{id}` | Endpoint and workergroup params via the Vast API |

## Notes that change the plan or docs
- Vast setup docs must say `min_workers = 0`, `min_load = 0`, and `inactivity_timeout > 0`. The defaults (5 cold workers, min load 1) either keep workers or keep billing storage.
- Orphan detection: RunPod pods have no label field, so it uses a `name` prefix plus an `env` marker. The same applies to Vast instances until their API is checked for labels.
- RunPod `/stream/{jobId}` returns the chunks accumulated so far, so read the first element rather than assuming one chunk per poll.
