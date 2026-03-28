---
id: ayeye-2ij
status: closed
deps: []
links: []
created: 2025-12-13T11:26:27.832262797-05:00
type: task
priority: 2
---
# Clean up temporary MP4 files after Gemini upload

When converting MKV to MP4 for Gemini upload (src/analyzer.rs), the converted MP4 file at `{original_path}.mp4` is never deleted. These files accumulate in ~/Videos/AyEye alongside the MKV originals. Should delete the temp MP4 after successful upload, or use a proper temp file path.


