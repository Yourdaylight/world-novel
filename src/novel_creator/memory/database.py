"""SQLite database initialization and connection management."""

from __future__ import annotations

from pathlib import Path

import aiosqlite

from novel_creator.config import settings

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS characters (
    character_id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS episodic_memories (
    memory_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    scene_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    importance REAL DEFAULT 0.5,
    emotional_valence REAL DEFAULT 0.0,
    involved_characters TEXT DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(character_id)
);

CREATE TABLE IF NOT EXISTS emotional_states (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    scene_index INTEGER NOT NULL,
    happiness REAL DEFAULT 0.0,
    anger REAL DEFAULT 0.0,
    fear REAL DEFAULT 0.0,
    sadness REAL DEFAULT 0.0,
    trust REAL DEFAULT 0.0,
    surprise REAL DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(character_id)
);

CREATE TABLE IF NOT EXISTS relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT DEFAULT '陌生人',
    trust REAL DEFAULT 0.0,
    affection REAL DEFAULT 0.0,
    description TEXT DEFAULT '',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_id, target_id)
);

CREATE TABLE IF NOT EXISTS character_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    scene_index INTEGER NOT NULL,
    action_type TEXT NOT NULL,
    content TEXT NOT NULL,
    target_character_id TEXT,
    emotional_shift TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(character_id)
);

CREATE TABLE IF NOT EXISTS semantic_memories (
    memory_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    content TEXT NOT NULL,
    category TEXT DEFAULT 'observation',
    importance REAL DEFAULT 0.5,
    embedding BLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(character_id)
);

CREATE INDEX IF NOT EXISTS idx_episodic_character ON episodic_memories(character_id);
CREATE INDEX IF NOT EXISTS idx_episodic_chapter ON episodic_memories(chapter_index, scene_index);
CREATE INDEX IF NOT EXISTS idx_emotional_character ON emotional_states(character_id);
CREATE INDEX IF NOT EXISTS idx_actions_chapter ON character_actions(chapter_index, scene_index);
CREATE INDEX IF NOT EXISTS idx_semantic_character ON semantic_memories(character_id);

-- V2: Chapter rendered texts (literary narrative from writer agent)
CREATE TABLE IF NOT EXISTS chapter_texts (
    chapter_index INTEGER NOT NULL,
    scene_index INTEGER NOT NULL,
    title TEXT DEFAULT '',
    content TEXT NOT NULL,
    pov_character TEXT DEFAULT '',
    summary TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (chapter_index, scene_index)
);

-- V2: World-building singleton (id=1)
CREATE TABLE IF NOT EXISTS world_building (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    world_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- V2: Story outline singleton (id=1)
CREATE TABLE IF NOT EXISTS story_outline (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    outline_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- V2: Volume structure
CREATE TABLE IF NOT EXISTS volumes (
    volume_index INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT DEFAULT '',
    theme TEXT DEFAULT '',
    chapter_start INTEGER NOT NULL,
    chapter_end INTEGER NOT NULL,
    arc_goal TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- V2: Foreshadowing tracking
CREATE TABLE IF NOT EXISTS foreshadows (
    foreshadow_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    hint_text TEXT DEFAULT '',
    planted_chapter INTEGER NOT NULL,
    expected_payoff_chapter INTEGER NOT NULL,
    actual_payoff_chapter INTEGER,
    status TEXT DEFAULT 'planted',
    importance TEXT DEFAULT 'minor',
    related_characters TEXT DEFAULT '[]',
    related_plot_thread TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- V2: Plot thread tracking
CREATE TABLE IF NOT EXISTS plot_threads (
    thread_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    start_chapter INTEGER DEFAULT 0,
    key_characters TEXT DEFAULT '[]',
    foreshadow_ids TEXT DEFAULT '[]',
    chapter_progress TEXT DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- V2: Generation checkpoints for pause/resume
CREATE TABLE IF NOT EXISTS generation_checkpoints (
    checkpoint_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_completed_chapter INTEGER NOT NULL,
    phase TEXT DEFAULT 'simulating',
    state_json TEXT NOT NULL,
    novel_title TEXT DEFAULT '',
    total_chapters INTEGER DEFAULT 0,
    completed_chapters INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_foreshadows_status ON foreshadows(status);
CREATE INDEX IF NOT EXISTS idx_foreshadows_chapter ON foreshadows(planted_chapter);
CREATE INDEX IF NOT EXISTS idx_plot_threads_status ON plot_threads(status);
CREATE INDEX IF NOT EXISTS idx_checkpoints_created ON generation_checkpoints(created_at);

-- V3: Story timeline eras
CREATE TABLE IF NOT EXISTS story_eras (
    era_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    "order" INTEGER NOT NULL,
    story_time_start TEXT DEFAULT '',
    story_time_end TEXT DEFAULT '',
    chapter_start INTEGER NOT NULL,
    chapter_end INTEGER NOT NULL,
    volume_index INTEGER DEFAULT 0
);

-- V3: Timeline events
CREATE TABLE IF NOT EXISTS timeline_events (
    event_id TEXT PRIMARY KEY,
    era_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    story_time TEXT DEFAULT '',
    event_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    affected_characters TEXT DEFAULT '[]',
    affected_locations TEXT DEFAULT '[]',
    source TEXT DEFAULT 'director',
    importance REAL DEFAULT 0.5,
    FOREIGN KEY (era_id) REFERENCES story_eras(era_id)
);

-- V3: God Agent decisions
CREATE TABLE IF NOT EXISTS god_decisions (
    decision_id TEXT PRIMARY KEY,
    chapter_index INTEGER NOT NULL,
    decision_json TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_events_era ON timeline_events(era_id);
CREATE INDEX IF NOT EXISTS idx_events_chapter ON timeline_events(chapter_index);
CREATE INDEX IF NOT EXISTS idx_god_chapter ON god_decisions(chapter_index);

-- V4: World propositions (三个终极命题)
CREATE TABLE IF NOT EXISTS world_propositions (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    what_is TEXT DEFAULT '',
    where_from TEXT DEFAULT '',
    where_to TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- V5: Layered memory: Core beliefs
CREATE TABLE IF NOT EXISTS core_beliefs (
    belief_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    content TEXT NOT NULL,
    strength REAL DEFAULT 0.5,
    origin_chapter INTEGER DEFAULT 0,
    last_reinforced_chapter INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(character_id)
);

CREATE INDEX IF NOT EXISTS idx_beliefs_character ON core_beliefs(character_id);

-- V5: Layered memory: Relationship schemas (mental models of others)
CREATE TABLE IF NOT EXISTS relationship_schemas (
    schema_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    mental_model TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    last_updated_chapter INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(character_id, target_id),
    FOREIGN KEY (character_id) REFERENCES characters(character_id)
);

CREATE INDEX IF NOT EXISTS idx_schemas_character ON relationship_schemas(character_id);

-- V5: Layered memory: Trauma/anchor memories
CREATE TABLE IF NOT EXISTS trauma_memories (
    trauma_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    content TEXT NOT NULL,
    trauma_type TEXT DEFAULT 'anchor',
    trigger_keywords TEXT DEFAULT '[]',
    emotional_impact TEXT DEFAULT '{}',
    origin_chapter INTEGER DEFAULT 0,
    importance REAL DEFAULT 0.8,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(character_id)
);

CREATE INDEX IF NOT EXISTS idx_trauma_character ON trauma_memories(character_id);

-- V5: Reflection logs
CREATE TABLE IF NOT EXISTS reflection_logs (
    reflection_id TEXT PRIMARY KEY,
    character_id TEXT NOT NULL,
    chapter_index INTEGER NOT NULL,
    beliefs_updated INTEGER DEFAULT 0,
    schemas_updated INTEGER DEFAULT 0,
    traumas_identified INTEGER DEFAULT 0,
    summary TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (character_id) REFERENCES characters(character_id)
);

CREATE INDEX IF NOT EXISTS idx_reflection_character ON reflection_logs(character_id);

-- V6: Token usage tracking
CREATE TABLE IF NOT EXISTS token_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    chapter_index INTEGER DEFAULT -1,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    model TEXT DEFAULT '',
    description TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_token_role ON token_usage(role);
CREATE INDEX IF NOT EXISTS idx_token_chapter ON token_usage(chapter_index);

-- V6: Relationship history snapshots
CREATE TABLE IF NOT EXISTS relationship_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT DEFAULT '',
    trust REAL DEFAULT 0.0,
    affection REAL DEFAULT 0.0,
    description TEXT DEFAULT '',
    chapter_index INTEGER NOT NULL,
    change_reason TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rel_history_chapter ON relationship_history(chapter_index);
CREATE INDEX IF NOT EXISTS idx_rel_history_pair ON relationship_history(source_id, target_id);
"""


async def get_connection(db_path: str | None = None) -> aiosqlite.Connection:
    """Get a database connection, creating the database if needed.

    Enables WAL mode for better concurrent read/write performance
    (multiple readers, single writer without blocking readers).
    Sets a busy timeout so parallel agents wait instead of failing
    with "database is locked".
    """
    path = Path(db_path or settings.db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(str(path))
    conn.row_factory = aiosqlite.Row

    # WAL mode: allows concurrent reads while writing
    await conn.execute("PRAGMA journal_mode=WAL")
    # Busy timeout: wait up to 30s for lock instead of failing immediately
    await conn.execute("PRAGMA busy_timeout=30000")
    # Synchronous NORMAL: safe with WAL, faster than FULL
    await conn.execute("PRAGMA synchronous=NORMAL")

    await conn.executescript(SCHEMA_SQL)
    return conn


async def reset_database(db_path: str | None = None) -> None:
    """Drop and recreate all tables."""
    path = Path(db_path or settings.db_path)
    if path.exists():
        path.unlink()
    await get_connection(db_path)
