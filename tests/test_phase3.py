import os, random, tempfile, unittest, urllib.error
from datetime import datetime, timedelta, timezone

from apps.api.sqlite_repo import SqliteAlertStore, SqliteDB, SqliteRepository
from apps.simulator.equipment import IvPump, OxygenConcentrator, equipment_alert
from services.alert_engine.engine import AlertStore, Severity, Status
from services.alert_engine.ladder import EscalationLadder, LEVELS, ack_metrics, current_level
from services.care_engine.checkins import sweep_missed_visits, visit_status
from services.notify.channels import Dispatcher, InAppChannel, NtfyChannel, TelegramChannel


class Clock:
    def __init__(self):
        self.t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def __call__(self):
        return self.t
    def adv(self, **kw):
        self.t += timedelta(**kw)


def crit(esc="emergency"):
    return {"recommended_escalation": esc, "hard_threshold_breaches": [], "explanation": "x"}


class TestEquipment(unittest.TestCase):
    def test_concentrator_faults(self):
        c = OxygenConcentrator("c1"); rng = random.Random(0)
        self.assertEqual(c.tick(rng), [])
        c.inject("low_purity"); c.inject("power_failure")
        faults = {e.fault for e in c.tick(rng)}
        self.assertEqual(faults, {"low_purity", "power_failure"})
        c.clear("low_purity"); c.clear("power_failure")
        self.assertEqual(c.tick(rng), [])

    def test_pump_occlusion_stops_infusion_and_empty_alarm(self):
        p = IvPump("p1", volume_ml=10, rate_ml_h=120)
        p.inject("occlusion"); v = p.volume_ml
        self.assertEqual(p.tick(5)[0].fault, "occlusion"); self.assertEqual(p.volume_ml, v)
        p.clear("occlusion")
        for _ in range(3):
            ev = p.tick(5)
        self.assertIn("empty", [e.fault for e in ev])

    def test_fault_becomes_deduped_alert(self):
        s = AlertStore(); c = OxygenConcentrator("c1"); c.inject("power_failure")
        for _ in range(3):
            for ev in c.tick(): a = equipment_alert(s, "p1", ev)
        self.assertEqual(len(s.list()), 1)
        self.assertEqual(a.severity, Severity.CRITICAL)


class TestLadder(unittest.TestCase):
    def setUp(self):
        self.clk = Clock(); self.s = AlertStore(clock=self.clk); self.sent = []
        self.l = EscalationLadder(self.s, notify=lambda a, name, i: self.sent.append((a.id, name)))

    def test_climbs_when_unacked_and_stops_on_ack(self):
        a = self.s.detect("p1", "t", crit())
        self.l.tick(); self.assertEqual(self.sent, [(a.id, "primary_caregiver")])
        self.clk.adv(minutes=2, seconds=1); self.l.tick()
        self.assertEqual(self.sent[-1][1], "secondary_caregiver"); self.assertEqual(a.status, Status.ESCALATED)
        self.clk.adv(minutes=2, seconds=1); self.l.tick()
        self.assertEqual(self.sent[-1][1], "on_call_doctor")
        self.s.acknowledge(a.id, "dr@x")
        self.clk.adv(hours=1); self.assertEqual(self.l.tick(), [])
        self.assertEqual(len(self.sent), 3)

    def test_caps_at_last_level_and_metrics(self):
        a = self.s.detect("p1", "t", crit())
        for _ in range(10):
            self.l.tick(); self.clk.adv(minutes=3)
        self.assertEqual(current_level(a)[0], len(LEVELS) - 1)
        b = self.s.detect("p2", "t", crit("escalate_to_doctor")); self.clk.adv(seconds=90); self.s.acknowledge(b.id, "n@x")
        m = ack_metrics(self.s)
        self.assertEqual(m["overall"]["n"], 1); self.assertEqual(m["overall"]["median_s"], 90.0)
        self.assertEqual(m["open_unacknowledged"], 1)

    def test_ladder_state_survives_restart(self):
        d = SqliteDB(os.path.join(tempfile.mkdtemp(), "l.db")); path = d.path
        s = SqliteAlertStore(d, clock=self.clk); l = EscalationLadder(s)
        a = s.detect("p1", "t", crit()); l.tick(); self.clk.adv(minutes=3); l.tick(); d.close()
        s2 = SqliteAlertStore(SqliteDB(path), clock=self.clk)
        self.assertEqual(current_level(s2.get(a.id))[0], 1)


class TestCheckins(unittest.TestCase):
    def test_visit_status_thresholds(self):
        now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        self.assertEqual(visit_status("2026-01-01T11:30:00+00:00", "HIGH", now)["state"], "ok")
        self.assertEqual(visit_status("2026-01-01T10:55:00+00:00", "HIGH", now)["state"], "due")
        self.assertEqual(visit_status("2026-01-01T10:00:00+00:00", "HIGH", now)["state"], "missed")
        self.assertEqual(visit_status(None, "LOW", now)["state"], "no_baseline")

    def test_missed_visit_alert_and_checkin_flow(self):
        db = SqliteDB(os.path.join(tempfile.mkdtemp(), "c.db")); repo = SqliteRepository(db); s = AlertStore()
        now = datetime(2026, 1, 1, 12, tzinfo=timezone.utc)
        repo.store_checkin("p1", "nurse@x", ts=(now - timedelta(minutes=30)).isoformat())
        repo.store_checkin("p2", "nurse@x", ts=(now - timedelta(hours=5)).isoformat())
        pts = [{"id": "p1", "risk_level": "HIGH"}, {"id": "p2", "risk_level": "HIGH"}]
        raised = sweep_missed_visits(repo, s, pts, now=now)
        self.assertEqual([a.patient_id for a in raised], ["p2"])
        sweep_missed_visits(repo, s, pts, now=now)
        self.assertEqual(len(s.list()), 1)    # deduped on re-sweep


class TestNotify(unittest.TestCase):
    def test_telegram_and_ntfy_build_correct_requests(self):
        seen = []
        tg = TelegramChannel("TOKEN", "42", transport=lambda r: seen.append(r) or 200)
        nt = NtfyChannel("topic-x", "https://ntfy.example", transport=lambda r: seen.append(r) or 200)
        self.assertTrue(tg.send("T", "body", "critical")); self.assertTrue(nt.send("T", "body", "critical"))
        self.assertIn("/botTOKEN/sendMessage", seen[0].full_url)
        self.assertEqual(seen[1].full_url, "https://ntfy.example/topic-x")
        self.assertEqual(seen[1].headers["Priority"], "5")

    def test_unconfigured_skipped_and_failure_falls_back_to_in_app(self):
        db = SqliteDB(os.path.join(tempfile.mkdtemp(), "n.db")); repo = SqliteRepository(db); got = []
        def boom(r): raise urllib.error.URLError("secret-host-down TOKEN123")
        d = Dispatcher([InAppChannel(got.append), TelegramChannel("TOKEN123", "1", transport=boom),
                        NtfyChannel(topic=None)], repo)
        out = d.send("Alert", "msg", "critical", alert_id=7)
        self.assertEqual(out, {"in_app": True, "telegram": False})     # ntfy not configured -> skipped
        self.assertEqual(len(got), 1)                                    # in-app delivered regardless
        log = repo.notifications()
        self.assertNotIn("TOKEN123", str(log))                            # secret never logged
        self.assertEqual({l["channel"] for l in log}, {"in_app", "telegram"})


if __name__ == "__main__":
    unittest.main()
