"""Interactive single-shot recording mode using wf-recorder.

Usage: Just run `ayeye` with no arguments.
- Prompts to select screen/window via wf-recorder
- Records until you press Enter
- Analyzes with Gemini and creates issue
- Exits
"""

import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from rich.console import Console

from .config import RECORDINGS_DIR
from .analyzer import analyze_video
from .issue_creator import create_issue

console = Console()


def run_interactive():
    """Run AyEye in interactive single-shot mode."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = RECORDINGS_DIR / f"issue_{timestamp}.mp4"

    console.print("[dim]Starting screen recorder...[/dim]")
    console.print("[dim]Select a screen or window in the dialog...[/dim]")

    # Start wf-recorder with audio, geometry selection
    process = subprocess.Popen(
        [
            "wf-recorder",
            "-a",  # Record audio
            "-g",
            "",  # Empty geometry triggers selection dialog (slurp)
            "-f",
            str(output_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait a moment to see if it started successfully
    import time

    time.sleep(0.5)

    if process.poll() is not None:
        # Process exited already - probably an error
        stderr = process.stderr.read().decode() if process.stderr else ""
        console.print(f"[red]Failed to start recorder: {stderr}[/red]")
        sys.exit(1)

    console.print(
        "\n[bold green]Recording![/bold green] Press [bold]Enter[/bold] to stop...\n"
    )

    # Wait for Enter
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        pass

    # Stop recording gracefully
    console.print("[yellow]Stopping recording...[/yellow]")
    process.send_signal(signal.SIGINT)

    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()

    # Check if file was created
    if not output_file.exists() or output_file.stat().st_size == 0:
        console.print("[red]No recording was made.[/red]")
        sys.exit(1)

    console.print(f"[dim]Saved to {output_file}[/dim]")

    # Analyze and create issue
    try:
        with console.status("[yellow]Uploading and analyzing video...[/yellow]"):
            analysis = analyze_video(output_file)

        console.print(
            f"[green]Analysis complete:[/green] {analysis.get('title', 'Untitled')}"
        )

        with console.status("[yellow]Creating issue...[/yellow]"):
            create_issue(analysis, output_file)

        console.print("[bold green]Done![/bold green]")
    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        sys.exit(1)
