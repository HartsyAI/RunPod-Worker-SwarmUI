"""RunPod Serverless handler for the Hartsy SwarmUI worker.

One job holds one worker. The `lease` action streams the worker's address and a fresh access token as
its first output, then keeps running while SwarmUI is in use. It returns on its own once the worker has
been idle for SWARMUI_IDLE_SECONDS, and RunPod then scales the worker down. Because a running lease
occupies its worker, a second lease queued while every worker is busy is real queue pressure, and
RunPod's autoscaler adds a worker for it, up to the endpoint's Max Workers.

Generations never pass through RunPod's queue. The client talks to SwarmUI directly at the worker's
proxy URL, through the base image's authenticated gateway, using the lease token.

Follows RunPod's worker template: heavy startup runs once at import, outside the handler, and the
handler is an async generator so its first output reaches the client through /stream while the job
keeps running (https://docs.runpod.io/serverless/workers/handler-functions).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any, AsyncGenerator, Optional

import runpod

from swarmui_worker import logs
from swarmui_worker.config import ConfigError, WorkerConfig
from swarmui_worker.supervisor import BackgroundSupervisor

WORKER_VERSION = "2.0.0"
PROTOCOL_VERSION = 2
"""Bumped whenever the lease output changes shape, so the client can refuse an incompatible worker."""

log = logging.getLogger("runpod_worker")

SUPERVISOR: Optional[BackgroundSupervisor] = None
POD_ID = os.environ.get("RUNPOD_POD_ID", "")


def public_url(pod_id: str, port: int) -> str:
    """The worker's address through RunPod's HTTP proxy."""
    return f"https://{pod_id}-{port}.proxy.runpod.net"


def _number(value: Any) -> Optional[float]:
    """A numeric job input, or None if absent or not a number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _error(message: str, error_id: str) -> dict[str, Any]:
    return {"success": False, "error": message, "error_id": error_id}


async def handler(job: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
    """Routes a job by its `action` (default `lease`)."""
    job_input = job.get("input") or {}
    action = job_input.get("action", "lease")
    if SUPERVISOR is None:
        yield _error("The worker is not initialized.", "worker_not_ready")
        return
    if action == "lease":
        async for output in _lease(job):
            yield output
    elif action == "health":
        yield {"success": True, "worker_id": POD_ID, "version": WORKER_VERSION, "protocol": PROTOCOL_VERSION}
    else:
        yield _error(f"Unknown action '{action}'. This worker supports 'lease' and 'health'.", "unknown_action")


async def _lease(job: dict[str, Any]) -> AsyncGenerator[dict[str, Any], None]:
    assert SUPERVISOR is not None
    config = SUPERVISOR.config
    job_input = job.get("input") or {}
    # The client's own idle and lease settings, clamped by the supervisor to safe bounds.
    requested = (_number(job_input.get("idle_seconds")), _number(job_input.get("startup_grace_seconds")),
                 _number(job_input.get("max_lease_seconds")))
    idle, grace, cap = SUPERVISOR.lease_limits(*requested)
    try:
        lease = await SUPERVISOR.begin_lease()
    except RuntimeError as ex:
        # Worker concurrency is 1, so this only happens if RunPod ever hands a busy worker a second job.
        yield _error(str(ex), "lease_busy")
        return
    ended = False
    try:
        yield {
            "success": True,
            "public_url": public_url(POD_ID, config.public_port),
            "token": lease.token,
            "worker_id": POD_ID,
            "lease": lease.lease_number,
            "version": WORKER_VERSION,
            "protocol": PROTOCOL_VERSION,
            "idle_seconds": idle,
            "startup_grace_seconds": grace,
            "max_lease_seconds": cap,
        }
        reason = await SUPERVISOR.wait_for_release(*requested)
        # Revoke before reporting the release: a generator pauses at each yield, so revoking after it
        # would leave the token valid until RunPod resumes the generator, if it ever does.
        await asyncio.shield(SUPERVISOR.end_lease())
        ended = True
        yield {"success": True, "released": True, "reason": reason}
    finally:
        # Cancellation and errors land here. Shielded so a cancellation cannot skip revoking the token.
        if not ended:
            await asyncio.shield(SUPERVISOR.end_lease())
        log.info("Lease %d for job %s finished", lease.lease_number, job.get("id", "?"))


def main() -> int:
    global SUPERVISOR
    try:
        config = WorkerConfig.from_env()
    except ConfigError as ex:
        logs.setup()
        log.error("Invalid configuration: %s", ex)
        return 2
    logs.setup(config.log_level, config.log_json)
    if config.token:
        # A fixed token would let a finished lease's holder reach the next lease on this worker.
        log.error("SWARMUI_WORKER_TOKEN must not be set for serverless workers; each lease gets its own")
        return 2
    if not POD_ID:
        log.error("RUNPOD_POD_ID is not set; this handler only runs on RunPod Serverless")
        return 2
    SUPERVISOR = BackgroundSupervisor(config)
    SUPERVISOR.start()
    runpod.serverless.start({"handler": handler, "return_aggregate_stream": True})
    return 0


if __name__ == "__main__":
    sys.exit(main())
