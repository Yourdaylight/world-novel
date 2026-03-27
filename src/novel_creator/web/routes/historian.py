"""AI/Historian routes: /ai/historian-chat, /ai/analyze-proposition, /ai/historian-write-file, /world PUT."""

from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from novel_creator.config import settings
from novel_creator.memory.database import get_connection
from novel_creator.memory.registry import get_novel_by_id

from ._helpers import _get_novel_db, logger

router = APIRouter()


class WorldSaveRequest(BaseModel):
    world: dict


@router.put("/world")
async def api_save_world(req: WorldSaveRequest, novel_id: str | None = Query(None)):
    """Save edited world-building data."""
    try:
        db_path = await _get_novel_db(novel_id)
        conn = await get_connection(db_path)
        world_json = json.dumps(req.world, ensure_ascii=False)
        await conn.execute(
            """INSERT INTO world_building (id, world_json)
               VALUES (1, ?)
               ON CONFLICT(id) DO UPDATE SET world_json=excluded.world_json""",
            (world_json,),
        )
        await conn.commit()
        await conn.close()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


class AnalyzePropositionRequest(BaseModel):
    step: int  # 1=what_is, 2=where_from, 3=where_to
    text: str
    context: dict = Field(default_factory=dict)  # previous steps


@router.post("/ai/analyze-proposition")
async def api_analyze_proposition(req: AnalyzePropositionRequest):
    """AI analysis of a proposition step (non-streaming)."""
    try:
        from langchain_openai import ChatOpenAI

        step_names = {1: "世界本质（是什么）", 2: "世界起源（从何而来）", 3: "世界命运（往何处去）"}
        step_name = step_names.get(req.step, "未知")

        context_parts = []
        if req.context.get("what_is"):
            context_parts.append(f"【世界本质】{req.context['what_is']}")
        if req.context.get("where_from"):
            context_parts.append(f"【世界起源】{req.context['where_from']}")
        context_text = "\n".join(context_parts) if context_parts else "（这是第一个命题）"

        system_prompt = (
            "你是一个专业的小说世界观顾问。用户正在通过三个终极命题来构建一个小说世界。\n"
            "请分析用户输入的命题，给出专业的评价和建议。\n"
            "输出格式 (JSON):\n"
            '{"analysis": "对基调和主题的简短判断", '
            '"conflict_points": ["可以挖掘的冲突点1", "冲突点2"], '
            '"suggestions": ["补充建议1", "建议2"], '
            '"references": ["类似作品参考1", "参考2"]}'
        )

        user_prompt = (
            f"当前步骤: {step_name}\n"
            f"已有命题:\n{context_text}\n\n"
            f"用户输入:\n{req.text}\n\n"
            "请分析这个命题并给出建议。返回 JSON 格式。"
        )

        llm = ChatOpenAI(
            model=settings.director_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
        )
        resp = await llm.ainvoke([
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ])

        # Try to parse as JSON, fallback to raw text
        content = resp.content
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            match = re.search(r'```(?:json)?\s*(.*?)```', content, re.DOTALL)
            if match:
                try:
                    result = json.loads(match.group(1))
                except json.JSONDecodeError:
                    result = {"analysis": content, "suggestions": [], "references": []}
            else:
                result = {"analysis": content, "suggestions": [], "references": []}

        return result
    except Exception as e:
        return {
            "analysis": f"AI 分析暂不可用: {str(e)}",
            "suggestions": [],
            "references": [],
        }


class HistorianChatRequest(BaseModel):
    message: str
    novel_id: str
    history: list = Field(default_factory=list)  # [{role, content}, ...]


@router.post("/ai/historian-chat")
async def api_historian_chat(req: HistorianChatRequest):
    """Chat with the historian agent — uses all character memories, actions, world data to answer."""
    try:
        novel = get_novel_by_id(req.novel_id)
        if novel is None:
            return {"reply": "未找到该世界", "error": "not found"}

        db_path = novel.db_path
        conn = await get_connection(db_path)

        # Gather world context
        cursor_o = await conn.execute("SELECT outline_json FROM story_outline WHERE id = 1")
        row_o = await cursor_o.fetchone()
        outline_text = ""
        if row_o:
            outline = json.loads(row_o["outline_json"])
            outline_text = f"标题: {outline.get('title','')}\n类型: {outline.get('genre','')}\n前提: {outline.get('premise','')}\n核心冲突: {outline.get('central_conflict','')}"

        # Characters
        cursor_c = await conn.execute("SELECT character_id, profile_json FROM characters")
        char_rows = await cursor_c.fetchall()
        chars_text = ""
        for r in char_rows:
            p = json.loads(r["profile_json"])
            chars_text += f"\n【{p.get('name',r['character_id'])}】({p.get('role','')}) {p.get('backstory','')[:200]}"

        # Recent actions (last 50)
        cursor_a = await conn.execute(
            "SELECT character_id, chapter_index, scene_index, action_type, content, target_character_id "
            "FROM character_actions ORDER BY chapter_index DESC, scene_index DESC, id DESC LIMIT 50"
        )
        action_rows = await cursor_a.fetchall()
        actions_text = ""
        for a in action_rows:
            target = f" → {a['target_character_id']}" if a['target_character_id'] else ""
            actions_text += f"\n第{a['chapter_index']+1}章场景{a['scene_index']+1} [{a['action_type']}] {a['character_id']}{target}: {a['content'][:150]}"

        # World building
        cursor_w = await conn.execute("SELECT world_json FROM world_building WHERE id = 1")
        row_w = await cursor_w.fetchone()
        world_text = ""
        if row_w:
            w = json.loads(row_w["world_json"])
            world_text = f"世界: {w.get('world_name','')}\n{w.get('world_description','')[:300]}"

        # God decisions
        cursor_g = await conn.execute("SELECT decision_json FROM god_decisions ORDER BY chapter_index")
        god_rows = await cursor_g.fetchall()
        god_text = ""
        for g in god_rows:
            d = json.loads(g["decision_json"])
            guidance = d.get("next_chapter_guidance", "")[:200]
            events = ", ".join(e.get("title","") for e in d.get("world_events",[]))
            god_text += f"\n命运决策: {events} | 指引: {guidance}"

        # Chapter texts (summaries)
        cursor_t = await conn.execute(
            "SELECT DISTINCT chapter_index, title, summary FROM chapter_texts ORDER BY chapter_index"
        )
        chapter_rows = await cursor_t.fetchall()
        chapters_text = ""
        for ch in chapter_rows:
            chapters_text += f"\n第{ch['chapter_index']+1}章 {ch['title']}: {(ch['summary'] or '')[:100]}"

        await conn.close()

        system_prompt = (
            "你是这个小说世界的「史官」，掌握这个世界的所有信息：世界观、角色档案、角色的每一句话和每一个行动、命运决策、剧情走向。\n"
            "你的职责：\n"
            "1. 回答造物主（用户）关于这个世界的任何问题\n"
            "2. 根据造物主的要求，基于角色的记忆和行动撰写章节片段、对话场景、内心独白\n"
            "3. 分析角色关系发展、剧情冲突、伏笔回收情况\n"
            "4. 建议新角色、新剧情线、新的命运转折\n\n"
            "你掌握的信息：\n"
            f"## 故事大纲\n{outline_text}\n\n"
            f"## 世界观\n{world_text}\n\n"
            f"## 角色档案\n{chars_text}\n\n"
            f"## 已完成章节\n{chapters_text}\n\n"
            f"## 近期角色行动记录\n{actions_text}\n\n"
            f"## 命运决策\n{god_text}\n\n"
            "回复时使用中文，语言要符合小说世界的基调。"
        )

        messages = [{"role": "system", "content": system_prompt}]
        # Add chat history
        for h in req.history[-10:]:  # Keep last 10 turns
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})
        messages.append({"role": "user", "content": req.message})

        from langchain_openai import ChatOpenAI
        llm = ChatOpenAI(
            model=settings.director_model,
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            temperature=0.7,
        )
        resp = await llm.ainvoke(messages)
        return {"reply": resp.content}
    except Exception as e:
        logger.error("Historian chat error: %s", e)
        return {"reply": f"史官暂时无法回应: {str(e)}", "error": str(e)}


class HistorianWriteFileRequest(BaseModel):
    novel_id: str
    filename: str
    content: str


@router.post("/ai/historian-write-file")
async def api_historian_write_file(req: HistorianWriteFileRequest):
    """Historian writes a file to the novel's workspace/historian/ directory."""
    try:
        novel = get_novel_by_id(req.novel_id)
        if novel is None:
            return {"ok": False, "error": "not found"}

        novel_dir = Path(novel.db_path).parent
        historian_dir = novel_dir / "historian"
        historian_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_name = req.filename.replace("/", "_").replace("\\", "_").replace("..", "_")
        if not safe_name:
            safe_name = "output.md"

        file_path = historian_dir / safe_name
        file_path.write_text(req.content, encoding="utf-8")

        return {"ok": True, "path": str(file_path), "filename": safe_name}
    except Exception as e:
        return {"ok": False, "error": str(e)}
