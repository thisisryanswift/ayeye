import os
from pathlib import Path
from dotenv import load_dotenv

# Config directory
CONFIG_DIR = Path.home() / ".config" / "ayeye"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Load environment variables from .env files
# Priority:
# 1. Environment variables set in shell
# 2. .env in current directory
# 3. .env in configuration directory (~/.config/ayeye/.env)

load_dotenv(Path.cwd() / ".env")
load_dotenv(CONFIG_DIR / ".env")

# Recordings directory - use ~/Videos/AyEye by default
RECORDINGS_DIR = Path(
    os.environ.get("AYEYE_RECORDINGS_DIR", Path.home() / "Videos" / "AyEye")
)
RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)

# Base directory for app data (PID file, etc.)
BASE_DIR = Path.home() / ".local/share/ayeye"
BASE_DIR.mkdir(parents=True, exist_ok=True)

# PID file for state management
PID_FILE = BASE_DIR / "recorder.pid"

# Gemini API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Recording settings
DEFAULT_FRAMERATE = 30
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
