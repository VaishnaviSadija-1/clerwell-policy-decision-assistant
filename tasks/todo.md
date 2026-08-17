# CLERWELL Policy Decision Assistant — Build Plan (TDD)

Architecture source of truth: `clerwell_architecture.html`. Tests were written first
(`tests/`) and define every interface. Each task must make its tests pass without
editing the tests.

## Wave 1 — parallel (disjoint files)
- [x] Task 01 — backend/models.py + backend/store.py (Sonnet, medium) → tests/test_models.py, tests/test_store.py
- [x] Task 02 — backend/retrieval.py (Sonnet, high) → tests/test_retrieval.py
- [x] Task 04 — app.py + frontend/ (Sonnet, high) → tests/test_app_api.py (UI parts manual)
- [x] Task 05 — README.md + docs (Sonnet, medium)

## Wave 2 — after 01 & 02
- [x] Task 03 — backend/llm.py + backend/analyzer.py (Sonnet, high) → tests/test_analyzer.py

## Wave 3 — integration (orchestrator)
- [x] Full pytest suite green — 64 passed
- [x] Smoke-launch PyWebView app
- [x] Commit per task, push to GitHub

## Review

- **Tests:** 64/64 passing (`.venv/bin/python -m pytest -q`), LLM fully mocked; the
  only network-adjacent test targets a closed localhost port to prove LLMError handling.
- **Retrieval sanity:** all 20 supplied requests retrieve their governing policy file
  as the top result (checked against the expected-decision map in the architecture doc).
- **Live smoke test:** PyWebView window launched with a scripted probe — 20 request
  rows rendered, selecting a row updates the detail panel, Analyze renders the
  decision badge, policy filename, section, exact passage, and approver roles;
  search filtering works (`refund` → 5 rows).
- **Guardrails verified by tests:** fabricated-quote rejection (exact-substring
  verification + one re-ask), invalid-JSON repair retry then safe fallback,
  provider-down readable error, no-relevant-policy fallback with zero LLM calls,
  prompt-injection defense (request text delimited as data; REQ-020 refused).
- **Per-task commits** pushed to GitHub (private repo
  `VaishnaviSadija-1/clerwell-policy-decision-assistant`).
- **Left for the candidate:** record the 3–5 min demo, flip the repo public for
  submission, and set a real `.env` to demo against a live model (Claude API).
