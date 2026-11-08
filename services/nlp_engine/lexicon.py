"""Symptom lexicon (English, Tamil, Telugu, Hindi Devanagari, romanized Hindi) + linguistic cue lists.

IMPORTANT: the Tamil/Telugu/Hindi entries were written without native-speaker or clinical review and are
NOT exhaustive. They are data, not code: extend/correct them in this file. Every entry maps to exactly one
tracked key from ml.features.schema.NOTE_KEYS; the engine never infers anything beyond a matched phrase.

Pattern syntax
  en / hi_rom : plain lowercase phrases. `*` at the end = any word suffix. In hi_rom, vowel runs and 'h' are
                matched fuzzily (takleef == taklif) and {me} / {nahi} expand to spelling variants.
  hi / ta / te: Indic script phrases. Space = optional whitespace (scripts are agglutinative). `$` at the end
                = word must end there (prevents e.g. 'भ्रम' matching 'भ्रमण'). Otherwise suffixes are allowed.
Phrases that embed their own negation ('भूख नहीं', 'ఆకలి లేదు', 'not eating') are listed in full so they are
matched as a symptom-present phrase and not treated as a negated finding.
"""
from __future__ import annotations

LEXICON_VERSION = "1.0.0"

LEXICON: dict[str, dict[str, list[str]]] = {
    "breathing_difficulty": {
        "en": ["short of breath", "shortness of breath", "breathless*", "difficulty breathing", "difficulty in breathing",
               "trouble breathing", "hard to breathe", "can't breathe", "cannot breathe", "struggling to breathe",
               "breathing difficulty", "breathing problem*", "gasping", "wheez*", "out of breath", "labored breathing",
               "laboured breathing", "breathing fast", "fast breathing", "rapid breathing", "heavy breathing",
               "breathing heavily", "noisy breathing", "unable to breathe", "not able to breathe", "sob"],
        "hi": ["सांस फूल", "सांस लेने में तकलीफ", "सांस लेने में दिक्कत", "सांस लेने में कठिनाई", "सांस लेने में परेशानी",
               "सांस की तकलीफ", "सांस में तकलीफ", "दम घुट", "हांफ", "सांस नहीं ले पा", "सांस नहीं आ", "दम फूल"],
        "hi_rom": ["saans phool*", "saans {me} takleef", "saans lene {me} takleef", "saans lene {me} dikkat",
                   "saans lene {me} pareshani", "saans ki takleef", "dum ghut*", "haanf*", "saans {nahi} le pa*",
                   "saans {nahi} aa*", "dum phool*"],
        "ta": ["மூச்சுத் திணறல்", "மூச்சு திணறல்", "மூச்சுத்திணறல்", "மூச்சு விட சிரமம்", "மூச்சு விடுவதில் சிரமம்",
               "சுவாசிக்க சிரமம்", "சுவாசக் கோளாறு", "மூச்சு வாங்க", "மூச்சிரைப்பு", "இளைப்பு", "மூச்சு விட முடியவில்லை"],
        "te": ["శ్వాస తీసుకోవడం కష్ట", "శ్వాస తీసుకోవడంలో ఇబ్బంది", "ఊపిరి తీసుకోవడం కష్ట", "ఊపిరి తీసుకోవడంలో ఇబ్బంది",
               "ఆయాసం", "ఊపిరి ఆడటం లేదు", "ఊపిరి ఆడడం లేదు", "ఊపిరి ఆడట్లేదు", "ఊపిరాడట్లేదు", "ఊపిరి ఆడడంలేదు"],
    },
    "weakness": {
        "en": ["weak", "weakness", "fatigue*", "tired*", "exhausted", "lethargic", "lethargy", "no energy",
               "lack of energy", "unable to stand", "can't stand", "can't get up", "cannot get up", "worn out"],
        "hi": ["कमजोरी", "कमजोर", "थकान", "थका", "सुस्ती", "सुस्त", "ताकत नहीं", "ताकत कम"],
        "hi_rom": ["kamzori", "kamzor$", "thakan", "thaka$", "susti", "sust$", "taqat {nahi}", "takat {nahi}"],
        "ta": ["பலவீன", "சோர்வு", "சோர்வாக", "களைப்பு", "தளர்ச்சி"],
        "te": ["నీరస", "బలహీన", "అలసట", "అలసిపోయ", "నిస్సత్తువ"],
    },
    "fever": {
        "en": ["fever*", "high temperature", "temperature is high", "running a temperature", "burning up",
               "hot to touch", "body is hot"],
        "hi": ["बुखार", "ज्वर", "शरीर गर्म", "शरीर गरम", "बदन गर्म", "बदन गरम"],
        "hi_rom": ["bukhar", "jwar", "badan garam", "sharir garam", "shareer garam"],
        "ta": ["காய்ச்ச", "ஜுரம்", "சுரம்", "உடல் சூடு", "உடம்பு சூடு"],
        "te": ["జ్వర", "ఒళ్ళు వేడి", "ఒంటి వేడి", "ఒళ్లు వేడి"],
    },
    "chest_discomfort": {
        "en": ["chest pain*", "chest discomfort", "chest tightness", "tight chest", "pain in chest", "pain in the chest",
               "pressure in chest", "pressure in the chest", "chest pressure", "chest heaviness",
               "heaviness in chest", "heaviness in the chest", "tightness in chest", "tightness in the chest"],
        "hi": ["सीने में दर्द", "सीने में जकड़न", "सीने में भारीपन", "सीने में दबाव", "सीने में तकलीफ",
               "छाती में दर्द", "छाती में जकड़न", "छाती में भारीपन", "छाती में दबाव", "छाती में तकलीफ"],
        "hi_rom": ["seene {me} dard", "seene {me} jakdan", "seene {me} bhaari*", "seene {me} takleef",
                   "chhati {me} dard", "chhaati {me} dard", "chati {me} dard", "chhati {me} jakdan"],
        "ta": ["நெஞ்சு வலி", "நெஞ்சில் வலி", "மார்பு வலி", "மார்பில் வலி", "நெஞ்சு இறுக்க", "நெஞ்சு அடைப்பு"],
        "te": ["ఛాతీ నొప్పి", "ఛాతిలో నొప్పి", "ఛాతీలో నొప్పి", "చాతి నొప్పి", "చాతీలో నొప్పి", "గుండె నొప్పి",
               "ఛాతీ బిగుతు", "ఛాతీ బరువు"],
    },
    "dizziness": {
        "en": ["dizzy", "dizziness", "lightheaded", "light-headed", "light headed", "giddy", "vertigo",
               "room spinning", "feel faint", "feeling faint", "about to faint", "fainted", "fainting"],
        "hi": ["चक्कर", "सिर घूम", "सर घूम", "सिर चकरा"],
        "hi_rom": ["chakkar", "sir ghum*", "sar ghum*", "sir chakra*"],
        "ta": ["தலைச்சுற்ற", "தலை சுற்ற", "தலைசுற்ற", "தலை சுத்த", "தலைசுத்த", "மயக்க"],
        "te": ["తల తిరుగ", "తలతిరుగ", "తల తిరిగ", "కళ్ళు తిరుగ", "కళ్ళు తిరిగ", "కళ్లు తిరుగ", "కళ్లు తిరిగ"],
    },
    "confusion": {
        "en": ["confused", "confusion", "disoriented", "disorientation", "not making sense", "doesn't recognize",
               "doesn't recognise", "does not recognize", "does not recognise", "not recognizing", "not recognising",
               "incoherent", "delirious", "talking nonsense", "talking gibberish", "doesn't know where"],
        "hi": ["भ्रमित", "भ्रम$", "कन्फ्यूज", "पहचान नहीं पा", "पहचान नहीं रहा", "पहचान नहीं रही",
               "बहकी बहकी", "बहकी हुई बातें"],
        "hi_rom": ["bhramit", "bhram$", "confuse*", "pehchan {nahi} pa*", "pehchaan {nahi} pa*", "behki behki"],
        "ta": ["குழப்ப", "குழம்ப", "உளற", "அடையாளம் தெரியவில்லை"],
        "te": ["గందరగోళ", "అయోమయ", "గుర్తు పట్టడం లేదు", "గుర్తుపట్టడం లేదు", "గుర్తు పట్టట్లేదు", "పొంతన లేని మాటలు"],
    },
    "reduced_appetite": {
        "en": ["no appetite", "loss of appetite", "poor appetite", "reduced appetite", "decreased appetite",
               "not eating", "refusing food", "refusing to eat", "won't eat", "doesn't want to eat",
               "does not want to eat", "skipped meals", "not hungry", "hasn't eaten", "has not eaten",
               "eating less", "barely eating", "off his food", "off her food"],
        "hi": ["भूख नहीं", "भूख कम", "खाना नहीं खा", "खाने का मन नहीं", "कम खा", "खाना छोड़"],
        "hi_rom": ["bhookh {nahi}", "bhukh {nahi}", "bhookh kam", "bhukh kam", "khana {nahi} kha*",
                   "khane ka man {nahi}", "kam kha*"],
        "ta": ["பசி இல்லை", "பசியில்லை", "பசி குறை", "சாப்பிடவில்லை", "சாப்பிட மறுக்க"],
        "te": ["ఆకలి లేదు", "ఆకలి తగ్గ", "తినడం లేదు", "తినట్లేదు", "అన్నం తినడం లేదు", "భోజనం చేయడం లేదు",
               "ఆకలిగా లేదు"],
    },
    "abnormal_behavior": {
        "en": ["behaving strangely", "behaving oddly", "acting strange*", "acting odd*", "abnormal behavior",
               "abnormal behaviour", "unusual behavior", "unusual behaviour", "agitated", "restless", "aggressive",
               "wandering", "unresponsive", "not responding", "drowsy", "very sleepy", "sleeping all day",
               "sleeping too much", "excessive sleep*", "hallucinat*", "seeing things", "talking to himself",
               "talking to herself", "irrational", "unusually quiet", "withdrawn"],
        "hi": ["अजीब व्यवहार", "अजीब बर्ताव", "अजीब हरकत", "अजीब सा व्यवहार", "अजीब बातें", "बेचैन", "चिड़चिड़ा",
               "जवाब नहीं दे", "आक्रामक", "बहुत सो रहे", "बहुत सोता", "बहुत सोती"],
        "hi_rom": ["ajeeb vyavhar", "ajeeb vyavahar", "ajeeb bartav", "ajeeb harkat", "ajeeb baatein", "bechain*",
                   "chidchida*", "jawab {nahi} de*"],
        "ta": ["வித்தியாசமாக நடந்து", "விசித்திரமாக நடந்து", "வினோதமாக நடந்து", "அமைதியின்மை", "அமைதியில்லாம",
               "பதிலளிக்கவில்லை", "பதில் சொல்லவில்லை", "அசாதாரண நடத்தை", "ஆக்ரோஷ", "தூக்கக் கலக்கம்"],
        "te": ["వింతగా ప్రవర్తి", "అసాధారణంగా ప్రవర్తి", "చిరాకు", "స్పందించడం లేదు", "స్పందించట్లేదు", "మగత",
               "ఎక్కువగా నిద్ర"],
    },
}

# Symptoms we don't track but that commonly sit in negated lists ("no cough, fever"): they keep a
# comma-separated negation list intact but never produce a finding.
KNOWN_OTHER = {"cough", "cold", "vomiting", "nausea", "headache", "pain", "chills", "swelling", "diarrhea",
               "diarrhoea", "rash", "ache", "sweating", "cramps", "bleeding", "itching", "constipation"}

EN_PRE_NEG = {"no", "not", "without", "denies", "denied", "denying", "never", "none", "negative", "free", "nil",
              "nothing", "nor", "isn't", "isnt", "doesn't", "doesnt", "don't", "dont", "hasn't", "hasnt", "haven't",
              "havent", "didn't", "didnt", "wasn't", "wasnt", "aren't", "arent", "won't", "wont", "bina", "बिना"}
# Post-position negation, exact tokens (Hindi/Hinglish 'nahi', Tamil/Telugu stand-alone words).
POST_NEG_EXACT = {"नहीं", "नही", "nahi", "nahin", "nhi", "nahee", "nai", "absent", "resolved", "gone", "negative",
                  "denied", "இல்லை", "இல்ல", "இல்லாமல்", "లేదు", "లేదని", "లేవు", "లేదండి", "కాదు"}
# Post-position negation as suffix inside the token (Tamil '-வில்லை', Telugu '-లేదు').
POST_NEG_SUFFIX = ("வில்லை", "இல்லை", "లేదు", "లేదని", "లేవు")
POST_NEG_BIGRAMS = {("not", "present"), ("not", "there"), ("no", "more"), ("not", "anymore"), ("not", "now"),
                    ("not", "today"), ("is", "gone"), ("has", "resolved")}

CONTRAST = {"but", "however", "although", "though", "except", "yet", "whereas", "while",
            "लेकिन", "मगर", "परंतु", "lekin", "magar", "parantu", "par",
            "ஆனால்", "ஆனா", "ஆனாலும்", "కానీ", "అయితే", "కాని"}
COORD_INDIC = {"और", "तथा", "aur", "மற்றும்", "మరియు", "ఇంకా"}
AFFIRM_VERBS = {"has", "have", "having", "had", "with", "complains", "complaining", "reports", "reported", "also",
                "developed", "got", "feels", "feeling", "shows", "showing", "is", "was", "seems"}

HIST_WORDS = {"yesterday", "earlier", "previously", "ago", "formerly", "पिछले", "pichle", "நேற்று", "முன்பு",
              "முன்னர்", "கடந்த", "నిన్న", "గతంలో", "గత"}
HIST_BIGRAMS = {("last", "week"), ("last", "month"), ("last", "year"), ("ఇంతకు", "ముందు")}
PRESENT_WORDS = {"still", "today", "now", "again", "currently", "आज", "अभी", "abhi", "aaj", "இன்று", "இப்போது",
                 "ఈరోజు", "ఇప్పుడు", "இன்னும்", "ఇంకా"}
UNCERTAIN_WORDS = {"maybe", "might", "possibly", "perhaps", "seems", "seemed", "unsure", "शायद", "shayad", "लगता",
                   "lagta", "ஒருவேளை", "போல", "బహుశా", "అనిపిస్తోంది"}
UNCERTAIN_BIGRAMS = {("looks", "like"), ("not", "sure"), ("i", "think")}
