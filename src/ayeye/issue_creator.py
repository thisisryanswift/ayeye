import subprocess
import os
import sys
from rich.console import Console

console = Console()


def create_issue(analysis, video_path):
    title = analysis.get("title", "Untitled Issue")
    summary = analysis.get("summary", "")
    steps = "\n".join(
        [f"{i + 1}. {step}" for i, step in enumerate(analysis.get("steps", []))]
    )
    timestamps = "\n".join(
        [
            f"- {t.get('time', '')}: {t.get('description', '')}"
            for t in analysis.get("timestamps", [])
        ]
    )

    description = f"""{summary}

## Reproduction Steps
{steps}

## Timestamps
{timestamps}

## Video Reference
Local: {video_path}
"""

    # Check if we are in a beads repo
    in_beads_repo = False
    try:
        # Check if .beads directory exists in current or parent dirs
        # Simple check: call bd status
        res = subprocess.run(["bd", "status"], capture_output=True, text=True)
        # bd status returns 0 if initialized
        if res.returncode == 0:
            in_beads_repo = True
    except FileNotFoundError:
        pass

    if in_beads_repo:
        console.print("[green]Beads repository detected. Creating issue...[/green]")
        try:
            cmd = [
                "bd",
                "create",
                "--title",
                title,
                "--description",
                description,
                "--type",
                "bug",
                "--labels",
                "video-report",
            ]
            subprocess.run(cmd, check=True)
            subprocess.run(["notify-send", "Issue Recorder", f"Issue created: {title}"])
            return
        except subprocess.CalledProcessError:
            console.print(
                "[red]Failed to create beads issue. Falling back to clipboard.[/red]"
            )

    # Fallback to clipboard
    console.print("Copying to clipboard...")
    full_text = f"# {title}\n{description}"

    try:
        process = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
        process.communicate(input=full_text.encode("utf-8"))
        console.print("[green]Copied to clipboard![/green]")
        subprocess.run(["notify-send", "Issue Recorder", "Issue copied to clipboard"])
    except FileNotFoundError:
        console.print("[red]wl-copy not found. Cannot copy to clipboard.[/red]")
