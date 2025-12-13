import os
import sys

# Suppress GLib/GTK warnings before importing gi
# Redirect stderr temporarily during import to suppress the warning
import io

_stderr = sys.stderr
sys.stderr = io.StringIO()

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("AyatanaAppIndicator3", "0.1")
from gi.repository import Gtk, GLib, Gio, AyatanaAppIndicator3

# Restore stderr
sys.stderr = _stderr

import threading
from rich.console import Console
from .config import GEMINI_API_KEY
from .recorder import PortalRecorder
from .analyzer import analyze_video
from .issue_creator import create_issue
from datetime import datetime
from pathlib import Path
from .config import RECORDINGS_DIR

console = Console()
APP_ID = "com.rswift.ayeye"


class AyEyeApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE
        )
        self.indicator = None
        self.recorder = None
        self.is_recording = False
        self.is_waiting_for_selection = False  # True while portal dialog is shown
        self.current_output_file = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Hold the application so it doesn't quit immediately
        self.hold()

        # Setup System Tray Icon
        self.indicator = AyatanaAppIndicator3.Indicator.new(
            "ayeye",
            "media-record",
            AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)

        # Setup Menu
        menu = Gtk.Menu()

        item_toggle = Gtk.MenuItem(label="Toggle Recording")
        item_toggle.connect("activate", self.on_toggle)
        menu.append(item_toggle)

        item_quit = Gtk.MenuItem(label="Quit")
        item_quit.connect("activate", self.on_quit)
        menu.append(item_quit)

        menu.show_all()
        self.indicator.set_menu(menu)

        console.print("[green]AyEye Daemon Started[/green]")

    def do_activate(self):
        pass

    def do_command_line(self, command_line):
        args = command_line.get_arguments()
        self.activate()

        if len(args) > 1:
            cmd = args[1]
            if cmd == "toggle":
                GLib.idle_add(self.toggle_recording)
            elif cmd == "start":
                if not self.is_recording:
                    GLib.idle_add(self.start_recording)
            elif cmd == "stop":
                if self.is_recording:
                    GLib.idle_add(self.stop_recording)
            elif cmd == "quit":
                GLib.idle_add(self.quit)

        return 0

    def on_toggle(self, widget):
        self.toggle_recording()

    def on_quit(self, widget):
        self.release()
        self.quit()

    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.is_recording or self.is_waiting_for_selection:
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.current_output_file = RECORDINGS_DIR / f"issue_{timestamp}.mp4"

        console.print(f"Starting recording to {self.current_output_file}")

        # Create recorder with callbacks
        self.recorder = PortalRecorder(
            str(self.current_output_file),
            on_ready=self._on_recording_started,
            on_error=self._on_recording_error,
            on_stopped=self._on_recording_stopped,
        )

        self.is_waiting_for_selection = True
        self._notify("Recording", "Select screen to begin...")

        # Start the async recording process (will show portal dialog)
        self.recorder.start()

    def _on_recording_started(self):
        """Called when recording actually starts (after user selects screen)."""
        self.is_waiting_for_selection = False
        self.is_recording = True
        self.indicator.set_icon("media-record-symbolic")
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ATTENTION)
        self._notify("Recording", "Recording in progress...")

    def _on_recording_error(self, error_msg):
        """Called when recording fails."""
        console.print(f"[red]Recording error: {error_msg}[/red]")
        self.is_waiting_for_selection = False
        self.is_recording = False
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_icon("media-record")
        self._notify("Error", error_msg)

    def _on_recording_stopped(self):
        """Called when recording stops."""
        console.print("Recording stopped callback")
        # Processing happens in stop_recording

    def stop_recording(self):
        if not self.is_recording or not self.recorder:
            # If waiting for selection, cancel it
            if self.is_waiting_for_selection and self.recorder:
                self.recorder.stop()
                self.is_waiting_for_selection = False
            return

        console.print("Stopping recording...")

        self.recorder.stop()

        self.is_recording = False
        self.indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_icon("media-record")

        self._notify("Recording Stopped", "Analyzing video...")

        video_file = self.current_output_file
        threading.Thread(
            target=self.process_recording, args=(video_file,), daemon=True
        ).start()

    def process_recording(self, video_file):
        try:
            console.print(f"[dim]Processing recording: {video_file}[/dim]")
            analysis = analyze_video(video_file)
            console.print(
                f"[dim]Analysis complete: {analysis.get('title', 'No title')}[/dim]"
            )
            create_issue(analysis, video_file)
            self._notify("Issue Created", analysis.get("title", "Done"))
        except Exception as e:
            import traceback

            console.print(f"[red]Analysis failed: {e}[/red]")
            console.print(f"[red]{traceback.format_exc()}[/red]")
            self._notify("Error", str(e)[:100])

    def _notify(self, title, body):
        import subprocess

        subprocess.run(["notify-send", "-a", "AyEye", title, body])


def main():
    app = AyEyeApp()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
