#!/usr/bin/env python3
"""Dump the FastAPI OpenAPI schema into docs-site/public/openapi.json.

Run: uv run python scripts/gen_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

from novel_creator.web.app import app

OUT = Path(__file__).resolve().parent.parent / "docs-site" / "public" / "openapi.json"


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    OUT.write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes, {len(schema.get('paths', {}))} paths)")


if __name__ == "__main__":
    main()
