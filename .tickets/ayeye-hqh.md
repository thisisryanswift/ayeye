---
id: ayeye-hqh
status: closed
deps: []
links: []
created: 2025-12-13T10:53:43.011191265-05:00
type: task
priority: 2
---
# Over-defensive fallback chain in config.rs

Lines 8-15 in src/config.rs: The unwrap_or_else chain with multiple fallbacks is overly paranoid. ProjectDirs::from() reliably returns Some on Linux. Simplify the config directory resolution.


