---
id: ayeye-hmn
status: closed
deps: []
links: []
created: 2025-12-13T10:53:38.674296248-05:00
type: task
priority: 2
---
# Inline struct definitions in analyzer.rs are verbose

Lines 115-133 and 218-241 in src/analyzer.rs: Struct definitions for API response deserialization (UploadResponse, FileInfo, StatusResponse, GenerateResponse, Candidate, Content, Part) are inlined mid-function. Consider moving to module-level or using serde attributes for cleaner code.


