import unittest
from ml.features.schema import NOTE_KEYS
from services.nlp_engine import analyze_note, merge_notes
from services.nlp_engine.engine import normalize


def st(text):
    return {(f["key"], f["status"]) for f in analyze_note(text)["findings"]}


class TestPresence(unittest.TestCase):
    def test_all_keys_reachable_english(self):
        cases = {"breathing_difficulty": "She is short of breath", "weakness": "feeling very weak",
                 "fever": "he has a fever", "chest_discomfort": "complains of chest pain",
                 "dizziness": "feels dizzy", "confusion": "he seems confused",
                 "reduced_appetite": "he is not eating", "abnormal_behavior": "acting strange since noon"}
        self.assertEqual(set(cases), set(NOTE_KEYS))
        for k, t in cases.items():
            self.assertIn((k, "present"), st(t), t)

    def test_signals_shape_matches_schema(self):
        r = analyze_note("fever and dizzy")
        self.assertEqual(set(r["signals"]), set(NOTE_KEYS))
        self.assertTrue(r["signals"]["fever"] and r["signals"]["dizziness"])
        self.assertFalse(r["signals"]["confusion"])

    def test_evidence_is_exact_substring_of_original(self):
        t = "Patient: FEVER and  Short of   Breath!"
        for f in analyze_note(t)["findings"]:
            self.assertEqual(t[f["span"][0]:f["span"][1]], f["evidence"])

    def test_no_invention_on_irrelevant_text(self):
        for t in ["", "   ", "Had a good sleep, walked in garden, ate lunch well.", "भ्रमण पर गए", "ok"]:
            r = analyze_note(t)
            self.assertEqual(r["findings"], [], t)
            self.assertFalse(any(r["signals"].values()))

    def test_no_clinical_outputs(self):
        r = analyze_note("short of breath and fever")
        for banned in ("severity", "diagnosis", "risk", "advice"):
            self.assertFalse(any(banned in k for k in r), banned)


class TestNegation(unittest.TestCase):
    def test_english(self):
        self.assertEqual(st("no fever"), {("fever", "negated")})
        self.assertEqual(st("denies fever, cough or chest pain"), {("fever", "negated"), ("chest_discomfort", "negated")})
        self.assertEqual(st("does not have any dizziness"), {("dizziness", "negated")})
        self.assertEqual(st("fever is not present"), {("fever", "negated")})
        self.assertEqual(st("No fever, no chest pain, but very weak"),
                         {("fever", "negated"), ("chest_discomfort", "negated"), ("weakness", "present")})

    def test_negation_does_not_leak_across_new_clause(self):
        self.assertIn(("fever", "present"), st("no cough and has fever"))
        self.assertIn(("dizziness", "present"), st("no fever. feels dizzy"))

    def test_intrinsic_negative_phrases_are_positive(self):
        self.assertEqual(st("he is not eating"), {("reduced_appetite", "present")})
        self.assertIn(("reduced_appetite", "present"), st("no appetite today"))
        self.assertEqual(st("no loss of appetite"), {("reduced_appetite", "negated")})

    def test_hindi(self):
        self.assertEqual(st("बुखार नहीं है लेकिन सांस फूल रही है"),
                         {("fever", "negated"), ("breathing_difficulty", "present")})
        self.assertEqual(st("भूख नहीं लग रही"), {("reduced_appetite", "present")})
        self.assertEqual(st("सीने में दर्द नहीं है"), {("chest_discomfort", "negated")})
        self.assertEqual(st("सांस नहीं ले पा रहे"), {("breathing_difficulty", "present")})

    def test_romanized_hindi_and_spelling_variants(self):
        self.assertEqual(st("bukhar nahi hai, chakkar aa raha hai"), {("fever", "negated"), ("dizziness", "present")})
        for v in ("saans lene mein takleef", "saans lene me taklif", "sans lene main takleef", "saans lene mein takleeef"):
            self.assertIn(("breathing_difficulty", "present"), st(v), v)
        self.assertIn(("weakness", "present"), st("bahut kamzori hai"))
        self.assertIn(("reduced_appetite", "present"), st("bhookh nahi lag rahi"))

    def test_tamil(self):
        self.assertEqual(st("காய்ச்சல் இல்லை ஆனால் மூச்சு திணறல் இருக்கு"),
                         {("fever", "negated"), ("breathing_difficulty", "present")})
        self.assertEqual(st("பசி இல்லை"), {("reduced_appetite", "present")})
        self.assertEqual(st("நெஞ்சு வலி இல்லை"), {("chest_discomfort", "negated")})
        self.assertIn(("dizziness", "present"), st("தலை சுற்றுகிறது"))
        self.assertEqual(st("பசி குறையவில்லை"), {("reduced_appetite", "negated")})

    def test_telugu(self):
        self.assertEqual(st("ఆకలి తగ్గలేదు కానీ జ్వరం ఉంది"), {("reduced_appetite", "negated"), ("fever", "present")})
        self.assertEqual(st("ఆకలి లేదు"), {("reduced_appetite", "present")})
        self.assertEqual(st("జ్వరం లేదు"), {("fever", "negated")})
        self.assertEqual(st("ఊపిరి ఆడటం లేదు"), {("breathing_difficulty", "present")})
        self.assertIn(("chest_discomfort", "present"), st("ఛాతీ నొప్పి ఉంది"))

    def test_other_symptoms_cue_words_do_not_cross_findings(self):
        # 'नहीं' belongs to the appetite phrase, it must not negate the fever before it
        self.assertEqual(st("बुखार है भूख नहीं"), {("fever", "present"), ("reduced_appetite", "present")})


class TestTimeAndHedging(unittest.TestCase):
    def test_historical(self):
        self.assertEqual(st("had fever yesterday"), {("fever", "historical")})
        self.assertEqual(st("fever last week"), {("fever", "historical")})
        # two literal mentions -> two findings: the earlier one stays historical, the later one present
        self.assertEqual(st("fever yesterday but still has fever today"),
                         {("fever", "historical"), ("fever", "present")})
        r2 = analyze_note("fever yesterday but still has fever today")
        self.assertTrue(r2["signals"]["fever"])  # present mention wins the signal
        r = analyze_note("fever yesterday")
        self.assertFalse(r["signals"]["fever"])
        self.assertEqual(r["historical"], ["fever"])

    def test_uncertain_counts_but_is_flagged(self):
        r = analyze_note("maybe some confusion")
        self.assertTrue(r["signals"]["confusion"])
        self.assertEqual(r["uncertain"], ["confusion"])


class TestLanguageAndLimits(unittest.TestCase):
    def test_language_detection(self):
        self.assertEqual(analyze_note("बुखार है")["languages"][0], "hi")
        self.assertEqual(analyze_note("காய்ச்சல்")["languages"][0], "ta")
        self.assertEqual(analyze_note("జ్వరం")["languages"][0], "te")
        self.assertEqual(analyze_note("bukhar hai")["languages"][0], "hi-Latn")
        self.assertEqual(analyze_note("has fever")["languages"][0], "en")

    def test_mixed_script(self):
        r = analyze_note("Patient has fever aur सांस फूल रही hai")
        self.assertTrue(r["signals"]["fever"] and r["signals"]["breathing_difficulty"])

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            analyze_note(None)
        with self.assertRaises(ValueError):
            analyze_note("x" * 5001)

    def test_normalize_maps_back(self):
        n, sp = normalize("सांस")  # chandrabindu variant
        self.assertEqual(normalize("साँस")[0], n)

    def test_merge_latest_wins(self):
        a = analyze_note("fever and dizzy")
        b = analyze_note("no fever now")
        c = analyze_note("fever yesterday")
        m = merge_notes([a, b, c])
        self.assertFalse(m["fever"])
        self.assertTrue(m["dizziness"])


if __name__ == "__main__":
    unittest.main()
