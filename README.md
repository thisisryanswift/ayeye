# AyEye

AI-powered video bug reporter for Linux. Record your screen, and let AI generate the issue report.

## Features

- **Screen Recording**: Captures screen and audio via XDG Desktop Portal (Wayland-native)
- **AI Analysis**: Uses Google Gemini to analyze the recording and extract:
  - Issue title
  - Summary
  - Step-by-step reproduction instructions
  - Key timestamps
- **Issue Creation**: Automatically creates issues in [beads](https://github.com/rswiftoffice/beads) projects, or generates a markdown file

## Requirements

- Linux with Wayland (tested on KDE Plasma / Fedora)
- GStreamer with x264 and opus encoders
- PipeWire
- ffmpeg (for video conversion)
- Google Gemini API key

### Fedora

```bash
sudo dnf install gstreamer1-plugins-base gstreamer1-plugins-good \
    gstreamer1-plugins-bad-free gstreamer1-plugin-openh264 \
    pipewire-gstreamer ffmpeg
```

## Installation

```bash
cargo install --path .
```

Or build from source:

```bash
cargo build --release
# Binary at target/release/ayeye
```

## Configuration

Set your Gemini API key in `~/.config/ayeye/.env`:

```bash
mkdir -p ~/.config/ayeye
echo "GEMINI_API_KEY=your_key_here" > ~/.config/ayeye/.env
```

Recordings are saved to `~/Videos/AyEye/` by default. Override with `AYEYE_RECORDINGS_DIR`.

## Usage

```bash
# Run in your project directory
ayeye
```

1. A screen/window picker dialog appears
2. Select what to record
3. Press **Enter** or **Ctrl+C** to stop recording
4. Video is uploaded to Gemini for analysis
5. Issue is created (beads) or markdown file saved

## License

MIT
