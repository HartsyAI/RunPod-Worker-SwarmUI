"""Runs one real lease through the handler inside the image, on CPU.

RunPod's own `--test_input` mode calls the handler once and never iterates a generator, so it cannot
exercise a lease. This drives the handler exactly as the SDK's streaming path does, and checks the
security properties end to end: the lease token opens the gateway, no token is refused, the lease
releases itself, and the token stops working the moment it does.

Run inside the image: docker run -i --entrypoint /opt/worker/venv/bin/python <image> - < lease_smoke.py
"""

import asyncio
import sys

import aiohttp

sys.path.insert(0, "/opt/worker")
import handler as h  # noqa: E402
from swarmui_worker import logs  # noqa: E402
from swarmui_worker.config import WorkerConfig  # noqa: E402
from swarmui_worker.supervisor import BackgroundSupervisor  # noqa: E402


async def status(session: aiohttp.ClientSession, url: str, token: str = "") -> int:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with session.post(url + "/API/GetNewSession", json={}, headers=headers) as r:
        return r.status


async def drive(config: WorkerConfig) -> None:
    base = f"http://127.0.0.1:{config.public_port}"
    gen = h.handler({"id": "smoke", "input": {"action": "lease"}})
    first = await gen.__anext__()
    assert first["success"], first
    assert first["public_url"] == f"https://smoke-{config.public_port}.proxy.runpod.net", first
    token = first["token"]
    async with aiohttp.ClientSession() as s:
        assert await status(s, base, token) == 200, "lease token rejected"
        assert await status(s, base) == 401, "request without a token accepted"
        assert await status(s, base, "wrong") == 401, "wrong token accepted"
    last = await gen.__anext__()
    assert last.get("released") and last["reason"] == "startup_grace_expired", last
    async with aiohttp.ClientSession() as s:
        assert await status(s, base, token) == 401, "token still works after the lease ended"
    print("LEASE SMOKE PASS", flush=True)


def main() -> None:
    config = WorkerConfig.from_env()
    logs.setup(config.log_level, as_json=False)
    h.POD_ID = "smoke"
    h.SUPERVISOR = BackgroundSupervisor(config)
    h.SUPERVISOR.start()
    try:
        asyncio.run(drive(config))
    finally:
        h.SUPERVISOR.stop()


if __name__ == "__main__":
    main()
