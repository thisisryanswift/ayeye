---
id: ayeye-xk2
status: closed
deps: []
links: []
created: 2025-12-13T10:53:44.842243224-05:00
type: task
priority: 2
---
# Duplicate code in format_issue_body and format_issue_markdown

Lines 109-144 and 146-172 in src/main.rs: These two functions share ~80% identical code. Extract common formatting logic into a shared helper or use a single function with a format parameter.


