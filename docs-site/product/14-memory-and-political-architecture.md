# 14 — 记忆机制与政治架构：集权/去中心化场景下的认知拓扑差异

> 版本: 1.0 | 2026-04-10
>
> 前置文档：
> - [12 — 记忆密钥交互机制](./12-memory-key-exchange.md)：信任度即密钥的核心协议设计
> - [13 — 通用记忆交互框架](./13-generic-cognition-kit.md)：从小说创作到通用多Agent系统的抽象

---

## 1. 问题：政治架构是否影响记忆机制？

文档12和13设计的记忆密钥机制基于一个隐含假设：**信任是私人之间的双向关系**——A对B的trust值是A和B之间的事，与第三方无关。

但现实并非如此。你敢对谁说什么话，不仅取决于你和他之间的关系，还取决于你们身处什么环境：

| 场景 | 你敢说的 | 你不敢说的 | 原因 |
|------|---------|----------|------|
| 民主国家，私密客厅 | 对政府的批评 | 无 | 信任的朋友+私密空间=安全 |
| 集权国家，公共广场 | 天气不错 | 对领导人的批评 | 不确定谁在听 |
| 集权国家，私密客厅 | 对政策的不满 | 核心反抗计划 | 担心朋友被审问后泄露 |
| 极权国家，任何地方 | 天气不错（可能） | 任何敏感话题 | 处处监控，信任不再有意义 |

**核心问题**：在不同的政治架构（集权/中心化 vs 自由/去中心化）下，同样的"信任度=0.8"所对应的记忆访问行为是否应该不同？

**答案**：是的，必须不同。因为政治架构改变了信息流动的**拓扑结构**，而不仅仅是信任度的数值。

---

## 2. 三种政治架构的认知拓扑

### 2.1 自由/去中心化架构（Liberal/Decentralized）

```
认知拓扑：网状 (Mesh)

     A ──── B
    / \    / \
   C───D──E───F
    \ /    \ /
     G ──── H

特征：
- 每个Agent是一个独立的信息节点
- 信任关系是私密的、双向的
- 信息流动路径：A→B→C→D（多跳、慢速、衰减）
- 无中心监控节点
- 没有强制性的信息共享义务
```

**记忆机制映射**（文档12的设计完全适用）：

| 机制 | 表现 |
|------|------|
| OBSERVE | 只能在物理/社交距离内观察到 |
| INFER | 信任度高才能从行为推断意图 |
| DISCLOSE | A自主决定告诉谁，基于A对B的信任 |
| COMPEL | 只有物理胁迫场景下才发生 |
| 密钥分配 | 纯粹基于私人关系的trust值 |
| 信息衰减 | 按传递链路逐级衰减 |

### 2.2 集权/中心化架构（Authoritarian/Centralized）

```
认知拓扑：星状 + 网状 (Star + Mesh)

          [中央监控者]
         /    |    \
        A     B     C
         \    |    /
          D───E───F

特征：
- 存在一个"全知"或"半全知"的中心节点
- 中心节点可以强制访问所有Agent的PUBLIC和PROTECTED记忆
- Agent之间的信任关系被"削弱"——即使你只告诉B，A也可能通过中心知道
- 信息流动路径：A→[中心]→B（中心中转，快速但不可控）
- 隐含的信息共享义务：某些记忆必须上报
```

**记忆机制的6个关键变化**：

#### 变化1：中心节点的"超级凭证"

```python
class CentralizedCredentialProvider(CredentialProvider):
    """集权场景的凭证提供者。"""
    
    def __init__(self, authority_ids: list[str], ...):
        self.authority_ids = authority_ids  # 中央监控者的ID列表
    
    async def get_credential(self, observer_id: str, target_id: str) -> float:
        # 中央监控者对任何Agent都有超级凭证
        if observer_id in self.authority_ids:
            return 1.0  # 完全访问权
        
        # 普通Agent之间的凭证计算
        base_credential = await self._get_base_credential(observer_id, target_id)
        
        # 集权压制效应：Agent感知到"被监控"，信任被打折
        surveillance_factor = await self._get_surveillance_intensity()
        return base_credential * (1 - surveillance_factor * 0.3)
```

**含义**：集权环境中，普通Agent之间的有效凭证被系统性压低。不是因为你不信任朋友，而是你**不敢**像自由环境中那样信任——你的信任行为被环境"冷却"了。

#### 变化2：强制上报协议 (MANDATE)

这是文档12中四种协议之外的第五种：

```
MANDATE — 强制上报协议

定义：某些类别的记忆被法律规定必须上报给中心节点

触发条件：
  - 记忆内容匹配"敏感词表"（如叛乱、异见、逃亡计划）
  - 记忆的visibility被标记为 mandated_reportable
  - Agent的角色职责包含报告义务（如线人、公务员）

执行：
  1. Agent产生一条匹配的记忆后，系统自动创建一条MANDATE事件
  2. Agent必须选择：上报 / 隐瞒（承担风险）
  3. 如果隐瞒被发现（概率 = surveillance_intensity），惩罚性后果
  
风险计算：
  conceal_risk = surveillance_intensity × content_sensitivity × (1 - agent_courage)
  
  如果 conceal_risk > 0.5:
    → Agent倾向于上报（即使不想）
  如果 conceal_risk < 0.2:
    → Agent倾向于隐瞒
  中间地带:
    → Agent产生犹豫、焦虑情绪
```

#### 变化3：信任的"污染效应"

在集权环境中，信任不再是纯粹的私人关系——它被**环境恐惧**污染了：

```
自由环境中：
  A 对 B 的 trust = 0.8
  → A 愿意告诉 B 一个秘密

集权环境中：
  A 对 B 的 trust = 0.8
  环境 surveillance_intensity = 0.6
  → A 的有效信任 = 0.8 × (1 - 0.6 × 0.3) = 0.656
  → A 犹豫："我信任你，但我不确定你是否会被审问"
  
  如果 B 是 known_informer:
    → A 的有效信任 = 0.8 × 0.3 = 0.24
    → A 绝对不告诉 B 任何事
```

```python
def effective_trust(
    base_trust: float,
    surveillance_intensity: float,     # 0~1，监控强度
    target_is_informer: bool = False,   # 对方是否是已知线人
    target_interrogation_risk: float = 0.0,  # 对方被审问的概率
) -> float:
    """集权环境中的有效信任计算。"""
    
    # 线人惩罚：信任直接打折
    if target_is_informer:
        return base_trust * 0.2
    
    # 监控恐惧：信任被环境压制
    fear_penalty = surveillance_intensity * 0.3
    
    # 审问风险：对方可能被逼供
    interrogation_penalty = target_interrogation_risk * 0.4
    
    return max(0.0, base_trust * (1 - fear_penalty - interrogation_penalty))
```

#### 变化4：DISCLOSE协议的风险重计算

```
自由环境中的DISCLOSE决策：
  条件: B→A trust >= min_trust_required
  
集权环境中的DISCLOSE决策：
  条件: B→A effective_trust >= min_trust_required
       AND conceal_risk < acceptable_threshold
       AND B 不是 known_informer
       AND 场景不是 monitored_space
```

```python
async def check_disclose_in_authoritarian(
    from_agent: str,
    to_agent: str,
    memory: dict,
    environment: EnvironmentContext,
) -> DiscloseDecision:
    """集权环境中的披露决策。"""
    
    # 基本信任检查
    base_trust = await get_trust(from_agent, to_agent)
    eff_trust = effective_trust(
        base_trust,
        surveillance_intensity=environment.surveillance_intensity,
        target_is_informer=await is_known_informer(to_agent),
        target_interrogation_risk=await get_interrogation_risk(to_agent),
    )
    
    min_required = memory.get("min_trust_required", 0.6)
    
    if eff_trust < min_required:
        return DiscloseDecision(
            allowed=False,
            reason=f"有效信任({eff_trust:.2f})低于门槛({min_required})，"
                   f"环境恐惧压制了信任",
        )
    
    # 场景安全性检查
    if environment.is_monitored_space:
        return DiscloseDecision(
            allowed=False,
            reason="当前场景有监控，不宜透露敏感信息",
        )
    
    # 风险计算
    sensitivity = memory.get("sensitivity", 0.5)
    conceal_risk = environment.surveillance_intensity * sensitivity
    
    if conceal_risk > 0.7:
        return DiscloseDecision(
            allowed=True,
            warning="风险极高，但信任允许。Agent可能选择沉默。",
            risk_level="critical",
        )
    
    return DiscloseDecision(allowed=True, risk_level="low")
```

#### 变化5：COMPEL协议的体系化

在自由环境中，COMPEL是个别事件（一次拷问）。在集权环境中，COMPEL变成**体系化的审讯机制**：

```
自由环境: COMPEL = 偶发的暴力胁迫
集权环境: COMPEL = 制度化的审讯系统

集权审讯的增强特性：
  1. 审讯者拥有合法的"超级凭证"（法律授权）
  2. 审讯可以反复进行（不是一次性事件）
  3. 审讯可以交叉验证（同时审问多人，比对口供）
  4. 拒绝回答本身就是罪证（沉默=嫌疑）
  5. 审讯结果自动进入中心知识库（所有人"共享"）

记忆泄露的级联效应：
  A 被审问 → COMPEL触发 → 泄露关于B的秘密
  → 中心获得情报 → 审问B → B泄露关于C的秘密
  → 中心获得更多情报 → ...
  
  这不是简单的1对1泄露，而是网络化的级联提取。
```

```python
class InterrogationCascade:
    """集权审讯的级联效应模拟。"""
    
    async def simulate_cascade(
        self, 
        initial_target: str, 
        max_depth: int = 3,
    ) -> list[CascadeStep]:
        """模拟从 initial_target 开始的审讯级联。"""
        
        cascade = []
        queue = [initial_target]
        visited = set()
        
        while queue and len(cascade) < max_depth * 5:
            target = queue.pop(0)
            if target in visited:
                continue
            visited.add(target)
            
            # 获取target的所有PRIVATE/SEALED记忆
            secrets = await self.get_secrets(target)
            
            for secret in secrets:
                # COMPEL触发
                extracted = await self.compel(target, secret)
                
                # 从泄露的秘密中发现新的审讯目标
                new_targets = secret.get("involved_characters", [])
                queue.extend(t for t in new_targets if t not in visited)
                
                cascade.append(CascadeStep(
                    target=target,
                    secret_extracted=secret["content"],
                    new_targets_discovered=new_targets,
                    confidence=extracted.confidence,
                ))
        
        return cascade
```

#### 变化6：记忆的"自我审查"

在集权环境中，Agent不仅对外部审查有反应，还会**内化**审查——在记忆形成阶段就自我审查：

```
自由环境中的记忆形成：
  经历事件 → 记忆写入 → visibility自动分类

集权环境中的记忆形成：
  经历事件 → 自我审查 → (1) 安全的部分 → 记忆写入
                          (2) 敏感的部分 → SEALED（主动封印）
                          (3) 极度危险的 → 不形成记忆（否认现实）
```

```python
async def classify_memory_in_authoritarian(
    memory_content: str,
    character_profile: CharacterProfile,
    environment: EnvironmentContext,
) -> MemoryClassificationOutput:
    """集权环境中的记忆分类——增加了自我审查。"""
    
    # 先按标准流程分类
    base_result = await classify_memory_visibility(memory_content, character_profile)
    
    # 自我审查叠加
    sensitivity = await compute_sensitivity(memory_content, environment.sensitive_topics)
    
    if sensitivity > 0.8 and environment.surveillance_intensity > 0.5:
        # 高敏感 + 高监控 → 主动封印
        return MemoryClassificationOutput(
            visibility="SEALED",
            trust_threshold=1.0,  # 永远不主动透露
            reasoning="自我审查：此记忆过于危险，主动封印以保护自己",
            self_censored=True,
        )
    elif sensitivity > 0.5:
        # 中敏感 → 提升可见性门槛
        return MemoryClassificationOutput(
            visibility="PRIVATE",
            trust_threshold=max(base_result.trust_threshold, 0.8),
            reasoning="环境审查：提升信任门槛以降低泄露风险",
            self_censored=True,
        )
    
    return base_result
```

---

### 2.3 共产主义/集体架构（Communal/Collective）

```
认知拓扑：全连接 (Fully Connected)

    A ──── B
    │  ╲╱  │
    │  ╱╲  │
    C ──── D

特征：
- 理想状态下，所有Agent共享所有记忆（无隐私边界）
- 存在集体决策机制（投票/共识）
- 记忆属于集体而非个人
- 但实际运行中，总会出现"暗流"——一些Agent私下保留秘密
```

**关键差异**：共产主义架构的核心理念是**记忆公共化**，这直接挑战了文档12中"认知自主权"的根基。

#### 差异1：记忆所有权的集体化

```
自由架构：  记忆属于产生它的Agent（私有产权）
集权架构：  记忆属于Agent，但中心有权强制访问（私有产权+超级访问权）
集体架构：  记忆属于集体（公共产权）

集体架构的记忆规则：
  - 所有 PUBLIC/PROTECTED 记忆自动进入"集体记忆池"
  - PRIVATE 记忆在理论上不存在（但实践中Agent会偷偷保留）
  - SEALED 记忆被视为"病态"——集体有义务帮助Agent"治愈"（解锁）
  - DISCLOSE 协议被"自愿分享"替代：Agent被期望主动分享一切
```

```python
class CommunalMemoryConfig:
    """集体架构的记忆配置。"""
    
    # 只有3个可见性层级（没有PRIVATE的理论空间）
    visibility_levels = ["PUBLIC", "SHARED", "CONCEALED"]
    
    # PUBLIC: 对所有人可见
    # SHARED: 进入集体记忆池，所有人可投票决定如何使用
    # CONCEALED: Agent私下保留，被视为"不健康的行为"
    
    trust_circles = [
        TrustCircle(name="collective", min_credential=0.0,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED],
                     description="集体成员（默认信任）"),
        TrustCircle(name="trusted_comrade", min_credential=0.5,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED, Visibility.PRIVATE],
                     description="经过考验的同志"),
        TrustCircle(name="secret_keeper", min_credential=0.8,
                     unlock_visibility=[Visibility.PUBLIC, Visibility.PROTECTED, Visibility.PRIVATE],
                     description="秘密守护者——在集体中保留秘密的人"),
    ]
    
    # 关键：初始凭证不为0，而是正的默认值
    # 集体架构的默认假设是"信任所有人"
    default_credential = 0.4  # 而非0.0
    
    # SEALED记忆的处理
    sealed_policy = "therapeutic"  # 治疗性解锁，而非惩罚性
```

#### 差异2：集体记忆池 (Collective Memory Pool)

```
集体记忆池：
  一个所有Agent可读写的共享记忆空间

  写入规则：
    - 所有 SHARED 记忆自动写入
    - Agent的reflection结果可写入
    - 集体决策的结论写入
    
  读取规则：
    - 所有集体成员默认可读
    - 但读取需要"共识确认"——不是一个人能随意使用的
    
  管理规则：
    - 集体投票决定哪些记忆可以被"整合/压缩"
    - 不能未经同意删除他人贡献的记忆
    - 但可以投票决定某条记忆的"重要性"排序
```

```python
class CollectiveMemoryPool:
    """集体记忆池。"""
    
    async def contribute(self, agent_id: str, memory: dict) -> str:
        """Agent向集体贡献一条记忆。"""
        memory_id = generate_id()
        await self.store.write(
            namespace="collective",
            key=memory_id,
            value={
                **memory,
                "contributor": agent_id,
                "consensus_score": 0.0,  # 待集体投票
                "access_count": 0,
            },
        )
        return memory_id
    
    async def vote_on_memory(self, memory_id: str, voter_id: str, 
                              importance: float) -> None:
        """集体成员对记忆重要性投票。"""
        # 类似 StackOverflow 的投票机制
        await self.store.update(
            namespace="collective",
            key=memory_id,
            updates={
                "consensus_score": IncrementBy(importance),
            },
        )
    
    async def recall_for_agent(self, agent_id: str, query: str, 
                                top_k: int = 5) -> list[dict]:
        """从集体记忆池中检索。"""
        results = await self.store.query(
            namespace="collective",
            filters={"query": query},
            limit=top_k * 2,  # 多检索一些，按共识过滤
        )
        # 按共识分数排序
        results.sort(key=lambda x: x.get("consensus_score", 0), reverse=True)
        return results[:top_k]
```

#### 差异3：隐瞒是"异常行为"

在集体架构中，一个Agent有PRIVATE/CONCEALED记忆不是正常状态，而是**需要解释的异常**：

```
集体架构中的隐瞒动态：

正常状态：
  Agent → 无CONCEALED记忆 → 被集体视为"健康成员"
  
异常状态：
  Agent → 有CONCEALED记忆 → 被集体视为"需要帮助"
    → 集体可能发起"关怀行动"（试探性INFER）
    → 如果Agent抗拒分享 → 被视为"有秘密"
    → 可能影响集体对Agent的信任（反向：你不分享=你不信任集体）

隐瞒悖论：
  在自由架构中：保留秘密是权利
  在集体架构中：保留秘密是不信任集体的表现
  
  这创造了一个自我强化的循环：
    Agent有秘密 → 不分享 → 被认为不信任集体 
    → 集体对Agent信任下降 → Agent更不敢分享 → 更多秘密
```

```python
class ConcealmentDetector:
    """集体架构中的隐瞒检测。"""
    
    async def detect_concealment(self, agent_id: str) -> ConcealmentReport:
        """检测Agent是否有隐瞒行为。"""
        
        # 统计Agent的CONCEALED记忆比例
        total_memories = await self.count_all_memories(agent_id)
        concealed_memories = await self.count_concealed_memories(agent_id)
        concealment_ratio = concealed_memories / max(total_memories, 1)
        
        # 检测"欲言又止"模式
        hesitation_score = await self.detect_hesitation_pattern(agent_id)
        
        # 检测INFER不一致（别人推断出的比Agent说的多）
        infer_gaps = await self.detect_infer_gaps(agent_id)
        
        return ConcealmentReport(
            agent_id=agent_id,
            concealment_ratio=concealment_ratio,
            hesitation_score=hesitation_score,
            infer_gaps=infer_gaps,
            severity="high" if concealment_ratio > 0.3 else "low",
        )
```

#### 差异4：DISCLOSE变成"坦白" (CONFESSION)

```
自由架构: DISCLOSE = 自主选择分享（权利）
集体架构: CONFESSION = 向集体坦白秘密（义务/净化仪式）

CONFESSION 协议：
  触发条件：
    1. Agent自愿坦白（内心压力释放）
    2. 集体关怀行动触发（半自愿）
    3. 隐瞒检测触发（被动坦白）
  
  执行：
    Agent → 集体记忆池: 写入CONCEALED记忆
    集体反应:
      - 接纳：信任+0.2（"你终于敞开了"）
      - 审查：对内容进行集体讨论
      - 惩罚：如果内容违反集体原则
    
  与DISCLOSE的区别：
    - 目标不是"一个人"，而是"集体"
    - 机制不是"一对一复制衰减"，而是"一对多广播"
    - 结果不是"二手记忆"，而是"集体共识记忆"
```

---

## 3. 三种架构的对比矩阵

| 维度 | 自由/去中心化 | 集权/中心化 | 共产主义/集体 |
|------|-------------|-----------|-------------|
| **认知拓扑** | 网状(Mesh) | 星状+网状(Star+Mesh) | 全连接(Fully Connected) |
| **记忆所有权** | 个人私有 | 个人私有+中心特权 | 集体公共 |
| **信任基础** | 私人关系积累 | 私人关系+权力层级 | 集体认同+思想纯洁 |
| **默认凭证** | 0.0（不信任） | 0.0（不信任）+中心=1.0 | 0.4（默认信任） |
| **PRIVATE记忆** | 正常权利 | 存在但有风险 | 异常行为 |
| **SEALED记忆** | 创伤封印 | 审讯目标 | 需要"治愈" |
| **DISCLOSE** | 权利行使 | 高风险行为 | → CONFESSION |
| **COMPEL** | 个别暴力事件 | 制度化审讯 | → 集体关怀 |
| **INFER** | 信任直觉 | 信任直觉+监控直觉 | 集体直觉+隐瞒检测 |
| **OBSERVE** | 物理可见 | 监控可见 | 集体可见 |
| **信息衰减** | 链路衰减 | 链路衰减+中心直达 | 衰减更慢（共享池） |
| **自我审查** | 无/弱 | 强（恐惧驱动） | 中（认同驱动） |
| **信任的敌人** | 背叛 | 监控+恐惧 | 私有化倾向 |

---

## 4. 通用框架的扩展：EnvironmentContext

为了在 `cognition-kit` 中支持不同政治架构，我们需要在文档13的6层模型中引入 **环境层 (Environment Layer)**——它横跨 Layer 2-4，影响凭证计算、访问控制和交互协议：

### 4.1 环境模型

```python
class PoliticalArchitecture(str, Enum):
    """政治架构类型。"""
    LIBERAL = "liberal"           # 自由/去中心化
    AUTHORITARIAN = "authoritarian"  # 集权/中心化
    COMMUNAL = "communal"         # 共产主义/集体

class EnvironmentContext(BaseModel):
    """环境上下文——影响所有记忆交互的"重力场"。"""
    
    # 政治架构
    architecture: PoliticalArchitecture = PoliticalArchitecture.LIBERAL
    
    # 监控强度 (0~1)
    surveillance_intensity: float = 0.0
    
    # 中央权威节点
    authority_ids: list[str] = []
    
    # 敏感词表
    sensitive_topics: list[str] = []
    
    # 强制上报类别
    mandated_reportable: list[str] = []
    
    # 默认凭证（新关系的初始信任）
    default_credential: float = 0.0
    
    # 线人网络（已知线人的ID列表及其渗透度）
    known_informers: dict[str, float] = {}  # {agent_id: reliability_score}
    
    # 集体记忆池（仅集体架构）
    collective_pool: CollectiveMemoryPool | None = None
    
    # 场景监控状态
    is_monitored_space: bool = False
    
    # 审讯概率（Agent被审问的概率）
    base_interrogation_risk: float = 0.0
    
    # 自我审查阈值（超过此敏感度的记忆会被自动封印）
    self_censorship_threshold: float = 1.0  # 默认不审查
```

### 4.2 环境感知的凭证提供者

```python
class EnvironmentAwareCredential(CredentialProvider):
    """环境感知的凭证提供者。"""
    
    def __init__(
        self, 
        base_provider: CredentialProvider,
        environment: EnvironmentContext,
    ):
        self.base = base_provider
        self.env = environment
    
    async def get_credential(self, observer_id: str, target_id: str) -> float:
        base = await self.base.get_credential(observer_id, target_id)
        
        if self.env.architecture == PoliticalArchitecture.LIBERAL:
            return base
        
        if self.env.architecture == PoliticalArchitecture.AUTHORITARIAN:
            # 中央权威有超级凭证
            if observer_id in self.env.authority_ids:
                return 1.0
            
            # 普通Agent的信任被监控恐惧压制
            is_informer = observer_id in self.env.known_informers
            return effective_trust(
                base_trust=base,
                surveillance_intensity=self.env.surveillance_intensity,
                target_is_informer=is_informer,
                target_interrogation_risk=self.env.base_interrogation_risk,
            )
        
        if self.env.architecture == PoliticalArchitecture.COMMUNAL:
            # 集体架构：默认信任更高，但有隐瞒惩罚
            if base > 0:
                return base  # 正常信任
            else:
                return self.env.default_credential  # 给默认信任
        
        return base
```

### 4.3 环境感知的交互协议

```python
class EnvironmentAwareDisclose(DiscloseProtocol):
    """环境感知的披露协议。"""
    
    async def execute(self, from_agent, to_agent, memory, context):
        env = context.get("environment", EnvironmentContext())
        
        if env.architecture == PoliticalArchitecture.AUTHORITARIAN:
            decision = await check_disclose_in_authoritarian(
                from_agent, to_agent, memory, env,
            )
            if not decision.allowed:
                return ExchangeResult(success=False, reason=decision.reason)
            if decision.risk_level == "critical":
                # 允许但添加警告——LLM可能选择沉默
                context["disclosure_warning"] = decision.warning
        
        if env.architecture == PoliticalArchitecture.COMMUNAL:
            # 披露目标从"个人"变为"集体"
            if to_agent == "__collective__":
                return await self._confess_to_collective(
                    from_agent, memory, env,
                )
        
        return await super().execute(from_agent, to_agent, memory, context)
```

### 4.4 新增协议：MANDATE（强制上报）和 CONFESSION（坦白）

```python
class MandateProtocol(MemoryExchangeProtocol):
    """MANDATE: 强制上报协议（集权架构）。"""
    protocol_name = "mandate"
    
    async def execute(self, from_agent, to_agent, memory, context):
        env = context.get("environment", EnvironmentContext())
        
        if env.architecture != PoliticalArchitecture.AUTHORITARIAN:
            return ExchangeResult(success=False, reason="not_applicable")
        
        # 检查是否属于强制上报类别
        memory_category = classify_memory_category(memory["content"])
        if memory_category not in env.mandated_reportable:
            return ExchangeResult(success=False, reason="not_mandated")
        
        # Agent的选择：上报 or 隐瞒
        sensitivity = compute_sensitivity(memory["content"], env.sensitive_topics)
        conceal_risk = env.surveillance_intensity * sensitivity
        
        agent_courage = await get_agent_courage(from_agent)
        will_conceal = (conceal_risk < 0.3) and (agent_courage > 0.7)
        
        if will_conceal:
            # Agent选择隐瞒——但风险被记录
            return ExchangeResult(
                success=False, 
                reason="agent_concealed",
                side_effects={
                    "concealment_registered": True,
                    "concealment_risk": conceal_risk,
                    "future_discovery_probability": conceal_risk * 0.3,
                },
            )
        
        # Agent选择上报——记忆流入中心
        for authority_id in env.authority_ids:
            await self.memory_store.store(
                agent_id=authority_id,
                memory={
                    **memory,
                    "source": f"mandated_from:{from_agent}",
                    "confidence": 0.9,  # 上报信息通常被采信
                },
            )
        
        return ExchangeResult(
            success=True,
            content=memory,
            confidence=0.9,
            side_effects={"mandate_complied": True},
        )


class ConfessionProtocol(MemoryExchangeProtocol):
    """CONFESSION: 坦白协议（集体架构）。"""
    protocol_name = "confession"
    
    async def execute(self, from_agent, to_agent, memory, context):
        env = context.get("environment", EnvironmentContext())
        
        if env.architecture != PoliticalArchitecture.COMMUNAL:
            return ExchangeResult(success=False, reason="not_applicable")
        
        # 坦白：将CONCEALED记忆写入集体记忆池
        if env.collective_pool:
            memory_id = await env.collective_pool.contribute(
                agent_id=from_agent,
                memory=memory,
            )
            
            # 集体反应
            reaction = await self._generate_collective_reaction(
                from_agent, memory, env,
            )
            
            # 更新信任——坦白通常获得集体接纳
            await self.credential.update_credential(
                "__collective__", from_agent, 
                delta=reaction.trust_delta,
                reason="confession_accepted",
            )
            
            return ExchangeResult(
                success=True,
                content=memory,
                confidence=reaction.consensus_score,
                side_effects={
                    "collective_reaction": reaction.reaction_type,
                    "trust_delta": reaction.trust_delta,
                },
            )
        
        return ExchangeResult(success=False, reason="no_collective_pool")
```

---

## 5. 三种架构的记忆流动模式图

### 5.1 自由架构：链式衰减

```
A 的 PRIVATE 记忆: "我是反抗军成员"
  │
  ├─ DISCLOSE(B, min_trust=0.7) ──→ B 获得: confidence=0.64
  │                                   │
  │                                   └─ B 转告 C ──→ C 获得: confidence=0.23
  │
  └─ A 不告诉任何人 ──→ 只有 A 知道
```

### 5.2 集权架构：中心汇聚 + 级联提取

```
A 的 PRIVATE 记忆: "我是反抗军成员"
  │
  ├─ MANDATE ──→ 中心自动获得（如果A选择上报）
  │               confidence=0.9
  │
  ├─ A 隐瞒 ──→ 审问B ──→ B泄露关于A的线索
  │              │           confidence=0.6
  │              └─ 中心用线索审问A ──→ COMPEL触发
  │                   A被迫泄露: confidence=0.6
  │
  └─ 监控 ──→ 中心从A的行为模式中推断
               INFER(中心→A): "A行为异常，可能是反抗军"
               confidence=0.4
```

### 5.3 集体架构：广播 + 共识

```
A 的 CONCEALED 记忆: "我其实不喜欢集体生活"
  │
  ├─ CONFESSION ──→ 集体记忆池
  │                  所有人可读: confidence=集体共识分数
  │                  反应: "接纳"/"批评"/"治疗建议"
  │
  ├─ 拒绝坦白 ──→ 隐瞒检测触发
  │                集体发起"关怀行动"
  │                → INFER（从A的行为推断隐瞒）
  │                → 半自愿CONFESSION
  │
  └─ 私下告诉B ──→ B面临道德困境
                    告诉集体? → 背叛A的私人信任
                    不告诉? → 对集体隐瞒 → 自己也有秘密了
```

---

## 6. 场景示例：同一故事在不同架构下的记忆流动

### 故事：A发现了领导的一个秘密

**设定**：A发现领导(leader)在私吞集体物资。

#### 6.1 自由架构

```
1. A 形成记忆: "leader私吞物资" (PRIVATE, trust_threshold=0.8)
2. A 的行为: 在公开场合对leader态度微妙变化 (PROTECTED)
3. B(朋友, trust=0.7) INFER: "A最近对leader有意见"
4. A DISCLOSE给B: "leader在私吞物资" → B获得(confidence=0.56)
5. B 告诉C(B的朋友): C获得(confidence=0.20)
6. C 不太相信 → 记忆沉入冷区
7. leader 完全不知道A知道了 → 没有后果
```

#### 6.2 集权架构

```
1. A 形成记忆: "leader私吞物资" (PRIVATE, trust_threshold=0.8)
   → 自我审查: 敏感度=0.9, surveillance=0.6 → 考虑提升为SEALED
   
2. A 的行为: 极力掩饰态度变化 (因为怕监控)
   → 即使PROTECTED行为也尽量隐藏

3. MANDATE检查: "领导腐败"属于强制上报类别
   → A 计算: conceal_risk = 0.6 × 0.9 = 0.54
   → A 决定: 犹豫。conceal_risk > 0.3 但 < 0.7

4. A 告诉B:
   → B→A effective_trust = 0.7 × (1 - 0.18) = 0.574
   → 低于0.8门槛 → A犹豫："我信任你，但万一你被审问..."
   → A 选择沉默

5. 线人D注意到A的异常行为 → MANDATE上报给中心
   → 中心审问A → COMPEL触发 → A被迫泄露

6. 级联效应: A泄露后，中心审问B "你知道A知道什么吗"
   → B说实话 → 中心确认情报
   → leader 知道了A知道了 → A被惩罚
```

#### 6.3 集体架构

```
1. A 形成记忆: "leader私吞物资" (CONCEALED, 因为属于敏感)
   → 隐瞒检测: A的concealment_ratio上升

2. 集体关怀行动:
   → 集体成员注意A"最近心神不宁"
   → INFER: "A似乎有事瞒着大家"
   → 集体发起谈话: "A，你有什么想分享的吗？"

3. A 的困境:
   → 说出来: 可能被leader报复（leader也是集体成员）
   → 不说: 集体对A的信任下降 → A被孤立

4. A 选择 CONFESSION:
   → 记忆进入集体记忆池
   → 集体讨论: "leader是否真的私吞物资？"
   → 投票: 6人相信A, 3人持疑, leader否认
   → 共识分数: 0.67

5. 后续:
   → 如果共识 > 阈值 → 集体决策处理leader
   → 如果共识 < 阈值 → A和leader的矛盾持续
   → leader对A: trust -0.5（公开指控的报复）
   → A对集体: trust +0.1（被接纳的感激）或 -0.2（被质疑的失望）
```

---

## 7. 对 cognition-kit 架构的影响

### 7.1 文档13的6层模型需要扩展

```
原6层模型：
  Layer 6: Application Domain
  Layer 5: Interaction Protocols
  Layer 4: Access Control Engine
  Layer 3: Memory Architecture
  Layer 2: Credential & Identity
  Layer 1: Storage Backend

扩展为7层模型：
  Layer 7: Application Domain          ← 不变
  Layer 6: Interaction Protocols       ← 扩展: +MANDATE, +CONFESSION
  Layer 5: Access Control Engine       ← 扩展: +EnvironmentContext
  Layer 4: Environment & Topology      ← 新增: 政治架构/认知拓扑
  Layer 3: Memory Architecture         ← 不变
  Layer 2: Credential & Identity       ← 扩展: +EnvironmentAwareCredential
  Layer 1: Storage Backend             ← 不变: +CollectiveMemoryPool
```

新增的 Layer 4 (Environment & Topology) 负责：

| 能力 | 说明 |
|------|------|
| 政治架构定义 | LIBERAL / AUTHORITARIAN / COMMUNAL |
| 监控强度计算 | surveillance_intensity 的来源和动态更新 |
| 权威节点管理 | authority_ids 的注册和权限 |
| 敏感词表维护 | 动态更新的 sensitive_topics |
| 认知拓扑模拟 | 不同架构下的信息流动路径模拟 |
| 线人网络 | known_informers 的管理和渗透度 |

### 7.2 包结构更新

```
cognition_kit/
├── core/
│   ├── identity.py
│   ├── visibility.py
│   ├── access_control.py
│   ├── memory_fragment.py
│   └── environment.py          ← 新增: EnvironmentContext, PoliticalArchitecture
│
├── protocols/
│   ├── base.py
│   ├── observe.py
│   ├── infer.py
│   ├── disclose.py
│   ├── compel.py
│   ├── mandate.py              ← 新增: 强制上报协议
│   └── confession.py           ← 新增: 坦白协议
│
├── environments/                ← 新增目录
│   ├── base.py                 # EnvironmentProvider 基类
│   ├── liberal.py              # 自由架构的默认环境
│   ├── authoritarian.py        # 集权架构的环境
│   ├── communal.py             # 集体架构的环境
│   └── topology.py             # 认知拓扑模拟器
│
├── memory/
│   ├── ...
│   └── collective.py           ← 新增: CollectiveMemoryPool
│
├── credentials/
│   ├── trust_based.py
│   ├── rbac.py
│   ├── faction.py
│   ├── interaction.py
│   └── environment_aware.py    ← 新增: EnvironmentAwareCredential
│
├── backends/
│   ├── ...
│   └── collective.py           ← 新增: CollectiveMemoryBackend
│
└── presets/
    ├── novel.py
    ├── enterprise.py
    ├── game_npc.py
    ├── social.py
    ├── authoritarian_state.py  ← 新增: 集权国家预设
    └── communal_society.py     ← 新增: 集体社会预设
```

---

## 8. 深层洞察：政治架构即认知架构

本文档的讨论揭示了一个深层规律：

```
政治架构 ≈ 认知架构 ≈ 记忆架构

原因：
  政治架构决定了信息如何在群体中流动
  信息流动模式决定了认知如何形成
  认知形成过程决定了记忆如何存储和访问

因此：
  自由政治 → 网状认知 → 分布式记忆
  集权政治 → 星状认知 → 中心化记忆
  集体政治 → 全连接认知 → 共享记忆
```

**这不仅仅是一个"配置项"的区别**——不同的政治架构要求不同的：

1. **交互协议集**：集权需要MANDATE，集体需要CONFESSION
2. **凭证计算方式**：信任度在不同架构下含义不同
3. **记忆可见性语义**：PRIVATE在自由架构中是权利，在集体架构中是异常
4. **信息衰减模式**：链式衰减 vs 中心直达 vs 共识衰减
5. **自我审查机制**：恐惧驱动 vs 认同驱动 vs 无

**设计启示**：`cognition-kit` 不应该只提供"参数调优"来适应不同架构，而应该提供**架构级的预设**（Architecture Preset），每种预设是一个完整的协议集+凭证模型+访问控制策略的组合。

---

## 9. 开放问题

### 9.1 混合架构

现实中很少有"纯粹"的架构。一个国家可能是：
- 经济上自由 + 政治上集权（新加坡模式）
- 政治上自由 + 文化上集体（日本模式）
- 不同地区不同架构（一国两制）

**问题**：如何在同一个模拟中支持混合架构？同一个Agent在不同场景下切换不同的记忆交互规则？

### 9.2 架构演化

政治架构不是静态的——革命、改革、政变会改变架构。当架构变化时，Agent的记忆系统如何适应？

```
场景：自由 → 集权（政变后）
  - 之前的PUBLIC记忆现在可能变成PROTECTED/SEALED
  - 之前DISCLOSE出去的秘密突然变得危险
  - 集体记忆池需要被"清洗"或"封存"
  - Agent需要快速学习新的自我审查规则
```

### 9.3 跨架构交互

当来自不同架构的Agent相遇时（如自由国家的Agent进入集权国家），记忆交互如何处理？

```
Agent A（自由架构，trust=0.8时愿意分享一切）
Agent B（集权架构，即使trust=0.8也小心翼翼）

A 对 B 的 DISCLOSE:
  A 的意图: "我们这么熟了，告诉你一个秘密"
  B 的反应: "你为什么告诉我这个？这是在试探我吗？"
  
同一个trust值，完全不同的行为语义。
```

### 9.4 数字极权的新形态

当代数字极权（如社会信用体系）创造了新的记忆交互模式——**持续评估**：

```
每个Agent有一个"信用分数"，动态更新：
  - DISCLOSE给不恰当的人 → 信用-5
  - 被发现CONCEALED记忆 → 信用-10
  - 主动MANDATE上报 → 信用+3
  - 信用低于阈值 → 行动受限 → 更难建立信任 → 恶性循环

这不是传统的"中心监控"，而是"无处不在的量化评估"。
```

---

## 10. 总结

| 架构 | 记忆机制的核心差异 | 需要新增的组件 |
|------|------------------|--------------|
| **自由/去中心化** | 文档12的设计完全适用 | 无（基线） |
| **集权/中心化** | 信任被恐惧污染，信息向中心汇聚，自我审查 | `MANDATE协议`、`InterrogationCascade`、`EnvironmentAwareCredential`、`surveillance_intensity` |
| **共产主义/集体** | 记忆公共化，隐瞒是异常，DISCLOSE→CONFESSION | `CONFESSION协议`、`CollectiveMemoryPool`、`ConcealmentDetector`、`集体关怀机制` |

**核心结论**：

> 政治架构不是记忆机制的"配置参数"，而是记忆机制的"架构决定因素"。不同的政治架构需要不同的**交互协议集**、**凭证模型**和**访问控制策略**，而不仅仅是不同的参数值。`cognition-kit` 应该通过 **Architecture Preset** 来封装这些差异，而非试图用同一套机制通过参数调优来适应所有场景。
