---
id: ayeye-zi2
status: closed
deps: []
links: []
created: 2025-12-13T11:38:32.776250523-05:00
type: bug
priority: 1
---
# Temp MP4 not cleaned up on error paths

In src/analyzer.rs, if any error occurs after the temp MP4 is created (ffmpeg conversion) but before the cleanup at the end of the function, the temp file is leaked. This includes upload failures, video processing failures, generation failures, and JSON parse failures.


