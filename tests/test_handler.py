"""Handler tests with a fake supervisor. `runpod` is stubbed, so no SDK or GPU is needed."""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
import types
from dataclasses import dataclass

import pytest

sys.modules.setdefault("runpod", types.SimpleNamespace(serverless=types.SimpleNamespace(start=lambda cfg: None)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
handler_mod = importlib.import_module("handler")


@dataclass
class FakeLease:
    token: str
    lease_number: int


class FakeConfig:
    public_port = 7801
    idle_seconds = 120.0
    max_seconds = 3600.0


class FakeSupervisor:
    def __init__(self, release_after: float = 0.0, busy: bool = False):
        self.config = FakeConfig()
        self.release_after = release_after
        self.busy = busy
        self.began = 0
        self.ended = 0

    async def begin_lease(self) -> FakeLease:
        if self.busy:
            raise RuntimeError("A lease is already active on this worker")
        self.began += 1
        return FakeLease(token="tok-" + "x" * 40, lease_number=self.began)

    async def wait_for_release(self) -> str:
        await asyncio.sleep(self.release_after)
        return "idle"

    async def end_lease(self) -> None:
        self.ended += 1


@pytest.fixture
def fake(monkeypatch):
    sup = FakeSupervisor()
    monkeypatch.setattr(handler_mod, "SUPERVISOR", sup)
    monkeypatch.setattr(handler_mod, "POD_ID", "abc123")
    return sup


async def collect(job) -> list:
    return [out async for out in handler_mod.handler(job)]


def test_lease_streams_address_then_release(fake):
    outputs = asyncio.run(collect({"id": "j1", "input": {"action": "lease"}}))
    first, last = outputs
    assert first["success"] and first["public_url"] == "https://abc123-7801.proxy.runpod.net"
    assert first["token"].startswith("tok-") and first["worker_id"] == "abc123"
    assert first["protocol"] == handler_mod.PROTOCOL_VERSION
    assert last == {"success": True, "released": True, "reason": "idle"}
    assert fake.began == 1 and fake.ended == 1


def test_lease_is_the_default_action(fake):
    outputs = asyncio.run(collect({"input": {}}))
    assert outputs[0]["public_url"].startswith("https://abc123-")


def test_cancelled_lease_still_revokes_token(fake):
    fake.release_after = 3600

    async def body():
        gen = handler_mod.handler({"input": {"action": "lease"}})
        first = await gen.__anext__()
        assert first["success"]
        task = asyncio.ensure_future(gen.__anext__())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(body())
    assert fake.ended == 1


def test_busy_worker_refuses_second_lease(fake):
    fake.busy = True
    outputs = asyncio.run(collect({"input": {"action": "lease"}}))
    assert outputs == [{"success": False, "error": "A lease is already active on this worker", "error_id": "lease_busy"}]
    assert fake.ended == 0


def test_health_and_unknown_action(fake):
    health = asyncio.run(collect({"input": {"action": "health"}}))[0]
    assert health["success"] and health["worker_id"] == "abc123"
    unknown = asyncio.run(collect({"input": {"action": "wakeup"}}))[0]
    assert unknown["error_id"] == "unknown_action"


def test_not_initialized(monkeypatch):
    monkeypatch.setattr(handler_mod, "SUPERVISOR", None)
    out = asyncio.run(collect({"input": {"action": "lease"}}))[0]
    assert out["error_id"] == "worker_not_ready"


def test_main_refuses_fixed_token_and_missing_pod_id(monkeypatch):
    monkeypatch.setenv("SWARMUI_WORKER_TOKEN", "y" * 48)
    monkeypatch.setattr(handler_mod, "POD_ID", "abc123")
    assert handler_mod.main() == 2
    monkeypatch.delenv("SWARMUI_WORKER_TOKEN")
    monkeypatch.setattr(handler_mod, "POD_ID", "")
    assert handler_mod.main() == 2
