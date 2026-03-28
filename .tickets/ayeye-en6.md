---
id: ayeye-en6
status: closed
deps: []
links: []
created: 2025-12-13T10:53:49.038175841-05:00
type: task
priority: 2
---
# Magic sleep duration in recorder.rs

Line 88 in src/recorder.rs: Hardcoded `Duration::from_millis(500)` sleep with comment 'Give a little extra time for the stream to stabilize' but no explanation of why 500ms or what instability is being addressed. Add a constant with documentation or remove if unnecessary.


