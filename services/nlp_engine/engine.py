"""Rule-based multilingual caregiver-note extractor.

Contract: output only what the note literally says. Each finding carries the exact evidence substring
from the ORIGINAL text. No severity, diagnosis or advice is produced. `signals` feeds
ml.features.engineering.build_features(note_signals=...).

Finding status:  present | negated | historical      (+ `uncertain` flag on hedged mentions)
signals[key] is True only for present (non-negated, non-historical) mentions; hedged mentions count as
present but are listed in `uncertain` so a human can see they were hedged.
"""
from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass
from ml.features.schema import NOTE_KEYS
from . import lexicon as L

MAX_NOTE_CHARS = 5000
DISCLAIMER = ("Keyword extraction from caregiver text; not a clinical assessment. Absence of a finding "
              "does not mean absence of a symptom.")

_INDIC = "\u0900-\u097F\u0B80-\u0BFF\u0C00-\u0C7F"
_WORDCH = f"A-Za-z0-9{_INDIC}\u200c\u200d"
_TOKEN = re.compile(rf"[{_WORDCH}'\-]+|[,;.!?\u0964\n]")
_HARD = {".", ";", "!", "?", "\u0964", "\n"}
_SCRIPT_RANGES = {"Devanagari": (0x0900, 0x097F), "Tamil": (0x0B80, 0x0BFF), "Telugu": (0x0C00, 0x0C7F)}


def normalize(text: str) -> tuple[str, list[tuple[int, int]]]:
    """Lowercase, unify apostrophes, chandrabindu->anusvara, drop nukta/ZW chars. Returns the normalized
    string and, per normalized char, its (start, end) span in the original (so evidence maps back)."""
    out, spans = [], []
    for i, ch in enumerate(text):
        if ch in "\u2019\u2018`":
            ch = "'"
        for c in unicodedata.normalize("NFD", ch):
            if c in ("\u093c", "\u200c", "\u200d"):
                continue
            if c == "\u0901":
                c = "\u0902"
            for lc in c.lower():
                out.append(lc)
                spans.append((i, i + 1))
    return "".join(out), spans


def _norm_pattern(p: str) -> str:  # lexicon entries go through the same normalization as text
    return normalize(p)[0]


def _en_regex(p: str) -> str:
    wild = p.endswith("*")
    p = p.rstrip("*")
    body = r"\s+".join(re.escape(w).replace("\\'", "['’]?").replace("\\-", r"[-\s]?") for w in p.split())
    return rf"(?<![A-Za-z0-9]){body}" + (r"[A-Za-z]*" if wild else r"(?![A-Za-z0-9])")


def _rom_word(w: str) -> str:
    if w == "{me}":
        return "(?:mein|main|mai|mei|me)"
    if w == "{nahi}":
        return "(?:nahi|nahin|nhi|nahee|nai)"
    parts, i = [], 0
    while i < len(w):
        c = w[i]
        if c in "aeiou":
            j = i
            while j < len(w) and w[j] in "aeiou":
                j += 1
            parts.append("[aeiou]+")
            i = j
            continue
        parts.append("h?" if c == "h" else re.escape(c))
        i += 1
    return "".join(parts)


def _rom_regex(p: str) -> str:
    wild = p.endswith("*")
    p = p.rstrip("*")
    body = r"\s+".join(_rom_word(w) for w in p.split())
    return rf"(?<![A-Za-z0-9]){body}" + (r"[A-Za-z]*" if wild else r"(?![A-Za-z0-9])")


def _indic_regex(p: str) -> str:
    end = p.endswith("$")
    p = p.rstrip("$")
    body = r"\s*".join(re.escape(w) for w in p.split())
    return rf"(?<![{_WORDCH}]){body}" + (rf"(?![{_WORDCH}])" if end else "")


_BUILDERS = {"en": _en_regex, "hi_rom": _rom_regex, "hi": _indic_regex, "ta": _indic_regex, "te": _indic_regex}


def _compile():
    comp = []
    for key, langs in L.LEXICON.items():
        assert key in NOTE_KEYS, f"lexicon key {key} not in schema.NOTE_KEYS"
        for lang, phrases in langs.items():
            for ph in phrases:
                comp.append((key, lang, re.compile(_BUILDERS[lang](_norm_pattern(ph))), ph))
    return comp


_COMPILED = _compile()
assert {c[0] for c in _COMPILED} == set(NOTE_KEYS), "lexicon must cover every NOTE_KEY"
_OTHER_RE = re.compile(r"(?<![a-z])(?:" + "|".join(sorted(L.KNOWN_OTHER)) + r")s?(?![a-z])")


@dataclass
class _Match:
    key: str
    lang: str
    s: int
    e: int
    phrase: str


def _find_matches(norm: str) -> list[_Match]:
    raw = []
    for key, lang, rx, ph in _COMPILED:
        for m in rx.finditer(norm):
            if m.end() > m.start():
                raw.append(_Match(key, lang, m.start(), m.end(), ph))
    # longest span wins on overlap (so 'भूख नहीं' beats any shorter overlapping phrase)
    raw.sort(key=lambda m: (-(m.e - m.s), m.s))
    kept: list[_Match] = []
    for m in raw:
        if not any(m.s < k.e and k.s < m.e for k in kept):
            kept.append(m)
    return sorted(kept, key=lambda m: m.s)


def _tokens(norm: str):
    return [(m.group(), m.start(), m.end()) for m in _TOKEN.finditer(norm)]


def _bigram(toks, i):
    return (toks[i][0], toks[i + 1][0]) if i + 1 < len(toks) else None


def _clause_bounds(toks, idx_lo, idx_hi):
    """Widen [idx_lo, idx_hi] token range to the clause (stop at hard punctuation / contrast words / comma)."""
    lo = idx_lo
    while lo > 0 and toks[lo - 1][0] not in _HARD and toks[lo - 1][0] != "," and toks[lo - 1][0] not in L.CONTRAST:
        lo -= 1
    hi = idx_hi
    while hi + 1 < len(toks) and toks[hi + 1][0] not in _HARD and toks[hi + 1][0] != "," \
            and toks[hi + 1][0] not in L.CONTRAST:
        hi += 1
    return lo, hi


def _analyse_match(m: _Match, toks, matches, norm) -> dict:
    first = next((i for i, t in enumerate(toks) if t[2] > m.s), len(toks))
    last = max((i for i, t in enumerate(toks) if t[1] < m.e), default=first)
    in_other_span = lambda t: any(t[1] < o.e and o.s < t[2] for o in matches if o is not m)
    in_own_span = lambda t: t[1] < m.e and m.s < t[2]
    known_symptom_tok = lambda t: in_other_span(t) or _OTHER_RE.fullmatch(t[0]) is not None

    # --- negation: preceding cue -------------------------------------------------------------
    negated, crossed, steps, affirm_seen = False, False, 0, False
    i = first - 1
    while i >= 0 and steps < 7:
        w, s0, e0 = toks[i]
        if w in _HARD or w in L.CONTRAST:
            break
        if w == ",":
            # comma keeps the scope only inside a list of symptom words: "no fever, chest pain"
            if i > 0 and known_symptom_tok(toks[i - 1]):
                crossed = True
                i -= 1
                continue
            break
        if w in ("and", "or", "nor"):
            if affirm_seen:  # "no cough and HAS fever": a new asserted clause starts here
                break
            crossed = True
        elif w in L.AFFIRM_VERBS:
            if crossed:
                break
            affirm_seen = True
        elif w in L.EN_PRE_NEG and not in_other_span(toks[i]):
            negated = True
            break
        i -= 1
        steps += 1

    # --- negation: following cue (Hindi/Tamil/Telugu are verb-final; also English 'absent') -----
    if not negated:
        rem = norm[m.e: toks[last][2]] if last < len(toks) and toks[last][2] > m.e else ""
        if rem and any(rem.endswith(sfx) or sfx in rem for sfx in L.POST_NEG_SUFFIX):
            negated = True
        j, steps = last + 1, 0
        while not negated and j < len(toks) and steps < 4:
            w, s0, e0 = toks[j]
            if w in _HARD or w == "," or w in L.CONTRAST or w in L.COORD_INDIC:
                break
            if any(o.s == s0 or (s0 < o.e and o.s < e0) for o in matches if o is not m):
                break  # another finding starts here: its own cue words are not ours
            if w in L.POST_NEG_EXACT or any(sfx in w for sfx in L.POST_NEG_SUFFIX):
                negated = True
                break
            bg = _bigram(toks, j)
            if bg in L.POST_NEG_BIGRAMS:
                negated = True
                break
            j += 1
            steps += 1

    # --- history / hedging inside the same clause ----------------------------------------------
    lo, hi = _clause_bounds(toks, first, last)
    cw = [t[0] for t in toks[lo:hi + 1]]
    cbig = set(zip(cw, cw[1:]))
    hist = bool(set(cw) & L.HIST_WORDS or cbig & L.HIST_BIGRAMS) and not (set(cw) & L.PRESENT_WORDS)
    unc = bool(set(cw) & L.UNCERTAIN_WORDS or cbig & L.UNCERTAIN_BIGRAMS)
    status = "negated" if negated else ("historical" if hist else "present")
    return {"status": status, "uncertain": unc and status == "present"}


def _detect_languages(text: str, findings: list[dict]) -> list[str]:
    counts: dict[str, int] = {}
    for name, (a, b) in _SCRIPT_RANGES.items():
        n = sum(1 for c in text if a <= ord(c) <= b)
        if n:
            counts[{"Devanagari": "hi", "Tamil": "ta", "Telugu": "te"}[name]] = n
    for f in findings:
        counts[f["language"]] = counts.get(f["language"], 0) + 1000
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    if latin and not any(k in counts for k in ("en", "hi_rom")):
        counts["en"] = 1  # unmatched Latin text: assume English, flagged low-confidence by caller via no findings
    return [("hi-Latn" if k == "hi_rom" else k) for k, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


def analyze_note(text: str) -> dict:
    """Extract structured signals from one note. Raises ValueError on non-string / oversize input."""
    if not isinstance(text, str):
        raise ValueError("note text must be a string")
    if len(text) > MAX_NOTE_CHARS:
        raise ValueError(f"note too long ({len(text)} > {MAX_NOTE_CHARS} chars)")
    norm, spans = normalize(text)
    matches = _find_matches(norm)
    toks = _tokens(norm)
    findings = []
    for m in matches:
        a = _analyse_match(m, toks, matches, norm)
        e_ext = m.e
        if m.lang in ("hi", "ta", "te"):  # stem matches: show the whole word as evidence
            while e_ext < len(norm) and re.match(rf"[{_WORDCH}]", norm[e_ext]):
                e_ext += 1
        os_, oe = spans[m.s][0], spans[e_ext - 1][1]
        findings.append({"key": m.key, "status": a["status"], "uncertain": a["uncertain"],
                         "evidence": text[os_:oe], "language": m.lang, "span": [os_, oe]})
    signals = {k: False for k in NOTE_KEYS}
    for f in findings:
        if f["status"] == "present":
            signals[f["key"]] = True
    by = lambda st: sorted({f["key"] for f in findings if f["status"] == st and not signals[f["key"]]}) \
        if st != "present" else sorted(k for k, v in signals.items() if v)
    return {
        "signals": signals,
        "findings": findings,
        "present": by("present"),
        "negated": by("negated"),
        "historical": by("historical"),
        "uncertain": sorted({f["key"] for f in findings if f["uncertain"]}),
        "languages": _detect_languages(text, findings) if text.strip() else [],
        "recognized": bool(findings),
        "lexicon_version": L.LEXICON_VERSION,
        "disclaimer": DISCLAIMER,
    }


def merge_notes(results: list[dict]) -> dict[str, bool]:
    """Combine several analysed notes (oldest -> newest). For each symptom the most recent explicit mention
    (present or negated) wins; historical mentions never set a signal."""
    state: dict[str, bool] = {k: False for k in NOTE_KEYS}
    for r in results:
        for f in r["findings"]:
            if f["status"] == "present":
                state[f["key"]] = True
            elif f["status"] == "negated":
                state[f["key"]] = False
    return state
