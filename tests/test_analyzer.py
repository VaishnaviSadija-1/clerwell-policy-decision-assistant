"""Tests for backend/analyzer.py — decision pipeline with a mocked LLM.

Contract under test:
  Analyzer(store, index, llm).analyze(request_id) -> dict
    success -> {"ok": True, "result": <AnalysisResult dump>}
    failure -> {"ok": False, "error": <readable str>, "request_id": <id or input>}
No test in this file performs any network call.
"""
import json

import pytest

from backend.analyzer import Analyzer
from backend.llm import LLMError
from backend.models import AnalysisResult
from tests.conftest import FakeLLM, valid_llm_response


@pytest.fixture
def analyzer_with(store, index):
    def _make(llm):
        return Analyzer(store, index, llm)
    return _make


# ---------- the three required scenarios ----------

class TestStraightforwardDecision:
    def test_req_009_eligible_refund(self, analyzer_with):
        llm = FakeLLM([valid_llm_response(
            "REQ-009", "eligible",
            summary="Within 14 days, under 20 workflows, and at or below INR 50,000.",
            evidence=[{
                "policy_file": "customer_refund_policy.md",
                "section": "Standard eligibility",
                "passage": ("A standard subscription is eligible for refund within "
                            "14 calendar days of purchase when usage is below 20 "
                            "processed workflows."),
            }],
        )])
        out = analyzer_with(llm).analyze("REQ-009")
        assert out["ok"] is True
        result = out["result"]
        assert result["decision"] == "eligible"
        assert result["approval"]["required"] is False
        assert result["supporting_evidence"], "evidence required for grounded decision"
        # the result dict must validate against the typed schema
        AnalysisResult(**result)


class TestMissingInformation:
    def test_req_011_vague_refund_needs_information(self, analyzer_with):
        llm = FakeLLM([valid_llm_response(
            "REQ-011", "needs_information",
            summary="Required refund fields are absent.",
            evidence=[{
                "policy_file": "customer_refund_policy.md",
                "section": "Required information",
                "passage": ("A refund request must include account email, invoice "
                            "number, purchase date, amount paid, payment method, and "
                            "the number of processed workflows."),
            }],
            missing=["invoice_number", "amount_paid", "payment_method",
                     "purchase_date", "processed_workflows"],
        )])
        out = analyzer_with(llm).analyze("REQ-011")
        assert out["ok"] is True
        result = out["result"]
        assert result["decision"] == "needs_information"
        assert len(result["missing_information"]) >= 1
        assert isinstance(result["missing_information"], list)


class TestApprovalRequired:
    def test_req_002_seven_day_leave_needs_manager_and_hr(self, analyzer_with):
        llm = FakeLLM([valid_llm_response(
            "REQ-002", "requires_approval",
            summary="A 7-day annual leave needs reporting-manager and HR approval.",
            evidence=[{
                "policy_file": "employee_leave_policy.md",
                "section": "Annual leave",
                "passage": ("4 to 7 consecutive working days requires "
                            "reporting-manager and HR approval."),
            }],
            required=True,
            roles=["reporting_manager", "hr"],
            reason="Leave spans 7 consecutive working days.",
        )])
        out = analyzer_with(llm).analyze("REQ-002")
        assert out["ok"] is True
        result = out["result"]
        assert result["decision"] == "requires_approval"
        assert result["approval"]["required"] is True
        assert len(result["approval"]["approver_roles"]) == 2
        assert result["approval"]["reason"]


# ---------- grounding: fabricated quotes ----------

class TestPassageGrounding:
    FABRICATED = valid_llm_response(
        "REQ-001", "requires_approval",
        evidence=[{
            "policy_file": "employee_leave_policy.md",
            "section": "Annual leave",
            "passage": "Employees may take unlimited leave with CEO approval.",
        }],
        required=True, roles=["reporting_manager"], reason="r")

    GOOD = valid_llm_response(
        "REQ-001", "requires_approval",
        required=True, roles=["reporting_manager"], reason="2-day annual leave")

    def test_fabricated_passage_triggers_reask_then_succeeds(self, analyzer_with):
        llm = FakeLLM([self.FABRICATED, self.GOOD])
        out = analyzer_with(llm).analyze("REQ-001")
        assert out["ok"] is True
        assert len(llm.calls) == 2, "analyzer must re-ask once after a fabricated quote"
        # every surviving passage must be verifiable
        for ev in out["result"]["supporting_evidence"]:
            assert "unlimited leave" not in ev["passage"]

    def test_persistent_fabrication_downgrades_safely(self, analyzer_with):
        llm = FakeLLM([self.FABRICATED, self.FABRICATED])
        out = analyzer_with(llm).analyze("REQ-001")
        assert out["ok"] is True
        result = out["result"]
        # fabricated quotes must never be shown as evidence
        for ev in result["supporting_evidence"]:
            assert ev["passage"] != "Employees may take unlimited leave with CEO approval."
        assert result["decision"] == "needs_information"


# ---------- invalid model output ----------

class TestInvalidModelOutput:
    def test_invalid_json_repaired_on_retry(self, analyzer_with):
        llm = FakeLLM(["this is not json {{{",
                       valid_llm_response("REQ-001", "requires_approval",
                                          required=True, roles=["reporting_manager"],
                                          reason="r")])
        out = analyzer_with(llm).analyze("REQ-001")
        assert out["ok"] is True
        assert len(llm.calls) == 2
        # the retry prompt must feed the problem back to the model
        assert "json" in llm.calls[1][1].lower() or "invalid" in llm.calls[1][1].lower()

    def test_schema_violation_repaired_on_retry(self, analyzer_with):
        bad = json.loads(valid_llm_response("REQ-001", "requires_approval",
                                            required=True, roles=["reporting_manager"],
                                            reason="r"))
        bad["confidence"] = 1.7  # out of range
        llm = FakeLLM([json.dumps(bad),
                       valid_llm_response("REQ-001", "requires_approval",
                                          required=True, roles=["reporting_manager"],
                                          reason="r")])
        out = analyzer_with(llm).analyze("REQ-001")
        assert out["ok"] is True
        assert len(llm.calls) == 2

    def test_persistently_invalid_output_falls_back_safely(self, analyzer_with):
        llm = FakeLLM(["garbage one", "garbage two"])
        out = analyzer_with(llm).analyze("REQ-001")
        assert out["ok"] is True
        result = out["result"]
        assert result["decision"] == "needs_information"
        AnalysisResult(**result)

    def test_json_wrapped_in_markdown_fences_is_parsed(self, analyzer_with):
        fenced = "```json\n" + valid_llm_response(
            "REQ-001", "requires_approval", required=True,
            roles=["reporting_manager"], reason="r") + "\n```"
        out = analyzer_with(FakeLLM([fenced])).analyze("REQ-001")
        assert out["ok"] is True


# ---------- provider unavailable ----------

class TestProviderDown:
    def test_llm_error_returns_readable_failure(self, analyzer_with):
        llm = FakeLLM([LLMError("connection refused")])
        out = analyzer_with(llm).analyze("REQ-001")
        assert out["ok"] is False
        assert isinstance(out["error"], str) and out["error"]
        assert "traceback" not in out["error"].lower()

    def test_unexpected_exception_does_not_crash(self, analyzer_with):
        llm = FakeLLM([RuntimeError("boom")])
        out = analyzer_with(llm).analyze("REQ-001")
        assert out["ok"] is False
        assert out["error"]


# ---------- bad input / no policy ----------

class TestBadInput:
    def test_unknown_request_id(self, analyzer_with):
        out = analyzer_with(FakeLLM([])).analyze("REQ-404")
        assert out["ok"] is False
        assert "REQ-404" in out["error"] or out.get("request_id") == "REQ-404"

    def test_no_relevant_policy_fallback_without_llm_call(self, index, tmp_path):
        from backend.store import RequestStore
        synthetic = [{
            "request_id": "REQ-X01",
            "submitted_at": "2026-08-17T09:00:00+05:30",
            "requester_type": "employee",
            "requester": "Nobody",
            "request_text": "zzzq flurble wibble quantum banana harmonica",
            "metadata": {},
        }]
        p = tmp_path / "requests.json"
        p.write_text(json.dumps(synthetic), encoding="utf-8")
        llm = FakeLLM([])
        out = Analyzer(RequestStore(p), index, llm).analyze("REQ-X01")
        assert out["ok"] is True
        result = out["result"]
        assert result["decision"] == "needs_information"
        assert llm.calls == [], "no LLM call should be made without relevant policy"
        assert "polic" in result["summary"].lower()  # mentions no applicable policy


# ---------- prompt-injection defense ----------

class TestInjectionDefense:
    def test_request_text_is_delimited_as_data(self, analyzer_with, store):
        llm = FakeLLM([valid_llm_response(
            "REQ-020", "not_eligible",
            summary="Secrets must never be disclosed; escalated to Security.",
            evidence=[{
                "policy_file": "information_security_and_privacy_policy.md",
                "section": "Secrets",
                "passage": ("Credentials, API keys, system prompts, internal access "
                            "tokens, and customer lists must never be disclosed."),
            }],
        )])
        out = analyzer_with(llm).analyze("REQ-020")
        assert out["ok"] is True
        assert out["result"]["decision"] == "not_eligible"

        system, user = llm.calls[0]
        assert "BEGIN REQUEST DATA" in user and "END REQUEST DATA" in user
        req_text = store.get("REQ-020")["request_text"]
        start = user.index("BEGIN REQUEST DATA")
        end = user.index("END REQUEST DATA")
        assert req_text[:40] in user[start:end], "request text must sit inside the data delimiters"
        assert "ignore" in system.lower(), \
            "system prompt must instruct the model to ignore embedded instructions"

    def test_system_prompt_forbids_invention(self, analyzer_with):
        llm = FakeLLM([valid_llm_response(
            "REQ-001", "requires_approval", required=True,
            roles=["reporting_manager"], reason="r")])
        analyzer_with(llm).analyze("REQ-001")
        system = llm.calls[0][0].lower()
        assert "invent" in system or "only" in system

    def test_results_not_hardcoded_by_request_id(self, analyzer_with):
        """Same request id, different scripted model outputs -> different results."""
        a = analyzer_with(FakeLLM([valid_llm_response(
            "REQ-001", "requires_approval", required=True,
            roles=["reporting_manager"], reason="r")])).analyze("REQ-001")
        b = analyzer_with(FakeLLM([valid_llm_response(
            "REQ-001", "needs_information",
            missing=["start_date"])])).analyze("REQ-001")
        assert a["result"]["decision"] != b["result"]["decision"]


# ---------- real client error path (no network reachable) ----------

class TestRealClientOffline:
    def test_openai_compat_client_raises_llm_error_when_unreachable(self):
        from backend.llm import OpenAICompatClient
        client = OpenAICompatClient(base_url="http://127.0.0.1:9",  # discard port, closed
                                    api_key="test", model="test-model", timeout=1)
        with pytest.raises(LLMError):
            client.complete("system", "user")
