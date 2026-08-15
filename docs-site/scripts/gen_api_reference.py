#!/usr/bin/env python3
"""Generate the API reference page from the live OpenAPI schema.

Usage:
    cd docs-site && uv run python scripts/gen_api_reference.py

Output: reference/api.md — grouped by tag/prefix, with method, path, summary
and auth hint. Runs offline against the app object (no server needed).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[2]
sys.path.insert(0, str(ROOT / "src"))

OUT = Path(__file__).parent.parent / "reference" / "api.md"

GROUPS = [
    ("认证与额度", ("/api/auth",)),
    ("分享与阅读", ("/api/share", "/api/bookshelf")),
    ("成书发布", ("/api/publish",)),
    ("管理后台", ("/api/admin",)),
    ("史官", ("/api/historian",)),
    ("生成流水线", ("/api/generat",)),
    ("章节内容", ("/api/chapter-text", "/api/novel-full")),
    ("小说与世界", ("/api/novels", "/api/worlds")),
]


def classify(path: str) -> str:
    for name, prefixes in GROUPS:
        if any(path.startswith(p) for p in prefixes):
            return name
    return "其他"


def main() -> None:
    from novel_creator.web.app import app

    spec = app.openapi()
    paths = spec.get("paths", {})

    grouped: dict[str, list[tuple[str, str, str]]] = {}
    for path, methods in sorted(paths.items()):
        for method, op in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue
            summary = op.get("summary") or op.get("description", "").split("\n")[0]
            grouped.setdefault(classify(path), []).append(
                (method.upper(), path, summary)
            )

    lines = [
        "# API 参考",
        "",
        "> 本页由 OpenAPI schema 自动生成：`uv run python docs-site/scripts/gen_api_reference.py`",
        "> 交互式版本：启动服务后访问 `/docs`（Swagger UI）。",
        "",
        "认证方式：请求头 `X-User-Token: <token>` 或 `Authorization: Bearer <token>`。"
        "jwt 模式下 token 来自 `POST /api/auth/login`（邀请码登录）。",
        "",
    ]

    for group, _ in GROUPS + [("其他", "")]:
        items = grouped.get(group)
        if not items:
            continue
        lines.append(f"## {group}")
        lines.append("")
        lines.append("| 方法 | 路径 | 说明 |")
        lines.append("|------|------|------|")
        for method, path, summary in items:
            summary = summary.replace("|", "\\|")
            lines.append(f"| `{method}` | `{path}` | {summary} |")
        lines.append("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    total = sum(len(v) for v in grouped.values())
    print(f"wrote {OUT} ({total} endpoints)")


if __name__ == "__main__":
    main()
