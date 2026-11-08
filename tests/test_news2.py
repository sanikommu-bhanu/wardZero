import unittest
from services.risk_engine.news2 import news2, escalation_from_news2

NORMAL = {"resp_rate": 16, "spo2": 97, "systolic_bp": 120, "heart_rate": 70, "temperature": 36.8}


class TestNews2(unittest.TestCase):
    def test_normal_is_zero(self):
        n = news2(NORMAL)
        self.assertEqual((n["score"], n["band"]), (0, "low"))

    def test_published_boundaries(self):
        cases = [("resp_rate", 8, 3), ("resp_rate", 9, 1), ("resp_rate", 20, 0), ("resp_rate", 21, 2), ("resp_rate", 25, 3),
                 ("spo2", 91, 3), ("spo2", 92, 2), ("spo2", 94, 1), ("spo2", 96, 0),
                 ("systolic_bp", 90, 3), ("systolic_bp", 100, 2), ("systolic_bp", 110, 1), ("systolic_bp", 219, 0), ("systolic_bp", 220, 3),
                 ("heart_rate", 40, 3), ("heart_rate", 50, 1), ("heart_rate", 90, 0), ("heart_rate", 110, 1), ("heart_rate", 130, 2), ("heart_rate", 131, 3),
                 ("temperature", 35.0, 3), ("temperature", 36.0, 1), ("temperature", 38.0, 0), ("temperature", 39.0, 1), ("temperature", 39.1, 2)]
        for k, v, pts in cases:
            n = news2({**NORMAL, k: v})
            self.assertEqual(n["score"], pts, f"{k}={v}")

    def test_single_three_is_low_medium(self):
        n = news2({**NORMAL, "spo2": 90})
        self.assertEqual((n["score"], n["band"]), (3, "low_medium"))
        self.assertEqual(escalation_from_news2(n), "caregiver_review")

    def test_bands(self):
        self.assertEqual(news2({**NORMAL, "resp_rate": 22, "heart_rate": 115, "temperature": 38.5})["band"], "medium")  # 2+2+1=5
        high = news2({**NORMAL, "resp_rate": 26, "spo2": 90, "heart_rate": 135})  # 3+3+3
        self.assertEqual((high["score"], high["band"]), (9, "high"))
        self.assertEqual(escalation_from_news2(high), "emergency")

    def test_oxygen_confusion_and_missing(self):
        n = news2(NORMAL, on_oxygen=True, new_confusion=True)
        self.assertEqual(n["score"], 5)
        m = news2({"heart_rate": 70})
        self.assertFalse(m["complete"])
        self.assertIn("SpO2", m["missing_parameters"])

    def test_scale2_copd(self):
        self.assertEqual(news2({**NORMAL, "spo2": 90}, use_scale2=True)["score"], 0)
        self.assertEqual(news2({**NORMAL, "spo2": 90})["score"], 3)
        self.assertEqual(news2({**NORMAL, "spo2": 97}, use_scale2=True, on_oxygen=True)["score"], 3 + 2)


if __name__ == "__main__":
    unittest.main()
