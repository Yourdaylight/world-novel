#!/usr/bin/env python3
"""Sync docs/product/*.md into docs-site/product/ and verify equality.

- Build mode (default): copy source docs into the VitePress content tree and
  rewrite sibling links (./xx.md -> /product/xx) for cleanUrls.
- Check mode (--check): exit non-zero if the destination is stale
  (used to keep docs/product and the published site in sync).

Usage:
    python3 scripts/sync_product_docs.py          # sync
    python3 scripts/sync_product_docs.py --check  # CI verify
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "product"
DST = ROOT / "docs-site" / "product"

LINK_RE = re.compile(r"\]\(\./([0-9a-zA-Z_-]+\.md)(#[^)]*)?\)")


def rewrite(text: str) -> str:
    # ./01-vision.md#x -> /product/01-vision#x  (cleanUrls drops .md)
    def repl(m: re.Match) -> str:
        name = m.group(1).removesuffix(".md")
        anchor = m.group(2) or ""
        return f"](/product/{name}{anchor})"

    return LINK_RE.sub(repl, text)


def main(check: bool) -> int:
    if not SRC.exists():
        print(f"source dir not found: {SRC}", file=sys.stderr)
        return 1

    DST.mkdir(parents=True, exist_ok=True)
    stale = False
    for src_file in sorted(SRC.glob("*.md")):
        expected = rewrite(src_file.read_text(encoding="utf-8"))
        dst_file = DST / src_file.name
        if check:
            if not dst_file.exists() or dst_file.read_text(encoding="utf-8") != expected:
                print(f"STALE: {dst_file.relative_to(ROOT)}")
                stale = True
        else:
            dst_file.write_text(expected, encoding="utf-8")
            print(f"synced {src_file.name}")

    if check and stale:
        print("\nRun `python3 scripts/sync_product_docs.py` to fix.", file=sys.stderr)
        return 1
    if check:
        print("product docs in sync ✓")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--check" in sys.argv))
