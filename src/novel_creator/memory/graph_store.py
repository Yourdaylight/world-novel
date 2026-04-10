"""Neo4j-backed relationship and knowledge graph store.

Provides multi-hop relationship queries, social context summaries,
and knowledge graph operations that SQLite cannot efficiently support.

All operations are fire-and-forget safe — failures are logged but never
block the main character action pipeline.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from novel_creator.config import settings

logger = logging.getLogger("novel_creator.memory.graph")


class GraphMemoryStore:
    """Neo4j async client wrapper for relationship and knowledge graph."""

    def __init__(
        self,
        uri: str | None = None,
        user: str | None = None,
        password: str | None = None,
    ):
        from neo4j import AsyncGraphDatabase

        self._uri = uri or settings.neo4j_uri
        self._user = user or settings.neo4j_user
        self._password = password or settings.neo4j_password
        self._driver = AsyncGraphDatabase.driver(
            self._uri, auth=(self._user, self._password),
        )
        logger.info("GraphMemoryStore connected to %s", self._uri)

    async def close(self) -> None:
        await self._driver.close()

    # ------------------------------------------------------------------
    # Schema initialization
    # ------------------------------------------------------------------

    async def init_schema(self) -> None:
        """Create constraints and indexes in Neo4j."""
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Character) REQUIRE c.character_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (l:Location) REQUIRE l.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Faction) REQUIRE f.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Event) REQUIRE e.event_id IS UNIQUE",
        ]
        indexes = [
            "CREATE INDEX IF NOT EXISTS FOR (c:Character) ON (c.name)",
            "CREATE INDEX IF NOT EXISTS FOR (e:Event) ON (e.chapter_index)",
        ]
        async with self._driver.session() as session:
            for stmt in constraints + indexes:
                try:
                    await session.run(stmt)
                except Exception as e:
                    logger.warning("Schema init warning: %s", e)
        logger.info("Neo4j schema initialized")

    # ------------------------------------------------------------------
    # Character node management
    # ------------------------------------------------------------------

    async def ensure_character(
        self, character_id: str, name: str = "", role: str = "",
    ) -> None:
        """Create or update a Character node."""
        async with self._driver.session() as session:
            await session.run(
                """MERGE (c:Character {character_id: $cid})
                   SET c.name = $name, c.role = $role""",
                cid=character_id, name=name, role=role,
            )

    # ------------------------------------------------------------------
    # Relationship sync
    # ------------------------------------------------------------------

    async def sync_relationship(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        trust: float,
        affection: float,
        description: str = "",
        chapter: int = -1,
    ) -> None:
        """Sync a relationship edge from SQLite to Neo4j."""
        sentiment = trust + affection
        edge_type = "HOSTILE_TO" if sentiment < -3 else "TRUSTS" if trust > 0.3 else "KNOWS"

        async with self._driver.session() as session:
            # Ensure both nodes exist
            await session.run(
                "MERGE (c:Character {character_id: $cid})",
                cid=source_id,
            )
            await session.run(
                "MERGE (c:Character {character_id: $cid})",
                cid=target_id,
            )
            # Upsert edge
            await session.run(
                f"""MATCH (a:Character {{character_id: $src}})
                    MATCH (b:Character {{character_id: $tgt}})
                    MERGE (a)-[r:{edge_type}]->(b)
                    SET r.relationship_type = $rel_type,
                        r.trust = $trust,
                        r.affection = $affection,
                        r.description = $desc,
                        r.chapter = $ch""",
                src=source_id, tgt=target_id,
                rel_type=relationship_type,
                trust=trust, affection=affection,
                desc=description, ch=chapter,
            )

    # ------------------------------------------------------------------
    # World knowledge sync
    # ------------------------------------------------------------------

    async def sync_world_knowledge(
        self,
        character_id: str,
        knowledge_type: str,
        knowledge_key: str,
        content: str,
        confidence: float,
    ) -> None:
        """Sync a world knowledge entry as a graph node + edge."""
        label_map = {
            "location": "Location",
            "faction": "Faction",
            "power_system": "PowerSystem",
            "culture": "Culture",
            "rule": "Rule",
        }
        node_label = label_map.get(knowledge_type, "Knowledge")

        async with self._driver.session() as session:
            await session.run(
                "MERGE (c:Character {character_id: $cid})",
                cid=character_id,
            )
            await session.run(
                f"""MERGE (k:{node_label} {{name: $key}})
                    SET k.content = $content""",
                key=knowledge_key, content=content,
            )
            await session.run(
                f"""MATCH (c:Character {{character_id: $cid}})
                    MATCH (k:{node_label} {{name: $key}})
                    MERGE (c)-[r:KNOWS_ABOUT]->(k)
                    SET r.confidence = $conf, r.knowledge_type = $ktype""",
                cid=character_id, key=knowledge_key,
                conf=confidence, ktype=knowledge_type,
            )

    # ------------------------------------------------------------------
    # Event tracking
    # ------------------------------------------------------------------

    async def record_event(
        self,
        event_id: str,
        chapter: int,
        title: str,
        description: str = "",
        witnesses: list[str] | None = None,
        caused_by: str | None = None,
        importance: float = 0.5,
    ) -> None:
        """Record an event and link to involved characters."""
        async with self._driver.session() as session:
            await session.run(
                """MERGE (e:Event {event_id: $eid})
                   SET e.chapter_index = $ch, e.title = $title,
                       e.description = $desc, e.importance = $imp""",
                eid=event_id, ch=chapter, title=title,
                desc=description, imp=importance,
            )
            for cid in (witnesses or []):
                await session.run(
                    """MATCH (c:Character {character_id: $cid})
                       MATCH (e:Event {event_id: $eid})
                       MERGE (c)-[:WITNESSED]->(e)""",
                    cid=cid, eid=event_id,
                )
            if caused_by:
                await session.run(
                    """MATCH (c:Character {character_id: $cid})
                       MATCH (e:Event {event_id: $eid})
                       MERGE (c)-[:CAUSED]->(e)""",
                    cid=caused_by, eid=event_id,
                )

    # ------------------------------------------------------------------
    # Graph queries
    # ------------------------------------------------------------------

    async def find_path(
        self, from_id: str, to_id: str, max_depth: int = 3,
    ) -> list[dict[str, Any]]:
        """Find shortest path between two characters."""
        async with self._driver.session() as session:
            result = await session.run(
                """MATCH path = shortestPath(
                       (a:Character {character_id: $src})-[*..%d]-(b:Character {character_id: $tgt})
                   )
                   RETURN [n IN nodes(path) | {id: n.character_id, name: n.name, labels: labels(n)}] AS nodes,
                          [r IN relationships(path) | {type: type(r), trust: r.trust, affection: r.affection}] AS edges"""
                % max_depth,
                src=from_id, tgt=to_id,
            )
            record = await result.single()
            if record is None:
                return []
            return [{"nodes": record["nodes"], "edges": record["edges"]}]

    async def get_social_context(self, character_id: str) -> str:
        """Generate a social context summary for a character."""
        async with self._driver.session() as session:
            # Direct relationships
            result = await session.run(
                """MATCH (me:Character {character_id: $cid})-[r]->(other:Character)
                   RETURN other.character_id AS other_id, other.name AS name,
                          type(r) AS rel_type, r.trust AS trust, r.affection AS affection,
                          r.relationship_type AS label
                   ORDER BY r.trust + r.affection DESC""",
                cid=character_id,
            )
            records = [r async for r in result]

            if not records:
                return ""

            parts = []
            friends = [r for r in records if (r["trust"] or 0) + (r["affection"] or 0) > 2]
            enemies = [r for r in records if (r["trust"] or 0) + (r["affection"] or 0) < -2]
            neutral = [r for r in records if r not in friends and r not in enemies]

            if friends:
                names = ", ".join(r["name"] or r["other_id"] for r in friends[:5])
                parts.append(f"盟友/友人: {names}")
            if enemies:
                names = ", ".join(r["name"] or r["other_id"] for r in enemies[:5])
                parts.append(f"敌对: {names}")
            if neutral:
                names = ", ".join(r["name"] or r["other_id"] for r in neutral[:5])
                parts.append(f"中立: {names}")

            # Second-degree connections
            result2 = await session.run(
                """MATCH (me:Character {character_id: $cid})-[r1]->(mid:Character)-[r2]->(far:Character)
                   WHERE far.character_id <> $cid AND NOT (me)-[]-(far)
                   RETURN far.name AS name, mid.name AS via, type(r2) AS rel
                   LIMIT 5""",
                cid=character_id,
            )
            second_degree = [r async for r in result2]
            if second_degree:
                parts.append("二度关系: " + "; ".join(
                    f"{r['name']}(经{r['via']})" for r in second_degree
                ))

            return "\n".join(parts)

    async def query_faction_network(self, character_id: str) -> str:
        """Query faction relationships from the character's perspective."""
        async with self._driver.session() as session:
            result = await session.run(
                """MATCH (me:Character {character_id: $cid})-[:KNOWS_ABOUT]->(f:Faction)
                   OPTIONAL MATCH (f)-[r]-(f2:Faction)
                   RETURN f.name AS faction, f.content AS desc,
                          collect(DISTINCT {other: f2.name, rel: type(r)}) AS connections""",
                cid=character_id,
            )
            records = [r async for r in result]
            if not records:
                return ""
            parts = []
            for r in records:
                line = f"{r['faction']}"
                conns = [c for c in r["connections"] if c.get("other")]
                if conns:
                    line += " — " + ", ".join(f"{c['rel']} {c['other']}" for c in conns)
                parts.append(line)
            return "\n".join(parts)

    async def get_full_graph(self) -> dict[str, Any]:
        """Get all nodes and edges for frontend visualization."""
        nodes: list[dict] = []
        edges: list[dict] = []

        async with self._driver.session() as session:
            # All character nodes
            result = await session.run(
                "MATCH (n) WHERE n:Character OR n:Location OR n:Faction OR n:Event "
                "RETURN labels(n) AS labels, properties(n) AS props"
            )
            async for record in result:
                labels = record["labels"]
                props = dict(record["props"])
                node_type = "character"
                node_id = ""
                label = ""
                if "Character" in labels:
                    node_type = "character"
                    node_id = props.get("character_id", "")
                    label = props.get("name", node_id)
                elif "Location" in labels:
                    node_type = "location"
                    node_id = f"loc_{props.get('name', '')}"
                    label = props.get("name", "")
                elif "Faction" in labels:
                    node_type = "faction"
                    node_id = f"fac_{props.get('name', '')}"
                    label = props.get("name", "")
                elif "Event" in labels:
                    node_type = "event"
                    node_id = props.get("event_id", "")
                    label = props.get("title", node_id)

                if node_id:
                    nodes.append({
                        "id": node_id, "label": label,
                        "type": node_type, "properties": props,
                    })

            # All edges
            result2 = await session.run(
                """MATCH (a)-[r]->(b)
                   WHERE (a:Character OR a:Location OR a:Faction OR a:Event)
                     AND (b:Character OR b:Location OR b:Faction OR b:Event)
                   RETURN coalesce(a.character_id, a.event_id, 'loc_'+a.name, 'fac_'+a.name) AS from_id,
                          coalesce(b.character_id, b.event_id, 'loc_'+b.name, 'fac_'+b.name) AS to_id,
                          type(r) AS rel_type, properties(r) AS props"""
            )
            async for record in result2:
                edges.append({
                    "from": record["from_id"],
                    "to": record["to_id"],
                    "label": record["rel_type"],
                    "type": record["rel_type"],
                    "properties": dict(record["props"]),
                })

        return {"nodes": nodes, "edges": edges}
