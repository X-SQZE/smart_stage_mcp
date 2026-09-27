from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
GITHUB_REPO = os.getenv("GITHUB_REPO_FULL_NAME") or (
    f"{os.getenv('GITHUB_OWNER')}/{os.getenv('GITHUB_REPO')}"
)
GITHUB_TOKEN=os.getenv("GITHUB_TOKEN", "")