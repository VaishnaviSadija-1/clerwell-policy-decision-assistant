"""Deterministic numeric-consistency checker.

Catches a class of error the schema check and the exact-quote grounding
check cannot: the AI citing a REAL policy sentence (so grounding passes)
but misapplying its number to the request (e.g. claiming "INR 12,000
exceeds the INR 50,000 threshold").

No business threshold value is hardcoded here. Every number this module
compares against comes from the actual, already-grounding-verified policy
passage the model cited — this module only re-does the arithmetic, using
plain regex to recognize the small set of comparison phrasings the five
policy files actually use ("up to", "above", "within N calendar days",
"N to M consecutive working days", ...). If a passage's comparison can't
be confidently parsed, or the request has no matching number, the check is
skipped for that item rather than guessed at.
"""
from __future__ import annotations

import re

_WORD_NUMBERS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}
_NUM_TOKEN = r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
_NUM_GROUP = r"(\d[\d,]*)"


def _to_number(token: str) -> float | None:
    token = token.strip().lower()
    if token.isdigit():
        return float(token)
    if token in _WORD_NUMBERS:
        return float(_WORD_NUMBERS[token])
    return None


def _to_number_commas(token: str) -> float:
    return float(token.replace(",", ""))


# ---------------------------------------------------------------------------
# Step 1: pull the real-world numbers out of the request itself
# ---------------------------------------------------------------------------

def extract_request_numbers(request: dict) -> dict[str, float]:
    """Best-effort, conservative extraction. Only returns a number for a
    kind when the match is unambiguous; silence (kind absent from the
    returned dict) is always the safe fallback, never a guess."""
    text = request.get("request_text") or ""
    metadata = request.get("metadata") or {}
    numbers: dict[str, float] = {}

    amount = metadata.get("amount")
    if isinstance(amount, (int, float)):
        numbers["currency"] = float(amount)

    discount = metadata.get("discount_percent")
    if isinstance(discount, (int, float)):
        numbers["percent"] = float(discount)

    m = re.search(_NUM_TOKEN + r"\s*(?:consecutive\s+)?working\s+days", text, re.IGNORECASE)
    if not m:
        m = re.search(_NUM_TOKEN + r"\s*days?\s+(?:of\s+)?(?:annual|sick)\s+leave", text, re.IGNORECASE)
    if m:
        val = _to_number(m.group(1))
        if val is not None:
            numbers["leave_days"] = val

    m = re.search(r"(?:purchased|signed up)\s+" + _NUM_TOKEN + r"\s*days?\s+ago", text, re.IGNORECASE)
    if m:
        val = _to_number(m.group(1))
        if val is not None:
            numbers["refund_window_days"] = val

    m = re.search(r"(\d+)\s*(?:processed\s+)?workflows?", text, re.IGNORECASE)
    if m:
        numbers["workflow_count"] = float(m.group(1))

    return numbers


# ---------------------------------------------------------------------------
# Step 2: parse comparisons out of a (real, grounding-verified) policy quote
# ---------------------------------------------------------------------------

def _range_incl(low, high):
    return lambda v: low <= v <= high, f"between {low:g} and {high:g} (inclusive)"


def _range_excl_low(low, high):
    return lambda v: low < v <= high, f"above {low:g} and up to {high:g}"


def _lte(threshold):
    return lambda v: v <= threshold, f"at most {threshold:g}"


def _lt(threshold):
    return lambda v: v < threshold, f"below {threshold:g}"


def _gt(threshold):
    return lambda v: v > threshold, f"above {threshold:g}"


# Each entry: (kind, compiled regex, comparator-builder taking the matched groups)
_PATTERNS: list[tuple[str, re.Pattern, callable]] = [
    ("percent", re.compile(r"above\s+" + _NUM_GROUP + r"%\s*and\s+up to\s+" + _NUM_GROUP + r"%", re.I),
     lambda m: _range_excl_low(_to_number_commas(m.group(1)), _to_number_commas(m.group(2)))),
    ("currency", re.compile(r"from\s+(?:inr\s*)?" + _NUM_GROUP + r"\s+through\s+(?:inr\s*)?" + _NUM_GROUP, re.I),
     lambda m: _range_incl(_to_number_commas(m.group(1)), _to_number_commas(m.group(2)))),
    ("leave_days", re.compile(r"\b" + _NUM_GROUP + r"\s+to\s+" + _NUM_GROUP + r"\s+consecutive\s+working\s+days", re.I),
     lambda m: _range_incl(_to_number_commas(m.group(1)), _to_number_commas(m.group(2)))),
    ("leave_days", re.compile(r"\b" + _NUM_GROUP + r"\s+or\s+" + _NUM_GROUP + r"\s+consecutive\s+working\s+days", re.I),
     lambda m: _range_incl(_to_number_commas(m.group(1)), _to_number_commas(m.group(2)))),
    ("percent", re.compile(r"up to and including\s+" + _NUM_GROUP + r"%", re.I),
     lambda m: (_lte(_to_number_commas(m.group(1))))),
    ("percent", re.compile(r"up to\s+" + _NUM_GROUP + r"%", re.I),
     lambda m: (_lte(_to_number_commas(m.group(1))))),
    ("leave_days", re.compile(r"up to\s+" + _NUM_GROUP + r"\s+consecutive\s+working\s+days", re.I),
     lambda m: (_lte(_to_number_commas(m.group(1))))),
    ("currency", re.compile(r"up to\s+(?:inr\s*)?" + _NUM_GROUP, re.I),
     lambda m: (_lte(_to_number_commas(m.group(1))))),
    ("refund_window_days", re.compile(r"within\s+" + _NUM_GROUP + r"\s+calendar\s+days", re.I),
     lambda m: (_lte(_to_number_commas(m.group(1))))),
    ("refund_window_days", re.compile(r"after\s+" + _NUM_GROUP + r"\s+calendar\s+days", re.I),
     lambda m: (_gt(_to_number_commas(m.group(1))))),
    ("workflow_count", re.compile(r"below\s+" + _NUM_GROUP + r"\s+processed\s+workflows", re.I),
     lambda m: (_lt(_to_number_commas(m.group(1))))),
    ("percent", re.compile(r"above\s+" + _NUM_GROUP + r"%", re.I),
     lambda m: (_gt(_to_number_commas(m.group(1))))),
    ("currency", re.compile(r"above\s+(?:inr\s*)?" + _NUM_GROUP, re.I),
     lambda m: (_gt(_to_number_commas(m.group(1))))),
    ("leave_days", re.compile(r"(?:more than|longer than)\s+" + _NUM_GROUP + r"\s+consecutive\s+working\s+days", re.I),
     lambda m: (_gt(_to_number_commas(m.group(1))))),
]


def extract_passage_comparisons(passage: str) -> list[dict]:
    """Returns a list of {"kind": ..., "check": fn(value)->bool, "explain": str}.

    Deliberately scoped to sentences containing the word "approval" — every
    exhaustive, mutually-exclusive decision-routing tier in these five
    policies is phrased that way ("...above INR 50,000 requires Finance
    Manager approval"), and citing one of those sentences always means "the
    value falls in this tier." Sentences *without* "approval" (a side-fact
    like "a receipt is required for expenses above INR 1,000", a compound
    eligibility definition, or a comma-separated list of alternative
    escalation triggers like "duplicate-charge claims, chargebacks, ...")
    can be, and legitimately are, cited by the model to explain why a
    threshold does NOT apply — treating those the same way produced false
    positives on real requests (verified against REQ-005, REQ-010, REQ-012)
    and is intentionally excluded here rather than guessed at.
    """
    if "approval" not in passage.lower():
        return []
    found = []
    for kind, pattern, build in _PATTERNS:
        for match in pattern.finditer(passage):
            check, explain = build(match)
            found.append({"kind": kind, "check": check, "explain": explain})
    return found


# ---------------------------------------------------------------------------
# Step 3: cross-check each piece of cited evidence against the real request
# ---------------------------------------------------------------------------

_REQUIRES_REVIEW_RE = re.compile(r"requires?\s+.{0,60}?(approval|review)\b", re.IGNORECASE)


def check_decision_consistency(decision: str, evidence: list) -> list[dict]:
    """Catches a specific real-world inconsistency: the model decides
    ``not_eligible`` while citing evidence that itself describes a review
    or approval process ("...require Support Lead and Finance review"),
    rather than an outright refusal. ``not_eligible`` means the excerpts
    say the request must be refused/must not proceed — citing a "send this
    to review" sentence to justify that is self-contradictory. Only checked
    for ``not_eligible``; every other decision is left alone."""
    if decision != "not_eligible":
        return []
    problems = []
    for ev in evidence:
        passage = ev.passage if hasattr(ev, "passage") else ev["passage"]
        if _REQUIRES_REVIEW_RE.search(passage):
            problems.append({
                "policy_file": ev.policy_file if hasattr(ev, "policy_file") else ev["policy_file"],
                "passage": passage,
                "explanation": (
                    "the cited passage describes a review/approval process, "
                    "which is inconsistent with a not_eligible decision — "
                    "not_eligible is only for cases the policy says must be "
                    "refused or must not proceed outright"
                ),
            })
    return problems


_APPROVAL_CLAIM_PATTERNS = [
    re.compile(r"\bapproval\b.{0,40}?\b(?:is|was|will be)\s+required\b", re.IGNORECASE),
    re.compile(r"\brequires?\b.{0,40}?\bapproval\b", re.IGNORECASE),
    re.compile(r"\bneeds?\b.{0,40}?\bapproval\b", re.IGNORECASE),
]
_NEGATION_BEFORE_RE = re.compile(r"\b(no|not|without|never|n't)\b[\w\s,-]{0,25}$", re.IGNORECASE)


def check_approval_text_consistency(decision: str, approval_required: bool,
                                    approval_reason: str) -> list[dict]:
    """Catches a different real regression: the model's own approval.reason
    prose says approval IS required ("Approval by reporting-manager is
    required..."), while the decision isn't requires_approval — which
    structurally forces approval.required to False. The prose and the
    structured field then flatly disagree with each other."""
    if approval_required or not approval_reason:
        return []
    for pattern in _APPROVAL_CLAIM_PATTERNS:
        match = pattern.search(approval_reason)
        if not match:
            continue
        preceding = approval_reason[:match.start()]
        if _NEGATION_BEFORE_RE.search(preceding):
            continue  # e.g. "no approval is required" -- not a contradiction
        return [{
            "field": "approval.reason",
            "text": approval_reason,
            "explanation": (
                "approval.reason states that approval is required, but the "
                f"decision is '{decision}' (not requires_approval), which "
                "forces approval.required to false -- the prose and the "
                "structured field contradict each other"
            ),
        }]
    return []


def check_numeric_consistency(evidence: list, request: dict) -> list[dict]:
    """``evidence`` is a list of Evidence-like objects/dicts with
    ``policy_file``/``section``/``passage``. Returns a list of problems —
    empty if nothing could be checked or everything checked out."""
    req_numbers = extract_request_numbers(request)
    problems = []
    for ev in evidence:
        passage = ev.passage if hasattr(ev, "passage") else ev["passage"]
        for comparison in extract_passage_comparisons(passage):
            kind = comparison["kind"]
            if kind not in req_numbers:
                continue
            value = req_numbers[kind]
            if not comparison["check"](value):
                problems.append({
                    "policy_file": ev.policy_file if hasattr(ev, "policy_file") else ev["policy_file"],
                    "passage": passage,
                    "kind": kind,
                    "actual_value": value,
                    "explanation": (
                        f"the cited passage requires {kind.replace('_', ' ')} to be "
                        f"{comparison['explain']}, but the request's actual "
                        f"{kind.replace('_', ' ')} is {value:g}"
                    ),
                })
    return problems
