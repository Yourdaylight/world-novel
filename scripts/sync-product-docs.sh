#!/usr/bin/env bash
# 同步产品设计文档 docs/product/*.md → docs-site/product/
# 用法:
#   scripts/sync-product-docs.sh          # 同步（覆盖）
#   scripts/sync-product-docs.sh --check  # CI 校验：不一致则退出 1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/docs/product"
DST="$ROOT/docs-site/product"

if [[ "${1:-}" == "--check" ]]; then
  tmp="$(mktemp -d)"
  cp "$SRC"/*.md "$tmp"/
  if ! diff -rq "$tmp" "$DST" >/dev/null 2>&1; then
    echo "✗ docs-site/product 与 docs/product 不一致，请运行 scripts/sync-product-docs.sh"
    diff -rq "$tmp" "$DST" || true
    rm -rf "$tmp"
    exit 1
  fi
  rm -rf "$tmp"
  echo "✓ 产品文档已同步"
  exit 0
fi

mkdir -p "$DST"
# Mirror semantics: also remove destination files no longer present upstream
rm -f "$DST"/*.md
cp "$SRC"/*.md "$DST"/
echo "✓ 已同步 $(ls "$SRC"/*.md | wc -l | tr -d ' ') 篇产品文档到 docs-site/product/"
