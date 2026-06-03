"""LLM factory — centralized creation of ChatOpenAI instances with retry."""

from __future__ import annotations

import asyncio
import logging
from typing import TypeVar

from langchain_core.runnables import Runnable
from langchain_openai import ChatOpenAI

from novel_creator.config import settings

logger = logging.getLogger("novel_creator.llm")

T = TypeVar("T")

# Default temperatures per role
_DEFAULT_TEMPERATURES: dict[str, float] = {
    "director": 0.8,
    "character": 0.9,
    "writer": 0.7,
    "god": 0.8,
    "reviewer": 0.3,
}

# Model selection per role
_ROLE_MODELS: dict[str, str] = {}


def _get_model_for_role(role: str) -> str:
    """Resolve which model to use for a given agent role."""
    if role == "character":
        return settings.character_model
    if role == "writer":
        return settings.writer_model
    if role == "god":
        return getattr(settings, "god_model", "") or settings.director_model
    # director, reviewer, and anything else uses director_model
    return settings.director_model


def get_llm(
    role: str,
    *,
    temperature: float | None = None,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance for the given agent role."""
    model = _get_model_for_role(role)
    temp = temperature if temperature is not None else _DEFAULT_TEMPERATURES.get(role, 0.7)

    return ChatOpenAI(
        model=model,
        api_key=settings.resolved_api_key,
        base_url=settings.resolved_base_url,
        temperature=temp,
    )


# ======================================================================
# Token Tracker - 支持全局记录和用户级别记录
# ======================================================================

class TokenTracker:
    """Accumulates token usage and flushes to DB.

    支持两种模式:
    1. 全局记录: 记录到 token_usage 表（原有功能）
    2. 用户级别记录: 当提供 user_code 时，同时记录到 user_token_usage_log 表
    """

    _pending: list[dict] = []

    @classmethod
    def record(
        cls,
        role: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        model: str = "",
        chapter_index: int = -1,
        description: str = "",
        user_code: str = "",
    ) -> None:
        cls._pending.append({
            "role": role,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "model": model,
            "chapter_index": chapter_index,
            "description": description,
            "user_code": user_code,
        })

    @classmethod
    async def flush(cls, db_path: str | None = None, user_code: str = "") -> None:
        """Write all pending records to the database.

        Args:
            db_path: 数据库路径
            user_code: 用户邀请码，如果提供则同时记录到用户级别日志
        """
        if not cls._pending:
            return
        from novel_creator.memory.database import get_connection
        from novel_creator.memory.quota_store import log_user_token_usage

        conn = await get_connection(db_path)
        try:
            for rec in cls._pending:
                # 1. 记录到全局 token_usage 表
                await conn.execute(
                    """INSERT INTO token_usage (role, chapter_index, prompt_tokens, completion_tokens, total_tokens, model, description)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (rec["role"], rec["chapter_index"], rec["prompt_tokens"],
                     rec["completion_tokens"], rec["total_tokens"], rec["model"], rec["description"]),
                )

                # 2. 如果提供了用户code，记录到用户级别日志
                code = user_code or rec.get("user_code", "")
                if code:
                    await log_user_token_usage(
                        conn=conn,
                        code=code,
                        role=rec["role"],
                        prompt_tokens=rec["prompt_tokens"],
                        completion_tokens=rec["completion_tokens"],
                        total_tokens=rec["total_tokens"],
                        model=rec["model"],
                        chapter_index=rec["chapter_index"],
                        description=rec["description"],
                    )
            await conn.commit()
        finally:
            await conn.close()
        cls._pending.clear()

    @classmethod
    def pending_total(cls) -> int:
        return sum(r["total_tokens"] for r in cls._pending)


def _extract_and_record_tokens(
    result,
    role: str,
    chapter_index: int,
    description: str,
    user_code: str = "",
) -> None:
    """Extract token usage from LLM response metadata and record it."""
    try:
        metadata = None
        if hasattr(result, "response_metadata"):
            metadata = result.response_metadata
        elif hasattr(result, "raw") and hasattr(result.raw, "response_metadata"):
            metadata = result.raw.response_metadata

        if metadata and "token_usage" in metadata:
            usage = metadata["token_usage"]
            TokenTracker.record(
                role=role,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                model=metadata.get("model_name", ""),
                chapter_index=chapter_index,
                description=description,
                user_code=user_code,
            )
    except Exception:
        pass  # Non-critical


async def invoke_with_retry(
    chain: Runnable,
    input_data: dict,
    *,
    max_retries: int = 3,
    base_delay: float = 2.0,
    description: str = "LLM call",
    role: str = "",
    chapter_index: int = -1,
    user_code: str = "",
) -> T:
    """Invoke a LangChain chain with exponential backoff retry.

    Parameters
    ----------
    chain : Runnable
        The LangChain chain to invoke (prompt | llm or prompt | structured_llm).
    input_data : dict
        Input variables for the chain.
    max_retries : int
        Maximum number of retry attempts (total calls = max_retries + 1).
    base_delay : float
        Base delay in seconds for exponential backoff (2s, 4s, 8s...).
    description : str
        Human-readable description for logging.
    role : str
        Agent role for token tracking (director, character, writer, etc.).
    chapter_index : int
        Current chapter index for token tracking (-1 if not applicable).
    user_code : str
        User invite code for per-user quota tracking (empty = no user tracking).

    Raises
    ------
    Exception
        The last exception if all retries are exhausted.
    """
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            result = await chain.ainvoke(input_data)
            if attempt > 0:
                logger.info(f"{description} succeeded on attempt {attempt + 1}")
            # Track token usage (global + per-user if code provided)
            if role:
                _extract_and_record_tokens(result, role, chapter_index, description, user_code)
            return result
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"{description} failed (attempt {attempt + 1}/{max_retries + 1}): "
                    f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"{description} failed after {max_retries + 1} attempts: "
                    f"{type(e).__name__}: {e}"
                )

    raise last_error  # type: ignore[misc]


async def stream_with_retry(
    chain: Runnable,
    input_data: dict,
    *,
    max_retries: int = 3,
    base_delay: float = 2.0,
    description: str = "LLM stream",
    role: str = "",
    chapter_index: int = -1,
    user_code: str = "",
):
    """Stream from a LangChain chain with retry on initial connection failure.

    Parameters
    ----------
    user_code : str
        User invite code for per-user quota tracking (empty = no user tracking).
    """
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            async for chunk in chain.astream(input_data):
                yield chunk
            return  # Stream completed successfully
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"{description} failed (attempt {attempt + 1}/{max_retries + 1}): "
                    f"{type(e).__name__}: {e}. Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"{description} failed after {max_retries + 1} attempts: "
                    f"{type(e).__name__}: {e}"
                )

    raise last_error  # type: ignore[misc]
