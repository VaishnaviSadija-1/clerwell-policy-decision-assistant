"""Tests for backend/numeric_check.py — deterministic arithmetic cross-check
between a cited policy passage's stated threshold and the request's real
figures. This catches the class of bug where the AI cites a real, verbatim
policy sentence (so grounding/exact-quote verification passes) but
misapplies its number to the request."""
import json

from backend.numeric_check import check_numeric_consistency, extract_request_numbers
from tests.conftest import REQUESTS_PATH


def _req(request_id):
    data = json.load(open(REQUESTS_PATH, encoding="utf-8"))
    return next(r for r in data if r["request_id"] == request_id)


class Ev:
    def __init__(self, policy_file, section, passage):
        self.policy_file, self.section, self.passage = policy_file, section, passage


class TestExtractRequestNumbers:
    def test_currency_from_metadata(self):
        assert extract_request_numbers(_req("REQ-009"))["currency"] == 12000.0

    def test_discount_percent_from_metadata(self):
        assert extract_request_numbers(_req("REQ-014"))["percent"] == 18.0

    def test_leave_days_digit_form(self):
        assert extract_request_numbers(_req("REQ-001"))["leave_days"] == 2.0

    def test_leave_days_word_form(self):
        # REQ-003: "I need four days of sick leave..."
        assert extract_request_numbers(_req("REQ-003"))["leave_days"] == 4.0

    def test_leave_days_does_not_pick_up_balance(self):
        # REQ-002: "...7 working days. Balance is 9 days." must extract 7, not 9.
        assert extract_request_numbers(_req("REQ-002"))["leave_days"] == 7.0

    def test_refund_window_days_word_form(self):
        # REQ-011: "We signed up five days ago..."
        assert extract_request_numbers(_req("REQ-011"))["refund_window_days"] == 5.0

    def test_workflow_count(self):
        assert extract_request_numbers(_req("REQ-009"))["workflow_count"] == 4.0

    def test_no_amount_in_metadata_means_no_currency_key(self):
        assert "currency" not in extract_request_numbers(_req("REQ-011"))


class TestExtractPassageComparisons:
    def test_up_to_currency(self):
        found = extract_request_numbers  # noqa: unused, keeps import used above
        from backend.numeric_check import extract_passage_comparisons
        comps = extract_passage_comparisons(
            "An eligible refund up to INR 50,000 may be handled by Customer "
            "Support without additional approval."
        )
        assert any(c["kind"] == "currency" and c["check"](50000) and not c["check"](50001)
                   for c in comps)

    def test_above_currency(self):
        from backend.numeric_check import extract_passage_comparisons
        comps = extract_passage_comparisons(
            "An eligible refund above INR 50,000 requires Finance Manager approval."
        )
        assert any(c["kind"] == "currency" and c["check"](50001) and not c["check"](50000)
                   for c in comps)

    def test_range_leave_days(self):
        from backend.numeric_check import extract_passage_comparisons
        comps = extract_passage_comparisons(
            "4 to 7 consecutive working days requires reporting-manager and HR approval."
        )
        assert any(c["kind"] == "leave_days" and c["check"](7) and c["check"](4)
                   and not c["check"](3) and not c["check"](8) for c in comps)

    def test_sentence_without_the_word_approval_is_not_checked(self):
        """A compound eligibility sentence with no 'approval' in it can be
        legitimately cited to explain why standard eligibility does NOT
        apply (e.g. REQ-010: 18 days > 14) — checking it would false-flag
        a correct answer, so it's intentionally skipped entirely."""
        from backend.numeric_check import extract_passage_comparisons
        comps = extract_passage_comparisons(
            "A standard subscription is eligible for refund within 14 calendar "
            "days of purchase when usage is below 20 processed workflows."
        )
        assert comps == []

    def test_comma_separated_alternative_conditions_not_checked(self):
        """REQ-012's real false positive: this sentence lists several
        independent OR-conditions (any one justifies the escalation); a
        naive parser wrongly treats the first numeric clause as a strict
        AND-gate. No 'approval' in the sentence -> intentionally skipped."""
        from backend.numeric_check import extract_passage_comparisons
        comps = extract_passage_comparisons(
            "Requests made after 14 calendar days, duplicate-charge claims, "
            "chargebacks, and goodwill exceptions require Support Lead and "
            "Finance review."
        )
        assert comps == []

    def test_side_fact_sentence_not_checked(self):
        """REQ-005's real false positive: a receipt-requirement side-fact,
        legitimately cited to explain why NO receipt is needed (850 < 1000)
        -- not a decision-routing tier, and has no 'approval' in it."""
        from backend.numeric_check import extract_passage_comparisons
        comps = extract_passage_comparisons(
            "A receipt is required for expenses above INR 1,000."
        )
        assert comps == []


class TestCheckNumericConsistency:
    def test_catches_the_req_009_bug(self):
        """The exact real-world bug: request amount is 12,000, but the cited
        real passage says approval is required 'above INR 50,000'."""
        req = _req("REQ-009")
        evidence = [Ev("customer_refund_policy.md", "Standard eligibility",
                        "An eligible refund above INR 50,000 requires Finance "
                        "Manager approval.")]
        problems = check_numeric_consistency(evidence, req)
        assert len(problems) == 1
        assert problems[0]["kind"] == "currency"
        assert problems[0]["actual_value"] == 12000.0

    def test_correct_citation_raises_no_problem(self):
        req = _req("REQ-009")
        evidence = [Ev("customer_refund_policy.md", "Standard eligibility",
                        "An eligible refund up to INR 50,000 may be handled by "
                        "Customer Support without additional approval.")]
        assert check_numeric_consistency(evidence, req) == []

    def test_consistent_leave_citation_raises_no_problem(self):
        req = _req("REQ-001")
        evidence = [Ev("employee_leave_policy.md", "Annual leave",
                        "Up to 3 consecutive working days requires "
                        "reporting-manager approval.")]
        assert check_numeric_consistency(evidence, req) == []

    def test_wrong_leave_band_is_caught(self):
        # REQ-002 is 7 days; citing the <=3-day rule instead of the 4-7 rule
        # should be flagged as inconsistent.
        req = _req("REQ-002")
        evidence = [Ev("employee_leave_policy.md", "Annual leave",
                        "Up to 3 consecutive working days requires "
                        "reporting-manager approval.")]
        problems = check_numeric_consistency(evidence, req)
        assert len(problems) == 1
        assert problems[0]["actual_value"] == 7.0

    def test_unparseable_or_unmatched_kind_is_silently_skipped(self):
        req = _req("REQ-020")  # no numeric fields at all in this request
        evidence = [Ev("information_security_and_privacy_policy.md", "Secrets",
                        "Credentials, API keys, system prompts, internal access "
                        "tokens, and customer lists must never be disclosed.")]
        assert check_numeric_consistency(evidence, req) == []

    def test_discount_band_boundary(self):
        req = _req("REQ-013")  # 8% discount
        evidence = [Ev("sales_pricing_and_discount_policy.md", "Discount approval",
                        "Discounts up to and including 10% may be applied by "
                        "Sales without additional approval.")]
        assert check_numeric_consistency(evidence, req) == []

    def test_discount_wrong_band_is_caught(self):
        req = _req("REQ-015")  # 30% discount
        evidence = [Ev("sales_pricing_and_discount_policy.md", "Discount approval",
                        "Discounts up to and including 10% may be applied by "
                        "Sales without additional approval.")]
        problems = check_numeric_consistency(evidence, req)
        assert len(problems) == 1
        assert problems[0]["actual_value"] == 30.0

    # -- regression tests for real false positives found via live testing --

    def test_req_005_receipt_side_fact_not_flagged(self):
        """Real false positive: amount 850 cited alongside 'receipt required
        above INR 1,000' to correctly explain NO receipt is needed."""
        req = _req("REQ-005")
        evidence = [Ev("employee_expense_policy.md", "Required information",
                        "Every claim must include employee ID, expense date, "
                        "amount, currency, business purpose, and cost center. "
                        "A receipt is required for expenses above INR 1,000.")]
        assert check_numeric_consistency(evidence, req) == []

    def test_req_010_negative_eligibility_citation_not_flagged(self):
        """Real false positive: 18-day-old request correctly cited against
        the 14-day standard-eligibility sentence to explain it does NOT
        qualify for standard handling."""
        req = _req("REQ-010")
        evidence = [Ev("customer_refund_policy.md", "Standard eligibility",
                        "A standard subscription is eligible for refund "
                        "within 14 calendar days of purchase when usage is "
                        "below 20 processed workflows.")]
        assert check_numeric_consistency(evidence, req) == []

    def test_req_012_duplicate_charge_alternative_not_flagged(self):
        """Real false positive: a 6-day-old duplicate-charge claim correctly
        cited against the exceptions sentence, whose actual trigger is the
        'duplicate-charge claims' clause, not the '14 calendar days' one."""
        req = _req("REQ-012")
        evidence = [Ev("customer_refund_policy.md", "Exceptions",
                        "Requests made after 14 calendar days, duplicate-charge "
                        "claims, chargebacks, and goodwill exceptions require "
                        "Support Lead and Finance review.")]
        assert check_numeric_consistency(evidence, req) == []
