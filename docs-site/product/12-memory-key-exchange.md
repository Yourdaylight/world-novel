# 12 — 记忆密钥交互机制：基于信任的认知自主权协议

> 版本: 1.0 | 2026-04-10

---

## 1. 动机与问题

当前系统的角色间记忆交换存在三个核心缺陷：

| 缺陷 | 表现 | 根因 |
|------|------|------|
| **记忆无隐私边界** | 任何在场角色对其他角色的行为享有同等观察权 | 缺少可见性分级，只有 `is_visible` 二元开关 |
| **信任不产生认知红利** | trust 从 0.1 到 0.9，观察到的信息完全一样 | 信任度不参与记忆访问控制 |
| **秘密只能通过对话泄露** | 角色想"告诉"另一人某条记忆，只能通过 dialogue 行为间接传递 | 无显式的记忆披露协议 |

**核心洞察**：现实人际中，信任是挣来的，不是给的。你对一个人的了解深度，取决于你们之间的信任积累。我们需要的不是"加密算法"，而是一套 **以信任度作为密钥门槛的认知访问控制协议**。

---

## 2. 核心概念

### 2.1 记忆可见性分层 (Memory Visibility Tiers)

每条记忆/行为有一个可见性标签，类比文件权限位：

```
┌──────────────┬───────────────────┬────────────────────────────────────┐
│   层级        │   类比             │   规则                             │
├──────────────┼───────────────────┼────────────────────────────────────┤
│ PUBLIC       │ 广场上的告示       │ 任何人可见（如身份、公开立场）        │
│ PROTECTED    │ 有锁的日记本       │ 需要对方授予权限才可见              │
│ PRIVATE      │ 保险箱中的秘密     │ 只有自己可见，除非主动"解密"分享     │
│ SEALED       │ 封印的创伤         │ 连自己都无法主动回忆，需特定触发器   │
└──────────────┴───────────────────┴────────────────────────────────────┘
```

**层级关系**：PUBLIC ⊂ PROTECTED ⊂ PRIVATE ⊂ SEALED（每一层包含更低层的全部内容）

### 2.2 信任圈层 (Trust Circles)

基于 `Relationship.trust` (-1.0 ~ 1.0) 定义5个圈层：

```
┌───────┬──────────┬────────────────┬────────────────────────────────────┐
│ 圈层   │ 信任区间  │ 类比            │ 可解锁的记忆层级                   │
├───────┼──────────┼────────────────┼────────────────────────────────────┤
│ 陌生   │ < 0.0    │ 路人            │ PUBLIC only                       │
│ 熟识   │ 0.0~0.3  │ 泛泛之交        │ PUBLIC + PROTECTED(level1)        │
│ 友好   │ 0.3~0.6  │ 朋友            │ PUBLIC + PROTECTED(all)           │
│ 信赖   │ 0.6~0.8  │ 至交/知己        │ + PRIVATE(level1)                 │
│ 心腹   │ > 0.8    │ 生死之交/挚爱    │ + PRIVATE(all)                    │
└───────┴──────────┴────────────────┴────────────────────────────────────┘
```

### 2.3 密钥隐喻映射

| 加密概念 | 本系统映射 | 说明 |
|---------|----------|------|
| 公钥 (Public Key) | 记忆的 `visibility` + `trust_threshold` | 公开声明"什么级别的秘密需要什么信任门槛" |
| 私钥 (Private Key) | 角色的 `disclosed_to` 列表 | 自主选择"我把秘密告诉了谁" |
| 解密 (Decryption) | B→A 的 trust 值 >= A 的 trust_threshold | 信任度达到门槛即可"解锁"读取 |
| 密钥分发 (Key Distribution) | 主动披露 (DISCLOSE) 操作 | A 主动将 PRIVATE 记忆解密给 B |
| 密钥回收 (Key Revocation) | trust 下降 → 自动失去访问权 | 信任降低后，高阶记忆自动不可见 |
| 数字信封 (Digital Envelope) | DISCLOSE 产生的二手记忆 | 原始记忆不转移，产生带衰减的副本 |

**关键设计决策**：密钥不是"发送"的，而是"达到"的。A 标记了记忆的门槛，B 需要通过长期互动积累信任才能"解锁"。这比真正的公钥加密更符合人际关系的本质。

---

## 3. 记忆交互协议 (Memory Exchange Protocol)

四种操作定义了角色间记忆交换的完整行为空间：

### 3.1 OBSERVE — 被动观察

**定义**：从其他角色的可见行为中获取信息。

**当前实现**：`character.py` 中 `is_visible` 过滤——THOUGHT 类型行为对他人不可见。

**增强**：为行为增加 `visibility` 标签，替代简单的 `is_visible` 布尔值：

```python
# 当前
if a.action_type == ActionType.THOUGHT:
    continue  # 不可见

# 增强
visible_actions = []
for a in other_actions:
    access = check_memory_access(
        observer_id=self.character_id,
        owner_id=a.character_id,
        visibility=a.visibility,
        trust_threshold=a.trust_threshold,
    )
    if access:
        detail_level = get_detail_level(access)  # trust 越高，观察到的细节越多
        visible_actions.append((a, detail_level))
```

**观察细粒度**：

| B→A trust | A 的 PROTECTED 行为对 B 的可见程度 |
|-----------|----------------------------------|
| < 0.0 | 完全不可见 |
| 0.0~0.3 | 看到表面行为（"A微微皱眉"） |
| 0.3~0.6 | 看到部分细节（"A皱眉后手不自觉地握紧了"） |
| > 0.6 | 看到深层意图线索（"A表面平静，但握紧的手暴露了他的紧张"） |

### 3.2 INFER — 推断

**定义**：基于信任关系，从公开行为中推断隐藏信息。

**新增能力**：当 B 对 A 的信任度达到 `熟识` 以上时，B 的认知系统会自动从 A 的行为中产生"直觉"：

```
A 的行动: "沉默片刻，然后说'没什么'" (PUBLIC 行为)

B 的推断 (trust=0.4, 友好):
  → "你对A较为了解，感觉A的话有些言不由衷"
  → 产生一条 PROTECTED 级别的推断记忆

B 的推断 (trust=0.1, 熟识):
  → "A说没什么，但语气有点犹豫"
  → 产生一条低置信度的观察记忆

B 的推断 (trust=-0.2, 陌生):
  → "A说没什么"
  → 无推断，仅接受表面信息
```

**实现方式**：在 `CharacterAgent.process_scene()` 中，构建 `others_context` 时根据信任度注入"直觉提示"：

```python
# 构建 others_context 时，注入信任直觉
for a in other_actions:
    if a.action_type == ActionType.THOUGHT:
        continue
    parts.append(f"  {a.character_id} {prefix}: {a.content}")
    
    # INFER: 根据信任度追加直觉
    trust = await get_trust(self.character_id, a.character_id)
    if trust > 0.6 and a.visibility in ("PROTECTED", "PRIVATE"):
        parts.append(f"  [你的直觉] 你对{a.character_id}非常了解，感觉事情没那么简单")
    elif trust > 0.3 and a.visibility == "PROTECTED":
        parts.append(f"  [你的感觉] {a.character_id}似乎有所保留")
```

### 3.3 DISCLOSE — 主动透露

**定义**：角色 A 主动选择将一条 PRIVATE 记忆"解密"后分享给角色 B。

这是"私钥"的真正体现——A 自主决定把秘密告诉谁。

**协议流程**：

```
1. A 决定 DISCLOSE:
   A → system: "我愿意告诉B关于'师父之死'的真相"
   
2. 系统检查:
   - B→A 的 trust 是否 >= A 设定的分享门槛（默认 0.6）
   - 如果不满足: "B尚未赢得你足够的信任，你不想冒这个险"
   
3. 执行披露:
   - A 的原记忆标记: disclosed_to += ["B"]
   - B 的 world_knowledge 新增一条:
     type = "secret"
     key = "{A}_disclosed_{memory_id}"
     content = A 的记忆原文 + "(A亲口所述)"
     source = "told_by:{A}"
     confidence = min(A→B 的 trust, B→A 的 trust) × 0.8
     
4. 关系更新:
   - B→A: trust +0.1 (被信任的感动)
   - A→B: affection +0.05 (倾诉后的释然)
   
5. 后续风险:
   - 已泄露的秘密无法收回
   - 如果 B 后来 trust 下降，B 仍拥有这条二手记忆
   - 但 confidence 会随关系恶化动态降低（见 §4.2）
```

**信息衰减**：

| 传递层级 | confidence 衰减 | 说明 |
|---------|----------------|------|
| 一手记忆 (A 自己的) | 1.0 | 原始体验 |
| A 亲口告诉 B | A→B trust × 0.8 | 亲述，较高保真 |
| B 转告 C | B→C trust × 0.5 | 二手传递，保真大幅衰减 |
| 传闻 (经过 3+ 人) | < 0.2 | 几乎不可信 |

### 3.4 COMPEL — 强迫泄露

**定义**：在胁迫场景中，SEALED 记忆被强制解锁。

**触发条件**（满足任一）：

1. 场景设定为胁迫类型（`scene_metadata` 标记 `coercion=True`）
2. A 的某条 SEALED 记忆的 `trigger_keywords` 被提及
3. A 的 fear 情绪 > 0.7 且当前 trauma 被激活

**执行效果**：

```
SEALED 记忆被强制解锁 → 以"痛苦回忆"形式暴露

A 的情感状态变化:
  fear +0.3, sadness +0.2
  
A 对施加者的关系变化:
  trust -0.3
  
施加者获得该记忆:
  source = "compelled:{A}"
  confidence = 0.6  (被迫者可能说谎或记忆失真)
```

---

## 4. 数据模型扩展

### 4.1 EpisodicMemory 扩展

```python
class EpisodicMemory(BaseModel):
    # 现有字段...
    memory_id: str
    character_id: str
    chapter_index: int
    scene_index: int
    content: str
    importance: float = 0.5
    emotional_valence: float = 0.0
    involved_characters: list[str] = []
    
    # 新增：可见性控制
    visibility: str = "PUBLIC"           # PUBLIC / PROTECTED / PRIVATE / SEALED
    trust_threshold: float = 0.0         # 解锁所需的对方→己方信任阈值
    disclosed_to: list[str] = []         # 已主动透露给哪些角色
```

### 4.2 CharacterAction 扩展

```python
class CharacterAction(BaseModel):
    # 现有字段...
    character_id: str
    chapter_index: int
    scene_index: int
    action_type: ActionType
    content: str
    target_character_id: str | None = None
    emotional_shift: dict[str, float] = {}
    
    # 新增：行为可见性
    visibility: str = "PUBLIC"           # 此行为的可见性层级
    trust_threshold: float = 0.0         # 对方需要达到的信任门槛才能看到细节
```

### 4.3 Relationship 扩展

```python
class Relationship(BaseModel):
    # 现有字段...
    source_id: str
    target_id: str
    relationship_type: str = "陌生人"
    trust: float = 0.0
    affection: float = 0.0
    description: str = ""
    
    # 新增：密钥交互相关
    shared_secrets: list[str] = []       # 双方共享的秘密 memory_id 列表
    intimacy_level: str = "stranger"     # stranger / acquaintance / friend / confidant / soulmate
```

### 4.4 CharacterActionOutput 扩展

```python
class CharacterActionOutput(BaseModel):
    actions: list[ActionItem] = Field(description="角色行动列表")
    emotional_changes: dict[str, float] = Field(default_factory=dict)
    memory_summary: str = Field(default="")
    relationship_changes: list[RelationshipChange] = Field(default_factory=list)
    
    # 新增：记忆披露
    disclosures: list[DisclosureItem] = Field(
        default_factory=list,
        description="主动向其他角色透露的记忆",
    )


class DisclosureItem(BaseModel):
    """角色主动披露一条记忆给另一角色。"""
    target_id: str = Field(description="披露目标角色ID")
    memory_content: str = Field(description="要透露的记忆内容")
    memory_visibility: str = Field(default="PRIVATE", description="原记忆的可见性")
    min_trust_required: float = Field(default=0.6, description="要求对方对自己的最低信任度")
```

### 4.5 新增表: memory_access_log

```sql
-- 记忆访问日志：追踪谁在什么时候访问了谁的什么记忆
CREATE TABLE IF NOT EXISTS memory_access_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    accessor_id TEXT NOT NULL,           -- 访问者角色ID
    owner_id TEXT NOT NULL,              -- 记忆拥有者角色ID
    memory_id TEXT,                      -- 被访问的记忆ID（可为空，表示行为观察）
    access_type TEXT NOT NULL,           -- OBSERVE / INFER / DISCLOSE / COMPEL
    visibility_level TEXT NOT NULL,      -- 访问到的可见性层级
    trust_at_access REAL DEFAULT 0.0,    -- 访问时的信任度快照
    chapter_index INTEGER NOT NULL,
    scene_index INTEGER NOT NULL,
    detail_level TEXT DEFAULT 'surface', -- surface / partial / deep
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_access_accessor ON memory_access_log(accessor_id);
CREATE INDEX IF NOT EXISTS idx_access_owner ON memory_access_log(owner_id);
CREATE INDEX IF NOT EXISTS idx_access_chapter ON memory_access_log(chapter_index);
```

### 4.6 新增表: memory_disclosures

```sql
-- 记忆披露记录：追踪谁把什么秘密告诉了谁
CREATE TABLE IF NOT EXISTS memory_disclosures (
    disclosure_id TEXT PRIMARY KEY,
    from_character_id TEXT NOT NULL,     -- 披露者
    to_character_id TEXT NOT NULL,       -- 接收者
    original_memory_id TEXT,             -- 原始记忆ID（如有）
    content TEXT NOT NULL,               -- 披露的内容
    visibility TEXT DEFAULT 'PRIVATE',   -- 原记忆的可见性
    chapter_index INTEGER NOT NULL,
    scene_index INTEGER NOT NULL,
    confidence_at_disclosure REAL DEFAULT 0.5,  -- 披露时的置信度
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_disclosure_from ON memory_disclosures(from_character_id);
CREATE INDEX IF NOT EXISTS idx_disclosure_to ON memory_disclosures(to_character_id);
```

### 4.7 SQLite Schema 变更 (V11)

```sql
-- V11: 情景记忆新增可见性字段
ALTER TABLE episodic_memories ADD COLUMN visibility TEXT DEFAULT 'PUBLIC';
ALTER TABLE episodic_memories ADD COLUMN trust_threshold REAL DEFAULT 0.0;
ALTER TABLE episodic_memories ADD COLUMN disclosed_to TEXT DEFAULT '[]';

-- V11: 角色行为新增可见性字段
ALTER TABLE character_actions ADD COLUMN visibility TEXT DEFAULT 'PUBLIC';
ALTER TABLE character_actions ADD COLUMN trust_threshold REAL DEFAULT 0.0;

-- V11: 关系新增亲密圈层字段
ALTER TABLE relationships ADD COLUMN shared_secrets TEXT DEFAULT '[]';
ALTER TABLE relationships ADD COLUMN intimacy_level TEXT DEFAULT 'stranger';
```

---

## 5. 访问控制引擎

### 5.1 核心函数

```python
def check_memory_access(
    observer_id: str,
    owner_id: str,
    visibility: str,
    trust_threshold: float,
    trust_value: float,           # observer → owner 的 trust 值
    disclosed_to: list[str] = [],  # 该记忆已披露给的角色列表
) -> str | None:
    """检查 observer 是否有权访问 owner 的某条记忆/行为。
    
    Returns:
        None: 无权访问
        'surface': 表层信息
        'partial': 部分细节
        'deep': 完整细节
    """
    # 自己的记忆始终可访问
    if observer_id == owner_id:
        return 'deep'
    
    # 已被主动披露
    if observer_id in disclosed_to:
        return 'deep'
    
    # 按可见性层级 + 信任度判定
    if visibility == "PUBLIC":
        return 'surface'
    
    if visibility == "PROTECTED":
        if trust_value >= trust_threshold:
            if trust_value >= 0.6:
                return 'deep'
            elif trust_value >= 0.3:
                return 'partial'
            else:
                return 'surface'
        return None
    
    if visibility == "PRIVATE":
        if trust_value >= trust_threshold and trust_value >= 0.6:
            return 'deep'
        return None
    
    if visibility == "SEALED":
        # SEALED 记忆只能通过 COMPEL 或 trigger 触发
        return None
    
    return None
```

### 5.2 信任圈层计算

```python
def compute_intimacy_level(trust: float, affection: float) -> str:
    """根据 trust 和 affection 计算亲密圈层。"""
    composite = trust * 0.7 + affection * 0.3  # 信任权重更高
    if composite > 0.8:
        return "soulmate"
    elif composite > 0.6:
        return "confidant"
    elif composite > 0.3:
        return "friend"
    elif composite > 0.0:
        return "acquaintance"
    else:
        return "stranger"
```

### 5.3 动态置信度调整

已披露的秘密的 confidence 不是固定的，会随关系动态变化：

```python
async def get_effective_confidence(
    disclosure: dict,
    current_trust: float,
) -> float:
    """已披露记忆的有效置信度，随关系恶化而降低。"""
    base = disclosure["confidence_at_disclosure"]
    # 当前 trust 低于披露时 → 置信度衰减
    if current_trust < 0.3:
        return base * 0.5  # "我开始怀疑他当时说的是不是真的"
    elif current_trust < 0.0:
        return base * 0.2  # "他当时可能在骗我"
    return base
```

---

## 6. 与现有系统的集成

### 6.1 CharacterAgent.process_scene() 改造

```python
async def process_scene(self, ...):
    # ... 现有逻辑 ...
    
    # 2. 构建 other_actions_context（增强版）
    others_context = ""
    if other_actions:
        parts = []
        for a in other_actions:
            # 检查访问权限
            trust = await self._get_trust_for(a.character_id)
            access = check_memory_access(
                observer_id=self.character_id,
                owner_id=a.character_id,
                visibility=a.visibility,
                trust_threshold=a.trust_threshold,
                trust_value=trust,
            )
            if access is None:
                continue  # 无权观察
            
            # 根据访问深度展示不同细节
            if a.action_type == ActionType.THOUGHT and access != 'deep':
                continue  # 内心想法只有 deep 级别才能看到
            
            prefix = {"dialogue": "说", "behavior": "做", ...}.get(a.action_type.value, "")
            parts.append(f"  {a.character_id} {prefix}: {a.content}")
            
            # INFER: 注入信任直觉
            if trust > 0.6 and a.visibility in ("PROTECTED", "PRIVATE"):
                parts.append(f"  [你的直觉] 你对{a.character_id}非常了解，感觉事情没那么简单")
            elif trust > 0.3 and a.visibility == "PROTECTED":
                parts.append(f"  [你的感觉] {a.character_id}似乎有所保留")
        
        if parts:
            others_context = "\n## 其他角色的行为\n" + "\n".join(parts)
    
    # ... LLM 调用 ...
    
    # 8. 处理 disclosures（新增）
    for disclosure in output.disclosures:
        await self._execute_disclosure(disclosure, chapter_index, scene_index)
    
    return actions
```

### 6.2 记忆写入时自动分类

在记忆写入时，LLM 自动标注可见性：

```python
class MemoryClassificationOutput(BaseModel):
    """LLM 输出的记忆分类结果。"""
    visibility: str = Field(description="PUBLIC / PROTECTED / PRIVATE / SEALED")
    trust_threshold: float = Field(description="解锁此记忆所需的信任门槛 0.0-1.0")
    reasoning: str = Field(description="分类理由")


async def classify_memory_visibility(
    memory_content: str,
    character_profile: CharacterProfile,
) -> MemoryClassificationOutput:
    """使用 LLM 对新记忆进行可见性自动分类。"""
    prompt = f"""请判断以下记忆的可见性等级：
    
    记忆内容: {memory_content}
    角色身份: {character_profile.name} ({character_profile.role})
    
    分级标准：
    - PUBLIC: 任何人都可以知道的事（如公开身份、常识）
    - PROTECTED: 需要一定了解才能察觉的事（如个人习惯、微妙情感）
    - PRIVATE: 只有非常信任的人才能知道的秘密（如隐藏的过去、真实意图）
    - SEALED: 深层创伤，需要特定触发才能回忆（如惨痛经历、被压抑的记忆）
    
    同时设定信任门槛（0.0-1.0）：要让别人知道这件事，需要多大的信任？"""
    
    # ... LLM call ...
```

### 6.3 SEALED 记忆与现有 TraumaStore 整合

SEALED 记忆本质上是创伤记忆的扩展：

```
现有 TraumaStore:
  trauma_type: "trauma" / "anchor"
  trigger_keywords: ["师父", "毒"]
  emotional_impact: {fear: 0.8, sadness: 0.7}

增强为:
  visibility: "SEALED"
  trigger_keywords: ["师父", "毒"]  ← 解锁触发器
  trust_threshold: N/A              ← SEALED 不通过信任解锁
  
解锁方式:
  1. trigger_keywords 被提及 → 自动触发（现有机制）
  2. COMPEL 操作 → 强制解锁（新增）
  3. Reflection Agent 识别 → 渐进解锁（新增）
```

---

## 7. 记忆交互流程示例

### 7.1 场景：主角向知己坦白师父之死

```
第5章: 主角(hero)和知己(mentor)深夜对话

初始状态:
  hero 有一条 PRIVATE 记忆: "师父是被长老毒死的，我亲眼所见"
    visibility=PRIVATE, trust_threshold=0.7, disclosed_to=[]
  mentor→hero trust=0.75

1. hero 的 DISCLOSE 决策:
   LLM 输出: disclosures = [
     DisclosureItem(target_id="mentor", memory_content="师父是被长老毒死的...",
                    min_trust_required=0.6)
   ]

2. 系统执行:
   检查 mentor→hero trust = 0.75 >= 0.6 ✓
   
   hero 原记忆更新: disclosed_to += ["mentor"]
   
   mentor 的 world_knowledge 新增:
     type = "secret"
     key = "hero_master_death"
     content = "主角亲口说：师父是被长老毒死的，他亲眼所见"
     source = "told_by:hero"
     confidence = min(hero→mentor trust, mentor→hero trust) × 0.8
               = min(0.7, 0.75) × 0.8 = 0.56
   
   关系更新:
     mentor→hero: trust +0.1, affection +0.1
     hero→mentor: affection +0.05

3. 后续风险:
   - 如果 mentor→hero trust 降到 0.3 以下，这条二手记忆的
     effective_confidence = 0.56 × 0.5 = 0.28（"他当时可能在骗我"）
   - 如果 mentor 把秘密告诉第三方，再衰减一轮
```

### 7.2 场景：敌人拷问主角

```
第12章: 敌人(villain)拷问主角(hero)

初始状态:
  hero 有一条 SEALED 记忆: "那夜我亲眼看见师父倒下，长老在旁冷笑"
    visibility=SEALED, trigger_keywords=["师父倒下", "长老冷笑"]
  hero 当前 fear = 0.8
  villain→hero trust = -0.5

1. villain 提及触发词:
   villain 的 dialogue: "你师父死的那晚，你到底看到了什么？"
   → 匹配 trigger_keywords: "师父" + "死"

2. COMPEL 触发:
   SEALED 记忆解锁 → hero 被迫回忆

3. 执行效果:
   hero 的情感状态: fear +0.3 = 1.0, sadness +0.2
   hero→villain: trust -0.3
   
   villain 的 world_knowledge 新增:
     type = "secret"
     key = "hero_sealed_memory"
     content = "主角在胁迫下回忆：那夜看见师父倒下，长老在旁冷笑"
     source = "compelled:hero"
     confidence = 0.6  (被迫者可能记忆失真或故意歪曲)

4. 叙事影响:
   - hero 获得 trauma: "被逼问师父之死" (trauma_type="trauma")
   - villain 获得了情报但 confidence 不高（可能被误导）
```

### 7.3 场景：陌生人观察高手

```
第1章: 陌生路人(stranger)观察高手(master)切磋

初始状态:
  master 的 PROTECTED 行为: "微微调整了呼吸节奏，暗运内力到右臂"
    visibility=PROTECTED, trust_threshold=0.2
  stranger→master trust = -0.1 (陌生)

1. OBSERVE:
   stranger→master trust = -0.1 < 0.2 (trust_threshold)
   → 无法观察到 PROTECTED 行为
   → stranger 只看到: "master出手了" (PUBLIC 部分)

2. 对比 — 如果是同门师弟(junior):
   junior→master trust = 0.5 > 0.2
   → 可以观察到 PROTECTED 行为
   → junior 看到: "师兄微微调整了呼吸节奏，暗运内力到右臂"
   
   如果 trust > 0.6:
   → junior 看到: "师兄以寸劲发力，内力走的是心经路线，看来在试探对方"
```

---

## 8. 与文档 10/11 的关系

| 文档 | 本文档依赖 | 本文档增强 |
|------|----------|----------|
| 10-cognition-architecture | WorldKnowledgeStore 的 per-character 认知 | 为世界认知增加 `source=told_by` 和 `source=compelled` 路径 |
| 10-cognition-architecture | InnerAgendaStore 的跨场景心理暗流 | agenda/vigilance 的可见性应为 PRIVATE |
| 10-cognition-architecture | MemoryFormation 的结构化记忆 | 每个维度可独立设 visibility |
| 11-memory-enhancement | MemoryRouter 的混合检索路由 | 路由前需增加访问控制检查 |
| 11-memory-enhancement | HeatManager 的热度衰减 | SEALED 记忆的 trauma_floor 机制 |
| 11-memory-enhancement | Neo4j 的 KNOWS/TRUSTS 边 | 增加 intimacy_level 属性，用于快速判断圈层 |

---

## 9. 实施计划

### Phase 1 — 核心访问控制 (2天)

1. 新增 `memory/access_control.py`：实现 `check_memory_access()` 和 `compute_intimacy_level()`
2. `database.py`：V11 迁移（新增 visibility, trust_threshold, disclosed_to 字段）
3. `character.py`：`process_scene()` 中替换 `is_visible` 过滤为访问控制检查
4. 验证：THOUGHT 行为默认 PROTECTED，低信任角色看不到

### Phase 2 — DISCLOSE 协议 (3天)

1. `models/memory.py`：新增 `DisclosureItem` 模型
2. `character.py`：`CharacterActionOutput` 新增 `disclosures` 字段
3. `character.md` prompt：增加披露决策指引
4. 新增 `memory/disclosure_store.py`：披露记录 CRUD
5. `database.py`：新增 `memory_disclosures` 表
6. 验证：角色可主动披露 PRIVATE 记忆给信任者

### Phase 3 — INFER 推断与观察细粒度 (2天)

1. `character.py`：构建 others_context 时注入信任直觉
2. `character.md` prompt：增加"根据信任度推断"的指引
3. 行为输出增加 visibility 标注
4. 验证：不同信任度的角色对同一行为的观察结果不同

### Phase 4 — COMPEL 与 SEALED 整合 (2天)

1. `character.py`：场景类型判断 + COMPEL 触发逻辑
2. 与 `TraumaStore` 整合：SEALED 记忆的解锁路径
3. `database.py`：新增 `memory_access_log` 表
4. 验证：胁迫场景中 SEALED 记忆可被强制解锁

### Phase 5 — 记忆自动分类 (3天)

1. 新增 `memory/visibility_classifier.py`：LLM 自动分类
2. 集成到 `CharacterAgent.process_scene()` 和 `EpisodicStore.add()`
3. 动态置信度调整逻辑
4. 验证：新写入的记忆自动获得合适的可见性标签

---

## 10. 设计哲学

```
传统记忆共享:  A的记忆 ──复制──→ B的记忆  (信息无损传递)
密钥记忆交互:  A的记忆 ──DISCLOSE──→ B的认知建构  (信息有损、主观化)
```

本机制的核心哲学：

1. **认知自主权**：每个角色是独立的认知主体，记忆不是共享数据库，而是个人化建构
2. **信任即密钥**：信任不是静态标签，而是动态的访问凭证——密钥自动获取与失效
3. **信息有损传递**：记忆在传递中必然衰减，这是特征而非缺陷
4. **秘密不可回收**：一旦披露，无法撤回——这创造了真实的叙事风险
5. **创伤的封印与解锁**：最深层的记忆不是"更难访问"，而是"无法主动回忆"——只有特定触发才能解锁
