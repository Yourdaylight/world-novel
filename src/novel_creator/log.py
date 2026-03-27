"""Unified logging — Rich console + Python logging + WebSocket events.

Usage:
    from novel_creator.log import get_logger
    logger = get_logger("novel_creator.agents")
    logger.info("角色行动完成", chapter=1, scene=2)
    logger.warning("角色处理失败", error=str(e))
"""

from __future__ import annotations

import logging
import sys

from rich.console import Console
from rich.logging import RichHandler

# Shared Rich console instance
console = Console()


def setup_logging(level: str = "INFO") -> None:
    """Configure the root novel_creator logger with Rich handler.

    Call once at app startup. Sets up:
    - Rich console handler (colored terminal output)
    - Standard logging to stderr (for file redirection in production)
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


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the novel_creator namespace.

    If setup_logging() hasn't been called yet, this will still work
    (Python's default logging behavior) but output won't be pretty.
    """
    return logging.getLogger(name)


# Auto-setup on import so that any module using get_logger() gets rich output
setup_logging()
