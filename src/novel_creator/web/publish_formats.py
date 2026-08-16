"""Platform export formats (L0 一键导出).

番茄/七猫等平台均无公开开放 API（见需求文档 §3.2），L0 按各平台导入规范
产出 TXT / EPUB 文件包，作者在平台作家后台手动上传。

- fanqie: GB18030 单文件 TXT（番茄作家助手导入），每章建议 ≤ 2000 字
- qimao:  GB18030 TXT + 分卷文件（七猫支持分卷导入）
- txt:    通用 UTF-8 TXT
- epub:   标准 EPUB 3（zipfile 纯标准库实现，无第三方依赖）
"""

from __future__ import annotations

import io
import logging
import os
import re
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from .book_service import Book, Chapter

logger = logging.getLogger("novel_creator.web.publish")

# ── Platform profiles ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class PlatformProfile:
    key: str
    label: str
    encoding: str
    chapter_word_hint: int  # 平台推荐单章字数（仅警告，0=不限）
    volumes: bool           # 是否产出分卷文件
    format: str             # txt | epub


_PLATFORMS: dict[str, PlatformProfile] = {
    "fanqie": PlatformProfile("fanqie", "番茄小说", "gb18030", 2000, False, "txt"),
    "qimao": PlatformProfile("qimao", "七猫小说", "gb18030", 2000, True, "txt"),
    "txt": PlatformProfile("txt", "通用 TXT", "utf-8", 0, False, "txt"),
    "epub": PlatformProfile("epub", "EPUB 电子书", "utf-8", 0, False, "epub"),
}


def get_profile(platform: str) -> PlatformProfile:
    p = _PLATFORMS.get((platform or "").lower())
    if p is None:
        raise ValueError(f"不支持的平台: {platform}（支持: {', '.join(_PLATFORMS)}）")
    return p


def platform_catalog() -> list[dict]:
    return [
        {
            "key": p.key,
            "label": p.label,
            "encoding": p.encoding,
            "chapter_word_hint": p.chapter_word_hint,
            "volumes": p.volumes,
            "format": p.format,
        }
        for p in _PLATFORMS.values()
    ]


# ── Sensitive words ───────────────────────────────────────────────────────

def _load_word_file(path: Path) -> list[str]:
    words: list[str] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            w = line.strip()
            if w and not w.startswith("#"):
                words.append(w)
    except OSError:
        pass
    return words


@lru_cache(maxsize=1)
def sensitive_words() -> tuple[str, ...]:
    base = Path(__file__).parent.parent / "data" / "sensitive_words_base.txt"
    words = _load_word_file(base)
    extra_path = os.environ.get("NOVEL_SENSITIVE_WORDS_PATH", "").strip()
    if extra_path:
        words.extend(_load_word_file(Path(extra_path)))
    # 去重保序
    seen: set[str] = set()
    uniq = [w for w in words if not (w in seen or seen.add(w))]
    if not uniq:
        # 词表丢失时敏感词门禁会静默全过——必须留下痕迹
        logger.warning(
            "sensitive word list is empty (base=%s, extra=%s); gate passes everything",
            base, extra_path or "(none)",
        )
    return tuple(uniq)


def reload_sensitive_words() -> tuple[str, ...]:
    """Drop the cached word list (e.g. after updating the custom word file)."""
    sensitive_words.cache_clear()
    return sensitive_words()


def scan_sensitive(book: Book) -> list[dict]:
    """命中返回 {word, chapter_index, count}，最多 50 条。"""
    words = sensitive_words()
    if not words:
        return []
    hits: list[dict] = []
    for ch in book.chapters:
        if not ch.text:
            continue
        for w in words:
            cnt = ch.text.count(w)
            if cnt:
                hits.append({"word": w, "chapter_index": ch.index, "count": cnt})
                if len(hits) >= 50:
                    return hits
    return hits


# ── TXT ───────────────────────────────────────────────────────────────────

def _txt_header(book: Book) -> str:
    lines = [book.title, ""]
    if book.genre:
        lines.append(f"类型：{book.genre}")
    if book.intro:
        lines.append("简介：")
        lines.extend(book.intro.splitlines())
    lines.append("")
    lines.append("═" * 20)
    lines.append("")
    return "\n".join(lines)


def chapter_heading(ch: Chapter) -> str:
    return f"第{ch.index + 1}章 {ch.title}".rstrip() if ch.title else f"第{ch.index + 1}章"


def build_txt(book: Book, profile: PlatformProfile, with_header: bool = True) -> bytes:
    parts: list[str] = []
    if with_header:
        parts.append(_txt_header(book))
    for ch in book.chapters:
        parts.append(chapter_heading(ch))
        parts.append("")
        parts.append(ch.text.strip())
        parts.append("")
        parts.append("")
    return "\n".join(parts).encode(profile.encoding, errors="replace")


def _meta_txt(book: Book, profile: PlatformProfile) -> bytes:
    tags = " ".join(t for t in (book.genre, book.theme) if t)
    lines = [
        f"书名：{book.title}",
        f"类型：{book.genre or '未分类'}",
        f"标签：{tags}",
        f"总字数：约 {book.total_words} 字",
        f"章节数：{len(book.chapters)}",
        f"导出编码：{profile.encoding.upper()}",
        "",
        "简介：",
        book.intro or "（请在作家后台填写简介）",
        "",
        "说明：本文件由 WorldNovel 自动生成，封面请使用同包内 封面占位.svg",
        "替换为正式封面图后，在作家后台上传发布。",
    ]
    return "\n".join(lines).encode(profile.encoding, errors="replace")


def _cover_svg(book: Book) -> bytes:
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">
  <rect width="600" height="800" fill="#1a1a1f"/>
  <rect x="24" y="24" width="552" height="752" fill="none" stroke="#d97706" stroke-width="2"/>
  <text x="300" y="360" text-anchor="middle" fill="#f5f1e8" font-size="44"
        font-family="Songti SC, Noto Serif CJK SC, serif">{xml_escape(book.title)}</text>
  <text x="300" y="430" text-anchor="middle" fill="#d97706" font-size="22"
        font-family="Songti SC, serif">{xml_escape(book.genre or '')}</text>
  <text x="300" y="720" text-anchor="middle" fill="#90909a" font-size="16"
        font-family="sans-serif">WorldNovel · 封面占位（请替换为正式封面）</text>
</svg>
"""
    return svg.encode("utf-8")


# ── EPUB 3 (stdlib only) ──────────────────────────────────────────────────

_EPUB_CSS = """\
body{margin:0;padding:1em;font-family:"Noto Serif CJK SC",serif;line-height:1.9;}
h1{font-size:1.4em;text-align:center;margin:2em 0;}
h2{font-size:1.15em;margin:1.6em 0 .8em;}
p{text-indent:2em;margin:.4em 0;}
.meta{color:#666;text-indent:0;}
"""


def _xhtml(title: str, body: str, lang: str = "zh-CN") -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}">'
        f'<head><title>{xml_escape(title)}</title>'
        '<link rel="stylesheet" type="text/css" href="style.css"/></head>'
        f'<body>{body}</body></html>'
    ).encode("utf-8")


def _paragraphs(text: str) -> str:
    return "".join(
        f'<p>{xml_escape(p)}</p>' for p in text.splitlines() if p.strip()
    )


def build_epub(book: Book) -> bytes:
    buf = io.BytesIO()
    # Compress everything (mimetype below is explicitly ZIP_STORED per EPUB spec)
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype must be the first entry and stored uncompressed
        info = zipfile.ZipInfo("mimetype", date_time=(2024, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, "application/epub+zip")

        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="OEBPS/content.opf" '
            'media-type="application/oebps-package+xml"/></rootfiles></container>',
        )

        title = xml_escape(book.title)
        intro_html = (
            f'<h1>{title}</h1>'
            f'<p class="meta">类型：{xml_escape(book.genre or "未分类")}</p>'
            f'<p class="meta">WorldNovel 自动生成 · 约 {book.total_words} 字</p>'
            + (f'<h2>简介</h2>{_paragraphs(book.intro)}' if book.intro else "")
        )
        zf.writestr("OEBPS/titlepage.xhtml", _xhtml(book.title, intro_html))
        zf.writestr("OEBPS/style.css", _EPUB_CSS.encode("utf-8"))

        manifest = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="titlepage" href="titlepage.xhtml" media-type="application/xhtml+xml"/>',
            '<item id="css" href="style.css" media-type="text/css"/>',
        ]
        # nav in spine (linear="no") so older EPUB3 readers still show the TOC page
        spine = ['<itemref idref="titlepage"/>',
                 '<itemref idref="nav" linear="no"/>']
        nav_items = [
            '<li><a href="titlepage.xhtml">封面与简介</a></li>'
        ]

        for i, ch in enumerate(book.chapters, start=1):
            href = f"ch{i:04d}.xhtml"
            body = f'<h2>{xml_escape(chapter_heading(ch))}</h2>{_paragraphs(ch.text)}'
            zf.writestr(f"OEBPS/{href}", _xhtml(chapter_heading(ch), body))
            manifest.append(
                f'<item id="ch{i:04d}" href="{href}" media-type="application/xhtml+xml"/>'
            )
            spine.append(f'<itemref idref="ch{i:04d}"/>')
            nav_items.append(
                f'<li><a href="{href}">{xml_escape(chapter_heading(ch))}</a></li>'
            )

        zf.writestr(
            "OEBPS/nav.xhtml",
            _xhtml(
                "目录",
                '<nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops">'
                f'<ol>{"".join(nav_items)}</ol></nav>',
            ),
        )

        opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" xml:lang="zh-CN" unique-identifier="bookid">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">urn:worldnovel:{xml_escape(book.novel_id)}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:creator>WorldNovel</dc:creator>
    <dc:language>zh-CN</dc:language>
    <dc:date>{datetime.now(timezone.utc).date().isoformat()}</dc:date>
  </metadata>
  <manifest>{''.join(manifest)}</manifest>
  <spine>{''.join(spine)}</spine>
</package>"""
        zf.writestr("OEBPS/content.opf", opf.encode("utf-8"))
    return buf.getvalue()


# ── Package assembly ──────────────────────────────────────────────────────

_INVALID_FS = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')


def safe_filename(name: str) -> str:
    """文件名清洗（防路径穿越、去非法字符）。"""
    cleaned = _INVALID_FS.sub("_", (name or "").strip()) or "novel"
    return cleaned[:80]


def build_export(book: Book, platform: str) -> tuple[str, str, bytes]:
    """Build the export artifact.

    Returns (download_filename, media_type, payload).
    txt/epub platforms return the raw file; fanqie/qimao return a .zip bundle.
    """
    profile = get_profile(platform)
    base = safe_filename(book.title)

    if profile.format == "epub":
        return f"{base}.epub", "application/epub+zip", build_epub(book)

    if profile.key == "txt":
        return f"{base}.txt", "text/plain; charset=utf-8", build_txt(book, profile)

    # Platform TXT bundles (fanqie / qimao) — zip with book + metadata + cover
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{base}.txt", build_txt(book, profile))
        zf.writestr("出版信息.txt", _meta_txt(book, profile))
        zf.writestr("封面占位.svg", _cover_svg(book))
        if profile.volumes:
            for vol in book.volumes:
                vol_chapters = [
                    ch for ch in book.chapters
                    if vol.chapter_start <= ch.index <= vol.chapter_end
                ]
                if not vol_chapters:
                    continue
                vol_book = Book(
                    novel_id=book.novel_id, title=book.title, genre=book.genre,
                    theme=book.theme, premise=book.premise, intro=book.intro,
                    chapters=vol_chapters,
                )
                name = safe_filename(
                    f"第{vol.index + 1}卷 {vol.title}"
                )
                zf.writestr(f"分卷/{name}.txt", build_txt(vol_book, profile, with_header=False))
    return f"{base}-{profile.key}.zip", "application/zip", buf.getvalue()


def export_warnings(book: Book, profile: PlatformProfile) -> list[str]:
    """Soft warnings surfaced both in preflight and export meta."""
    warnings: list[str] = []
    if profile.chapter_word_hint:
        for ch in book.chapters:
            if ch.words > profile.chapter_word_hint:
                warnings.append(
                    f"{chapter_heading(ch)} 约 {ch.words} 字，"
                    f"超过{profile.label}建议单章 {profile.chapter_word_hint} 字，建议拆分"
                )
    return warnings
