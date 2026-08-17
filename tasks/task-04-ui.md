# Task 04 — PyWebView app + frontend (complexity: high)

Create: `app.py`, `frontend/index.html`, `frontend/app.js`, `frontend/styles.css`.
Do not touch any other file. Do not edit tests.

Follow `UI_REQUIREMENTS.md` and `clerwell_architecture.html` §1/§3. Backend modules
(backend/models.py, store.py, retrieval.py, llm.py, analyzer.py) may not all exist yet —
code against these contracts and guard imports so `import app` never fails hard at
import time... actually they WILL exist by integration time; import normally at module
top: `from backend.store import RequestStore`, `from backend.retrieval import
PolicyIndex`, `from backend.analyzer import Analyzer`, `from backend.llm import
OpenAICompatClient`. If they are missing while you develop, create nothing — just make
sure app.py is correct against the contracts below and verify what you can.

## app.py (contract fixed by tests/test_app_api.py)
- `create_api(llm_client=None) -> Api` — builds RequestStore(data/requests.json),
  PolicyIndex(policies/), Analyzer(store, index, llm_client or OpenAICompatClient()).
  Paths resolved relative to this file, not CWD.
- `class Api` (the pywebview js_api):
  - `get_requests() -> list[dict]` — all 20 records, JSON-serializable.
  - `analyze(request_id) -> dict` — delegates to Analyzer.analyze; any exception (and
    request_id=None) is caught and returned as {"ok": False, "error": "<readable>"}.
    PyWebView already runs js_api calls off the UI thread, so no extra threading needed;
    the JS side handles async via the returned promise.
- `if __name__ == "__main__":` load_dotenv(), webview.create_window("CLERWELL Policy
  Decision Assistant", "frontend/index.html", js_api=create_api(), width~1200,
  height~800), webview.start(). Importing app must NOT open a window or start webview.

## Frontend (plain HTML/CSS/JS, no frameworks, no CDN — must work offline)
Single-window two/three-pane layout per UI_REQUIREMENTS.md:
1. Left: request list — ID, requester type badge (employee/customer), requester name,
   ~80-char preview of request_text. Search box (matches text + requester) and a
   requester-type filter (All/Employee/Customer). Selected row highlighted.
2. Middle/right: request detail — full request_text plus all metadata key/values,
   submitted_at, and a prominent "Analyze" button.
3. Result panel:
   - decision badge color-coded: eligible=green, not_eligible=red,
     needs_information=amber, requires_approval=blue.
   - summary/explanation text; confidence shown (e.g. small meter or %).
   - supporting evidence list: policy filename + section heading + exact passage
     (styled as a quote).
   - missing information: list, or an explicit "None" state.
   - approval block: required yes/no, approver role chips, reason.
4. States: empty (no request selected), loading (spinner/disabled Analyze while
   `pywebview.api.analyze` promise is pending — UI stays interactive), error (readable
   message + "Try again" button that re-runs the same analysis), success.
- Wait for `pywebviewready` event before calling `window.pywebview.api`.
- Never hard-code results by request id.
- Escape all request/policy content when injecting into the DOM (textContent or an
  escape helper) — request text may contain hostile HTML/instructions.
- Clean, professional look (system font stack fine); no responsiveness requirements.

## Verify
- `.venv/bin/python -m pytest tests/test_app_api.py -q` from the repo root must pass
  IF backend modules exist by then; if they don't yet, verify `python -c "import ast;
  ast.parse(open('app.py').read())"` and validate the HTML/JS by review.
- Do not launch the webview window yourself (the orchestrator smoke-tests it).
Report what you verified.
