# Task 02 — Policy retrieval engine (complexity: high)

Create exactly one file: `backend/retrieval.py`. Do not touch any other file. Do not edit tests.

## Requirements (interface fixed by tests/test_retrieval.py)
- `PolicySection` (dataclass or model) with attributes: policy_file (basename str),
  section (H2 heading text without `## `), text (the exact raw text of that section's body).
- `PolicyIndex(policies_dir)`:
  - parses every `*.md` in the dir, splitting into sections on `## ` headings;
    content before the first `## ` (title line, version line) is not a section.
  - `.sections: list[PolicySection]` — section text must be exact (verbatim from file)
    and must not bleed into the next section.
  - `.search(query: str, metadata: dict | None = None, top_k: int = 6) -> list[tuple[PolicySection, float]]`
    - keyword scoring (token overlap / TF-IDF / BM25-lite — your choice, stdlib only).
    - Tokenize with lowercasing; ignore trivial stopwords. Consider bigram or
      substring boosts for domain words (leave, refund, discount, expense, credential…).
    - metadata values (e.g. {"leave_type": "sick"}) should contribute to the query signal.
    - returns ONLY results scoring above a relevance threshold, sorted descending,
      at most top_k. Gibberish (e.g. "zzzq flurble wibble quantum banana harmonica")
      must return `[]`. All returned scores must be > 0.
    - Calibrate the threshold so that each of the 20 real requests in data/requests.json
      still retrieves its governing policy (spot-check leave/refund/discount/security
      examples in the tests).
  - `.verify_passage(policy_file: str, passage: str) -> bool` — True iff passage is an
    EXACT substring of the raw file content of that specific file. No normalization,
    no fuzzy matching. Unknown file -> False.

No third-party dependencies (stdlib only). No LLM calls.

## Verify
Run: `.venv/bin/python -m pytest tests/test_retrieval.py -q` from the repo root — all tests must pass. Report the final pytest output.
