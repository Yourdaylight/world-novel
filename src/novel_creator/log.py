"""Unified logging — Rich console + file logging + WebSocket events.

Usage:
    from novel_creator.log import get_logger
    logger = get_logger("novel_creator.agents")
    logger.info("角色行动完成 chapter=%d scene=%d", 1, 2)
    logger.warning("角色处理失败: %s", str(e))
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

# Shared Rich console instance
console = Console()

# Default log dir — data/logs/ at project root
_LOG_DIR = Path(os.environ.get("NOVEL_LOG_DIR", "logs"))


def setup_logging(level: str = "INFO") -> None:
    """Configure the root novel_creator logger.

    Sets up:
    - Rich console handler (colored terminal output)
    - File handler → logs/worldnovel.log (JSON-ish, rotated by external tool)
    """
    root_logger = logging.getLogger("novel_creator")

    # Avoid duplicate handlers if called multiple times
    if root_logger.handlers:
        return

    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Rich handler for pretty terminal output
    rich_handler = RichHandler(
        console=console,
        show_path=False,
        show_time=True,
        rich_tracebacks=True,
        markup=True,
    )
    rich_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(rich_handler)

    # File handler — structured log for post-mortem debugging
    try:
        _LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(
            _LOG_DIR / "worldnovel.log", encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root_logger.addHandler(file_handler)
    except Exception:
        pass  # Non-critical — don't break startup if log dir fails


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the novel_creator namespace.

    If setup_logging() hasn't been called yet, this will still work
    (Python's default logging behavior) but output won't be pretty.
    """
    return logging.getLogger(name)


# Auto-setup on import so that any module using get_logger() gets rich output
setup_logging()
