"""Simple recorder using ffmpeg subprocess instead of GStreamer.

This avoids all the GLib/GStreamer threading nightmares.
"""

import subprocess
import signal
import os
from rich.console import Console

console = Console()


class SimpleRecorder:
    """Records screen using ffmpeg via PipeWire."""

    def __init__(self, output_file):
        self.output_file = output_file
        self.process = None

    def start(self):
        """Start recording. Returns immediately, recording runs in background."""
        # Use pw-record for PipeWire screen capture piped to ffmpeg
        # Or use wf-recorder which is simpler

        # Check if wf-recorder is available (Wayland screen recorder)
        try:
            result = subprocess.run(["which", "wf-recorder"], capture_output=True)
            if result.returncode == 0:
                self._start_wf_recorder()
                return
        except:
            pass

        # Fallback: try ffmpeg with pipewire
        self._start_ffmpeg_pipewire()

    def _start_wf_recorder(self):
        """Start recording with wf-recorder."""
        cmd = [
            "wf-recorder",
            "-a",  # Record audio
            "-f",
            str(self.output_file),
        ]
        console.print(f"[dim]Starting: {' '.join(cmd)}[/dim]")
        self.process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _start_ffmpeg_pipewire(self):
        """Start recording with ffmpeg + pipewire."""
        # This requires the user to have already set up a pipewire screen capture
        raise NotImplementedError(
            "ffmpeg+pipewire not implemented, install wf-recorder"
        )

    def stop(self):
        """Stop recording gracefully."""
        if self.process:
            # Send SIGINT for graceful shutdown (ffmpeg/wf-recorder handle this)
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None

    @property
    def is_recording(self):
        return self.process is not None and self.process.poll() is None
