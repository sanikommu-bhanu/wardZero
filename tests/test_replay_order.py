import unittest

from apps.api.replay import ingest_batch


class _Recorder:
    def __init__(self):
        self.order = []

    def ingest(self, ev, ctx, note_signals):
        self.order.append(ev["event_id"])

        class R:
            status = "accepted"
            notification = None
            errors = []
        return R()


def _item(eid, ts):
    return {"event": {"event_id": eid, "timestamp": ts}, "context": {}}


class TestReplayOrder(unittest.TestCase):
    def test_numeric_timestamps_sorted_numerically_not_as_strings(self):
        p = _Recorder()
        ingest_batch(p, [_item("a", 1000.0), _item("b", 999.0), _item("c", 50.0)])
        self.assertEqual(p.order, ["c", "b", "a"])

    def test_iso_timestamps_sorted_by_instant_including_offsets(self):
        p = _Recorder()
        ingest_batch(p, [_item("late", "2026-01-01T10:00:00+00:00"),
                         _item("early", "2026-01-01T09:00:00Z"),
                         _item("mid", "2026-01-01T12:30:00+03:00")])   # 09:30 UTC
        self.assertEqual(p.order, ["early", "mid", "late"])

    def test_missing_or_bad_timestamp_does_not_crash(self):
        p = _Recorder()
        ingest_batch(p, [_item("x", None), _item("y", "garbage"), _item("z", 5)])
        self.assertEqual(sorted(p.order), ["x", "y", "z"])


if __name__ == "__main__":
    unittest.main()
