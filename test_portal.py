import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gio
import os
import sys


def test_portal():
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    session_token = f"ayeye_test_{os.getpid()}"

    print(f"Token: {session_token}")

    try:
        print("1. CreateSession")
        res = connection.call_sync(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.ScreenCast",
            "CreateSession",
            GLib.Variant(
                "(a{sv})", ({"session_handle_token": GLib.Variant("s", session_token)},)
            ),
            GLib.VariantType("(o)"),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
        print(f"Result type: {type(res)}")
        print(f"Result: {res}")

        # In PyGObject, GVariant is usually returned. We can unpack.
        session_handle = res.unpack()[0]
        print(f"Session Handle: {session_handle}")

        print("2. SelectSources")
        res = connection.call_sync(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.ScreenCast",
            "SelectSources",
            GLib.Variant(
                "(oa{sv})",
                (
                    session_handle,
                    {
                        "multiple": GLib.Variant("b", False),
                        "types": GLib.Variant("u", 1 | 2),
                        "cursor_mode": GLib.Variant("u", 2),
                        "handle_token": GLib.Variant("s", f"request_{session_token}"),
                    },
                ),
            ),
            GLib.VariantType("(o)"),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
        )
        request_handle = res.unpack()[0]
        print(f"Request Handle: {request_handle}")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_portal()
