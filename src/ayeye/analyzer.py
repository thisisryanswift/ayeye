from google import genai
from google.genai import types
from .config import GEMINI_API_KEY
import json
import time
import os
from rich.console import Console

console = Console()


def analyze_video(video_path):
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set")

    client = genai.Client(api_key=GEMINI_API_KEY)

    console.print(f"Uploading {video_path} to Gemini...")
    file_ref = client.files.upload(file=str(video_path))

    console.print(f"File uploaded: {file_ref.name}")

    # Wait for processing to complete
    while True:
        # file_ref.name is guaranteed to be a string here as it came from upload
        if not file_ref.name:
            raise Exception("Upload failed, no file name returned")

        file_ref = client.files.get(name=file_ref.name)
        if file_ref.state == "ACTIVE":
            break
        elif file_ref.state == "FAILED":
            raise Exception("Video processing failed")

        console.print("Processing video...", end="\r")
        time.sleep(2)

    console.print("[green]Video ready.[/green]")

    prompt = """
    Analyze this screen recording of a software issue. The user is demonstrating a bug or problem.
    
    Extract:
    1. A concise title (max 80 chars)
    2. A summary of the issue (2-3 sentences)
    3. Step-by-step reproduction instructions based on the user's actions
    4. Key timestamps where important actions occur
    
    Provide the output in JSON format.
    """

    console.print("Requesting analysis from Gemini 2.5 Flash...")

    # JSON Schema definition for structured output
    schema = {
        "type": "OBJECT",
        "properties": {
            "title": {"type": "STRING"},
            "summary": {"type": "STRING"},
            "steps": {"type": "ARRAY", "items": {"type": "STRING"}},
            "timestamps": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "time": {"type": "STRING"},
                        "description": {"type": "STRING"},
                    },
                },
            },
        },
        "required": ["title", "summary", "steps", "timestamps"],
    }

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[file_ref, prompt],
            config=types.GenerateContentConfig(
                response_mime_type="application/json", response_schema=schema
            ),
        )

        # Parse JSON
        if not response.text:
            raise ValueError("Empty response from Gemini")

        # Clean up code blocks if present (Gemini sometimes adds ```json ... ```)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        result = json.loads(text.strip())
        return result

    except Exception as e:
        console.print(f"[bold red]Analysis failed: {e}[/bold red]")
        raise
