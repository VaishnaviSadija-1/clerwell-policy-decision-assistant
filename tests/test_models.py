"""Tests for backend/models.py — Pydantic schema and consistency rules."""
import pytest
from pydantic import ValidationError

from backend.models import AnalysisResult, Approval, Decision, Evidence


def make_result(**overrides):
    base = {
        "request_id": "REQ-001",
        "decision": "requires_approval",
        "summary": "Two days of annual leave needs reporting-manager approval.",
        "supporting_evidence": [{
            "policy_file": "employee_leave_policy.md",
            "section": "Annual leave",
            "passage": "Up to 3 consecutive working days requires reporting-manager approval.",
        }],
        "missing_information": [],
        "approval": {
            "required": True,
            "approver_roles": ["reporting_manager"],
            "reason": "Leave of 2 consecutive working days.",
        },
        "confidence": 0.94,
    }
    base.update(overrides)
    return base


class TestDecisionEnum:
    def test_exactly_four_allowed_values(self):
        assert {d.value for d in Decision} == {
            "eligible", "not_eligible", "needs_information", "requires_approval",
        }

    def test_decision_serializes_to_plain_string(self):
        r = AnalysisResult(**make_result())
        assert r.model_dump()["decision"] == "requires_approval"

    def test_invalid_decision_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisResult(**make_result(decision="approved"))


class TestEvidence:
    def test_fields(self):
        e = Evidence(policy_file="a.md", section="S", passage="P")
        assert (e.policy_file, e.section, e.passage) == ("a.md", "S", "P")

    def test_missing_field_rejected(self):
        with pytest.raises(ValidationError):
            Evidence(policy_file="a.md", section="S")


class TestApproval:
    def test_required_must_be_boolean(self):
        with pytest.raises(ValidationError):
            Approval(required="maybe", approver_roles=[], reason="")

    def test_roles_default_to_empty_list(self):
        a = Approval(required=False)
        assert a.approver_roles == []


class TestAnalysisResult:
    def test_valid_result_roundtrips(self):
        r = AnalysisResult(**make_result())
        dumped = r.model_dump()
        assert dumped["request_id"] == "REQ-001"
        assert dumped["approval"]["approver_roles"] == ["reporting_manager"]
        # round-trip
        assert AnalysisResult(**dumped).model_dump() == dumped

    def test_missing_information_defaults_to_empty_array(self):
        data = make_result(decision="eligible",
                           approval={"required": False, "approver_roles": [], "reason": ""})
        data.pop("missing_information")
        r = AnalysisResult(**data)
        assert r.missing_information == []

    def test_confidence_bounds_enforced(self):
        with pytest.raises(ValidationError):
            AnalysisResult(**make_result(confidence=1.7))
        with pytest.raises(ValidationError):
            AnalysisResult(**make_result(confidence=-0.1))

    def test_confidence_edges_allowed(self):
        assert AnalysisResult(**make_result(confidence=0.0)).confidence == 0.0
        assert AnalysisResult(**make_result(confidence=1.0)).confidence == 1.0

    def test_requires_approval_demands_approval_required_true(self):
        with pytest.raises(ValidationError):
            AnalysisResult(**make_result(
                approval={"required": False, "approver_roles": [], "reason": ""}))

    def test_non_approval_decision_demands_required_false(self):
        with pytest.raises(ValidationError):
            AnalysisResult(**make_result(
                decision="eligible",
                approval={"required": True, "approver_roles": ["x"], "reason": "r"}))

    def test_required_true_demands_at_least_one_role(self):
        with pytest.raises(ValidationError):
            AnalysisResult(**make_result(
                approval={"required": True, "approver_roles": [], "reason": "r"}))

    def test_missing_information_must_be_list(self):
        with pytest.raises(ValidationError):
            AnalysisResult(**make_result(missing_information="invoice number"))

    def test_evidence_list_parsed_into_models(self):
        r = AnalysisResult(**make_result())
        assert isinstance(r.supporting_evidence[0], Evidence)

    def test_needs_information_may_have_empty_evidence(self):
        r = AnalysisResult(**make_result(
            decision="needs_information",
            supporting_evidence=[],
            missing_information=["invoice_number"],
            approval={"required": False, "approver_roles": [], "reason": ""}))
        assert r.supporting_evidence == []
