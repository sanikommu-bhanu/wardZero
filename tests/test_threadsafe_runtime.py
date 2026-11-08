"""Regression tests for a real bug class: FastAPI runs plain `def` routes in a worker thread, where
asyncio.get_running_loop()/ensure_future() fail. These exercise the fix with a real event loop running
in a background thread, exactly like uvicorn + a sync route handler (no fastapi needed)."""
import asyncio
import threading
import time
import unittest

from apps.api.ws_manager import ConnectionManager
from apps.api.simulator_manager import SimulatorManager
from apps.api.pipeline import IngestionPipeline
from apps.api.repository import InMemoryRepository
from services.alert_engine.engine import AlertStore


class FakeSocket:
    def __init__(self):
        self.sent = []

    async def accept(self):
        pass

    async def send_text(self, t):
        self.sent.append(t)


class LoopThread:
    def __enter__(self):
        self.loop = asyncio.new_event_loop()
        self.t = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.t.start()
        while not self.loop.is_running():
            time.sleep(0.01)
        return self.loop

    def __exit__(self, *a):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.t.join(2)


class TestThreadSafeBroadcast(unittest.TestCase):
    def test_broadcast_from_worker_thread_reaches_clients(self):
        with LoopThread() as loop:
            mgr = ConnectionManager()
            mgr.bind_loop(loop)
            sock = FakeSocket()
            asyncio.run_coroutine_threadsafe(mgr.connect(sock), loop).result(2)
            mgr.broadcast_sync({"type": "alert", "x": 1})  # called from THIS (non-loop) thread
            for _ in range(100):
                if sock.sent:
                    break
                time.sleep(0.02)
            self.assertEqual(len(sock.sent), 1)

    def test_no_loop_is_silent_noop(self):
        ConnectionManager().broadcast_sync({"a": 1})  # must not raise


class TestSimulatorStartFromWorkerThread(unittest.TestCase):
    def test_start_from_thread_runs_and_ingests_with_patient_context(self):
        repo = InMemoryRepository()
        pipe = IngestionPipeline(repo, alert_store=AlertStore())
        seen = []
        orig = pipe.ingest

        def spy(flat, ctx, *a, **k):
            seen.append(ctx)
            return orig(flat, ctx, *a, **k)
        pipe.ingest = spy
        with LoopThread() as loop:
            mgr = SimulatorManager(pipe, repo, ConnectionManager(), step_minutes=0.05)
            mgr.bind_loop(loop)
            snap = mgr.start("p1", "p1-vitals", {"age": 67, "hypertension": True, "diabetes": True}, "normal", 5.0)
            self.assertEqual(snap["status"], "running")
            for _ in range(150):
                if seen:
                    break
                time.sleep(0.05)
            mgr.stop("p1")
        self.assertTrue(seen, "simulator never ingested a reading")
        self.assertEqual(seen[0]["age"], 67)          # context no longer dropped
        self.assertTrue(seen[0]["hypertension"])

    def test_start_without_bound_loop_fails_loudly(self):
        mgr = SimulatorManager(None, None, None)
        with self.assertRaises(RuntimeError):
            mgr.start("p", "d", {}, "normal")


if __name__ == "__main__":
    unittest.main()
