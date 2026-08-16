# 10 — 角色认知架构：从"打怪升级拼凑"到"自然生长"

> 版本: 1.0 | 2026-03-28

## 1. 现状：7层记忆架构

WorldEngine 的角色记忆系统已有7层：

| 层 | 存储 | 说明 |
|----|------|------|
| 情景记忆 (Episodic) | `episodic_memories` | 场景级事件记录 |
| 情感状态 (Emotional) | `emotional_states` | 6维情感向量 (快乐/愤怒/恐惧/悲伤/信任/惊讶) |
| 语义记忆 (Semantic) | `semantic_memories` | 知识与观察，带向量嵌入 |
| 关系网络 (Relationship) | `relationships` | 信任/好感度 + 关系类型 |
| 核心信念 (Belief) | `core_beliefs` | 可强化/动摇的信念系统 |
| 心智模型 (Schema) | `relationship_schemas` | 对他人的认知模型 |
| 创伤锚点 (Trauma) | `trauma_memories` | 创伤与力量锚点，带触发关键词 |

这7层通过 `CharacterMemory` 统一外观（facade），在 `get_context_window()` 中组装成 LLM 上下文。

## 2. 四个诊断

### 2.1 世界认知注入式

**症状**: 所有角色在场景模拟时收到完整的 `world.summary()`——包含所有力量体系、所有势力、所有地点。

**后果**: 一个刚出狱的底层人物"知道"全大陆政治格局，生成的对话和行为缺乏认知差异。

**根因**: `simulate_scene_node` 直接调用 `world.summary()` 注入所有角色。

### 2.2 记忆是流水账

**症状**: `memory_summary: str` 是一句话总结，如"我和老陈聊了天，他给了我一本心法"。

**后果**: 角色记住了"发生了什么"但没有记住"这对我意味着什么"。后续场景中角色无法延续疑虑、好奇、警觉等心理暗线。

**根因**: `CharacterActionOutput.memory_summary` 只是一个 `str`，没有结构化的解读维度。

### 2.3 场景间心理断裂

**症状**: 角色在场景A中暗自起疑，到场景B完全忘记，因为只有6个 emotion 浮点数跨场景传递。

**后果**: 角色的计谋、猜疑、暗中准备等"暗流"在场景间消失，故事缺乏连贯的心理张力。

**根因**: `EmotionalState` 只传递情绪维度（快乐、愤怒等），不传递心理状态（打算、警觉、关注点）。

### 2.4 反思太机械

**症状**: `should_reflect()` 固定每2章触发一次，所有角色在相同节点同时"顿悟"。

**后果**: 角色成长曲线均匀、刻意，缺乏"被事件推动"的真实感。

**根因**: `should_reflect(current_chapter, interval=2)` 只检查章节间距。

## 3. 四个手术

### 3.1 手术一：角色世界认知层 (WorldKnowledgeStore)

**原理**: 替代全局 `world.summary()` 注入。每个角色拥有自己的世界知识图谱，初始知识由背景决定，后续通过场景交互逐步扩展。

**数据模型**:
```
character_world_knowledge
├── character_id   TEXT    — 角色ID
├── knowledge_type TEXT    — location / faction / power_system / culture / history
├── knowledge_key  TEXT    — 具体知识条目（如地点名、势力名）
├── content        TEXT    — 角色所知的内容
├── source         TEXT    — 知识来源 (backstory / scene / told_by / observed)
├── confidence     REAL    — 确信度 0-1
└── chapter_learned INTEGER — 获知章节
```

**种子化规则** (`seed_from_backstory`):
- 主角：出身地描述 + 基本力量体系常识（等级名称，不含高阶秘密）
- 反派：所属势力详情 + 政治格局概览
- 配角：家乡地点 + 街头常识
- 通用：文化风俗（所有角色共享基础文化认知）

**动态学习** (`auto_learn_from_scene`):
- 到达新地点 → 解锁该地点描述
- 遇到某势力成员 → 解锁该势力基本信息
- 由角色背景推断已知信息 → 不重复学习

### 3.2 手术二：跨场景心理暗流 (InnerAgendaStore)

**原理**: 在情感维度之外，增加自然语言的心理状态传递。

**数据模型**:
```
character_inner_agenda
├── character_id    TEXT PRIMARY KEY
├── agenda          TEXT    — 隐藏打算/策略（如"先假装配合，暗中查探"）
├── vigilance       TEXT    — 警惕/关注事项（如"老陈的来历有蹊跷"）
├── chapter_updated INTEGER — 最近更新章节
└── scene_updated   INTEGER — 最近更新场景
```

**流程**: 每次场景结束，角色输出中包含 `inner_agenda` 和 `vigilance`，写入DB。下次场景开始时，从DB读取注入上下文的「当前心思」区块。

### 3.3 手术三：结构化记忆形成 (MemoryFormation)

**原理**: 将"流水账"记忆升级为有主观解读的结构化记忆。

**数据结构**:
```python
class MemoryFormation:
    event: str           # 客观事件："老陈给了我一本破心法"
    interpretation: str  # 主观解读："他可能知道我师门的事"
    unresolved: str      # 未解之谜："心法最后一页为什么被撕？"
    lesson: str          # 领悟："陈老头不简单，不可小看任何人"
```

**存储**: JSON 序列化存入 `episodic_memories.content`，向后兼容纯字符串格式。

**展示**: 解析后按格式展示——`[第X章] 事件: ... | 我的理解: ... | 疑问: ...`

### 3.4 手术四：条件触发式反思

**原理**: 反思不再按固定间隔触发，而是被事件驱动。

**触发条件** (任一满足即触发):
1. **最大间隔**: 超过4章未反思 → 强制反思
2. **情感冲击**: 任何情绪维度绝对值 > 0.7
3. **重大关系转变**: 信任或好感变化 > 0.3
4. **创伤触发**: 场景中出现了创伤记忆的触发关键词
5. **最小冷却**: 不论如何，至少间隔1章

## 4. 信息流

```
导演Agent
  │
  ├─→ 创建角色 Profile
  │     │
  │     └─→ seed_from_backstory() ──→ character_world_knowledge (初始认知)
  │
  └─→ 世界构建Agent ──→ WorldView (完整世界观，导演/作者可见)
                            │
场景模拟                      │
  │                           │
  ├─ 读取角色上下文            │
  │   ├─ get_context_window()  │
  │   │   ├─ 身份              │
  │   │   ├─ 记忆 (MemoryFormation 格式)
  │   │   ├─ 情感              │
  │   │   ├─ 关系              │
  │   │   ├─ 信念              │
  │   │   ├─ 心智模型          │
  │   │   ├─ 创伤锚点          │
  │   │   ├─ 【新】对世界的认知 ←─ world_knowledge.get_knowledge_summary()
  │   │   └─ 【新】当前心思    ←─ inner_agenda.get()
  │   │
  │   └─ world_context: 角色个人化世界认知（非全局 summary）
  │
  ├─ 角色行动（2轮）
  │   └─ 输出: actions + emotional_changes + memory_formation + inner_agenda + vigilance
  │
  └─ 场景结束
      ├─ 保存 MemoryFormation → episodic_memories
      ├─ 保存 inner_agenda → character_inner_agenda
      └─ auto_learn_from_scene() → character_world_knowledge (新认知)
          │
反思节点    │
  │         │
  ├─ should_reflect() ←─ 情感状态 + 关系变化 + 创伤触发
  │   (条件驱动，非固定间隔)
  │
  └─ reflect() → 信念/心智模型/创伤 更新
```

## 5. 前后对比

### 场景：刚出狱的底层主角在酒馆遇到神秘老者

**改造前**:
> 世界观注入: "这个世界有七大仙门，灵根分五行..."（完整体系）
> 记忆: "我在酒馆遇到了老陈，他给了我一本心法"
> 下一场景: 主角表现正常，无延续心理

**改造后**:
> 世界认知: "我只知道修炼者很厉害，具体分什么等级不清楚。我在南城长大，这里是赤霄城的贫民区"
> 记忆:
>   事件: 酒馆里遇到自称老陈的人，他看了我一眼后给了我一本残缺的心法
>   解读: 他似乎认识我？不然为什么无缘无故给东西
>   疑问: 心法最后几页被撕了，是故意的还是本来就残缺？
>   领悟: 天下没有免费的午餐，这老头不简单
> 当前心思:
>   隐藏打算: 先研究心法，但不告诉任何人。找机会打听老陈的来历
>   警惕: 老陈可能在利用我，要留意他是否跟踪我

## 6. 向后兼容

| 机制 | 兼容方案 |
|------|---------|
| `memory_summary: str` | 保留，`memory_formation` 为可选新增 |
| 旧纯字符串记忆 | `get_context_window()` 自动判断格式 |
| `world_context` 参数 | 保留作为 fallback（世界认知为空时使用） |
| `should_reflect(chapter, interval)` | 旧调用方式仍可工作（extra kwargs 有默认值） |
| 新DB表 | `CREATE IF NOT EXISTS`，无需迁移 |
