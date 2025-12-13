#!/usr/bin/env python3
"""Standalone recording helper that runs in its own process.

This avoids all the GLib main loop threading issues by being a separate process.
The parent can just send SIGTERM to stop it cleanly.
"""

import gi

gi.require_version("Gst", "1.0")
gi.require_version("Gio", "2.0")
from gi.repository import Gst, GLib, Gio

import os
import signal
import sys

Gst.init(None)


class Recorder:
    def __init__(self, output_file):
        self.output_file = output_file
        self.pipeline = None
        self.loop = GLib.MainLoop()
        self.node_id = None
        self.session_handle = None
        self.connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.session_token = f"ayeye_helper_{os.getpid()}"

    def run(self):
        """Run the recorder - blocks until stopped."""

        # Set up signal handler for clean shutdown
        def on_signal(sig, frame):
            self.stop()

        signal.signal(signal.SIGINT, on_signal)
        signal.signal(signal.SIGTERM, on_signal)

        # Start the portal flow
        if not self._setup_portal():
            sys.exit(1)

        # Start pipeline
        if not self._start_pipeline():
            sys.exit(1)

        print("RECORDING_STARTED", flush=True)

        # Run until stopped
        self.loop.run()

        print("RECORDING_STOPPED", flush=True)

    def _setup_portal(self):
        """Set up the XDG portal screencast session."""
        try:
            # Create session
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
            request_path = res[0]

            if not self._wait_for_response(request_path):
                return False

            # Select sources
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
                            "cursor_mode": GLib.Variant("u", 2),
                            "persist_mode": GLib.Variant("u", 2),
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
            request_path = res[0]

            if not self._wait_for_response(request_path):
                return False

            # Start stream
            res = self.connection.call_sync(
                "org.freedesktop.portal.Desktop",
                "/org/freedesktop/portal/desktop",
                "org.freedesktop.portal.ScreenCast",
                "Start",
                GLib.Variant(
                    "(osa{sv})",
                    (
                        self.session_handle,
                        "",
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
            request_path = res[0]

            if not self._wait_for_response(request_path, get_streams=True):
                return False

            return True

        except Exception as e:
            print(f"Portal error: {e}", file=sys.stderr, flush=True)
            return False

    def _wait_for_response(self, request_path, get_streams=False, timeout=60):
        """Wait for portal response."""
        result = [None]
        got_response = [False]

        def on_response(connection, sender, path, interface, signal, params, data):
            if path != request_path:
                return

            code = params[0]
            results = params[1]

            if code != 0:
                got_response[0] = True
                return

            if get_streams:
                streams = results.get("streams")
                if streams:
                    self.node_id = streams[0][0]
            else:
                session = results.get("session_handle")
                if session:
                    self.session_handle = session

            result[0] = True
            got_response[0] = True

        sub_id = self.connection.signal_subscribe(
            "org.freedesktop.portal.Desktop",
            "org.freedesktop.portal.Request",
            "Response",
            None,
            None,
            Gio.DBusSignalFlags.NONE,
            on_response,
            None,
        )

        # Run loop until response or timeout
        def check_response():
            if got_response[0]:
                self.loop.quit()
                return False
            return True

        GLib.timeout_add(100, check_response)
        GLib.timeout_add_seconds(timeout, lambda: (self.loop.quit(), False)[1])

        self.loop.run()
        self.loop = GLib.MainLoop()  # Reset for next use

        self.connection.signal_unsubscribe(sub_id)

        return result[0] is True

    def _start_pipeline(self):
        """Start the GStreamer pipeline."""
        if not self.node_id:
            print("No node_id", file=sys.stderr, flush=True)
            return False

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

        try:
            self.pipeline = Gst.parse_launch(pipeline_str)

            # Watch for errors
            bus = self.pipeline.get_bus()
            bus.add_signal_watch()
            bus.connect("message::error", self._on_error)
            bus.connect("message::eos", self._on_eos)

            ret = self.pipeline.set_state(Gst.State.PLAYING)
            if ret == Gst.StateChangeReturn.FAILURE:
                print("Failed to start pipeline", file=sys.stderr, flush=True)
                return False

            return True

        except Exception as e:
            print(f"Pipeline error: {e}", file=sys.stderr, flush=True)
            return False

    def _on_error(self, bus, msg):
        err, debug = msg.parse_error()
        print(f"GStreamer error: {err.message}", file=sys.stderr, flush=True)
        self.loop.quit()

    def _on_eos(self, bus, msg):
        self.pipeline.set_state(Gst.State.NULL)
        self.loop.quit()

    def stop(self):
        """Stop recording gracefully."""
        if self.pipeline:
            self.pipeline.send_event(Gst.Event.new_eos())
            # Don't block - let the EOS handler deal with it


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: record_helper.py <output_file>", file=sys.stderr)
        sys.exit(1)

    recorder = Recorder(sys.argv[1])
    recorder.run()
