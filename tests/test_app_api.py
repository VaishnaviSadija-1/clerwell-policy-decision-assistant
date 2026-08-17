"""Tests for app.py — the PyWebView js_api bridge class (no window is opened)."""
import json

from tests.conftest import FakeLLM, valid_llm_response


def make_api(llm=None):
    from app import create_api
    return create_api(llm_client=llm or FakeLLM([]))


class TestApiBridge:
    def test_importing_app_does_not_open_a_window(self):
        import app  # noqa: F401  — must not call webview.start() on import

    def test_get_requests_returns_all_20(self):
        api = make_api()
        reqs = api.get_requests()
        assert len(reqs) == 20
        first = reqs[0]
        for key in ("request_id", "requester_type", "requester", "request_text"):
            assert key in first

    def test_get_requests_is_json_serializable(self):
        json.dumps(make_api().get_requests())

    def test_analyze_delegates_and_returns_serializable_dict(self):
        llm = FakeLLM([valid_llm_response(
            "REQ-001", "requires_approval", required=True,
            roles=["reporting_manager"], reason="2-day annual leave")])
        out = make_api(llm).analyze("REQ-001")
        assert out["ok"] is True
        json.dumps(out)

    def test_analyze_bad_id_returns_error_not_exception(self):
        out = make_api().analyze("NOPE-1")
        assert out["ok"] is False
        assert out["error"]

    def test_analyze_none_id_handled(self):
        out = make_api().analyze(None)
        assert out["ok"] is False
