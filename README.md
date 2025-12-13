# Video AyEye

A quick way to record video bug reports on Linux (KDE Wayland) using AI to automatically generate issue titles, summaries, and reproduction steps.

## Features

- **One-click recording**: Records screen and microphone via XDG Desktop Portal (same as OBS).
- **AI Analysis**: Uses Google Gemini 2.0 Flash to watch the video and understand the bug.
- **Auto-Ticketing**: Automatically creates an issue in your `beads` tracker if you are in a project, or copies the Markdown report to your clipboard.
- **Privacy**: Recordings are stored locally in `~/.local/share/ayeye`.

## Installation

1. **Install Prerequisites (Fedora)**:
   ```bash
   sudo dnf install python3-gobject gstreamer1-plugins-base gstreamer1-plugins-good gstreamer1-plugins-bad-free gstreamer1-plugin-openh264 pipewire-gstreamer libnotify wl-clipboard
   ```

2. **Install the Tool**:
   Clone this repository and install:
   ```bash
   pip install --user .
   ```
   Or run directly from source.

3. **Set API Key**:
   You need a Google Gemini API key. Export it in your shell:
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

## Usage

### Command Line
```bash
# Start recording (select screen in dialog)
ayeye start

# Stop recording and analyze
ayeye stop

# Toggle (useful for shortcuts)
ayeye toggle
```

### KDE Shortcut Setup (Recommended)

To set up a global hotkey (e.g., `Meta+Shift+R`):

1. Open **System Settings** -> **Shortcuts** -> **Custom Shortcuts**.
2. Click **Add New** -> **Global Shortcut** -> **Command/URL**.
3. Name it "AyEye Toggle".
4. In the **Trigger** tab, set your shortcut (e.g., `Meta+Shift+R`).
5. In the **Action** tab, set the command:
   ```bash
   /path/to/venv/bin/ayeye toggle
   ```
   (Make sure `GEMINI_API_KEY` is available to this command, or wrap it in a script that exports it).

## Configuration

Recordings are stored in `~/.local/share/ayeye/recordings`.

## License

MIT
