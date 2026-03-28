# WorldEngine UI 全局重构 — 设计规格

## 目标

将 WorldEngine 的 UI 从「史官的仪器」风格（深紫+琥珀+衬线+emoji）转变为专业 SaaS 产品风格（中性暗色+干净排版+SVG图标+卡片布局），同时修复四个核心页面的结构问题和全局状态文字不统一。

## 改动范围

### 第一层：设计系统重建
- `DESIGN.md` — 重写设计方向文档
- `web/index.html` — 更换 Google Fonts 加载
- `web/src/styles/global.scss` — 新 CSS 变量 + Element Plus 覆盖
- `web/src/styles/variables.scss` — 新 SCSS 变量

### 第二层：四页联动重构
- `DashboardLayout.vue` — 侧边栏去 emoji 化，用文字图标或 SVG
- `OverviewPage.vue` — 生成面板卡片化，状态文字统一
- `ChaptersPage.vue` — 列表去 emoji，标题格式统一
- `NovelPage.vue` — Notion 风格左目录+右阅读
- `NovelReader.vue` — 阅读排版微调

### 第三层：全局统一
- 所有 38 个引用设计 token 的组件文件（自动迁移，token 名不变只换值）

---

## 1. 新设计系统

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
  --border-default: #30363d    (标准边框，实色)
  --border-muted:   #21262d    (次级分隔)
  --border-active:  rgba(212, 121, 58, 0.45)
```

注意: `--border-ghost` 和 `--border-rule` 两个旧 token 名保留做别名映射到新值，避免 38 个文件每行都改。

```css
--border-ghost: var(--border-muted);
--border-rule:  var(--border-default);
```

### 1.2 字体

从 4 套字体简化为 2+1 套:

```
UI:      Inter, -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif
阅读正文: 'Noto Serif SC', 'Source Serif 4', 'STSong', serif
数据:    'JetBrains Mono', 'Menlo', monospace  (保留)
```

去掉 Cormorant Garamond（装饰性展示字体）和 Instrument Sans。

CSS token 映射:
```
--font-display:  var(--font-ui)         (不再单独字体，统一为 UI 字体)
--font-serif:    'Noto Serif SC', 'Source Serif 4', serif
--font-ui:       'Inter', -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif
--font-data:     'JetBrains Mono', 'Menlo', monospace
```

`--font-display` 保留 token 名但指向 `--font-ui`，这样所有使用 `var(--font-display)` 的组件自动切换，无需逐个修改。

Google Fonts 加载改为:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Serif+SC:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

### 1.3 字体比例尺

保留现有 `--fs-xs` 到 `--fs-hero` 的 token 名和值，不改。

### 1.4 间距

保留现有 `--sp-2xs` 到 `--sp-3xl`，不改。

### 1.5 圆角

```
--radius-sm:  4px
--radius-md:  6px
--radius-lg:  8px
```
保留不变（已经是 SaaS 标准值）。

### 1.6 阴影

```
--shadow-sm:   0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08)
--shadow-md:   0 4px 12px rgba(0,0,0,0.15)
--shadow-deep: 0 8px 24px rgba(0,0,0,0.2)
```

去掉 `--glow-ember` 和 `--glow-jade`（装饰性光效）。保留 token 名但值设为 `none`。

### 1.7 动效

从「瞬间+缓慢」改为标准 SaaS:
```
--duration-fast:  150ms
--duration-base:  200ms
--duration-slow:  300ms
--ease-default:   cubic-bezier(0.4, 0, 0.2, 1)
```

### 1.8 侧边栏图标

将 emoji 图标替换为 Unicode 文字符号或简单的 CSS 图标。不引入 Lucide 图标库依赖（避免增加包体积），而是用简洁的中文单字 + 圆形背景作为 tab 图标。

```
概览 → 概
世界观 → 界
角色 → 角
时间线 → 线
伏笔 → 伏
章节 → 章
成书 → 书
史官 → 史
Token → T
控制台 → 控
```

或者用简单的 SVG inline 图标（8个左右，手写，每个 <20 bytes）。

最终方案：保留简短文字 label，去掉 emoji 前缀。侧边栏足够窄，只显示文字。

---

## 2. DashboardLayout 侧边栏重构

### 2.1 结构变化

```
旧:
┌──────────────────────┐
│ ← 首页               │
│ WorldEngine           │
│ ● 模拟运行中          │
├──────────────────────┤
│ 📖 概览              │
│ 🌍 世界观            │
│ 👥 角色              │
│ ...                  │
├──────────────────────┤
│ 章节进度 7/10章       │
│ ▓▓▓▓▓▓▓░░░           │
│ [▶ 继续第8章]         │
│ 🪙 12.3K tokens      │
└──────────────────────┘

新:
┌──────────────────────┐
│ ← 首页               │
│ WorldEngine           │
│ ● 生成中 · 7/10章     │  ← 合并状态+进度到一行
├──────────────────────┤
│  概览                 │  ← 去掉 emoji
│  世界观               │
│  角色                 │
│  大纲与时间线          │
│  伏笔                 │
│  章节                 │
│  成书                 │
│  史官                 │
│  Token               │
│  控制台               │
├──────────────────────┤
│ ▓▓▓▓▓▓▓░░░ 70%       │
│ [▶ 继续生成第8章]     │
│ 12.3K tokens          │
└──────────────────────┘
```

### 2.2 状态表达规范

**全局四种状态，一套表达：**

| 状态 | 指示器颜色 | 文字 | 侧边栏显示 |
|------|-----------|------|------------|
| 待命 | `--text-muted` (灰) | 待命 | `● 待命` |
| 生成中 | `--accent-ember` (琥珀) + 脉搏动画 | 生成中 | `● 生成中 · X/Y章` |
| 已暂停 | `--accent-blue` (蓝) | 已暂停 | `● 已暂停 · X/Y章` |
| 已完成 | `--accent-jade` (绿) | 已完成 | `● 已完成 · X/Y章` |
| 出错 | `--accent-cinnabar` (红) | 出错 | `● 出错` |

### 2.3 按钮文字规范

```
首次启动: "开始生成"
继续生成: "继续生成第X章"  (X = chapters_completed + 1)
暂停:     "暂停"
```

---

## 3. OverviewPage 重构

### 3.1 生成控制面板

去掉琥珀底色 `accent-ember-dim` 背景。改为标准卡片:
- `background: var(--bg-surface)`
- `border: 1px solid var(--border-default)`
- `border-radius: var(--radius-lg)`

按钮文字用统一的状态规范。

### 3.2 事件日志

保留现有结构，但去掉 emoji 图标前缀。事件类型用左侧色条区分:
```
│ ■ 12:03:45  阶段切换: 导演规划中       │  ← 蓝色条
│ ■ 12:04:12  第3章完成: 破碎的天穹 (3200字) │  ← 琥珀色条
│ ■ 12:05:00  创世完成                    │  ← 绿色条
```

### 3.3 Dashboard Grid

`grid-card` 保留但统一用 `--bg-surface` + `--border-default`。

### 3.4 进度显示

概览页正文中的进度统一为 `X/Y章` 格式（无空格）。

---

## 4. NovelPage — Notion 风格重写

### 4.1 布局

```
┌──────────┬─────────────────────────────┐
│ 目录      │ 第1章 破碎的天穹              │
│ (200px)  │                              │
│ 第1章  ◄ │   [衬线正文...]               │
│ 第2章    │                              │
│ 第3章    │                              │
│ 第4章    │                              │
│ ...      │     ── 3,200 字 ──           │
│          │                              │
│          │ [上一章]        [下一章]       │
│──────────│                              │
│ [导出 ▾] │                              │
└──────────┴─────────────────────────────┘
```

### 4.2 左侧目录

- 宽度 200px，sticky 定位
- 顶部: `目录` 标题 + 章节数
- 列表: 每项 `第X章 标题`，字数右对齐
- active 状态: 左边框高亮 `--accent-ember`，背景 `--accent-ember-dim`
- 底部: 导出按钮（下拉菜单: Markdown / JSON / 复制全文）

### 4.3 右侧阅读区

- 使用 `NovelReader` 组件渲染单章
- 底部上一章/下一章按钮
- 最大宽度不限（跟随内容区自然宽度）

### 4.4 空状态

生成中: 显示进度条 + `生成中 · X/Y章`
未开始: 显示引导文字 `尚未生成章节，请在概览页启动生成`

### 4.5 实时更新

保留现有 `onWSEvent('chapter_completed')` + `onWSEvent('generation_finished')` 监听。

---

## 5. NovelReader 微调

### 5.1 排版

```css
.chapter-body {
  font-family: var(--font-serif);
  font-size: var(--fs-md);     /* 17px */
  line-height: 1.8;            /* 从 2.0 调到 1.8，略紧凑 */
  color: var(--text-primary);
}

.chapter-paragraph {
  text-indent: 2em;
  margin: 0 0 1em 0;           /* 从 1.2em 调到 1em */
}
```

### 5.2 章节尾部

```
旧: ── 3,200 字 ──   (居中装饰线)
新: 3,200 字         (右对齐小字，去掉装饰线)
```

---

## 6. ChaptersPage 微调

### 6.1 ChapterTabs

`已渲染` / `仅行动` 的 el-tag 保留（有用信息）。格式统一为 `第X章`。

### 6.2 章节标题

保持 `第X章 标题名` 统一格式。

---

## 7. 全局 Element Plus 覆盖更新

更新 `global.scss` 中的 Element Plus 暗色覆盖，匹配新色板:

```scss
.el-button--primary {
  background: var(--accent-ember);
  border-color: var(--accent-ember);
}

.el-input__wrapper {
  background: var(--bg-elevated);
  box-shadow: 0 0 0 1px var(--border-default) inset;
}
```

---

## 8. 状态文字全局统一规范

### 8.1 章节编号

**统一格式: `第X章`**

所有显示章节编号的地方使用 `第{n}章`。不用 `一章`、不用纯数字。

### 8.2 进度

**统一格式: `X/Y章`**

无空格，紧凑。用在侧边栏、概览页、成书页空状态等所有进度显示处。

### 8.3 按钮

```
开始: "开始生成"
继续: "继续生成第X章"
暂停: "暂停"
```

### 8.4 运行状态

```
待命 / 生成中 / 已暂停 / 已完成 / 出错
```

五个词，全系统统一。不再使用「创世进行中」「模拟运行中」「运行中」等不同说法。

---

## 9. 不改的东西

- 路由结构 — 10 个 tab 保持不变
- 数据流 — progressStore / chapterStore / eventLogStore 结构不变
- WebSocket 逻辑 — 已修复的 reconnect / dispatch 不再改
- API 调用 — 不改
- CharactersPage / TimelinePage / ForeshadowsPage / HistorianChat / TokenPage / ControlPage — 这些页面只受设计 token 值变化影响（自动迁移），不做结构改动
- HomePage / CreateWizard — 不改结构

---

## 10. 迁移策略

由于 token 名保留不变（`--accent-ember` 等），38 个组件文件大部分不需要手动修改。只需要:

1. 改 `global.scss` 中的 CSS 变量值
2. 改 `variables.scss` 中的 SCSS 变量值
3. 改 `index.html` 中的 Google Fonts URL
4. 手动改 5 个文件: DashboardLayout / OverviewPage / NovelPage / NovelReader / ChaptersPage

旧 token 向新值的别名映射:
```css
--border-ghost:      var(--border-muted);    /* #21262d */
--border-rule:       var(--border-default);  /* #30363d */
--accent-ember-glow: none;
--glow-ember:        none;
--glow-jade:         none;
--accent-silver:     #8b949e;                /* 映射到 text-secondary */
--font-display:      var(--font-ui);         /* 不再单独展示字体 */
```

这样其余 33 个组件无需任何代码修改即可适配新设计系统。

---

## 文件清单

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `DESIGN.md` | 重写 | 新设计方向文档 |
| `web/index.html` | 修改 | 换 Google Fonts |
| `web/src/styles/global.scss` | 重写 | 新 CSS 变量 + EP 覆盖 |
| `web/src/styles/variables.scss` | 重写 | 新 SCSS 变量 |
| `web/src/layouts/DashboardLayout.vue` | 重写 | 侧边栏去 emoji + 状态统一 |
| `web/src/components/overview/OverviewPage.vue` | 修改 | 面板卡片化 + 状态文字统一 |
| `web/src/components/novel/NovelPage.vue` | 重写 | Notion 风格目录+阅读 |
| `web/src/components/novel/NovelReader.vue` | 修改 | 排版微调 |
| `web/src/components/chapters/ChaptersPage.vue` | 微调 | 状态文字统一 |
| `web/src/stores/eventLog.ts` | 修改 | 去掉 emoji 前缀 |

---

## 验证标准

1. `npm run build` 无错误
2. 所有页面使用统一的 `第X章` 格式
3. 所有进度使用 `X/Y章` 格式
4. 所有运行状态使用「待命/生成中/已暂停/已完成/出错」五词
5. 侧边栏无 emoji
6. 成书页为 Notion 风格左目录+右阅读
7. 暗色主题颜色为中性灰（非紫色）
