# Required Output Contract

Each analysis result must contain the following semantic fields. A typed Python model must validate the result before it is returned to the UI.

```json
{
  "request_id": "REQ-001",
  "decision": "requires_approval",
  "summary": "The request is within the available leave balance but requires reporting-manager approval.",
  "supporting_evidence": [
    {
      "policy_file": "employee_leave_policy.md",
      "section": "Annual leave",
      "passage": "Up to 3 consecutive working days requires reporting-manager approval."
    }
  ],
  "missing_information": [],
  "approval": {
    "required": true,
    "approver_roles": ["reporting_manager"],
    "reason": "The annual-leave request is for two consecutive working days."
  },
  "confidence": 0.94
}
```

## Required rules

- `decision` must be one of `eligible`, `not_eligible`, `needs_information`, or `requires_approval`.
- `supporting_evidence` must contain at least one item for a successful policy-grounded decision.
- Every `passage` must be copied from the identified policy file.
- `missing_information` must be an array, including when empty.
- `approval.required` must be a boolean.
- `approval.approver_roles` must be an array, including when empty.
- `confidence`, if used, must be between 0 and 1 and must not replace explicit uncertainty handling.
- When no applicable policy can be found, return `needs_information` or a clearly documented safe fallback without inventing a policy.

Candidates may add trace IDs, latency, retrieved-document scores, or model metadata.
