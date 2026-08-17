"""Shared fixtures for the CLERWELL Policy Decision Assistant test suite.

The LLM is always mocked — no test makes a paid or network API call
(except one that deliberately targets a closed localhost port).
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
POLICIES_DIR = ROOT / "policies"
REQUESTS_PATH = ROOT / "data" / "requests.json"


class FakeLLM:
    """Scripted LLM client. Returns queued responses in order and records
    every (system, user) prompt pair it receives.

    If a queued item is an Exception instance, it is raised instead.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []  # list of (system, user) tuples

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if not self.responses:
            raise AssertionError("FakeLLM ran out of scripted responses")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def fake_llm_factory():
    return FakeLLM


@pytest.fixture(scope="session")
def requests_data():
    with open(REQUESTS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def store():
    from backend.store import RequestStore

    return RequestStore(REQUESTS_PATH)


@pytest.fixture(scope="session")
def index():
    from backend.retrieval import PolicyIndex

    return PolicyIndex(POLICIES_DIR)


def valid_llm_response(request_id, decision, *, summary="Grounded summary.",
                       evidence=None, missing=None, required=False,
                       roles=None, reason="", confidence=0.9):
    """Build a syntactically valid model response payload as a JSON string."""
    if evidence is None:
        evidence = [{
            "policy_file": "employee_leave_policy.md",
            "section": "Annual leave",
            "passage": "Up to 3 consecutive working days requires reporting-manager approval.",
        }]
    return json.dumps({
        "request_id": request_id,
        "decision": decision,
        "summary": summary,
        "supporting_evidence": evidence,
        "missing_information": missing or [],
        "approval": {
            "required": required,
            "approver_roles": roles or [],
            "reason": reason,
        },
        "confidence": confidence,
    })
