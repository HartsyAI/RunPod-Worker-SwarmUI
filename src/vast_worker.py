"""Vast.ai Serverless worker for SwarmUI, built on the real `vastai` PyWorker framework.

This is NOT a standalone Flask app. Vast's routing engine (`POST run.vast.ai/route/`) only ever
returns a worker's URL once that worker has registered itself with the autoscaler, which happens
by running the actual `vastai.serverless.server.worker.Worker` from the official SDK: it verifies
the RSA-signed `auth_data` grant against Vast's own public key, tracks load/session state, and
posts heartbeats to `{REPORT_ADDR}/worker_status/` in the background. A bespoke HTTP server that
only imitates the request/response shape never becomes routable at all, since nothing tells the
autoscaler it exists - `WakeupWorkerAsync` on the SwarmUI-CloudBackends side would just poll
`/route/` forever with no worker to route to.

What this worker actually does:
    1. Registers one handler at the `/handler` route (matches VastAIProvider's `workerRoute`
       default), whose "model API call" is SwarmUI's own `POST /API/GetNewSession` - a real
       session is the cheapest possible proof SwarmUI is actually up and responding.
    2. On success, returns the shape SwarmUI-CloudBackends' `WakeupWorkerAsync` expects:
       {success, public_url, session_id, version, worker_id}. `public_url` is built from the
       same VAST_TCP_PORT_{port}/PUBLIC_IPADDR env vars Vast injects into every instance
       (serverless or not) - the client then talks to SwarmUI directly at that URL from then on,
       the same as it would for a rented instance. This worker's own /handler route is only ever
       used for that one initial wakeup call.
    3. Everything else (session management, generation, streaming) happens directly against
       `public_url` outside of Vast's routing entirely, exactly like the RunPod Serverless
       provider talks to its proxy URL - `/route/` is a one-time lookup, not a request relay.

Install: `pip install vastai` (the official SDK/CLI package; the serverless server lives inside
it). Run as the container's serverless entrypoint with WORKER_PORT, PUBLIC_IPADDR, CONTAINER_ID,
REPORT_ADDR and VAST_TCP_PORT_{WORKER_PORT} all present - Vast sets all of these automatically
for any container launched by a workergroup, no template configuration needed beyond choosing
WORKER_PORT and exposing it (`-p {WORKER_PORT}:{WORKER_PORT}` in Docker options).
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

import aiohttp
from aiohttp import ClientResponse, web

from vastai.serverless.server.lib.data_types import ApiPayload, EndpointHandler
from vastai.serverless.server.worker import HandlerConfig, Worker, WorkerConfig

log = logging.getLogger("vast_worker")

# SwarmUI is cloned/copied and launched by start.sh in the background while this worker starts, so
# it is normally not listening yet when the first probe runs. Generous, since a cold worker also
# competes with the image pull for disk on some hosts.
SWARMUI_BOOT_TIMEOUT = float(os.environ.get("SWARMUI_BOOT_TIMEOUT", "900"))
SWARMUI_BOOT_POLL_INTERVAL = 2.0

SWARMUI_PORT = os.environ.get("SWARMUI_PORT", "7801")
PUBLIC_IPADDR = os.environ.get("PUBLIC_IPADDR", "localhost")
VAST_CONTAINERLABEL = os.environ.get("VAST_CONTAINERLABEL", "unknown")
# Vast maps this container's SWARMUI_PORT to a random external port, exposed under this exact
# env var name - same convention used for a plain rented instance, not something serverless-specific.
VAST_TCP_PORT_SWARMUI = os.environ.get(f"VAST_TCP_PORT_{SWARMUI_PORT}", SWARMUI_PORT)


def get_public_url() -> str:
    return f"http://{PUBLIC_IPADDR}:{VAST_TCP_PORT_SWARMUI}"


@asynccontextmanager
async def swarmui_lifecycle():
    """Blocks until SwarmUI actually answers, which is what makes this worker report ready.

    The SDK only ever calls `metrics._model_loaded()` - the flag the autoscaler reads to move a
    worker out of "loading" - from one of two places (vastai 1.6.0, lib/backend.py): the log-tailing
    path, which needs both `model_log_file` and a `LogAction.ModelLoaded` pattern to match a line,
    or this lifecycle path. A worker that configures none of them can never report ready, so the
    autoscaler eventually recycles it and tries another host, forever, no matter how healthy the
    container actually is.

    The lifecycle is used here rather than log tailing because readiness for this worker is exactly
    "SwarmUI answers GetNewSession" - the same call the handler makes - so probing it directly is
    both the true condition and immune to SwarmUI changing its startup log wording.
    """
    url = f"http://127.0.0.1:{SWARMUI_PORT}/API/GetNewSession"
    deadline = time.monotonic() + SWARMUI_BOOT_TIMEOUT
    attempt = 0
    log.info(f"Waiting for SwarmUI to come up at {url} (timeout {SWARMUI_BOOT_TIMEOUT:.0f}s)...")
    async with aiohttp.ClientSession() as session:
        while True:
            attempt += 1
            try:
                async with session.post(
                    url, json={}, timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    if response.status == 200 and (await response.json()).get("session_id"):
                        log.info(f"SwarmUI is up after {attempt} probe(s); reporting worker ready.")
                        break
                    log.debug(f"SwarmUI not ready yet (HTTP {response.status})")
            except Exception as exc:
                log.debug(f"SwarmUI not reachable yet: {exc}")
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    f"SwarmUI did not answer {url} within {SWARMUI_BOOT_TIMEOUT:.0f}s "
                    f"({attempt} probes) - refusing to report this worker ready."
                )
            await asyncio.sleep(SWARMUI_BOOT_POLL_INTERVAL)
    yield


@dataclass
class WakeupPayload(ApiPayload):
    """SwarmUI's GetNewSession takes no body, so every field here is unused - the incoming
    {"action": "wakeup"} from the C# client is accepted but ignored, matched by shape only."""

    @classmethod
    def for_test(cls) -> "WakeupPayload":
        return cls()

    def generate_payload_json(self) -> Dict[str, Any]:
        return {}

    def count_workload(self) -> float:
        # Fixed cost: this handler always does exactly one cheap SwarmUI call.
        return 1.0

    @classmethod
    def from_json_msg(cls, json_msg: Dict[str, Any]) -> "WakeupPayload":
        return cls()


@dataclass
class WakeupHandler(EndpointHandler[WakeupPayload]):
    """Forwards to SwarmUI's own GetNewSession, then reshapes the response into what
    VastAIProvider.WakeupWorkerAsync (SwarmUI-CloudBackends, C#) expects."""

    @property
    def endpoint(self) -> str:
        return "/API/GetNewSession"

    @property
    def healthcheck_endpoint(self) -> Optional[str]:
        return None

    @classmethod
    def payload_cls(cls):
        return WakeupPayload

    def make_benchmark_payload(self) -> WakeupPayload:
        return WakeupPayload()

    async def generate_client_response(
        self, client_request: web.Request, model_response: ClientResponse
    ) -> Union[web.Response, web.StreamResponse]:
        if model_response.status != 200:
            text = await model_response.text()
            return web.json_response(
                {"success": False, "error": f"SwarmUI returned {model_response.status}: {text[:500]}"},
                status=502,
            )
        body = await model_response.json()
        session_id = body.get("session_id")
        if not session_id:
            return web.json_response(
                {"success": False, "error": f"SwarmUI answered but returned no session_id: {body}"},
                status=502,
            )
        return web.json_response(
            {
                "success": True,
                "public_url": get_public_url(),
                "session_id": session_id,
                "version": body.get("version"),
                "worker_id": VAST_CONTAINERLABEL,
            }
        )

    async def call_remote_dispatch_function(self, params: dict):
        raise NotImplementedError("This handler proxies to SwarmUI's own API; it has no remote-dispatch mode.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    log.info(f"Starting Vast.ai serverless worker; SwarmUI at 127.0.0.1:{SWARMUI_PORT}, public URL {get_public_url()}")
    # A HandlerConfig with handler_class set only reads route + handler_class - benchmark and
    # healthcheck config come from WakeupHandler's own dataclass fields instead, so those
    # HandlerConfig fields are left at their defaults here rather than duplicated.
    config = WorkerConfig(
        model_server_url="http://127.0.0.1",
        model_server_port=int(SWARMUI_PORT),
        handlers=[HandlerConfig(route="/handler", handler_class=WakeupHandler)],
        # Without this the worker never reports ready and the autoscaler recycles it - see
        # swarmui_lifecycle's docstring. This is not optional.
        lifecycle=swarmui_lifecycle(),
    )
    Worker(config).run()
