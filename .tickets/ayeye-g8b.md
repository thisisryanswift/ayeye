---
id: ayeye-g8b
status: closed
deps: []
links: []
created: 2025-12-13T10:53:40.94577735-05:00
type: bug
priority: 1
---
# Bug: PathBuf::from with tilde does not expand

Line 13-14 in src/config.rs: `PathBuf::from("~/.config/ayeye")` does not expand the tilde. This fallback path would fail silently on systems where ProjectDirs and BaseDirs both return None. Use dirs::home_dir() or shellexpand crate instead.


