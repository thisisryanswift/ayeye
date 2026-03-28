---
id: ayeye-t64
status: closed
deps: []
links: []
created: 2025-12-13T11:38:33.211813626-05:00
type: bug
priority: 1
---
# No timeout on Gemini processing loop

In src/analyzer.rs:160-182, the loop waiting for file status to become ACTIVE has no timeout. If Gemini gets stuck in PROCESSING state, the program hangs forever. Add a 5-minute timeout.


