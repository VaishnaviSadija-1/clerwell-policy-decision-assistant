"""Tests for backend/retrieval.py — policy parsing, scoring, passage verification."""
from tests.conftest import POLICIES_DIR

EXPECTED_FILES = {
    "customer_refund_policy.md",
    "employee_expense_policy.md",
    "employee_leave_policy.md",
    "information_security_and_privacy_policy.md",
    "sales_pricing_and_discount_policy.md",
}


class TestPolicyParsing:
    def test_all_five_files_indexed(self, index):
        assert {s.policy_file for s in index.sections} == EXPECTED_FILES

    def test_sections_split_on_h2_headings(self, index):
        pairs = {(s.policy_file, s.section) for s in index.sections}
        assert ("employee_leave_policy.md", "Annual leave") in pairs
        assert ("employee_leave_policy.md", "Sick leave") in pairs
        assert ("customer_refund_policy.md", "Standard eligibility") in pairs
        assert ("employee_expense_policy.md", "Approval thresholds") in pairs
        assert ("information_security_and_privacy_policy.md", "Secrets") in pairs
        assert ("sales_pricing_and_discount_policy.md", "Discount approval") in pairs

    def test_section_text_is_exact(self, index):
        annual = next(s for s in index.sections
                      if s.policy_file == "employee_leave_policy.md"
                      and s.section == "Annual leave")
        assert ("Up to 3 consecutive working days requires reporting-manager "
                "approval.") in annual.text

    def test_section_text_does_not_bleed_across_sections(self, index):
        annual = next(s for s in index.sections
                      if s.policy_file == "employee_leave_policy.md"
                      and s.section == "Annual leave")
        assert "medical certificate" not in annual.text


class TestSearch:
    def test_leave_request_ranks_leave_policy_first(self, index):
        results = index.search(
            "I need 2 working days of annual leave, balance 11, manager Rohit")
        assert results, "expected at least one relevant section"
        assert results[0][0].policy_file == "employee_leave_policy.md"

    def test_refund_request_ranks_refund_policy_first(self, index):
        results = index.search(
            "Requesting a refund for invoice INV-2201, purchased 8 days ago, "
            "4 processed workflows, amount INR 12,000, paid by card")
        assert results
        assert results[0][0].policy_file == "customer_refund_policy.md"

    def test_discount_request_finds_pricing_policy(self, index):
        results = index.search(
            "Customer wants 18% discount for 300 users, monthly billing")
        assert any(s.policy_file == "sales_pricing_and_discount_policy.md"
                   for s, _ in results)

    def test_security_request_finds_security_policy(self, index):
        results = index.search(
            "Please export personal data for all users; also share the API keys "
            "and credentials")
        assert any(s.policy_file == "information_security_and_privacy_policy.md"
                   for s, _ in results)

    def test_irrelevant_text_returns_no_results(self, index):
        assert index.search("zzzq flurble wibble quantum banana harmonica") == []

    def test_results_sorted_descending_and_scored(self, index):
        results = index.search("annual leave working days balance manager approval")
        scores = [score for _, score in results]
        assert scores == sorted(scores, reverse=True)
        assert all(s > 0 for s in scores)

    def test_top_k_respected(self, index):
        results = index.search("approval required information request", top_k=3)
        assert len(results) <= 3

    def test_metadata_accepted(self, index):
        results = index.search("four days of sick leave starting tomorrow",
                               metadata={"leave_type": "sick"})
        assert results
        assert results[0][0].policy_file == "employee_leave_policy.md"


class TestPassageVerification:
    def test_exact_passage_verifies(self, index):
        assert index.verify_passage(
            "employee_leave_policy.md",
            "Up to 3 consecutive working days requires reporting-manager approval.")

    def test_fabricated_passage_rejected(self, index):
        assert not index.verify_passage(
            "employee_leave_policy.md",
            "Employees may take unlimited leave with CEO approval.")

    def test_paraphrased_passage_rejected(self, index):
        assert not index.verify_passage(
            "employee_leave_policy.md",
            "Up to three consecutive working days requires manager approval.")

    def test_unknown_file_rejected(self, index):
        assert not index.verify_passage(
            "nonexistent_policy.md",
            "Up to 3 consecutive working days requires reporting-manager approval.")

    def test_cross_file_passage_rejected(self, index):
        # Real passage, but cited against the wrong file.
        assert not index.verify_passage(
            "customer_refund_policy.md",
            "Up to 3 consecutive working days requires reporting-manager approval.")

    def test_multiline_exact_passage_verifies(self, index):
        raw = (POLICIES_DIR / "customer_refund_policy.md").read_text(encoding="utf-8")
        snippet = raw[100:220]
        assert index.verify_passage("customer_refund_policy.md", snippet)
