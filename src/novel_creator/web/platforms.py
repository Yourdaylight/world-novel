"""Platform profiles and book exporters (requirement A — L0 one-click export).

External novel platforms (番茄/七猫/起点…) expose **no** public writer API, so
"one-click publish" is realised as standards-compliant export the author
uploads in the platform's writer console (see docs requirement 3.2).

Every exporter is pure-stdlib (``zipfile``/stdlib text codecs) on purpose:
- TXT  — Fanqie uses GB18030; generic/Qimao use UTF-8, Qimao keeps 分卷 headers
- EPUB — hand-rolled OCF container (valid EPUB 3) since ebooklib is not a dep
- RTF  — Unicode-escaped so Microsoft Word opens it with CJK intact
- bundle — a .zip with every format + cover placeholder + intro/metadata

``PLATFORMS`` is the extension table: add a new platform by registering a
profile + exporter, no database migration required.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass
from html import escape
from time import gmtime, strftime
from uuid import uuid4

from .book import Book, Volume


@dataclass(frozen=True)
class PlatformProfile:
    key: str
    label: str
    file_ext: str
    media_type: str
    encoding: str = "utf-8"
    supports_volumes: bool = False
    # Recommended per-chapter length; preflight warns outside [min, max].
    chapter_words_recommended: tuple[int, int] = (1500, 3000)
    intro_max_chars: int = 1000
    description: str = ""


PLATFORMS: dict[str, PlatformProfile] = {
    "fanqie": PlatformProfile(
        key="fanqie",
        label="番茄小说",
        file_ext="txt",
        media_type="text/plain; charset=gb18030",
        encoding="gb18030",
        supports_volumes=False,
        chapter_words_recommended=(1500, 3000),
        intro_max_chars=1000,
        description="TXT / GB18030 编码，番茄作家助手批量上传",
    ),
    "qimao": PlatformProfile(
        key="qimao",
        label="七猫小说",
        file_ext="txt",
        media_type="text/plain; charset=utf-8",
        encoding="utf-8",
        supports_volumes=True,
        chapter_words_recommended=(1500, 3000),
        intro_max_chars=500,
        description="TXT / UTF-8，保留分卷结构，七猫作家平台导入",
    ),
    "txt": PlatformProfile(
        key="txt",
        label="通用 TXT (UTF-8)",
        file_ext="txt",
        media_type="text/plain; charset=utf-8",
        encoding="utf-8",
        supports_volumes=True,
        description="任意平台通用的 UTF-8 纯文本",
    ),
    "epub": PlatformProfile(
        key="epub",
        label="EPUB 电子书",
        file_ext="epub",
        media_type="application/epub+zip",
        supports_volumes=True,
        description="标准 EPUB3，Apple Books / 多看 / Kindle 转换工具通用",
    ),
    "rtf": PlatformProfile(
        key="rtf",
        label="Word (RTF)",
        file_ext="rtf",
        media_type="application/rtf",
        supports_volumes=True,
        description="Word 直接打开，可另存为 .docx",
    ),
    "bundle": PlatformProfile(
        key="bundle",
        label="全格式打包 ZIP",
        file_ext="zip",
        media_type="application/zip",
        supports_volumes=True,
        description="一次导出 TXT(GB18030+UTF-8)/EPUB/RTF/封面/简介",
    ),
}

# Filenames use the same sanitisation as the novel registry slug.
_BAD_FN = set('<>:"/\\|?*')


_RESERVED = {
    "con", "prn", "aux", "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def safe_filename(name: str) -> str:
    cleaned = "".join("_" if c in _BAD_FN or ord(c) < 32 else c for c in name)
    # Strip trailing dots/spaces (Windows semantics) and forbid traversal.
    cleaned = cleaned.strip().rstrip(". ")
    if cleaned in ("", ".", "..") or cleaned.lower() in _RESERVED:
        return "novel"
    return cleaned


def _volume_for(book: Book, chapter_index: int) -> Volume | None:
    for v in book.volumes:
        if v.chapter_start <= chapter_index <= v.chapter_end:
            return v
    return None


def _chapter_heading(book: Book, index: int, with_volume_marker: str | None = None) -> list[str]:
    ch = book.chapters[index]
    lines: list[str] = []
    if with_volume_marker is not None:
        vol = _volume_for(book, ch.chapter_index)
        if vol is not None:
            lines.append(with_volume_marker.format(vol=vol.title))
    lines.append(f"第{ch.chapter_index + 1}章 {ch.title}".rstrip())
    return lines


def _plain_text(book: Book, *, encoding: str, with_volumes: bool) -> bytes:
    lines = [book.title, "", book.intro, ""]
    last_vol: int | None = None
    for i in range(len(book.chapters)):
        ch = book.chapters[i]
        if with_volumes:
            vol = _volume_for(book, ch.chapter_index)
            if vol is not None and (last_vol is None or vol.volume_index != last_vol):
                lines.extend(["", f"第{vol.volume_index + 1}卷 {vol.title}".rstrip(), ""])
                last_vol = vol.volume_index
        elif book.volumes:
            last_vol = None
        lines.extend(_chapter_heading(book, i))
        lines.extend(["", ch.text, ""])
    body = "\n".join(lines)
    return body.encode(encoding, errors="replace")


def _rtf_unicode_escape(text: str) -> str:
    """Escape a string for RTF: ASCII passthrough, CJK as \\uN? signed 16-bit."""
    out: list[str] = []
    for ch in text:
        o = ord(ch)
        if ch in ("\\", "{", "}"):
            out.append("\\" + ch)
        elif ch == "\n":
            out.append("\\par\n")
        elif o < 128:
            out.append(ch)
        elif o <= 0xFFFF:
            signed = o if o < 32768 else o - 65536
            out.append(f"\\u{signed}?")
        else:
            # Non-BMP: emit a UTF-16 surrogate pair (both signed 16-bit).
            high, low = _surrogate_pair(o)
            out.append(f"\\u{high - 65536 if high >= 32768 else high}?"
                       f"\\u{low - 65536 if low >= 32768 else low}?")
    return "".join(out)


def _surrogate_pair(codepoint: int) -> tuple[int, int]:
    adj = codepoint - 0x10000
    return 0xD800 + (adj >> 10), 0xDC00 + (adj & 0x3FF)


def _rtf(book: Book) -> bytes:
    parts = [
        r"{\rtf1\ansi\deff0{\fonttbl{\f0\fnil\fcharset134 Noto Serif SC;}}"
        r"\f0\fs28 ",
        _rtf_unicode_escape(book.title) + r"\par\par",
    ]
    if book.intro:
        parts.append(_rtf_unicode_escape(book.intro) + r"\par\par")
    for i, ch in enumerate(book.chapters):
        vol = _volume_for(book, ch.chapter_index)
        if vol is not None and (i == 0 or _volume_for(book, book.chapters[i - 1].chapter_index) != vol):
            parts.append(r"\b " + _rtf_unicode_escape(f"第{vol.volume_index + 1}卷 {vol.title}") + r"\b0\par\par")
        parts.append(r"\b " + _rtf_unicode_escape(f"第{ch.chapter_index + 1}章 {ch.title}") + r"\b0\par\par")
        parts.append(_rtf_unicode_escape(ch.text) + r"\par\par")
    parts.append("}")
    return "".join(parts).encode("ascii", errors="replace")


def _xhtml(title: str, body_html: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN"><head>'
        f'<title>{escape(title)}</title>'
        '<style>body{margin:5%;line-height:1.9;font-family:serif}'
        'h1,h2{text-align:center}p{text-indent:2em;margin:0.6em 0}</style>'
        '</head><body>'
        f'{body_html}'
        '</body></html>'
    )


def _epub(book: Book) -> bytes:
    book_uuid = f"urn:uuid:{uuid4()}"
    files: dict[str, bytes] = {}

    # Title / intro page
    intro_paras = "".join(f"<p>{escape(p)}</p>" for p in book.intro.split("\n") if p.strip())
    files["OEBPS/title.xhtml"] = _xhtml(
        book.title,
        f"<h1>{escape(book.title)}</h1><p style='text-align:center'>{escape(book.genre)}</p>{intro_paras}",
    ).encode("utf-8")

    manifest = ['<item id="title" href="title.xhtml" media-type="application/xhtml+xml"/>']
    spine = ["<itemref idref=\"title\"/>"]
    for i, ch in enumerate(book.chapters):
        href = f"chap{i:04d}.xhtml"
        paras = "".join(f"<p>{escape(p)}</p>" for p in ch.text.split("\n") if p.strip())
        files[f"OEBPS/{href}"] = _xhtml(
            f"第{ch.chapter_index + 1}章 {ch.title}",
            f"<h2>第{ch.chapter_index + 1}章 {escape(ch.title)}</h2>{paras}",
        ).encode("utf-8")
        manifest.append(
            f'<item id="c{i}" href="{href}" media-type="application/xhtml+xml"/>'
        )
        spine.append(f'<itemref idref="c{i}"/>')

    # content.opf
    date = strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())
    opf = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid">'
        f'<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:identifier id="bookid">{book_uuid}</dc:identifier>'
        f'<dc:title>{escape(book.title)}</dc:title>'
        f'<dc:language>zh-CN</dc:language><dc:date>{date}</dc:date>'
        f'<dc:publisher>WorldNovel</dc:publisher></metadata>'
        f'<manifest>{"".join(manifest)}'
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        '</manifest><spine>'
        f'{"".join(spine)}<itemref idref="nav"/></spine></package>'
    )
    files["OEBPS/content.opf"] = opf.encode("utf-8")

    # nav.xhtml (EPUB3 navigation)
    nav_items = "".join(
        f'<li><a href="chap{i:04d}.xhtml">第{ch.chapter_index + 1}章 {escape(ch.title)}</a></li>'
        for i, ch in enumerate(book.chapters)
    )
    files["OEBPS/nav.xhtml"] = _xhtml(
        "目录",
        f'<nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops"><ol>'
        f'<li><a href="title.xhtml">{escape(book.title)}</a></li>{nav_items}</ol></nav>',
    ).encode("utf-8")

    files["mimetype"] = b"application/epub+zip"
    files["META-INF/container.xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
        '<rootfiles><rootfile full-path="OEBPS/content.opf" '
        'media-type="application/oebps-package+xml"/></rootfiles></container>'
    ).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype MUST be first and stored uncompressed for valid EPUB
        zi = zipfile.ZipInfo("mimetype")
        zi.compress_type = zipfile.ZIP_STORED
        zf.writestr(zi, files.pop("mimetype"))
        for path, data in files.items():
            zf.writestr(path, data)
    return buf.getvalue()


def build_cover_svg(book: Book) -> bytes:
    """Generate a deterministic placeholder cover (SVG) — no image dependency."""
    title = escape(book.title[:24])
    genre = escape(book.genre)
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="600" height="800" viewBox="0 0 600 800">
  <defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#1c1917"/><stop offset="1" stop-color="#431407"/>
  </linearGradient></defs>
  <rect width="600" height="800" fill="url(#g)"/>
  <rect x="40" y="40" width="520" height="720" fill="none" stroke="#f97316" stroke-width="2"/>
  <text x="300" y="360" font-family="serif" font-size="52" fill="#fafaf9"
        text-anchor="middle" font-weight="700">{title}</text>
  <line x1="220" y1="400" x2="380" y2="400" stroke="#f97316" stroke-width="2"/>
  <text x="300" y="460" font-family="sans-serif" font-size="24" fill="#a8a29e"
        text-anchor="middle">{genre}</text>
  <text x="300" y="730" font-family="sans-serif" font-size="18" fill="#78716c"
        text-anchor="middle">WorldNovel · {len(book.chapters)} 章 · {book.total_words} 字</text>
</svg>"""
    return svg.encode("utf-8")


def export_book(book: Book, platform: str) -> tuple[bytes, str, str]:
    """Export ``book`` for ``platform``.

    Returns ``(payload, filename, media_type)``. Raises ``KeyError`` for an
    unknown platform.
    """
    if platform not in PLATFORMS:
        raise KeyError(f"未知平台: {platform}")
    stem = safe_filename(book.title)

    if platform == "epub":
        return _epub(book), f"{stem}.epub", PLATFORMS["epub"].media_type
    if platform == "rtf":
        return _rtf(book), f"{stem}.rtf", PLATFORMS["rtf"].media_type
    if platform == "fanqie":
        data = _plain_text(book, encoding="gb18030", with_volumes=False)
        return data, f"{stem}.txt", PLATFORMS["fanqie"].media_type
    if platform == "qimao":
        data = _plain_text(book, encoding="utf-8", with_volumes=True)
        return data, f"{stem}.txt", PLATFORMS["qimao"].media_type
    if platform == "txt":
        data = _plain_text(book, encoding="utf-8", with_volumes=True)
        return data, f"{stem}.txt", PLATFORMS["txt"].media_type

    # bundle — every format + cover + intro in one zip
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{stem}/封面.txt", f"{book.title}\n类型：{book.genre}\n\n{book.intro}\n".encode("utf-8"))
        zf.writestr(f"{stem}/cover.svg", build_cover_svg(book))
        zf.writestr(f"{stem}/{stem}-番茄.txt", _plain_text(book, encoding="gb18030", with_volumes=False))
        zf.writestr(f"{stem}/{stem}-七猫.txt", _plain_text(book, encoding="utf-8", with_volumes=True))
        zf.writestr(f"{stem}/{stem}.epub", _epub(book))
        zf.writestr(f"{stem}/{stem}.rtf", _rtf(book))
        meta = (
            f"书名: {book.title}\n类型: {book.genre}\n章节数: {len(book.chapters)}\n"
            f"总字数: {book.total_words}\n卷数: {len(book.volumes)}\n"
        )
        zf.writestr(f"{stem}/meta.txt", meta.encode("utf-8"))
    return buf.getvalue(), f"{stem}-全格式.zip", PLATFORMS["bundle"].media_type
