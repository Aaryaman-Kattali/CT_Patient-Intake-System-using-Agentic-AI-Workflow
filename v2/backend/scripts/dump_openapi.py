"""Write the API's OpenAPI schema to stdout (for the frontend's generated TypeScript types).

Usage: uv run python scripts/dump_openapi.py > ../frontend/openapi.json
Needs no server, no database and no API key.
"""

import json
import os
import secrets
import sys

os.environ.setdefault("APP_SECRET", secrets.token_hex(32))

from app.config import Settings
from app.main import create_app

app = create_app(Settings(_env_file=None, database_url="sqlite://"))
sys.stdout.write(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n")
