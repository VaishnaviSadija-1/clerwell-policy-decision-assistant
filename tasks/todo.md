# CLERWELL Policy Decision Assistant — Build Plan (TDD)

Architecture source of truth: `clerwell_architecture.html`. Tests were written first
(`tests/`) and define every interface. Each task must make its tests pass without
editing the tests.

## Wave 1 — parallel (disjoint files)
- [ ] Task 01 — backend/models.py + backend/store.py (Sonnet, medium) → tests/test_models.py, tests/test_store.py
- [ ] Task 02 — backend/retrieval.py (Sonnet, high) → tests/test_retrieval.py
- [ ] Task 04 — app.py + frontend/ (Sonnet, high) → tests/test_app_api.py (UI parts manual)
- [ ] Task 05 — README.md + docs (Sonnet, medium)

## Wave 2 — after 01 & 02
- [ ] Task 03 — backend/llm.py + backend/analyzer.py (Sonnet, high) → tests/test_analyzer.py

## Wave 3 — integration (orchestrator)
- [ ] Full pytest suite green
- [ ] Smoke-launch PyWebView app
- [ ] Commit per task, push to GitHub

## Review
(filled in when complete)
