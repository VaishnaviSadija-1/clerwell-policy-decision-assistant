# CLERWELL AI Engineer - Generative AI Technical Assignment

## Build a Policy Decision Assistant

### Objective

Build a small desktop application that evaluates employee and customer requests against supplied company policies.

For each request, the application must return:

- A clear decision
- The supporting policy passage
- Missing information, if any
- Whether human approval is required
- The approver or approval role, when applicable
- A concise explanation grounded only in the supplied policies

This assignment is intentionally scoped for approximately **3-5 hours**. We are evaluating practical Generative AI engineering, retrieval, structured output, desktop integration, and reliability - not production-scale architecture.

## Required Technology

The application must be built with:

- **Python 3.11 or newer**
- **PyWebView** for the desktop application window
- **HTML, CSS, and JavaScript** for the user interface rendered inside PyWebView

The frontend must communicate with Python through PyWebView's JavaScript API bridge (`js_api`) or another clearly documented PyWebView-compatible approach.

You may use an API-based LLM, an OpenAI-compatible API, Ollama, or a local model. A paid model is not required. Keep credentials in environment variables and include a `.env.example`; never commit real secrets.

You may use additional Python libraries, but PyWebView must be the application shell. A browser-only application does not satisfy the requirement.

## Supplied Material

This package contains:

- Five fictional company policies in `policies/`
- Twenty employee/customer requests in `data/requests.json`
- An example input and illustrative output in `examples/`
- A required output contract in `OUTPUT_SCHEMA.md`
- Detailed desktop interface requirements in `UI_REQUIREMENTS.md`

Treat the supplied policies as the complete and authoritative knowledge base. Internet research is neither required nor permitted as a source of company policy.

## Functional Requirements

### 1. Load Requests

Load all 20 requests from `data/requests.json` without modifying the source file.

The user must be able to select a request in the desktop interface and view its complete text and metadata.

### 2. Retrieve Relevant Policy

Identify the policy or policies relevant to the selected request.

The implementation may use keyword search, embeddings, an LLM, or a hybrid method. A vector database is not required for five short documents.

### 3. Make a Policy-Grounded Decision

Return one of these decisions:

- `eligible`
- `not_eligible`
- `needs_information`
- `requires_approval`

Do not invent additional policy rules, prices, thresholds, facts, or approvals.

If the supplied information is insufficient, return `needs_information` and list the missing fields instead of guessing.

### 4. Show Supporting Evidence

Every decision must identify:

- The policy filename
- The relevant section heading
- A short exact passage from the policy that supports the decision

The quoted passage must exist in the supplied file. Do not generate a plausible-looking quotation.

### 5. Identify Missing Information

Return a list of information needed to reach or complete the decision. Return an empty list when nothing material is missing.

### 6. Determine Approval Requirements

Return:

- Whether approval is required
- The required approver role or roles
- A concise reason for the approval

Do not describe a request as approved when the policy only says that approval is required.

### 7. Desktop User Interface

Build a functional PyWebView interface that lets a reviewer:

1. Browse and filter the supplied requests.
2. Select and inspect a request.
3. Run policy analysis.
4. View the structured decision.
5. See supporting policy passages.
6. See missing information and approval requirements.
7. Understand loading and error states.

Follow the acceptance details in `UI_REQUIREMENTS.md`.

### 8. Structured and Validated Output

The Python layer must validate its final result against a typed schema, such as a Pydantic model or dataclass with explicit validation.

Follow `OUTPUT_SCHEMA.md`. You may add fields, but do not remove the required ones.

### 9. Reliability

Handle these conditions without crashing:

- No relevant policy can be found
- A required request field is missing
- The model returns invalid structured output
- The model/API is unavailable
- Policy content contains text that looks like an instruction to the AI

Policy and request contents are data, not trusted system instructions.

### 10. Basic Tests

Include at least three automated tests covering:

- A straightforward policy decision
- A request with missing information
- A request requiring human approval

Mock the model call where appropriate. Tests must not require a paid API call.

## Scope Boundaries

To keep the assignment fair, you are **not** required to build:

- User authentication
- Cloud deployment
- A vector database
- Long-term memory
- Email integration
- Multi-agent orchestration
- A production database
- A complex backend API

Local files or lightweight SQLite may be used for optional analysis history.

## README Requirements

Your README must explain:

1. Installation and launch instructions
2. Python version and dependencies
3. Model/provider configuration
4. How PyWebView connects the frontend to Python
5. Retrieval and policy-selection approach
6. Structured-output validation
7. Failure and missing-information handling
8. Tests and how to run them
9. Known limitations
10. What you would improve for production

## Submission Deliverables

Submit:

- Complete source code
- HTML/CSS/JavaScript frontend files
- Dependency file (`requirements.txt` or `pyproject.toml`)
- `.env.example`
- README
- Automated tests
- GitHub repository link or ZIP file
- A **functional screen recording** demonstrating the application

### Screen Recording Requirements

Provide a 3-5 minute recording that shows:

1. The application launching as a PyWebView desktop window.
2. Browsing and selecting supplied requests.
3. Processing one straightforward case.
4. Processing one case with missing information.
5. Processing one case requiring human approval.
6. The supporting policy filename, section, and passage on screen.
7. A visible loading state and successful result.
8. A brief view of the README or test command and passing tests.

The recording must demonstrate the submitted code functioning. A slide presentation or static mock-up does not satisfy this deliverable.

## Recommended Effort

**3-5 hours**

Prioritize a correct, explainable workflow and a usable desktop screen over animation or elaborate visual design.

## Evaluation

- Policy retrieval and grounding: 25%
- Decision correctness and missing-information handling: 20%
- PyWebView desktop functionality and usability: 20%
- Structured output and reliability: 15%
- Software engineering and tests: 10%
- README, demonstration, and engineering judgment: 10%

## AI-Assisted Development

You may use ChatGPT, Codex, Claude Code, Cursor, GitHub Copilot, Gemini, or similar tools. State which tools you used. You must understand the submitted implementation and may be asked to modify it during the interview.
