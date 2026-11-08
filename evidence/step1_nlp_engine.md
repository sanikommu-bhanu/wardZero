# Step 1 — services/nlp_engine — VERIFIED

Command run: `PYTHONPATH=. python3 -m unittest discover -s tests -v`
Result: 20/20 tests pass (see tests/test_nlp_engine.py).

Files:
- services/nlp_engine/lexicon.py — phrase lists (en, hi Devanagari, hi romanized, ta, te) mapped to the
  8 ml.features.schema.NOTE_KEYS, plus negation/history/uncertainty cue word lists. Data only, not code logic.
- services/nlp_engine/engine.py — normalization (accent/nukta/case folding with offset tracking back to the
  original string), phrase matching (longest-match-wins on overlaps), negation scope (pre- and post-position,
  clause-bounded, does not leak across "and"/comma/contrast words), historical vs. present tense, hedging
  ("maybe"/"shayad") flagged as uncertain, multi-language detection, note-length limit (5000 chars), and a
  merge_notes() that combines a patient's note history (latest explicit mention wins; historical never sets
  a signal).

What it deliberately does NOT do (by design, and covered by test_no_clinical_outputs):
- No severity, diagnosis, or recommendation of any kind — only {status: present|negated|historical,
  uncertain: bool, evidence: <verbatim substring>} per matched phrase, plus a boolean signals dict that
  ml/features/engineering.py already consumes as `note_signals`.

Known limitations, stated rather than hidden:
- The Tamil/Telugu/Hindi phrase lists are my own construction, not reviewed by a native speaker or
  clinician. They should be treated as a first draft and expanded/corrected before production use.
- Coverage is keyword/pattern based, not a statistical language model — it will miss phrasings not in the
  lexicon and this is by design (never inventing clinical facts) rather than a bug to silently patch.
- Romanized Hindi matching is fuzzy on vowels/aspiration only; it does not handle all transliteration schemes.
