---
id: ayeye-dod
status: closed
deps: []
links: []
created: 2025-12-13T11:38:34.671217604-05:00
type: task
priority: 2
---
# Temp file collision risk

In src/analyzer.rs:68-71, temp MP4 files use only the original filename stem. If two recordings have the same filename, they could overwrite each other. Add a UUID or unique suffix to the temp filename.


