import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROFILES_DIR = DATA_DIR / "profiles"
PROJECTS_DIR = DATA_DIR / "projects"
OUTPUT_DIR = DATA_DIR / "output"
ACCOUNTS_FILE = DATA_DIR / "accounts.json"

DEFAULT_MUSE_URL = os.environ.get("MUSE_URL", "https://muse.ai")
DEFAULT_HOST = os.environ.get("HOST", "127.0.0.1")
DEFAULT_PORT = int(os.environ.get("PORT", "8000"))
DEFAULT_MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "3"))

def ensure_directories():
    for p in [DATA_DIR, PROFILES_DIR, PROJECTS_DIR, OUTPUT_DIR]:
        p.mkdir(parents=True, exist_ok=True)
    # accounts.json is NOT created here: only AccountManager._ensure_storage() may create it, under the
    # accounts OS lock and create-exclusive (an unlocked write here could wipe accounts written by another process).

ensure_directories()
