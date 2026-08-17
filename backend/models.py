"""Pydantic v2 models for policy decision analysis results."""
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class Decision(str, Enum):
    eligible = "eligible"
    not_eligible = "not_eligible"
    needs_information = "needs_information"
    requires_approval = "requires_approval"


class Evidence(BaseModel):
    policy_file: str
    section: str
    passage: str


class Approval(BaseModel):
    required: bool
    approver_roles: list[str] = Field(default_factory=list)
    reason: str = ""


class AnalysisResult(BaseModel):
    model_config = {"use_enum_values": True}

    request_id: str
    decision: Decision
    summary: str
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    approval: Approval
    confidence: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _check_approval_consistency(self):
        decision_value = (
            self.decision.value if isinstance(self.decision, Decision) else self.decision
        )
        expected_required = decision_value == Decision.requires_approval.value
        if self.approval.required != expected_required:
            raise ValueError(
                "approval.required must equal (decision == requires_approval)"
            )
        if self.approval.required and not self.approval.approver_roles:
            raise ValueError(
                "approver_roles must be non-empty when approval.required is True"
            )
        return self
