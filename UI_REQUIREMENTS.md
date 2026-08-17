# Desktop UI Requirements

The submitted application must launch as a native desktop window using PyWebView.

## Required layout

The interface must provide:

1. **Request list** - show request ID, requester type, requester name, and a shortened request preview.
2. **Filter/search** - filter by requester type or search request text/requester.
3. **Request detail** - show the complete selected request and metadata.
4. **Analyze action** - a clearly visible button that calls the Python analysis layer.
5. **Decision result** - show the decision as `eligible`, `not_eligible`, `needs_information`, or `requires_approval`.
6. **Supporting evidence** - show policy filename, section heading, and exact supporting passage.
7. **Missing information** - show a list or a clear `None` state.
8. **Approval requirement** - show whether approval is required, approver role(s), and reason.
9. **Explanation** - show a concise policy-grounded explanation.
10. **System state** - visible loading, success, empty-selection, and error states.

## Required interaction

- Selecting another request must update the detail panel.
- Clicking Analyze must invoke Python through the PyWebView bridge.
- The interface must remain responsive while analysis is running.
- An error must produce a readable message and allow the user to try again.
- Results must not be hard-coded by request ID.

## Design expectation

The screen should be clean and usable, but extensive visual polish is not required. A single-window desktop layout is sufficient. Responsive browser/mobile design is not required.

## Suggested project structure

```text
app.py
backend/
  analyzer.py
  models.py
  retrieval.py
frontend/
  index.html
  app.js
  styles.css
tests/
requirements.txt
.env.example
README.md
```

Candidates may choose a different structure if the separation between UI, retrieval, model interaction, and validation remains understandable.
