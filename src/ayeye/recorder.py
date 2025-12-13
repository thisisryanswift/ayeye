import gi

gi.require_version("Gst", "1.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gst, GLib, Gio
import os
from rich.console import Console

console = Console()


class PortalRecorder:
    """Portal-based screen recorder using XDG Desktop Portal.

    This recorder uses async callbacks to work correctly within GTK applications.
    The portal dialogs are shown by the system and signals are received through
    the application's main GLib event loop.
    """

    def __init__(
        self, output_file, on_ready=None, on_error=None, on_stopped=None, verbose=False
    ):
        """Initialize the recorder.

        Args:
            output_file: Path to save the recording
            on_ready: Callback when recording actually starts (after user selects screen)
            on_error: Callback(error_message) when an error occurs
            on_stopped: Callback when recording stops
            verbose: If True, print detailed debug messages
        """
        Gst.init(None)
        self.output_file = output_file
        self.pipeline = None
        self.node_id = None
        self.session_handle = None
        self.session_token = f"ayeye_{os.getpid()}_{id(self)}"
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.signal_sub_id = None
        self.is_recording = False
        self.verbose = verbose

        # Callbacks
        self.on_ready = on_ready
        self.on_error = on_error
        self.on_stopped = on_stopped

        # State machine
        self._state = "idle"  # idle -> creating -> selecting -> starting -> recording
        self._pending_request_path = None

    def _debug(self, msg):
        """Print debug message if verbose mode is enabled."""
        if self.verbose:
            console.print(f"[dim]{msg}[/dim]")

    def _subscribe_to_responses(self):
        """Subscribe to portal Response signals."""
        if self.signal_sub_id is not None:
            return

        self.signal_sub_id = self.connection.signal_subscribe(
            "org.freedesktop.portal.Desktop",
            "org.freedesktop.portal.Request",
            "Response",
            None,  # Listen to all paths, filter in handler
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_portal_response,
            None,
        )
        self._debug(f"Subscribed to portal signals (id={self.signal_sub_id})")

    def _unsubscribe_from_responses(self):
        """Unsubscribe from portal Response signals."""
        if self.signal_sub_id is not None:
            self.connection.signal_unsubscribe(self.signal_sub_id)
            self.signal_sub_id = None

    def _on_portal_response(
        self,
        connection,
        sender_name,
        object_path,
        interface_name,
        signal_name,
        parameters,
        user_data,
    ):
        """Handle portal Response signals."""
        # Only handle responses we're waiting for
        if self._pending_request_path and object_path != self._pending_request_path:
            return

        response_code = parameters[0]
        results = parameters[1]

        self._debug(
            f"Portal response: state={self._state}, code={response_code}, path={object_path}"
        )

        if response_code != 0:
            error_msg = f"Portal request cancelled or failed (code={response_code})"
            console.print(f"[red]{error_msg}[/red]")
            self._cleanup()
            if self.on_error:
                GLib.idle_add(self.on_error, error_msg)
            return

        # State machine transitions
        if self._state == "creating":
            self.session_handle = results.get("session_handle")
            self._debug(f"Session created: {self.session_handle}")
            # Move to selecting sources
            GLib.idle_add(self._select_sources)

        elif self._state == "selecting":
            self._debug("Source selected!")
            # Move to starting stream
            GLib.idle_add(self._start_stream)

        elif self._state == "starting":
            streams = results.get("streams")
            if not streams:
                error_msg = "No streams returned from portal"
                console.print(f"[red]{error_msg}[/red]")
                self._cleanup()
                if self.on_error:
                    GLib.idle_add(self.on_error, error_msg)
                return

            self.node_id = streams[0][0]
            self._debug(f"Got PipeWire Node ID: {self.node_id}")
            # Start the actual recording
            GLib.idle_add(self._start_pipeline)

    def start(self):
        """Start the recording process (async).

        This initiates the portal session. The user will see a dialog to select
        the screen/window to record. Recording actually starts after selection.
        """
        if self._state != "idle":
            console.print("[yellow]Recording already in progress[/yellow]")
            return

        self._debug("Starting recording process...")
        self._subscribe_to_responses()
        self._create_session()

    def _create_session(self):
        """Create a ScreenCast session."""
        self._state = "creating"

        try:
            res = self.connection.call_sync(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.ScreenCast",
                "CreateSession",
                GLib.Variant(
                    "(a{sv})",
                    (
                        {
                            "session_handle_token": GLib.Variant(
                                "s", self.session_token
                            ),
                            "handle_token": GLib.Variant(
                                "s", f"create_{self.session_token}"
                            ),
                        },
                    ),
                ),
                GLib.VariantType("(o)"),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            self._pending_request_path = res[0]
            self._debug(f"CreateSession request: {self._pending_request_path}")
        except Exception as e:
            console.print(f"[red]CreateSession failed: {e}[/red]")
            self._cleanup()
            if self.on_error:
                self.on_error(str(e))

    def _select_sources(self):
        """Request source selection (shows dialog)."""
        self._state = "selecting"

        self._debug("Requesting sources (dialog should appear)...")

        try:
            res = self.connection.call_sync(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.ScreenCast",
                "SelectSources",
                GLib.Variant(
                    "(oa{sv})",
                    (
                        self.session_handle,
                        {
                            "multiple": GLib.Variant("b", False),
                            "types": GLib.Variant("u", 3),  # Monitor + Window
                            "cursor_mode": GLib.Variant("u", 2),  # Embedded
                            "persist_mode": GLib.Variant("u", 2),  # Application decides
                            "handle_token": GLib.Variant(
                                "s", f"select_{self.session_token}"
                            ),
                        },
                    ),
                ),
                GLib.VariantType("(o)"),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            self._pending_request_path = res[0]
            self._debug(f"SelectSources request: {self._pending_request_path}")
        except Exception as e:
            console.print(f"[red]SelectSources failed: {e}[/red]")
            self._cleanup()
            if self.on_error:
                self.on_error(str(e))

    def _start_stream(self):
        """Start the screencast stream."""
        self._state = "starting"

        self._debug("Starting stream...")

        try:
            res = self.connection.call_sync(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.ScreenCast",
                "Start",
                GLib.Variant(
                    "(osa{sv})",
                    (
                        self.session_handle,
                        "",  # parent_window
                        {
                            "handle_token": GLib.Variant(
                                "s", f"start_{self.session_token}"
                            )
                        },
                    ),
                ),
                GLib.VariantType("(o)"),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
            )
            self._pending_request_path = res[0]
            self._debug(f"Start request: {self._pending_request_path}")
        except Exception as e:
            console.print(f"[red]Start failed: {e}[/red]")
            self._cleanup()
            if self.on_error:
                self.on_error(str(e))

    def _start_pipeline(self):
        """Build and start the GStreamer pipeline."""
        self._state = "recording"
        self.is_recording = True

        pipeline_str = (
            f"pipewiresrc path={self.node_id} do-timestamp=true ! "
            "videoconvert ! "
            "x264enc tune=zerolatency speed-preset=superfast ! "
            "queue ! "
            "mp4mux name=mux ! "
            f"filesink location={self.output_file} "
            "pulsesrc ! "
            "audioconvert ! "
            "lamemp3enc target=1 bitrate=128 cbr=true ! "
            "queue ! mux."
        )

        self._debug(f"Starting GStreamer pipeline: {pipeline_str}")

        try:
            self.pipeline = Gst.parse_launch(pipeline_str)

            # Set up error handling on the bus
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message::error", self._on_bus_error)

            ret = self.pipeline.set_state(Gst.State.PLAYING)

            if ret == Gst.StateChangeReturn.FAILURE:
                raise Exception("Unable to start pipeline")

            if self.on_ready:
                self.on_ready()

        except Exception as e:
            console.print(f"[red]Pipeline failed: {e}[/red]")
            self._cleanup()
            if self.on_error:
                self.on_error(str(e))

    def _on_bus_error(self, bus, msg):
        """Handle GStreamer bus errors."""
        err, debug = msg.parse_error()
        console.print(f"[red]GStreamer error: {err.message}[/red]")
        console.print(f"[dim]Debug: {debug}[/dim]")
        self._cleanup()
        if self.on_error:
            GLib.idle_add(self.on_error, err.message)

    def _cleanup(self):
        """Clean up resources."""
        self._unsubscribe_from_responses()
        self._state = "idle"
        self._pending_request_path = None
        self.is_recording = False

        if self.session_handle:
            try:
                self.connection.call_sync(
                    "org.freedesktop.portal.Desktop",
                    self.session_handle,
                    "org.freedesktop.portal.Session",
                    "Close",
                    None,
                    None,
                    Gio.DBusCallFlags.NONE,
                    -1,
                    None,
                )
            except Exception:
                pass
            self.session_handle = None

    def stop(self):
        """Stop the recording with proper EOS handling."""
        if not self.pipeline:
            self._cleanup()
            if self.on_stopped:
                self.on_stopped()
            return

        # Send EOS
        self.pipeline.send_event(Gst.Event.new_eos())

        # Set up async EOS handling via bus callback
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()

        def on_message(bus, msg):
            if msg.type == Gst.MessageType.EOS:
                self.pipeline.set_state(Gst.State.NULL)
                self.pipeline = None
                self._cleanup()
                if self.on_stopped:
                    self.on_stopped()
                return False  # Remove handler
            elif msg.type == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                console.print(f"[red]GStreamer error: {err.message}[/red]")
                self.pipeline.set_state(Gst.State.NULL)
                self.pipeline = None
                self._cleanup()
                if self.on_stopped:
                    self.on_stopped()
                return False
            return True

        bus.connect("message", on_message)

        # Fallback timeout in case EOS never arrives
        def timeout_stop():
            if self.pipeline:
                self.pipeline.set_state(Gst.State.NULL)
                self.pipeline = None
                self._cleanup()
                if self.on_stopped:
                    self.on_stopped()
            return False

        GLib.timeout_add_seconds(3, timeout_stop)

        self._cleanup()

        if self.on_stopped:
            self.on_stopped()


def record(output_file):
    """Standalone recording function (for CLI use)."""
    import signal

    recorder = PortalRecorder(output_file)
    loop = GLib.MainLoop()

    def on_ready():
        console.print("[bold red]Recording... Press Ctrl+C to stop[/bold red]")

    def on_error(msg):
        console.print(f"[red]Error: {msg}[/red]")
        loop.quit()

    def on_stopped():
        loop.quit()

    def handle_sigint(sig, frame):
        console.print("\n[yellow]Stopping...[/yellow]")
        recorder.stop()

    signal.signal(signal.SIGINT, handle_sigint)

    recorder.on_ready = on_ready
    recorder.on_error = on_error
    recorder.on_stopped = on_stopped

    recorder.start()
    loop.run()
