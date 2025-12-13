import click
import os
import sys


@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """AyEye - AI-powered video issue recorder.

    Run without arguments for interactive single-shot recording.
    Use 'ayeye start' to run as a background daemon with system tray.
    """
    if ctx.invoked_subcommand is None:
        # Default: interactive single-shot mode
        from .interactive import run_interactive

        run_interactive()


@cli.command()
@click.option(
    "--foreground", "-f", is_flag=True, help="Run in foreground (don't daemonize)"
)
def start(foreground):
    """Start the AyEye daemon (system tray).

    By default, runs in the background. Use -f to run in foreground.
    """
    if foreground:
        _run_daemon_foreground()
    else:
        _daemonize()


def _run_daemon_foreground():
    """Run the daemon in foreground (for debugging)."""
    from .app import main as app_main

    sys.argv = [sys.argv[0]]
    app_main()


def _daemonize():
    """Fork to background and run daemon."""
    # First fork
    try:
        pid = os.fork()
        if pid > 0:
            # Parent exits
            print(f"AyEye daemon started (PID: {pid})")
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f"Fork #1 failed: {e}\n")
        sys.exit(1)

    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        sys.stderr.write(f"Fork #2 failed: {e}\n")
        sys.exit(1)

    # Redirect standard file descriptors to /dev/null
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    with open("/dev/null", "a+") as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())

    # Now run the daemon
    from .app import main as app_main

    sys.argv = [sys.argv[0]]
    app_main()


@cli.command()
def watch():
    """Toggle recording - 'ayeye, watch this!'

    Sends toggle command to running daemon.
    """
    from .app import main as app_main

    sys.argv = [sys.argv[0], "toggle"]
    app_main()


@cli.command()
def stop():
    """Stop recording (sends stop to daemon)."""
    from .app import main as app_main

    sys.argv = [sys.argv[0], "stop"]
    app_main()


@cli.command(name="quit")
def quit_cmd():
    """Quit the daemon."""
    from .app import main as app_main

    sys.argv = [sys.argv[0], "quit"]
    app_main()


if __name__ == "__main__":
    cli()
