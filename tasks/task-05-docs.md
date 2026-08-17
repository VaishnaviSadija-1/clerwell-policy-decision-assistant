# Task 05 — README + submission docs (complexity: medium)

Rewrite `README.md` (the supplied package README is preserved in git history — replace
it). Do not touch any other file except creating `docs/` if helpful (prefer a single
README).

The README must cover all 10 required sections from ASSIGNMENT.md:
1. Installation and launch (python3.11+ venv, pip install -r requirements.txt,
   `python app.py`; note macOS/Windows/Linux pywebview backends).
2. Python version (3.11+; developed on 3.12) and dependency list with one-line purpose each.
3. Model/provider configuration: .env from .env.example; any OpenAI-compatible API or
   Ollama (`LLM_BASE_URL=http://localhost:11434/v1`); the app degrades gracefully to a
   readable error when no provider is reachable.
4. How PyWebView connects frontend↔Python: js_api bridge, `window.pywebview.api.analyze()`
   promises, pywebviewready event, calls run off the UI thread.
5. Retrieval approach: policies parsed into ## sections; keyword scoring with a
   relevance threshold; top-k sections quoted verbatim into the prompt; no vector DB
   (right-sized for 5 short documents).
6. Structured output: Pydantic v2 AnalysisResult (+Decision enum, Evidence, Approval),
   cross-field consistency rules, one repair retry feeding validation errors back to
   the model, post-hoc exact-substring passage verification.
7. Failure handling: unknown request, no relevant policy (safe needs_information
   fallback), invalid model output (repair retry then safe fallback), provider down
   (readable error + retry), prompt injection (request text delimited as data; system
   rules; REQ-020-style requests refused and escalated per the security policy).
8. Tests: `python -m pytest` — suite covers straightforward/missing-info/approval
   cases and all edge cases with a mocked LLM; no paid API call needed.
9. Known limitations (honest: keyword retrieval, no analysis history persistence,
   single-window, English-only, LLM quality depends on chosen model).
10. Production improvements (eval harness over the 20 labeled cases, caching,
    streaming, telemetry/trace ids, packaging, CI).

Also state AI-assisted development disclosure: built with Claude Code (Anthropic).

Keep it crisp, use the real file names, include exact commands in fenced bash blocks.
Base every claim on the actual files in the repo — read tests/ and tasks/ first;
if implementation files are missing while you write, describe the contracts from the
task files (they are the source of truth and will be implemented exactly).

## Verify
README renders correctly (markdown lint by eye), all commands are correct for this
repo layout. Report a section checklist.
