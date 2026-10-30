"""Load this checkout's ignored .env without replacing explicitly set variables."""
import os
from pathlib import Path


def load_local_env(path=None):
    file = Path(path) if path else Path(__file__).resolve().parents[1] / '.env'
    if not file.is_file():
        return
    for raw in file.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if key.isidentifier():
            os.environ.setdefault(key, value.strip().strip('"').strip("'"))
