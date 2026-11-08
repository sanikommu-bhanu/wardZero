"""Shared data contract: vital names, plausible ranges, population baselines."""
VITALS = ("heart_rate", "spo2", "temperature", "resp_rate", "systolic_bp", "diastolic_bp", "activity")
UNITS = {"heart_rate": "bpm", "spo2": "%", "temperature": "°C", "resp_rate": "/min",
         "systolic_bp": "mmHg", "diastolic_bp": "mmHg", "activity": "idx"}
# Physically plausible ranges. Values outside are rejected as malformed at ingestion.
RANGES = {"heart_rate": (20, 250), "spo2": (50, 100), "temperature": (30.0, 43.0),
          "resp_rate": (4, 60), "systolic_bp": (50, 260), "diastolic_bp": (30, 160), "activity": (0, 100)}
BASELINE = {"heart_rate": 74.0, "spo2": 97.0, "temperature": 36.7, "resp_rate": 16.0,
            "systolic_bp": 124.0, "diastolic_bp": 78.0, "activity": 35.0}
NOISE_SD = {"heart_rate": 2.0, "spo2": 0.5, "temperature": 0.08, "resp_rate": 0.8,
            "systolic_bp": 3.0, "diastolic_bp": 2.0, "activity": 6.0}
CONTEXT_KEYS = ("age", "hypertension", "diabetes", "cardiac", "copd", "post_surgery")
NOTE_KEYS = ("breathing_difficulty", "weakness", "fever", "chest_discomfort",
             "dizziness", "confusion", "reduced_appetite", "abnormal_behavior")
WINDOW = 30  # readings used for trend features
