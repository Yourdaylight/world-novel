"""Exporters — TXT (GB18030/UTF-8), EPUB3 (stdlib zipfile), per-volume ZIP.

No third-party ebook dependency: EPUB3 is a small fixed set of XML files in a
ZIP, so it is assembled directly with the standard library.
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from html import escape

from .loader import NovelContent, VolumeBrief
from .platforms import PlatformProfile


@dataclass
class ExportResult:
    filename: str
    media_type: str
    data: bytes
    meta: dict


def _safe_filename(name: str) -> str:
    """Filesystem-safe filename (keep CJK, strip path-unsafe chars)."""
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "_", name).strip().strip(".")
    return name or "novel"


def _chapter_heading(index: int, title: str) -> str:
    return f"第{index + 1}章 {title}".strip()


# XML 1.0 合法字符：#x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
_XML_INVALID = re.compile(
    "[^\t\n\r\u0020-\ud7ff\ue000-\ufffd\U00010000-\U0010FFFF]"
)


def _xml_safe(text: str) -> str:
    """Drop characters illegal in XML 1.0 (LLM output occasionally contains them)."""
    return _XML_INVALID.sub("", text)


def _xhtml_paragraphs(paragraphs: list[str], intro: bool = False) -> str:
    cls = ' class="intro"' if intro else ""
    return "\n".join(
        f"<p{cls}>{escape(_xml_safe(p))}</p>" for p in paragraphs if p.strip()
    )


def _intro_block(content: NovelContent) -> str:
    intro = content.intro.strip()
    if not intro:
        intro = "（暂无简介，请在平台侧补充）"
    author = content.author.strip() or "WorldNovel"
    return f"{content.title}\n作者：{author}\n\n简介：\n{intro}\n"


def build_txt(content: NovelContent, encoding: str) -> bytes:
    """Single-file TXT in the requested encoding (gb18030 / utf-8)."""
    parts = [_intro_block(content), "\n" + "═" * 30 + "\n\n"]
    for chapter in content.chapters:
        parts.append(_chapter_heading(chapter.index, chapter.title))
        parts.append("")
        parts.append(chapter.text.strip())
        parts.append("")
        parts.append("")
    text = "\n".join(parts)
    return text.encode(encoding, errors="replace")


def cover_svg(content: NovelContent) -> bytes:
    """Placeholder cover — a simple SVG card (no AI / image deps)."""
    title = escape(content.title or "未命名小说")
    author = escape(content.author.strip() or "WorldNovel 生成")
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0%" stop-color="#1c1917"/>
      <stop offset="100%" stop-color="#451a03"/>
    </linearGradient>
  </defs>
  <rect width="600" height="800" fill="url(#bg)"/>
  <rect x="36" y="36" width="528" height="728" fill="none" stroke="#d97706" stroke-width="2" opacity="0.7"/>
  <text x="300" y="360" font-family="serif" font-size="44" fill="#fbbf24"
        text-anchor="middle">{title}</text>
  <text x="300" y="430" font-family="sans-serif" font-size="22" fill="#fcd34d"
        text-anchor="middle" opacity="0.85">{author}</text>
  <text x="300" y="720" font-family="sans-serif" font-size="16" fill="#a8a29e"
        text-anchor="middle" opacity="0.8">WorldNovel · 多 Agent 世界演化生成</text>
</svg>
"""
    return svg.encode("utf-8")


# ── EPUB3 (minimal, stdlib-only) ────────────────────────────────────────

_EPUB_CONTAINER = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

_EPUB_CSS = """
body { font-family: serif; line-height: 1.8; margin: 5%; }
h1 { font-size: 1.4em; text-align: center; margin: 2em 0 1em; }
p { text-indent: 2em; margin: 0.6em 0; }
.intro { white-space: pre-wrap; text-indent: 0; }
"""


def _xhtml_body(title: str, paragraphs: list[str], intro: bool = False) -> str:
    body = _xhtml_paragraphs(paragraphs, intro=intro)
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="zh-CN" lang="zh-CN">\n'
        f"<head><title>{escape(_xml_safe(title))}</title>"
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>\n'
        f"<body><h1>{escape(_xml_safe(title))}</h1>\n{body}\n</body></html>\n"
    )


def _volume_for_chapter(volumes: list[VolumeBrief], index: int) -> VolumeBrief | None:
    for volume in volumes:
        if volume.chapter_start <= index <= volume.chapter_end:
            return volume
    return None


def build_epub(content: NovelContent) -> bytes:
    """Assemble a minimal valid EPUB3 (stored mimetype first, per spec)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", _EPUB_CONTAINER)
        zf.writestr("OEBPS/style.css", _EPUB_CSS)

        # Title / intro page
        intro_paragraphs = [
            f"作者：{content.author.strip() or 'WorldNovel'}",
            f"类型：{content.genre}" if content.genre else "",
            "",
            content.intro.strip() or "（暂无简介）",
        ]
        zf.writestr(
            "OEBPS/title.xhtml",
            _xhtml_body(content.title or "未命名小说", intro_paragraphs, intro=True),
        )

        chapter_files = []
        for chapter in content.chapters:
            href = f"chap-{chapter.index + 1}.xhtml"
            paragraphs = [p.strip() for p in chapter.text.split("\n") if p.strip()]
            zf.writestr(
                f"OEBPS/{href}",
                _xhtml_body(_chapter_heading(chapter.index, chapter.title), paragraphs),
            )
            chapter_files.append((href, chapter))

        # Navigation
        nav_items = [
            f'<li><a href="title.xhtml">{escape(content.title or "封面")}</a></li>'
        ]
        current_volume: VolumeBrief | None = None
        for href, chapter in chapter_files:
            volume = _volume_for_chapter(content.volumes, chapter.index)
            if volume is not None and volume != current_volume:
                current_volume = volume
                nav_items.append(
                    f'<li><strong>{escape(volume.title)}</strong></li>'
                )
            nav_items.append(
                f'<li><a href="{href}">'
                f"{escape(_chapter_heading(chapter.index, chapter.title))}</a></li>"
            )
        nav = (
            '<?xml version="1.0" encoding="utf-8"?>\n'
            '<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" '
            'xml:lang="zh-CN" lang="zh-CN">\n<head><title>目录</title></head>\n'
            '<body><nav epub:type="toc"><h1>目录</h1>\n<ol>\n'
            + "\n".join(nav_items)
            + "\n</ol></nav></body></html>\n"
        )
        zf.writestr("OEBPS/nav.xhtml", nav)

        # Package document
        uid = f"urn:uuid:worldnovel-{content.novel_id}"
        manifest_items = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>',
            '<item id="css" href="style.css" media-type="text/css"/>',
        ]
        spine_items = ['<itemref idref="title"/>']
        for i, (href, _chapter) in enumerate(chapter_files):
            cid = f"chap{i}"
            manifest_items.append(
                f'<item id="{cid}" href="{href}" media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="{cid}"/>')
        opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-CN">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{escape(_xml_safe(uid))}</dc:identifier>
    <dc:title>{escape(_xml_safe(content.title or '未命名小说'))}</dc:title>
    <dc:creator>{escape(content.author.strip() or 'WorldNovel')}</dc:creator>
    <dc:language>zh-CN</dc:language>
  </metadata>
  <manifest>
    {''.join(manifest_items)}
  </manifest>
  <spine>
    {''.join(spine_items)}
  </spine>
</package>
"""
        zf.writestr("OEBPS/content.opf", opf)

    return buf.getvalue()


def build_volume_zip(content: NovelContent, encoding: str) -> bytes:
    """Qimao-style package: per-volume TXTs + intro + placeholder cover."""
    buf = io.BytesIO()
    base = _safe_filename(content.title)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("cover.svg", cover_svg(content))
        zf.writestr(
            "简介.txt",
            _intro_block(content).encode(encoding, errors="replace"),
        )

        if content.volumes:
            used_names: set[str] = set()

            def _unique(name: str) -> str:
                candidate, n = name, 2
                while candidate in used_names:
                    candidate = f"{name}-{n}"
                    n += 1
                used_names.add(candidate)
                return candidate

            covered: set[int] = set()
            for volume in content.volumes:
                chapters = [
                    c
                    for c in content.chapters
                    if volume.chapter_start <= c.index <= volume.chapter_end
                ]
                if not chapters:
                    continue
                covered |= {c.index for c in chapters}
                vc = NovelContent(
                    novel_id=content.novel_id,
                    title=content.title,
                    genre=content.genre,
                    intro=content.intro,
                    author=content.author,
                    volumes=[],
                    chapters=chapters,
                    planned_count=len(chapters),
                )
                zf.writestr(
                    f"{_unique(_safe_filename(volume.title))}.txt",
                    build_txt(vc, encoding),
                )

            # 兜底：不属于任何卷的章节绝不静默丢失
            leftover = [c for c in content.chapters if c.index not in covered]
            if leftover:
                vc = NovelContent(
                    novel_id=content.novel_id,
                    title=content.title,
                    genre=content.genre,
                    intro=content.intro,
                    author=content.author,
                    volumes=[],
                    chapters=leftover,
                    planned_count=len(leftover),
                )
                zf.writestr("未分卷章节.txt", build_txt(vc, encoding))
        else:
            zf.writestr(f"{base}.txt", build_txt(content, encoding))

    return buf.getvalue()


def export_content(content: NovelContent, profile: PlatformProfile) -> ExportResult:
    """Dispatch to the right exporter per the platform profile."""
    base = _safe_filename(content.title)

    if profile.output_format == "epub":
        data = build_epub(content)
        return ExportResult(
            filename=f"{base}.epub",
            media_type="application/epub+zip",
            data=data,
            meta={
                "format": "epub",
                "encoding": "utf-8",
                "chapters": len(content.chapters),
                "words": content.total_words,
                "volumes": len(content.volumes),
            },
        )

    if profile.output_format == "zip":
        data = build_volume_zip(content, profile.encoding)
        return ExportResult(
            filename=f"{base}-{profile.key}.zip",
            media_type="application/zip",
            data=data,
            meta={
                "format": "zip",
                "encoding": profile.encoding,
                "chapters": len(content.chapters),
                "words": content.total_words,
                "volumes": len(content.volumes),
                "cover": "cover.svg",
            },
        )

    data = build_txt(content, profile.encoding)
    charset = "gb18030" if profile.encoding.lower() == "gb18030" else "utf-8"
    return ExportResult(
        filename=f"{base}.txt",
        media_type=f"text/plain; charset={charset}",
        data=data,
        meta={
            "format": "txt",
            "encoding": profile.encoding,
            "chapters": len(content.chapters),
            "words": content.total_words,
        },
    )
