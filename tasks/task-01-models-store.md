# Task 01 — Pydantic models + request store (complexity: medium)

Create exactly two files. Do not touch any other file. Do not edit tests.

## backend/models.py (Pydantic v2)
- `Decision(str, Enum)` with values: eligible, not_eligible, needs_information, requires_approval.
- `Evidence(BaseModel)`: policy_file: str, section: str, passage: str (all required).
- `Approval(BaseModel)`: required: bool (required), approver_roles: list[str] = [], reason: str = "".
- `AnalysisResult(BaseModel)`: request_id: str, decision: Decision, summary: str,
  supporting_evidence: list[Evidence] = [], missing_information: list[str] = [],
  approval: Approval, confidence: float in [0,1].
- `model_dump()` must serialize decision as a plain string (use `use_enum_values` or a serializer) and round-trip.
- Cross-field validation (model_validator):
  - approval.required must equal (decision == requires_approval), else ValidationError.
  - if approval.required is True, approver_roles must be non-empty.
- missing_information given as a plain string must fail validation (no coercion of str to list).

## backend/store.py
- `RequestStore(path)`: loads JSON list on construction; read-only (never writes the file).
- `.all() -> list[dict]` — deep copies (mutating a returned record must not affect the store).
- `.get(request_id) -> dict | None` — deep copy, None when absent.

## Verify
Run: `.venv/bin/python -m pytest tests/test_models.py tests/test_store.py -q` from the repo root — all tests must pass. Report the final pytest output.
