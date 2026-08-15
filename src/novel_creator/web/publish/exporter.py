"""Export builders for platform publishing (A-2, needs doc §3.3–3.4).

Outputs:
- TXT rendering with platform-specific chapter headers & encoding
  (fanqie: GB18030; qimao: per-volume files; generic: UTF-8)
- Minimal standards-compliant EPUB3 (no external deps)
- SVG cover placeholder + intro/README/metadata
- ZIP delivery package with everything an author uploads manually

L1 browser automation is intentionally NOT here — no platform has an open API
(needs doc §3.2); L0 export is the guaranteed path.
"""

from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from datetime import date

COVER_TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#1c1917"/>
      <stop offset="1" stop-color="#431407"/>
    </linearGradient>
  </defs>
  <rect width="600" height="800" fill="url(#bg)"/>
  <circle cx="300" cy="330" r="120" fill="none" stroke="#f97316" stroke-width="3" opacity="0.85"/>
  <path d="M250 330 Q 260 270, 300 260 Q 340 270, 350 330 Q 340 390, 300 400 Q 260 390, 250 330Z"
        fill="none" stroke="#fdba74" stroke-width="2" opacity="0.7"/>
  <text x="300" y="560" text-anchor="middle" font-family="serif" font-size="44" fill="#fafafa">{title}</text>
  <text x="300" y="610" text-anchor="middle" font-family="sans-serif" font-size="20" fill="#a8a29e">{genre}</text>
  <text x="300" y="740" text-anchor="middle" font-family="sans-serif" font-size="14" fill="#78716c">WorldNovel · 封面占位图 · 请在平台侧替换正式封面</text>
</svg>
"""


def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\s]+", "-", name.strip())
    return name[:60] or "novel"


def build_cover_svg(title: str, genre: str = "") -> str:
    return COVER_TEMPLATE.format(
        title=_xml_escape(title or "未命名"), genre=_xml_escape(genre)
    )


def build_intro(meta: dict) -> str:
    """Compose the book intro shipped with the export package."""
    parts = []
    if meta.get("premise"):
        parts.append(meta["premise"].strip())
    if meta.get("setting"):
        parts.append(meta["setting"].strip())
    if not parts:
        parts.append(
            f"《{meta.get('title') or '未命名'}》是一部由 WorldNovel 多 Agent "
            "系统生成的长篇小说。简介待作者补充。"
        )
    return "\n\n".join(parts)


def _chapter_header(chapter: dict) -> str:
    num = f"第{chapter['chapter_index'] + 1}章"
    title = (chapter["title"] or "").strip()
    # 空标题或标题本身即"第N章"时，避免重复章号
    if not title or title == num:
        return num
    return f"{num} {title}"


def _group_by_volume(chapters: list[dict], volumes: list[dict]) -> list[dict]:
    """Return [{title, chapters:[...]}]; single pseudo-volume when no volumes.

    Each chapter belongs to at most one volume: when volume ranges overlap the
    FIRST volume wins (prevents duplicate chapters in TXT / duplicate manifest
    ids in EPUB). Chapters not covered by any volume go to a trailing group.
    """
    if not volumes:
        return [{"title": "", "chapters": chapters}]

    groups: list[dict] = []
    assigned: set[int] = set()
    for v in volumes:
        in_range = [
            c
            for c in chapters
            if v["chapter_start"] <= c["chapter_index"] <= v["chapter_end"]
            and c["chapter_index"] not in assigned
        ]
        if in_range:
            assigned.update(c["chapter_index"] for c in in_range)
            groups.append({"title": v["title"], "chapters": in_range})
    leftovers = [c for c in chapters if c["chapter_index"] not in assigned]
    if leftovers:
        groups.append({"title": "其他章节", "chapters": leftovers})
    return groups


def build_txt(chapters: list[dict], volumes: list[dict], *, with_volume_marks: bool) -> str:
    """Single-file TXT with optional volume headers (UTF-8 string)."""
    parts: list[str] = []
    for group in _group_by_volume(chapters, volumes):
        if with_volume_marks and group["title"]:
            parts.append(f"\n{'=' * 20}\n卷 · {group['title']}\n{'=' * 20}\n")
        for ch in group["chapters"]:
            parts.append(f"\n{_chapter_header(ch)}\n\n{ch['body'].strip()}\n")
    return "\n".join(parts).strip() + "\n"


def build_volume_txts(chapters: list[dict], volumes: list[dict]) -> dict[str, str]:
    """Per-volume TXT map for platforms supporting volume import (七猫)."""
    out: dict[str, str] = {}
    for i, group in enumerate(_group_by_volume(chapters, volumes), start=1):
        label = f"卷{i:02d}-{_safe_filename(group['title'])}" if group["title"] else f"卷{i:02d}"
        body = "\n".join(
            f"\n{_chapter_header(ch)}\n\n{ch['body'].strip()}\n"
            for ch in group["chapters"]
        ).strip() + "\n"
        out[f"{label}.txt"] = body
    return out


def _epub_chapter_xhtml(chapter: dict) -> str:
    paragraphs = [
        f"<p>{_xml_escape(p.strip())}</p>"
        for p in chapter["body"].splitlines()
        if p.strip()
    ]
    body = "\n".join(paragraphs) or "<p>（本章暂无内容）</p>"
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN">
<head><title>{_xml_escape(_chapter_header(chapter))}</title></head>
<body>
<h2>{_xml_escape(_chapter_header(chapter))}</h2>
{body}
</body>
</html>
"""


def build_epub(title: str, chapters: list[dict], volumes: list[dict],
               meta: dict, identifier: str | None = None) -> bytes:
    """Build a minimal valid EPUB3 as bytes."""
    book_id = identifier or f"urn:uuid:{uuid.uuid4()}"
    lang = "zh-CN"
    modified = date.today().isoformat() + "T00:00:00Z"

    manifest_items = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="cover" href="cover.svg" media-type="image/svg+xml"/>',
    ]
    spine_items: list[str] = []
    xhtmls: dict[str, str] = {}

    for i, group in enumerate(_group_by_volume(chapters, volumes)):
        for ch in group["chapters"]:
            idx = ch["chapter_index"]
            cid = f"ch{idx}"
            fname = f"chapter-{idx:04d}.xhtml"
            manifest_items.append(
                f'<item id="{cid}" href="{fname}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{cid}"/>')
            xhtmls[fname] = _epub_chapter_xhtml(ch)

    manifest = "\n    ".join(manifest_items)
    spine = "\n    ".join(spine_items)

    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{book_id}</dc:identifier>
    <dc:title>{_xml_escape(title)}</dc:title>
    <dc:language>{lang}</dc:language>
    <dc:creator>WorldNovel</dc:creator>
    <dc:description>{_xml_escape(build_intro(meta)[:500])}</dc:description>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
    {manifest}
  </manifest>
  <spine>
    {spine}
  </spine>
</package>
"""

    nav_lis = []
    for ch in chapters:
        idx = ch["chapter_index"]
        nav_lis.append(
            f'<li><a href="chapter-{idx:04d}.xhtml">'
            f"{_xml_escape(_chapter_header(ch))}</a></li>"
        )
    nav = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" lang="zh-CN">
<head><title>目录</title></head>
<body>
<nav epub:type="toc" id="toc">
<h1>目录</h1>
<ol>
{chr(10).join(nav_lis)}
</ol>
</nav>
</body>
</html>
"""

    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # EPUB spec: mimetype must be first entry, stored uncompressed
        zf.writestr(
            zipfile.ZipInfo("mimetype", date_time=(1980, 1, 1, 0, 0, 0)),
            "application/epub+zip",
            compress_type=zipfile.ZIP_STORED,
        )
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/nav.xhtml", nav)
        zf.writestr(
            "OEBPS/cover.svg",
            build_cover_svg(title, meta.get("genre", "")),
        )
        for fname, content in xhtmls.items():
            zf.writestr(f"OEBPS/{fname}", content)
    return buf.getvalue()


def build_readme(platform_profile: dict, title: str, stats: dict) -> str:
    return f"""《{title}》发布说明
════════════════════════════════════════
目标平台：{platform_profile['display_name']}（{platform_profile['platform']}）
导出格式：{platform_profile['formats'].upper()}   编码：{platform_profile['encoding']}
章节数：{stats.get('chapters', 0)}   总字数：{stats.get('total_words', 0)}

操作步骤：
1. 前往 {platform_profile['display_name']} 作家后台（无公开开放 API，需手动上传）。
2. 完成平台要求的实名认证（如适用）。
3. 创建新书，填写书名/简介（见 synopsis.txt），上传封面（cover.svg 为占位图，
   建议替换为正式封面）。
4. 上传正文文件{('（按卷依次上传 ' + str(stats.get('volume_count', 1)) + ' 个文件）') if platform_profile.get('supports_volumes') else ''}。
5. 回到 WorldNovel 发布管理页，回填平台侧书籍链接/ID，标记为已发布。

{platform_profile.get('notes', '')}

本包由 WorldNovel 一键导出生成。
"""


def build_package(
    *,
    platform_profile: dict,
    title: str,
    novel_id: str,
    chapters: list[dict],
    volumes: list[dict],
    meta: dict,
    stats: dict,
) -> tuple[bytes, str, dict]:
    """Build the delivery ZIP.

    Returns ``(zip_bytes, filename, export_meta)``.
    """
    platform = platform_profile["platform"]
    encoding = platform_profile.get("encoding") or "utf-8"
    safe_title = _safe_filename(title or novel_id)
    dir_name = f"{safe_title}-{platform}"

    buf = io.BytesIO()
    export_meta: dict = {
        "format": platform_profile["formats"],
        "encoding": encoding,
        "chapters": len(chapters),
        "words": stats.get("total_words", 0),
        "cover": "cover.svg",
        "files": [],
    }

    def _write(zf: zipfile.ZipFile, name: str, text: str):
        data = text.encode(encoding, errors="replace")
        zf.writestr(f"{dir_name}/{name}", data)
        export_meta["files"].append(name)

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        _write(zf, "synopsis.txt", build_intro(meta))
        _write(
            zf,
            "README-发布说明.txt",
            build_readme(platform_profile, title or novel_id, stats),
        )
        _write(zf, "meta.json", json.dumps(
            {
                "novel_id": novel_id,
                "title": title,
                "platform": platform,
                "stats": stats,
            },
            ensure_ascii=False,
            indent=2,
        ))
        zf.writestr(
            f"{dir_name}/cover.svg",
            build_cover_svg(title or novel_id, meta.get("genre", "")),
        )
        export_meta["files"].append("cover.svg")

        if platform == "epub":
            epub = build_epub(title or novel_id, chapters, volumes, meta)
            zf.writestr(f"{dir_name}/{safe_title}.epub", epub)
            export_meta["files"].append(f"{safe_title}.epub")
        elif platform == "qimao" and platform_profile.get("supports_volumes"):
            # 七猫：按卷拆分 TXT 文件
            for fname, body in build_volume_txts(chapters, volumes).items():
                _write(zf, fname, body)
        else:
            # fanqie / txt：单文件正文
            txt = build_txt(
                chapters, volumes,
                with_volume_marks=bool(platform_profile.get("supports_volumes")),
            )
            _write(zf, f"{safe_title}-全文.txt", txt)

    return buf.getvalue(), f"{safe_title}-{platform}-export.zip", export_meta
