# WorldEngine UI 全局重构 — 设计规格 v2

## 目标

将 WorldEngine 从「能跑的 demo」升级为「用起来舒服的产品」。核心解决五个问题：
1. **生成过程黑洞** — 点击生成后 2-3 小时里，用户在大部分时间看不到有效反馈
2. **状态语言混乱** — 同一件事在不同页面用不同词描述
3. **成书/章节页职责不清** — 两个页面功能重叠又都不完整
4. **关系图谱/时间线的可视化太弱** — 图谱被困在小盒子里，时间线只是文字列表
5. **史官对话是孤岛** — 藏在第 8 个 tab 里，几乎不可能被自然使用

设计方向：从「史官的仪器」风格转向 **专业 SaaS 产品**（参考 Notion/Linear/GitHub Dark），中性暗色+干净排版+SVG 图标。

---

## 一、设计系统重建

### 1.1 色彩

```
背景层级:
  --bg-void:      #0d1117    (GitHub Dark 底色)
  --bg-surface:   #161b22    (面板/卡片)
  --bg-elevated:  #1c2128    (悬浮/弹出)
  --bg-glass:     rgba(22, 27, 34, 0.85)
  --bg-scrim:     rgba(13, 17, 23, 0.94)

文字:
  --text-primary:   #e6edf3    (高对比白)
  --text-secondary: #8b949e    (中灰)
  --text-muted:     #484f58    (低对比辅助)
  --text-inverse:   #0d1117

强调色（保留琥珀为主色，增加蓝色信息色）:
  --accent-ember:     #d4793a    (主操作色，保留)
  --accent-ember-dim: rgba(212, 121, 58, 0.12)
  --accent-blue:      #58a6ff    (信息/链接)
  --accent-jade:      #3fb950    (成功/完成)
  --accent-cinnabar:  #f85149    (错误/危险)
  --accent-aurora:    #bc8cff    (伏笔/记忆)
  --accent-phosphor:  #7ee787    (活跃状态)

结构线:
  --border-default: #30363d    (标准边框)
  --border-muted:   #21262d    (次级分隔)
  --border-active:  rgba(212, 121, 58, 0.45)
```

旧 token 别名映射（38 个组件自动适配，无需手改）:
```css
--border-ghost:      var(--border-muted);
--border-rule:       var(--border-default);
--accent-ember-glow: none;
--glow-ember:        none;
--glow-jade:         none;
--accent-silver:     #8b949e;
--font-display:      var(--font-ui);
```

### 1.2 字体

从 4 套简化到 2+1 套:

| 用途 | 旧 | 新 |
|------|-----|-----|
| UI/标题 | Cormorant Garamond + Instrument Sans | **Inter** |
| 阅读正文 | Source Serif 4 | **Noto Serif SC** (回退 Source Serif 4) |
| 数据 | JetBrains Mono | 保留不变 |

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Serif+SC:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

### 1.3 阴影

```css
--shadow-sm:   0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);
--shadow-md:   0 4px 12px rgba(0,0,0,0.15);
--shadow-deep: 0 8px 24px rgba(0,0,0,0.2);
```

### 1.4 动效

```css
--duration-fast:  150ms;
--duration-base:  200ms;
--duration-slow:  300ms;
--ease-default:   cubic-bezier(0.4, 0, 0.2, 1);
```

间距(`--sp-*`)、字体比例尺(`--fs-*`)、圆角(`--radius-*`) 保留现有值不变。

---

## 二、生成过程交互设计

### 问题诊断

生成小说 ≈ 2-3 小时。当前反馈机制：

| 阶段 | 时长 | 当前反馈 | 问题 |
|------|------|---------|------|
| 导演规划 | 30-60s | 仅一条 `phase_change` 消息 | 60秒空白，用户以为卡了 |
| 世界构建 | 20-40s | 同上 | 同上 |
| 伏笔规划 | 15-30s | 同上 | 同上 |
| 章节循环(×N) | 3-5min/章 | 场景模拟→场景写作→章节完成，较丰富 | 还行但只在概览页可见 |

**核心缺陷**：事件日志只存在于概览页。切到任何其他页面就完全看不到生成状态。

### 解决方案：侧边栏迷你事件流

在 `DashboardLayout` 的侧边栏底部（进度条下方），增加一个迷你事件流面板，显示最近 5 条事件：

```
┌──────────────────────┐
│ ← 首页               │
│ WorldEngine           │
│ ● 生成中 · 7/10章     │
├──────────────────────┤
│  概览                 │
│  ...                  │
│  控制台               │
├──────────────────────┤
│ ▓▓▓▓▓▓▓░░░ 70%       │
│                      │
│ 12:03 第7章完成 3.2k字 │  ← 迷你事件流
│ 12:01 场景模拟完成     │
│ 11:58 命运裁决        │
│                      │
│ [暂停]               │
│ 12.3K tokens          │
└──────────────────────┘
```

**实现方式**：
- 从 `eventLogStore.entries` 取最后 5 条
- 紧凑单行格式：`HH:MM 事件摘要`
- 去掉 emoji，用 `--text-muted` 颜色
- 新事件进来时有 0.2s 淡入
- 点击事件行可跳转到概览页查看完整日志

**文件改动**: `DashboardLayout.vue` (模板 + 样式)

### 补充：前置阶段反馈增强

在 `eventLog.pushFromWS()` 中，对导演/世界观/伏笔三个阶段增加子阶段提示（即使后端没发中间事件，前端在 phase_change 时生成提示文字）：

```typescript
if (event.phase === 'directing') {
  addEntry('阶段切换: 导演规划 — 分析命题、设计冲突弧线', 'phase')
} else if (event.phase === 'world_building') {
  addEntry('阶段切换: 构建世界 — 生成地理、势力、魔法体系', 'phase')
} else if (event.phase === 'foreshadow_planning') {
  addEntry('阶段切换: 伏笔网络 — 规划植入点和回收时机', 'phase')
}
```

去掉 emoji 前缀，改用纯文字描述。

---

## 三、侧边栏重构 (DashboardLayout)

### 导航项

去掉所有 emoji。只保留文字 label：

```typescript
const tabs = [
  { name: 'overview',    label: '概览' },
  { name: 'world-view',  label: '世界观' },
  { name: 'characters',  label: '角色' },
  { name: 'timeline',    label: '大纲与时间线' },
  { name: 'foreshadows', label: '伏笔' },
  { name: 'chapters',    label: '章节' },
  { name: 'novel',       label: '成书' },
  { name: 'historian',   label: '史官' },
  { name: 'tokens',      label: 'Token 统计' },
  { name: 'control',     label: '控制台' },
]
```

### 史官快捷入口

在导航列表和底部控制区之间，增加一个独立的史官入口按钮：

```
├──────────────────────┤
│  控制台               │
├──────────────────────┤
│  💬 与史官对话         │  ← 独立按钮，视觉上和 nav 不同
├──────────────────────┤
│ ▓▓▓▓▓▓▓░░░ 70%       │
```

点击行为：跳转到 historian tab（和点导航一样），但视觉上更突出（用 `--bg-elevated` 背景 + `--border-default` 边框，和普通导航项区分）。

### 状态表达规范

| 状态 | 指示器颜色 | 文字 |
|------|-----------|------|
| 待命 | `--text-muted` | `● 待命` |
| 生成中 | `--accent-ember` + 脉搏 | `● 生成中 · X/Y章` |
| 已暂停 | `--accent-blue` | `● 已暂停 · X/Y章` |
| 已完成 | `--accent-jade` | `● 已完成 · X/Y章` |
| 出错 | `--accent-cinnabar` | `● 出错` |

### 按钮文字

```
首次启动: "开始生成"
继续生成: "继续生成第X章"
暂停:     "暂停"
```

---

## 四、成书页 NovelPage — Notion 风格

### 布局

```
┌──────────┬─────────────────────────────┐
│ 目录      │ 第1章 破碎的天穹              │
│ (200px)  │                              │
│ 第1章  ◄ │   [衬线正文...]               │
│ 第2章    │                              │
│ 第3章    │                              │
│ ...      │                              │
│          │         3,200 字              │
│          │                              │
│──────────│ [上一章]        [下一章]       │
│ 导出 ▾   │                              │
└──────────┴─────────────────────────────┘
```

### 左侧目录

- 宽度 200px，`position: sticky`
- 列表项：`第X章 标题`，字数右对齐 `--text-muted`
- active：左边框 `--accent-ember` + 背景 `--accent-ember-dim`
- 底部：导出下拉菜单（Markdown / JSON / 复制全文）

### 右侧阅读区

- `NovelReader` 组件渲染单章
- 底部上一章/下一章按钮

### 空状态

- 生成中：进度条 + `生成中 · X/Y章`
- 未开始：`尚未生成章节，请在概览页启动生成`

### NovelReader 排版

```css
.chapter-body {
  font-family: var(--font-serif);
  font-size: var(--fs-md);
  line-height: 1.8;
  color: var(--text-primary);
}
.chapter-paragraph {
  text-indent: 2em;
  margin: 0 0 1em 0;
}
```

章节尾部：右对齐 `3,200 字`，去掉 `── ──` 装饰线。

---

## 五、关系图谱增强 (CharactersPage / RelationshipGraph)

### 问题

- vis-network 容器固定 `height: 500px`，10 个角色就挤满
- 章节滑块太小不显眼
- 图谱和当前阅读上下文脱节

### 改动

#### 5.1 容器自适应

```css
.relationship-graph {
  /* 旧: height: 500px */
  min-height: 400px;
  height: calc(100vh - 280px);  /* 减去头部+控件+底部边距 */
  max-height: 800px;
}
```

#### 5.2 章节滑块增强

当前滑块是一个小 el-slider。改为更显眼的控件：
- 滑块上方加文字标签 `第X章关系快照`
- 滑块两端标注 `第1章` / `第N章`
- 增加播放按钮：点击后自动从第1章递增到最新章，每章停留 1.5 秒（关系演进动画）
- 播放中显示暂停按钮

```
┌──────────────────────────────────┐
│  第5章关系快照           [▶ 演进] │
│  第1章 ━━━━●━━━━━━━━━ 第10章      │
└──────────────────────────────────┘
```

**实现**: `RelationshipGraph.vue` 中增加 `playTimelapse()` 方法，用 `setInterval` 递增 `sliderChapter`。

#### 5.3 点击节点交互

当前点击节点无响应。增加：
- 点击节点 → 打开 CharacterProfile 的 el-drawer（已有这个组件）
- 聚焦该角色的所有连线（其他连线降低透明度）

**实现**: 在 vis-network 的 `click` 事件中调用已有的 drawer 打开逻辑。

**文件改动**:
- `web/src/components/characters/RelationshipGraph.vue` — 容器高度、滑块增强、播放、点击交互
- `web/src/components/characters/CharactersPage.vue` — 可能需要调整布局比例

---

## 六、时间线可视化 (TimelinePage)

### 问题

当前 `TimelinePage` 分两部分：
1. 故事大纲（手风琴展开章节→场景）— 纯文字层级
2. "时间线"（EraCard 用 CSS 竖线模拟）— 不可交互

### 改动：水平时间轴

在页面顶部增加一个**水平时间轴组件** `HorizontalTimeline.vue`：

```
  第1章  第2章  第3章  第4章  第5章  第6章  第7章
  ──●─────●─────●─────●─────●─────●─────●──
    │     │           │                 │
    ▼     ▼           ▼                 ▼
  世界    角色      命运裁决          伏笔回收
  创建    登场      事件X             事件Y
```

#### 6.1 时间轴结构

- 水平滚动容器（`overflow-x: auto`）
- 章节为主刻度（等间距分布）
- 事件节点挂在对应章节下方
- 节点颜色按类型区分：
  - 普通事件 → `--accent-jade`
  - 命运裁决 → `--accent-ember`（更大的点）
  - 伏笔植入 → `--accent-aurora`（虚线连接到回收点）

#### 6.2 交互

- hover 节点 → tooltip 显示事件详情
- 点击节点 → 滚动到下方对应的 EraCard 详情
- 当前章节高亮（基于 `progressStore.completed`）

#### 6.3 现有内容保留

水平时间轴在上方作为导航/概览，下方保留现有的 outline + EraCard 详情内容，但做视觉统一（去 emoji、用新色板）。

**新增文件**: `web/src/components/timeline/HorizontalTimeline.vue`
**修改文件**: `web/src/components/timeline/TimelinePage.vue` — 引入时间轴组件，传入 events + decisions 数据

---

## 七、史官对话入口增强

### 问题

- 在第 8 个 tab，太深
- 建议提示硬编码，不随上下文变化
- localStorage 存储不可靠

### 改动

#### 7.1 侧边栏快捷入口

在 DashboardLayout 的导航列表下方、底部控制区上方，增加一个独立的史官对话按钮（详见第三节）。

#### 7.2 动态建议

根据当前页面上下文动态生成前 2 条建议：

```typescript
const dynamicSuggestions = computed(() => {
  const chapter = progressStore.completed
  const suggestions: string[] = []
  if (chapter > 0) {
    suggestions.push(`分析第${chapter}章中角色的关系变化`)
    suggestions.push(`第${chapter}章有哪些伏笔被埋下了？`)
  }
  return [
    ...suggestions,
    '帮我梳理当前所有角色的关系变化',
    '分析目前的伏笔哪些还没回收',
    '建议下一章的剧情走向',
  ]
})
```

**文件改动**: `web/src/components/historian/HistorianChat.vue` — 动态建议

---

## 八、概览页 OverviewPage 重构

### 生成控制面板

- 去掉 `accent-ember-dim` 背景色，改为 `--bg-surface` + `--border-default`
- 按钮文字统一（见第三节）
- 状态文字统一（`生成中` 替代 `创世进行中`）

### 事件日志

- 去掉 emoji 图标，改为左侧 4px 色条区分事件类型
- 色条颜色：phase=`--accent-blue`, chapter=`--accent-ember`, done=`--accent-jade`, error=`--accent-cinnabar`

### Dashboard Grid

保留 `grid-card`，统一用 `--bg-surface` + `--border-default` + `--radius-lg`。

---

## 九、全局状态文字规范

### 章节编号

**`第X章`** — 所有地方

### 进度

**`X/Y章`** — 无空格

### 运行状态

**`待命` / `生成中` / `已暂停` / `已完成` / `出错`** — 五个词，全系统统一

### 按钮

**`开始生成` / `继续生成第X章` / `暂停`**

---

## 十、不改的东西

- 路由结构（10 个 tab 保持不变）
- 数据流（progressStore / chapterStore / eventLogStore 结构不变）
- WebSocket 逻辑（已修复的 reconnect / dispatch 不再改）
- API 调用
- HomePage / CreateWizard 结构
- ForeshadowsPage / TokenPage / ControlPage / WorldPage 结构（只受 token 值变化影响）

---

## 文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `DESIGN.md` | 重写 | 新设计方向文档 |
| `web/index.html` | 修改 | 换 Google Fonts |
| `web/src/styles/global.scss` | 重写 | 新色板 + EP 覆盖 |
| `web/src/styles/variables.scss` | 重写 | 新 SCSS 变量 |
| `web/src/layouts/DashboardLayout.vue` | 重写 | 去 emoji + 迷你事件流 + 史官入口 + 状态统一 |
| `web/src/components/overview/OverviewPage.vue` | 修改 | 面板卡片化 + 事件日志色条 + 状态文字 |
| `web/src/components/novel/NovelPage.vue` | 重写 | Notion 风格目录+阅读 |
| `web/src/components/novel/NovelReader.vue` | 修改 | 排版微调 |
| `web/src/components/characters/RelationshipGraph.vue` | 修改 | 容器自适应 + 滑块增强 + 播放 + 点击交互 |
| `web/src/components/characters/CharactersPage.vue` | 微调 | 布局比例调整 |
| `web/src/components/timeline/HorizontalTimeline.vue` | **新增** | 水平时间轴组件 |
| `web/src/components/timeline/TimelinePage.vue` | 修改 | 引入时间轴 + 视觉统一 |
| `web/src/components/historian/HistorianChat.vue` | 修改 | 动态建议 |
| `web/src/stores/eventLog.ts` | 修改 | 去 emoji + 增强阶段描述 |
| `web/src/components/chapters/ChaptersPage.vue` | 微调 | 状态文字统一 |

---

## 验证标准

1. `npm run build` 无错误
2. 所有页面使用统一的 `第X章` / `X/Y章` / 五种状态词
3. 侧边栏无 emoji，有迷你事件流，有史官快捷入口
4. 成书页为 Notion 风格左目录+右阅读
5. 关系图谱容器自适应，有播放演进功能，点击节点打开详情
6. 时间线页顶部有水平时间轴，可交互
7. 史官建议随章节进度动态变化
8. 暗色主题为中性灰（非紫色）
9. 切换到任何页面都能在侧边栏看到生成进度和最近事件
