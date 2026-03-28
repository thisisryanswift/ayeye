---
id: ayeye-1yl
status: closed
deps: []
links: []
created: 2025-12-13T10:53:50.984049532-05:00
type: task
priority: 2
---
# Debug logging in recorder.rs should be behind a flag

Lines 120-123 in src/recorder.rs: StateChanged logging is debug cruft that prints during normal operation. Either remove it or put behind a --verbose flag or RUST_LOG environment variable using the tracing crate.


