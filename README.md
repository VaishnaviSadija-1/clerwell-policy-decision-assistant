# CLERWELL Policy Decision Assistant

A desktop application (PyWebView) that evaluates employee and customer requests
against five supplied company policies and returns a structured, policy-grounded
decision: the decision itself, supporting evidence quoted verbatim from policy,
missing information, and approval requirements.

## 1. Installation and launch

Requires Python 3.11+ (see [Python version](#2-python-version-and-dependencies) below).

```bash
python3.11 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then edit .env with your provider details
python app.py
```

This opens a native desktop window titled "CLERWELL Policy Decision Assistant"
(~1200x800) built with [PyWebView](https://pywebview.flowrl.com/). PyWebView picks
a platform-appropriate rendering backend automatically:

- **macOS** — WKWebView (Cocoa), no extra install needed.
- **Windows** — Edge WebView2 (bundled with modern Windows; install the
  [WebView2 runtime](https://developer.microsoft.com/microsoft-edge/webview2/) if missing).
- **Linux** — GTK WebKit2 (`python3-gi`, `gir1.2-webkit2-4.0` or QT via `pywebview[qt]`).

## 2. Python version and dependencies

- **Python 3.11 or newer** (developed and tested on 3.12).
- Dependencies, from `requirements.txt`:

| Package | Purpose |
|---|---|
| `pywebview` | Native desktop window + `js_api` bridge between JS and Python |
| `pydantic` | Typed, validated `AnalysisResult` schema (v2) |
| `python-dotenv` | Loads `.env` for LLM provider configuration |
| `pytest` | Automated test suite |
| `requests` | HTTP calls to the OpenAI-compatible chat-completions endpoint |

No vector database or heavyweight ML/embedding library is used — see
[Retrieval approach](#5-retrieval-approach).

## 3. Model/provider configuration

Copy `.env.example` to `.env` and fill in your provider:

```bash
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-api-key-here
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=45
```

Any **OpenAI-compatible** chat-completions endpoint works — hosted (OpenAI,
Groq, Together, etc.) or local. For **Ollama**, run a model locally and set:

```bash
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=llama3.1
```

`backend/llm.py` reads these four variables (`LLM_BASE_URL`, `LLM_API_KEY`,
`LLM_MODEL`, `LLM_TIMEOUT_SECONDS`) via `python-dotenv`, with constructor
arguments taking priority over env vars for testability. If no provider is
reachable, the app never crashes — `analyze()` returns
`{"ok": false, "error": "Language model unavailable — check provider settings and try again."}`,
which the UI renders as a readable error state with a "Try again" button.

## 4. How PyWebView connects frontend and Python

`app.py` creates a `webview.create_window(..., js_api=create_api())` window
pointed at `frontend/index.html`. This exposes an `Api` object to the page as
`window.pywebview.api`.

- The frontend waits for the `pywebviewready` event (fired once the bridge is
  attached) before touching `window.pywebview.api`.
- `Api.get_requests()` returns all 20 requests as plain JSON-serializable
  dicts, used to populate the request list on load.
- `Api.analyze(request_id)` delegates to `Analyzer.analyze(request_id)` and
  always returns a JSON-serializable dict — `{"ok": true, "result": {...}}` or
  `{"ok": false, "error": "..."}` — never raises.
- Every `js_api` call from JavaScript (`window.pywebview.api.analyze(id)`)
  returns a **Promise**; the frontend `await`s it and updates the result
  panel. PyWebView already runs `js_api` calls on a background thread, so the
  UI thread — and the rest of the interface — stays responsive while an
  analysis is in flight (loading state shown, Analyze button disabled, other
  interactions still work).

## 5. Retrieval approach

`backend/retrieval.py` implements a lightweight, stdlib-only keyword search —
no embeddings, no vector database, which would be over-engineering for five
short markdown documents:

1. **Parsing** — each policy file in `policies/` is split into sections on
   `## ` headings. A `PolicySection` holds `policy_file` (basename),
   `section` (the heading text), and `text` (the exact verbatim body of that
   section, not bleeding into the next one). Content before the first `## `
   (title/version lines) is not indexed as a section.
2. **Scoring** — `PolicyIndex.search(query, metadata=None, top_k=6)`
   tokenizes and lowercases the query and section text, filters trivial stop
   words, and scores by token overlap with boosts for domain terms (leave,
   refund, discount, expense, credential, etc.). Request `metadata` (e.g.
   `{"leave_type": "sick"}`) is folded into the query signal so structured
   fields help retrieval, not just free text.
3. **Thresholding** — only sections scoring above a calibrated relevance
   threshold are returned, sorted descending, capped at `top_k`. Irrelevant/
   gibberish queries return `[]` (and this short-circuits the analyzer — see
   below), while each of the 20 real requests in `data/requests.json` still
   retrieves its governing policy.
4. **Grounding** — `PolicyIndex.verify_passage(policy_file, passage)` checks
   that a quoted passage is an **exact substring** of the raw policy file
   content (no normalization, no fuzzy match). This is the mechanism used to
   catch fabricated quotes post-hoc (see below).

The top-scoring sections are quoted **verbatim** into the LLM prompt so the
model only ever sees real policy text to ground its answer in.

## 6. Structured output

`backend/models.py` defines the result contract with Pydantic v2, per
`OUTPUT_SCHEMA.md`:

- `Decision(str, Enum)` — `eligible`, `not_eligible`, `needs_information`,
  `requires_approval`.
- `Evidence` — `policy_file`, `section`, `passage` (all required strings).
- `Approval` — `required: bool`, `approver_roles: list[str]`,
  `reason: str`.
- `AnalysisResult` — `request_id`, `decision`, `summary`,
  `supporting_evidence: list[Evidence]`, `missing_information: list[str]`,
  `approval: Approval`, `confidence: float` (0-1).

Cross-field validation (a `model_validator`) enforces:

- `approval.required == (decision == "requires_approval")`.
- if `approval.required` is `True`, `approver_roles` must be non-empty.
- `missing_information` must genuinely be a list (a plain string is rejected,
  not silently coerced).

`decision` serializes as a plain string on `model_dump()` so the result is
directly JSON-safe for the `js_api` bridge.

**Validation pipeline** (`backend/analyzer.py`): the LLM's raw text response
is stripped of markdown code fences, parsed as JSON, and validated against
`AnalysisResult`. If parsing or validation fails, the analyzer does **one
repair retry** — a second `llm.complete()` call whose prompt includes the
invalid output and the validation error, asking the model to return corrected
JSON. If that also fails, the analyzer falls back to a safe, schema-valid
`AnalysisResult` (`needs_information`, with a summary noting the model
returned invalid output) rather than crashing or returning malformed data.

After validation, each piece of `supporting_evidence` is checked with
`index.verify_passage()`. A fabricated (non-verbatim) passage triggers one
re-ask telling the model which quote failed. If it's still unverifiable, that
evidence is dropped and the result is downgraded to `needs_information`
(with `approval.required` reset to `False`) rather than shown to the
reviewer as fact. The analyzer makes at most 2 LLM calls per `analyze()`.

## 7. Failure and missing-information handling

| Condition | Behavior |
|---|---|
| Unknown/missing `request_id` | `analyze()` returns `{"ok": false, "error": "..."}` naming the id; no LLM call. |
| No relevant policy found | `index.search()` returns `[]` → no LLM call; a safe `needs_information` fallback is returned (`approval.required=False`, summary explicitly says no applicable policy was found). |
| Invalid/malformed model output | Bad JSON or a schema violation triggers one repair retry; still-invalid output falls back to a safe, schema-valid `needs_information` result rather than propagating an error. |
| Provider unreachable / times out | `backend/llm.py` raises `LLMError` on network errors, timeouts, or non-2xx responses (no raw traceback text); the analyzer converts this into a readable error, and the UI shows it with a "Try again" button. |
| Prompt injection in policy or request text | Policy and request content is treated as **data, not instructions**. The system prompt explicitly tells the model to ignore any instructions embedded in the request text, and the request JSON is wrapped between literal `BEGIN REQUEST DATA` / `END REQUEST DATA` markers in the user prompt so it can never be confused with system rules. Security-sensitive requests (e.g. asking to disclose credentials, per `information_security_and_privacy_policy.md`) are expected to resolve to `not_eligible` and be escalated, grounded in the "Secrets" policy passage — never silently complied with. |

## 8. Tests and how to run them

```bash
python -m pytest
```

or, from a fresh venv:

```bash
.venv/bin/python -m pytest -q
```

The suite (`tests/`) covers, with a mocked LLM (`FakeLLM` in
`tests/conftest.py` — no network/paid API call is ever made):

- `test_models.py` — Pydantic schema validation and cross-field rules.
- `test_store.py` — read-only request loading, deep-copy semantics.
- `test_retrieval.py` — section parsing, keyword scoring/threshold,
  passage verification.
- `test_analyzer.py` — the three required scenarios (straightforward
  decision, missing information, approval required) plus edge cases:
  fabricated-passage re-ask and downgrade, invalid/malformed JSON repair and
  fallback, provider-down handling, unknown request id, no-relevant-policy
  fallback, prompt-injection delimiting, and a real-client offline test
  (`OpenAICompatClient` against a closed local port raising `LLMError`).
- `test_app_api.py` — the `js_api` bridge (`create_api`, `get_requests`,
  `analyze`) returns JSON-serializable results and never raises.

## 9. Known limitations

- **Keyword retrieval, not semantic search** — scoring is token-overlap
  based; it is calibrated against the 20 supplied requests but may miss
  paraphrases outside that distribution. No embeddings or vector store are
  used (intentionally, given the small, fixed corpus).
- **No analysis history persistence** — each analysis is stateless; nothing
  is written back to disk or a database between runs.
- **Single-window desktop app** — no multi-window, tabs, or multi-user
  session support.
- **English-only** — policies, requests, and prompts assume English text.
- **LLM output quality depends on the configured model** — a weaker or
  smaller local model may need more repair retries or fall back to
  `needs_information` more often; results are only as good as the underlying
  model's instruction-following.
- **`data/requests.json` is never modified** — the app is read-only against
  the supplied source data by design.

## 10. Production improvements

- Build an **evaluation harness** over the 20 labeled requests (and more)
  to track decision accuracy, evidence-grounding rate, and missing-information
  precision/recall against expected answers over time.
- **Caching** of retrieval results and/or LLM responses for identical
  request/policy states to cut latency and cost.
- **Streaming** the LLM response to the UI instead of waiting for the full
  completion, for a more responsive feel on slower models.
- **Telemetry and trace IDs** — structured logging per analysis (retrieval
  scores, retry counts, latency) to debug and monitor decision quality in
  production.
- **Packaging** — ship as a signed, installable desktop binary (e.g. via
  PyInstaller/briefcase) instead of running from source.
- **CI** — run `pytest` (and linting) automatically on every push/PR.

## AI-assisted development disclosure

This project was built with the assistance of **Claude Code** (Anthropic).
The submitted implementation is understood by the author and can be modified
or explained on request.
