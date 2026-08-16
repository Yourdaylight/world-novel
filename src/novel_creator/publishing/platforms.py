"""Platform profiles — export specifications for external novel platforms.

现实约束：番茄/七猫/起点等平台均无公开开放 API，"一键发布"在开源版
分层为 L0 一键导出（本模块）、L1 浏览器半自动化（远期）、L2 直发（远期）。
新增平台只需在此注册一个 PlatformProfile。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformProfile:
    key: str                       # fanqie | qimao | txt | epub
    name: str                      # 展示名
    output_format: str             # txt | zip | epub
    encoding: str                  # 文本编码
    chapter_chars_recommended: int  # 平台建议的单章字数上限（0 = 无建议）
    supports_volumes: bool         # 导出物是否按分卷组织
    writer_url: str                # 作家后台地址（供作者手动上传）
    description: str               # 导出规范说明


PROFILES: tuple[PlatformProfile, ...] = (
    PlatformProfile(
        key="fanqie",
        name="番茄小说",
        output_format="txt",
        encoding="gb18030",
        chapter_chars_recommended=2000,
        supports_volumes=False,
        writer_url="https://fanqienovel.com/main/writer/book-manage",
        description=(
            "单文件 TXT（GB18030 编码），章节以「第N章 标题」分隔；"
            "平台建议单章 2000 字左右，超长章节会给出警告。"
            "番茄无开放 API，下载后请在番茄作家助手手动上传。"
        ),
    ),
    PlatformProfile(
        key="qimao",
        name="七猫小说",
        output_format="zip",
        encoding="gb18030",
        chapter_chars_recommended=0,
        supports_volumes=True,
        writer_url="https://www.qimao.com/",
        description=(
            "ZIP 打包：按分卷生成 TXT（GB18030），附简介.txt 与封面占位；"
            "无分卷时全书单文件。七猫无开放 API，下载后请在作家平台手动导入。"
        ),
    ),
    PlatformProfile(
        key="txt",
        name="通用 TXT",
        output_format="txt",
        encoding="utf-8",
        chapter_chars_recommended=0,
        supports_volumes=False,
        writer_url="",
        description="UTF-8 单文件 TXT，适用于起点/晋江等任意支持 TXT 导入的平台。",
    ),
    PlatformProfile(
        key="epub",
        name="EPUB 电子书",
        output_format="epub",
        encoding="utf-8",
        chapter_chars_recommended=0,
        supports_volumes=True,
        writer_url="",
        description="标准 EPUB3 电子书，含目录与书名页，可导入电子书工具或支持 EPUB 的平台。",
    ),
)

PROFILES_BY_KEY: dict[str, PlatformProfile] = {p.key: p for p in PROFILES}


def get_profile(key: str) -> PlatformProfile | None:
    return PROFILES_BY_KEY.get(key)


def platform_dicts() -> list[dict]:
    """JSON-serializable profile list for the API."""
    return [
        {
            "key": p.key,
            "name": p.name,
            "output_format": p.output_format,
            "encoding": p.encoding,
            "chapter_chars_recommended": p.chapter_chars_recommended,
            "supports_volumes": p.supports_volumes,
            "writer_url": p.writer_url,
            "description": p.description,
        }
        for p in PROFILES
    ]
