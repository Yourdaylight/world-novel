# 13 — 通用记忆交互框架：从小说创作到多Agent系统的抽象

> 版本: 1.0 | 2026-04-10

---

## 1. 问题：当前记忆系统的领域耦合

当前记忆密钥机制（文档12）的核心概念虽然是通用的，但实现深度耦合了"小说创作"领域：

| 领域耦合点 | 小说场景 | 通用场景 |
|-----------|---------|---------|
| 信任度来源 | `Relationship.trust` (-1~1) | 需要抽象为 `CredentialProvider` |
| 可见性触发 | 章节/场景索引 | 需要抽象为 `Event` / `Context` |
| 时间衰减 | `chapter_index` 衰减 | 需要抽象为 `Tick` / `Epoch` |
| 记忆类型 | 情景/语义/情感/关系/信念/创伤 | 需要抽象为可插拔的 `MemoryLayer` |
| 交互操作 | OBSERVE/INFER/DISCLOSE/COMPEL | 这些是通用的，但触发条件需抽象 |
| 存储后端 | SQLite + Qdrant + Neo4j | 需要抽象为 `MemoryBackend` |

**目标**：提取出一套 **`cognition-kit`** —— 任何多 Agent 系统都可以使用的记忆交互框架，WorldEngine 只是其一个应用实例。

---

## 2. 通用化抽象层次

### 2.1 六层抽象模型

```
┌──────────────────────────────────────────────────────────────────┐
│ Layer 6: Application Domain                                      │
│   (WorldEngine 小说创作 / 企业多Agent协作 / 游戏NPC系统 / ...)    │
├──────────────────────────────────────────────────────────────────┤
│ Layer 5: Interaction Protocols                                   │
│   OBSERVE / INFER / DISCLOSE / COMPEL 的通用协议定义              │
├──────────────────────────────────────────────────────────────────┤
│ Layer 4: Access Control Engine                                   │
│   可见性分层 + 信任圈层 + 动态密钥的通用引擎                       │
├──────────────────────────────────────────────────────────────────┤
│ Layer 3: Memory Architecture                                     │
│   记忆层(MemoryLayer) + 热度管理 + 整合压缩                       │
├──────────────────────────────────────────────────────────────────┤
│ Layer 2: Credential & Identity                                   │
│   身份模型 + 凭证提供者 + 关系度量                                 │
├──────────────────────────────────────────────────────────────────┤
│ Layer 1: Storage Backend                                         │
│   结构化(SQLite/Postgres) + 向量(Qdrant/Milvus) + 图(Neo4j/...)  │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 各层核心接口

---

#### Layer 1: Storage Backend

```python
from abc import ABC, abstractmethod
from typing import Any

class MemoryBackend(ABC):
    """存储后端的通用接口。"""
    
    @abstractmethod
    async def write(self, namespace: str, key: str, value: dict) -> None:
        """写入一条记忆。namespace 用于隔离（如 character_id）。"""
    
    @abstractmethod
    async def read(self, namespace: str, key: str) -> dict | None:
        """读取一条记忆。"""
    
    @abstractmethod
    async def query(self, namespace: str, filters: dict, limit: int = 10) -> list[dict]:
        """按条件查询记忆。"""
    
    @abstractmethod
    async def delete(self, namespace: str, key: str) -> None:
        """删除一条记忆。"""


class VectorBackend(MemoryBackend):
    """向量检索后端的扩展接口。"""
    
    @abstractmethod
    async def upsert_vector(self, namespace: str, key: str, 
                            vector: list[float], payload: dict) -> None:
        """写入向量+payload。"""
    
    @abstractmethod
    async def search_similar(self, namespace: str, query_vector: list[float],
                            filters: dict, top_k: int = 5) -> list[tuple[dict, float]]:
        """向量相似度检索。"""


class GraphBackend(MemoryBackend):
    """图关系后端的扩展接口。"""
    
    @abstractmethod
    async def upsert_edge(self, from_node: str, to_node: str, 
                          edge_type: str, properties: dict) -> None:
        """写入/更新一条边。"""
    
    @abstractmethod
    async def find_path(self, from_node: str, to_node: str, 
                        max_depth: int = 3) -> list[dict]:
        """查找两节点间的路径。"""
    
    @abstractmethod
    async def query_neighbors(self, node: str, edge_type: str | None = None) -> list[dict]:
        """查询邻居节点。"""
```

---

#### Layer 2: Credential & Identity

```python
class AgentIdentity(BaseModel):
    """Agent 身份模型。"""
    agent_id: str                           # 唯一标识
    agent_type: str = "generic"             # agent 类型标签
    metadata: dict[str, Any] = {}           # 领域特定元数据


class CredentialProvider(ABC):
    """凭证提供者 —— 决定"信任度"如何计算。
    
    不同的应用场景有不同的凭证来源：
    - 小说: Relationship.trust + affection
    - 企业: RBAC 角色权限 + 历史协作评分
    - 游戏: 阵营好感度 + 声望系统
    """
    
    @abstractmethod
    async def get_credential(self, observer_id: str, target_id: str) -> float:
        """获取 observer 对 target 的凭证值（0.0~1.0）。
        
        返回值语义由应用定义：
        - 0.0: 无任何信任/权限
        - 1.0: 完全信任/最高权限
        """
    
    @abstractmethod
    async def update_credential(self, observer_id: str, target_id: str, 
                                 delta: float, reason: str = "") -> None:
        """更新凭证值。"""
    
    @abstractmethod
    async def get_credential_history(self, observer_id: str, 
                                      target_id: str) -> list[dict]:
        """获取凭证变化历史。"""


# 小说领域的实现
class TrustBasedCredential(CredentialProvider):
    """基于 Relationship.trust 的凭证提供者。"""
    
    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn
    
    async def get_credential(self, observer_id: str, target_id: str) -> float:
        cursor = await self.conn.execute(
            "SELECT trust FROM relationships WHERE source_id = ? AND target_id = ?",
            (observer_id, target_id),
        )
        row = await cursor.fetchone()
        if row is None:
            return 0.0
        # 将 trust (-1~1) 映射到 credential (0~1)
        return (row["trust"] + 1) / 2


# 企业领域的实现
class RBACCredential(CredentialProvider):
    """基于 RBAC + 协作评分的凭证提供者。"""
    
    async def get_credential(self, observer_id: str, target_id: str) -> float:
        # 检查角色权限 + 协作评分
        role_access = self._check_role(observer_id, target_id)
        collab_score = await self._get_collab_score(observer_id, target_id)
        return role_access * 0.5 + collab_score * 0.5
```

---

#### Layer 3: Memory Architecture

```python
class MemoryLayer(ABC):
    """记忆层 —— 可插拔的记忆类型。"""
    
    layer_name: str                        # 层名称（如 episodic, semantic, belief）
    
    @abstractmethod
    async def store(self, agent_id: str, memory: dict, **kwargs) -> str:
        """存入一条记忆，返回 memory_id。"""
    
    @abstractmethod
    async def retrieve(self, agent_id: str, query: str, **kwargs) -> list[dict]:
        """检索相关记忆。"""
    
    @abstractmethod
    async def consolidate(self, agent_id: str, **kwargs) -> int:
        """整合/压缩记忆，返回被整合的条数。"""


class HeatManager(ABC):
    """热度管理 —— 记忆的衰减与唤醒。"""
    
    @abstractmethod
    async def decay(self, agent_id: str, tick: int) -> None:
        """按 tick 衰减所有记忆的热度。"""
    
    @abstractmethod
    async def access(self, memory_id: str, tick: int) -> None:
        """记忆被访问，提升热度。"""
    
    @abstractmethod
    async def get_partition(self, agent_id: str) -> dict[str, list[dict]]:
        """获取 Hot/Warm/Cold/Frozen 分区。"""


class MemoryRouter(ABC):
    """记忆路由 —— 决定从哪个层/后端读取。"""
    
    @abstractmethod
    async def recall(self, agent_id: str, query: str, 
                     context: dict, top_k: int = 8) -> list[MemoryFragment]:
        """混合检索，返回排序后的记忆片段。"""
    
    @abstractmethod
    async def build_context_window(self, agent_id: str, 
                                    context: dict) -> str:
        """为 LLM 构建完整的上下文窗口。"""
```

---

#### Layer 4: Access Control Engine

```python
class Visibility(str, Enum):
    """记忆可见性枚举。"""
    PUBLIC = "public"        # 任何人可见
    PROTECTED = "protected"  # 需要凭证
    PRIVATE = "private"      # 需要高凭证或主动披露
    SEALED = "sealed"        # 需要特定触发器


class AccessControlEngine:
    """通用访问控制引擎。"""
    
    def __init__(
        self,
        credential_provider: CredentialProvider,
        trust_circles: list[TrustCircle],   # 可配置的圈层定义
    ):
        self.credential = credential_provider
        self.trust_circles = trust_circles
    
    async def check_access(
        self,
        observer_id: str,
        owner_id: str,
        visibility: Visibility,
        trust_threshold: float = 0.0,
        disclosed_to: list[str] = [],
        triggers_matched: list[str] = [],    # SEALED 记忆的触发器
    ) -> AccessResult:
        """检查访问权限，返回访问结果（含细粒度）。"""
        
        # 自己的记忆
        if observer_id == owner_id:
            return AccessResult(granted=True, detail_level="deep", circle="self")
        
        # 已被披露
        if observer_id in disclosed_to:
            return AccessResult(granted=True, detail_level="deep", circle="disclosed")
        
        # SEALED: 只能通过触发器
        if visibility == Visibility.SEALED:
            if triggers_matched:
                return AccessResult(granted=True, detail_level="deep", circle="triggered")
            return AccessResult(granted=False)
        
        # 获取凭证
        cred = await self.credential.get_credential(observer_id, owner_id)
        
        # 按可见性判定
        if visibility == Visibility.PUBLIC:
            return AccessResult(granted=True, detail_level="surface", circle="public")
        
        if visibility == Visibility.PROTECTED:
            if cred >= trust_threshold:
                circle = self._resolve_circle(cred)
                detail = self._resolve_detail(cred)
                return AccessResult(granted=True, detail_level=detail, circle=circle)
            return AccessResult(granted=False)
        
        if visibility == Visibility.PRIVATE:
            if cred >= max(trust_threshold, self._private_threshold()):
                return AccessResult(granted=True, detail_level="deep", circle="confidant")
            return AccessResult(granted=False)
        
        return AccessResult(granted=False)
    
    def _resolve_circle(self, credential: float) -> str:
        for circle in self.trust_circles:
            if credential >= circle.min_credential:
                return circle.name
        return "stranger"
    
    def _resolve_detail(self, credential: float) -> str:
        if credential > 0.8:
            return "deep"
        elif credential > 0.5:
            return "partial"
        else:
            return "surface"


class TrustCircle(BaseModel):
    """信任圈层定义。"""
    name: str                     # 圈层名称
    min_credential: float         # 进入此圈层所需的最低凭证值
    unlock_visibility: list[Visibility]  # 此圈层可解锁的可见性
    description: str = ""


class AccessResult(BaseModel):
    """访问检查结果。"""
    granted: bool
    detail_level: str = "none"    # none / surface / partial / deep
    circle: str = "none"          # 匹配的信任圈层
    confidence_modifier: float = 1.0  # 信息的置信度修正
```

---

#### Layer 5: Interaction Protocols

```python
class MemoryExchangeProtocol(ABC):
    """记忆交互协议的基类。"""
    
    protocol_name: str
    
    @abstractmethod
    async def execute(
        self,
        from_agent: str,
        to_agent: str,
        memory: dict,
        context: dict,
    ) -> ExchangeResult:
        """执行一次记忆交互。"""


class ObserveProtocol(MemoryExchangeProtocol):
    """OBSERVE: 被动观察。"""
    protocol_name = "observe"
    
    async def execute(self, from_agent, to_agent, memory, context):
        access = await self.access_engine.check_access(
            observer_id=from_agent,
            owner_id=to_agent,
            visibility=memory.get("visibility", "public"),
            trust_threshold=memory.get("trust_threshold", 0.0),
        )
        if not access.granted:
            return ExchangeResult(success=False, reason="access_denied")
        
        # 根据 detail_level 裁剪信息
        filtered = self._filter_by_detail(memory, access.detail_level)
        return ExchangeResult(
            success=True,
            content=filtered,
            detail_level=access.detail_level,
            confidence=access.confidence_modifier,
        )


class InferProtocol(MemoryExchangeProtocol):
    """INFER: 从可观察行为推断隐藏信息。"""
    protocol_name = "infer"
    
    async def execute(self, from_agent, to_agent, memory, context):
        cred = await self.credential.get_credential(from_agent, to_agent)
        if cred < self.infer_threshold:
            return ExchangeResult(success=False, reason="insufficient_credential")
        
        # 使用 LLM 推断（或规则推断）
        inference = await self._infer(from_agent, to_agent, memory, cred)
        return ExchangeResult(
            success=True,
            content=inference,
            detail_level="partial",
            confidence=cred * 0.6,  # 推断的置信度永远低于直接观察
        )


class DiscloseProtocol(MemoryExchangeProtocol):
    """DISCLOSE: 主动透露。"""
    protocol_name = "disclose"
    
    async def execute(self, from_agent, to_agent, memory, context):
        # 检查 from_agent 是否愿意披露
        min_trust = memory.get("disclose_min_trust", 0.6)
        reverse_cred = await self.credential.get_credential(to_agent, from_agent)
        if reverse_cred < min_trust:
            return ExchangeResult(
                success=False, 
                reason=f"target trust ({reverse_cred:.2f}) below threshold ({min_trust})"
            )
        
        # 计算信息衰减
        from_cred = await self.credential.get_credential(from_agent, to_agent)
        confidence = min(from_cred, reverse_cred) * self.decay_factor
        
        # 写入接收者的记忆
        await self.memory_store.store(
            agent_id=to_agent,
            memory={
                **memory,
                "source": f"disclosed_by:{from_agent}",
                "confidence": confidence,
                "original_visibility": memory.get("visibility", "private"),
            },
        )
        
        # 更新关系
        await self.credential.update_credential(
            to_agent, from_agent, delta=0.1, reason="disclosure_trust_boost"
        )
        
        return ExchangeResult(
            success=True,
            content=memory,
            confidence=confidence,
        )


class CompelProtocol(MemoryExchangeProtocol):
    """COMPEL: 强迫泄露。"""
    protocol_name = "compel"
    
    async def execute(self, from_agent, to_agent, memory, context):
        # 检查触发条件
        triggers = memory.get("trigger_keywords", [])
        context_triggers = context.get("active_triggers", [])
        matched = [t for t in triggers if t in context_triggers]
        
        if not matched and not context.get("coercion", False):
            return ExchangeResult(success=False, reason="no_trigger")
        
        # 强制解锁
        confidence = self.compel_confidence  # 低于自愿披露
        
        # 写入施加者的记忆
        await self.memory_store.store(
            agent_id=from_agent,
            memory={
                **memory,
                "source": f"compelled_from:{to_agent}",
                "confidence": confidence,
            },
        )
        
        # 惩罚关系
        await self.credential.update_credential(
            to_agent, from_agent, delta=-0.3, reason="compelled"
        )
        
        return ExchangeResult(
            success=True,
            content=memory,
            confidence=confidence,
            side_effects={"trauma_triggered": True, "trust_damage": -0.3},
        )


class ExchangeResult(BaseModel):
    """交互结果。"""
    success: bool
    content: dict | None = None
    detail_level: str = "none"
    confidence: float = 1.0
    reason: str = ""
    side_effects: dict = {}
```

---

#### Layer 6: Application Domain (WorldEngine 示例)

```python
# WorldEngine 的领域配置
class WorldEngineMemoryConfig:
    """WorldEngine 领域的记忆系统配置。"""
    
    # 信任圈层
    trust_circles = [
        TrustCircle(name="soulmate", min_credential=0.9, 
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED, Visibility.PRIVATE],
                     description="生死之交"),
        TrustCircle(name="confidant", min_credential=0.7,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED, Visibility.PRIVATE],
                     description="至交知己"),
        TrustCircle(name="friend", min_credential=0.4,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED],
                     description="朋友"),
        TrustCircle(name="acquaintance", min_credential=0.15,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED],
                     description="泛泛之交"),
        TrustCircle(name="stranger", min_credential=0.0,
                     unlock_visibility=[Visibility.PUBLIC],
                     description="路人"),
    ]
    
    # 凭证提供者
    credential_provider = TrustBasedCredential  # 基于 Relationship.trust
    
    # 热度衰减参数
    decay_factor = 0.92
    access_bonus = 0.15
    trauma_floor = 0.6
    
    # 披露衰减
    disclose_decay_factor = 0.8
    compel_confidence = 0.6
    infer_threshold = 0.15  # 凭证 > 0.15 才能推断
    
    # 记忆层
    memory_layers = [
        "episodic",     # 情景记忆
        "emotional",    # 情感状态
        "semantic",     # 语义记忆
        "relationship", # 关系网络
        "belief",       # 核心信念
        "schema",       # 心智模型
        "trauma",       # 创伤锚点
        "world",        # 世界认知
        "agenda",       # 内心暗流
    ]
```

---

## 3. 不同领域的适配示例

### 3.1 企业多 Agent 协作

```python
class EnterpriseMemoryConfig:
    """企业协作场景的记忆系统配置。"""
    
    trust_circles = [
        TrustCircle(name="admin", min_credential=1.0,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED, Visibility.PRIVATE],
                     description="系统管理员"),
        TrustCircle(name="team_lead", min_credential=0.8,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED, Visibility.PRIVATE],
                     description="团队负责人"),
        TrustCircle(name="teammate", min_credential=0.5,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED],
                     description="同团队成员"),
        TrustCircle(name="colleague", min_credential=0.2,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED],
                     description="跨团队同事"),
        TrustCircle(name="external", min_credential=0.0,
                     unlock_visibility=[Visibility.PUBLIC],
                     description="外部人员"),
    ]
    
    credential_provider = RBACCredential  # 基于 RBAC + 协作评分
    
    # 企业场景无创伤概念，但有机密文档
    # SEALED → 机密文档，需要特定审批才能访问
    
    memory_layers = [
        "task",         # 任务记忆
        "decision",     # 决策记录
        "knowledge",    # 专业知识
        "communication",# 沟通历史
        "preference",   # 工作偏好
    ]
```

**场景**：Agent A 完成了一个技术方案的调研，标记为 PROTECTED。Agent B 是同团队成员（credential=0.6），可以看到方案摘要但看不到详细技术细节（detail_level=partial）。Agent C 是外部协作方（credential=0.1），只能看到方案标题。

### 3.2 游戏 NPC 系统

```python
class GameNPCMemoryConfig:
    """游戏 NPC 的记忆系统配置。"""
    
    trust_circles = [
        TrustCircle(name="blood_brother", min_credential=0.9,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED, Visibility.PRIVATE],
                     description="结拜兄弟"),
        TrustCircle(name="ally", min_credential=0.6,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED],
                     description="盟友"),
        TrustCircle(name="neutral", min_credential=0.3,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED],
                     description="中立NPC"),
        TrustCircle(name="suspicious", min_credential=0.0,
                     unlock_visibility=[Visibility.PUBLIC],
                     description="可疑人物"),
        TrustCircle(name="enemy", min_credential=-1.0,  # 特殊：敌对
                     unlock_visibility=[],
                     description="敌人"),
    ]
    
    # 凭证来源：阵营好感度 + 声望 + 个人互动历史
    credential_provider = FactionReputationCredential
    
    memory_layers = [
        "quest",        # 任务记忆
        "location",     # 地点记忆
        "faction",      # 势力认知
        "item",         # 物品知识
        "rumor",        # 传闻
        "grudge",       # 仇恨记忆（类似创伤）
    ]
```

**场景**：NPC 铁匠知道一把传说武器的锻造方法（PRIVATE），只有声望达到"信赖"（credential > 0.7）的玩家才能触发 DISCLOSE 对话选项获得锻造线索。

### 3.3 社交模拟系统

```python
class SocialSimMemoryConfig:
    """社交模拟（如 AI 伴侣/虚拟社区）的记忆系统配置。"""
    
    trust_circles = [
        TrustCircle(name="intimate", min_credential=0.85,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED, Visibility.PRIVATE],
                     description="亲密关系"),
        TrustCircle(name="close_friend", min_credential=0.6,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED],
                     description="好朋友"),
        TrustCircle(name="friend", min_credential=0.35,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED],
                     description="朋友"),
        TrustCircle(name="acquaintance", min_credential=0.1,
                     unlock_visibility=[Visibility.PUBLIC],
                     description="认识的人"),
        TrustCircle(name="stranger", min_credential=0.0,
                     unlock_visibility=[Visibility.PUBLIC],
                     description="陌生人"),
    ]
    
    # 凭证来源：互动频率 + 情感投入 + 一致性评分
    credential_provider = InteractionBasedCredential
    
    # 社交场景中 SEALED = 被压抑的记忆（心理防御机制）
    # 触发方式：特定话题触发、心理辅导场景、醉酒状态
    
    memory_layers = [
        "interaction",  # 互动记忆
        "emotion",      # 情感记忆
        "preference",   # 偏好
        "secret",       # 秘密
        "boundary",     # 边界/禁忌
        "narrative",    # 自我叙事
    ]
```

---

## 4. cognition-kit 的包结构

```
cognition_kit/
├── __init__.py
├── core/
│   ├── identity.py          # AgentIdentity, CredentialProvider
│   ├── visibility.py        # Visibility enum, TrustCircle, AccessResult
│   ├── access_control.py    # AccessControlEngine
│   └── memory_fragment.py   # MemoryFragment 基类
│
├── protocols/
│   ├── base.py              # MemoryExchangeProtocol, ExchangeResult
│   ├── observe.py           # ObserveProtocol
│   ├── infer.py             # InferProtocol
│   ├── disclose.py          # DiscloseProtocol
│   └── compel.py            # CompelProtocol
│
├── memory/
│   ├── base.py              # MemoryLayer, HeatManager, MemoryRouter
│   ├── episodic.py          # EpisodicMemoryLayer
│   ├── semantic.py          # SemanticMemoryLayer
│   ├── emotional.py         # EmotionalMemoryLayer
│   └── composite.py         # CompositeMemory (多层组合)
│
├── backends/
│   ├── sqlite.py            # SQLiteBackend
│   ├── qdrant.py            # QdrantBackend
│   ├── neo4j.py             # Neo4jBackend
│   └── memory_backend.py    # InMemoryBackend (测试用)
│
├── credentials/
│   ├── trust_based.py       # TrustBasedCredential (小说)
│   ├── rbac.py              # RBACCredential (企业)
│   ├── faction.py           # FactionReputationCredential (游戏)
│   └── interaction.py       # InteractionBasedCredential (社交)
│
├── decay/
│   ├── heat.py              # HeatManager 默认实现
│   ├── exponential.py       # 指数衰减策略
│   └── step.py              # 阶梯衰减策略
│
└── presets/
    ├── novel.py             # WorldEngineMemoryConfig
    ├── enterprise.py        # EnterpriseMemoryConfig
    ├── game_npc.py          # GameNPCMemoryConfig
    └── social.py            # SocialSimMemoryConfig
```

---

## 5. 关键设计决策

### 5.1 凭证 (Credential) vs 权限 (Permission)

| 维度 | 传统 RBAC | 本框架 Credential |
|------|----------|------------------|
| 本质 | 离散角色标签 | 连续数值 (0.0~1.0) |
| 获取 | 管理员分配 | 通过互动积累 |
| 变化 | 罕见 | 频繁、渐变 |
| 语义 | "你能做什么" | "你有多了解" |
| 回收 | 立即生效 | 渐进衰减 |

**选择理由**：Agent 系统中的"信任"天然是连续的、动态的。RBAC 的离散角色模型无法表达"我以前信任你但现在不那么信任了"。

### 5.2 为什么不使用真正的加密？

| 方案 | 优点 | 缺点 |
|------|------|------|
| 真正的公钥加密 | 信息论安全 | 密钥管理复杂，无法动态调整权限 |
| ACL (访问控制列表) | 实现简单 | 无法表达连续信任，维护成本高 |
| **Credential-Based Access** | 动态、连续、自动 | 非信息论安全（但这不是目标） |

**选择理由**：本系统的目标不是防止恶意攻击者窃取数据，而是模拟真实认知中的信息不对称。Credential-Based Access 最符合这个目标——"信任度即密钥"。

### 5.3 记忆不转移，只复制衰减

**原则**：当 A 向 B 披露一条记忆时，原始记忆始终留在 A 的存储中，B 获得的是一条带衰减的副本。

**理由**：
1. 记忆是主观建构，不是客观事实——A 和 B 对同一件事的记忆永远不同
2. 允许双方对同一记忆有不同的 confidence——B 可以怀疑 A 说的话
3. 避免级联效应——A 删除记忆不应该影响 B 已获得的认知

### 5.4 框架是"约定"而非"实现"

`cognition-kit` 的 Layer 1-4 提供接口和默认实现，但不强制具体实现。使用者可以：
- 替换 `CredentialProvider` 来适应不同的信任计算方式
- 替换 `MemoryBackend` 来使用不同的存储引擎
- 自定义 `TrustCircle` 来定义不同的圈层体系
- 新增 `MemoryExchangeProtocol` 来支持新的交互模式

---

## 6. WorldEngine 迁移路径

### 阶段 1：接口抽取（不改动运行时行为）

1. 从现有 `RelationshipStore` 中抽取 `CredentialProvider` 接口
2. 从 `character.py` 的 `is_visible` 逻辑中抽取 `AccessControlEngine`
3. 从 `EpisodicStore` / `SemanticStore` 中抽取 `MemoryLayer` 接口
4. 现有代码改为调用接口，实现类保持不变

### 阶段 2：接口替换（切换到 cognition-kit）

1. `pip install cognition-kit`（或 `uv add cognition-kit`）
2. 配置 `WorldEngineMemoryConfig` 作为预设
3. 逐步将现有 Store 实现替换为 cognition-kit 的默认实现
4. 验证行为不变

### 阶段 3：能力增强

1. 启用 DISCLOSE 协议（新增能力）
2. 启用 INFER 协议（增强观察细粒度）
3. 启用 COMPEL 协议（胁迫场景）
4. 启用记忆自动分类（visibility 自动标注）

---

## 7. 开放问题

### 7.1 凭证的双向性

当前 `CredentialProvider.get_credential(A, B)` 只返回 A 对 B 的凭证。但在某些场景中，凭证应该是双向的：

- **互信场景**：A 信任 B，B 也信任 A → 双向凭证都高
- **单相思场景**：A 信任 B，B 不信任 A → 只有 A→B 高

**问题**：DISCLOSE 协议中，A 向 B 披露的 confidence 应该基于 A→B 还是 B→A 的凭证？

**当前设计**：`min(A→B, B→A) × decay_factor`——取双向凭证的较小值。理由：如果 A 不信任 B（A→B 低），A 不会愿意披露；如果 B 不信任 A（B→A 低），B 不会认真对待 A 的披露。

### 7.2 多步推理的凭证传递

如果 A 告诉 B 一个秘密，B 又告诉 C，C 对这个秘密的凭证如何计算？

```
A 的原始记忆: confidence = 1.0
A→B 披露: confidence = min(A→B, B→A) × 0.8 = 0.64
B→C 转述: confidence = min(B→C, C→B) × 0.64 × 0.6 = 0.23
```

**问题**：0.23 是否过低？在某些场景（如企业协作），信息传递的衰减应该更温和。

**可能方案**：让 `decay_factor` 成为 `CredentialProvider` 的配置项，不同领域设不同值。

### 7.3 SEALED 记忆的跨框架表达

SEALED 记忆在小说场景中对应"被压抑的创伤"，在企业场景中对应"机密文档"，在社交场景中对应"心理防御"。触发机制各不相同：

| 领域 | SEALED 含义 | 触发方式 |
|------|-----------|---------|
| 小说 | 创伤记忆 | trigger_keywords, COMPEL |
| 企业 | 机密文档 | 审批流程, 安全审计 |
| 游戏 | 封印技能 | 任务触发, 物品使用 |
| 社交 | 压抑记忆 | 特定话题, 情境暗示 |

**问题**：`trigger_keywords` 是小说特有的概念。是否需要一个更通用的 `UnlockCondition` 接口？

```python
class UnlockCondition(ABC):
    @abstractmethod
    async def check(self, context: dict) -> bool:
        """检查是否满足解锁条件。"""

class KeywordTrigger(UnlockCondition):  # 小说
    keywords: list[str]
    async def check(self, context): 
        return any(kw in context.get("dialogue", "") for kw in self.keywords)

class ApprovalTrigger(UnlockCondition):  # 企业
    required_approvals: list[str]
    async def check(self, context):
        return all(a in context.get("approvals", []) for a in self.required_approvals)

class QuestTrigger(UnlockCondition):  # 游戏
    quest_id: str
    quest_stage: int
    async def check(self, context):
        return context.get("quest_progress", {}).get(self.quest_id, 0) >= self.quest_stage
```

### 7.4 记忆所有权与 GDPR 式删除

在社交模拟场景中，用户可能要求"删除关于我的所有记忆"。但本框架中记忆是不转移的——A 的记忆始终在 A 的存储中。如果 A 拥有关于 B 的记忆，B 要求删除时怎么办？

**可能的策略**：
- **强删除**：删除所有涉及 B 的记忆（可能破坏叙事连贯性）
- **匿名化**：将 B 的名字替换为"某人"，保留事件结构
- **拒绝权**：框架只提供接口，由应用层决定策略

---

## 8. 总结

```
┌──────────────────────────────────────────────────────────────────┐
│                                                                  │
│   cognition-kit 的核心价值主张:                                    │
│                                                                  │
│   1. 任何多 Agent 系统都需要"信息不对称"                           │
│   2. 信息不对称需要"访问控制"                                     │
│   3. 访问控制需要"凭证"                                          │
│   4. 凭证的最自然来源是"信任"                                     │
│   5. 信任是挣来的，不是给的                                       │
│                                                                  │
│   因此: Credential-Based Access Control                           │
│   是多 Agent 记忆交互的最通用范式                                  │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

WorldEngine 是这套框架的第一个应用实例，但不应是唯一的。通过将领域特定逻辑（`TrustBasedCredential`、`KeywordTrigger`、`chapter_index` 衰减）从通用逻辑（`AccessControlEngine`、`DiscloseProtocol`、`HeatManager`）中分离出来，`cognition-kit` 可以服务于任何需要"认知自主权"的多 Agent 系统。
