# WorldEngine UI 全局重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform WorldEngine from a purple-themed demo into a professional SaaS product with neutral dark theme, unified status language, cross-page generation feedback, enhanced graph/timeline visualization, and accessible historian chat.

**Architecture:** Design token values change in 2 SCSS/CSS files; token names stay the same so 38+ components auto-adapt. Five pages get structural rewrites. One new component (HorizontalTimeline). All changes are frontend-only — no API or backend changes.

**Tech Stack:** Vue 3, TypeScript, Element Plus, SCSS, vis-network (existing), Pinia stores (existing)

---

### Task 1: Design System — New Color Palette and Fonts

**Files:**
- Modify: `web/index.html`
- Modify: `web/src/styles/variables.scss`
- Modify: `web/src/styles/global.scss`

This is the foundation. Every other task depends on these token values being correct.

- [ ] **Step 1: Update Google Fonts in index.html**

Replace the existing font link on line 10 of `web/index.html`:

```html
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Serif+SC:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

Also update the title on line 6:

```html
    <title>WorldEngine — 创作工坊</title>
```

- [ ] **Step 2: Rewrite variables.scss**

Replace the entire content of `web/src/styles/variables.scss`:

```scss
// === WorldEngine — Professional Dark Theme ===

// --- Backgrounds (neutral dark, GitHub Dark style) ---
$bg-void:       #0d1117;
$bg-surface:    #161b22;
$bg-elevated:   #1c2128;
$bg-glass:      rgba(22, 27, 34, 0.85);
$bg-scrim:      rgba(13, 17, 23, 0.94);

// --- Text ---
$text-primary:   #e6edf3;
$text-secondary: #8b949e;
$text-muted:     #484f58;
$text-inverse:   #0d1117;

// --- Accents ---
$accent-ember:     #d4793a;
$accent-ember-dim: rgba(212, 121, 58, 0.12);
$accent-blue:      #58a6ff;
$accent-jade:      #3fb950;
$accent-cinnabar:  #f85149;
$accent-aurora:    #bc8cff;
$accent-phosphor:  #7ee787;
$accent-silver:    #8b949e;

// --- Structure ---
$border-default: #30363d;
$border-muted:   #21262d;
$border-active:  rgba(212, 121, 58, 0.45);

// Legacy aliases (used by 38+ components — DO NOT REMOVE)
$border-ghost:  $border-muted;
$border-rule:   $border-default;

// --- Font families ---
$font-ui:       'Inter', -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
$font-serif:    'Noto Serif SC', 'Source Serif 4', 'STSong', serif;
$font-display:  $font-ui;  // No separate display font
$font-data:     'JetBrains Mono', 'Menlo', monospace;

// --- Font scale (unchanged) ---
$fs-xs:   11px;
$fs-sm:   13px;
$fs-base: 15px;
$fs-md:   17px;
$fs-lg:   22px;
$fs-xl:   32px;
$fs-2xl:  48px;
$fs-3xl:  68px;
$fs-hero: 96px;

// --- Spacing scale (8px base, unchanged) ---
$sp-2xs: 2px;
$sp-xs:  4px;
$sp-sm:  8px;
$sp-md:  16px;
$sp-lg:  24px;
$sp-xl:  32px;
$sp-2xl: 48px;
$sp-3xl: 64px;

// --- Border radius (unchanged) ---
$radius-sm:     4px;
$radius-md:     6px;
$radius-lg:     8px;
$radius-badge:  4px;
$radius-avatar: 50%;

// --- Easing & Duration ---
$duration-fast: 150ms;
$duration-base: 200ms;
$duration-slow: 300ms;
$ease-default:  cubic-bezier(0.4, 0, 0.2, 1);

// --- Shadows ---
$shadow-sm:   0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);
$shadow-md:   0 4px 12px rgba(0,0,0,0.15);
$shadow-deep: 0 8px 24px rgba(0,0,0,0.2);
$glow-ember:  none;
$glow-jade:   none;
```

- [ ] **Step 3: Rewrite global.scss CSS custom properties**

Replace lines 1-70 of `web/src/styles/global.scss` (the `:root` block) with new token values. Keep the rest (reset, utilities, Element Plus overrides) but update their values.

The full `global.scss` rewrite:

```scss
/* === WorldEngine — Professional Dark Theme === */

:root {
  /* === Backgrounds === */
  --bg-void:        #0d1117;
  --bg-surface:     #161b22;
  --bg-elevated:    #1c2128;
  --bg-glass:       rgba(22, 27, 34, 0.85);
  --bg-scrim:       rgba(13, 17, 23, 0.94);

  /* === Text === */
  --text-primary:   #e6edf3;
  --text-secondary: #8b949e;
  --text-muted:     #484f58;
  --text-inverse:   #0d1117;

  /* === Accents === */
  --accent-ember:     #d4793a;
  --accent-ember-dim: rgba(212, 121, 58, 0.12);
  --accent-ember-glow: none;
  --accent-blue:      #58a6ff;
  --accent-jade:      #3fb950;
  --accent-cinnabar:  #f85149;
  --accent-aurora:    #bc8cff;
  --accent-phosphor:  #7ee787;
  --accent-silver:    #8b949e;

  /* === Structure === */
  --border-default: #30363d;
  --border-muted:   #21262d;
  --border-active:  rgba(212, 121, 58, 0.45);

  /* Legacy aliases */
  --border-ghost:   var(--border-muted);
  --border-rule:    var(--border-default);

  /* === Shadows === */
  --shadow-sm:   0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.08);
  --shadow-md:   0 4px 12px rgba(0,0,0,0.15);
  --shadow-deep: 0 8px 24px rgba(0,0,0,0.2);
  --glow-ember:  none;
  --glow-jade:   none;

  /* === Fonts === */
  --font-ui:       'Inter', -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  --font-serif:    'Noto Serif SC', 'Source Serif 4', 'STSong', serif;
  --font-display:  var(--font-ui);
  --font-data:     'JetBrains Mono', 'Menlo', monospace;

  /* === Radius === */
  --radius-sm:  4px;
  --radius-md:  6px;
  --radius-lg:  8px;

  /* === Font Scale === */
  --fs-xs:   11px;
  --fs-sm:   13px;
  --fs-base: 15px;
  --fs-md:   17px;
  --fs-lg:   22px;
  --fs-xl:   32px;
  --fs-2xl:  48px;
  --fs-3xl:  68px;
  --fs-hero: 96px;

  /* === Spacing === */
  --sp-2xs: 2px;
  --sp-xs:  4px;
  --sp-sm:  8px;
  --sp-md:  16px;
  --sp-lg:  24px;
  --sp-xl:  32px;
  --sp-2xl: 48px;
  --sp-3xl: 64px;

  /* === Motion === */
  --duration-fast:  150ms;
  --duration-base:  200ms;
  --duration-slow:  300ms;
  --ease-default:   cubic-bezier(0.4, 0, 0.2, 1);
}

/* === Reset === */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: var(--font-ui);
  background: var(--bg-void);
  color: var(--text-primary);
  font-size: var(--fs-base);
  line-height: 1.5;
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  min-height: 100vh;
}

/* === Font utility classes === */
.font-data {
  font-family: var(--font-data);
  font-variant-numeric: tabular-nums;
}
.font-ui {
  font-family: var(--font-ui);
}
.font-display {
  font-family: var(--font-display);
}
.font-serif {
  font-family: var(--font-serif);
}

/* === Layout utilities === */
.ledger-rule {
  border-bottom: 1px solid var(--border-rule);
  padding-bottom: var(--sp-md);
  margin-bottom: var(--sp-md);
}

.section-label {
  font-family: var(--font-ui);
  font-size: var(--fs-xs);
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: var(--sp-sm);
  display: block;
}

/* === Element Plus dark overrides === */
.el-tabs__item {
  font-family: var(--font-ui) !important;
  color: var(--text-muted) !important;
  &.is-active {
    color: var(--accent-ember) !important;
  }
  &:hover {
    color: var(--text-secondary) !important;
  }
}

.el-tabs__active-bar {
  background-color: var(--accent-ember) !important;
}

.el-card {
  background: var(--bg-surface) !important;
  border-color: var(--border-default) !important;
  border-radius: var(--radius-lg) !important;
  box-shadow: none !important;
}

.el-card__header {
  border-bottom-color: var(--border-default) !important;
}

.el-button--primary {
  background: var(--accent-ember) !important;
  border-color: var(--accent-ember) !important;
  color: var(--text-inverse) !important;
  border-radius: var(--radius-md) !important;
  font-family: var(--font-ui);

  &:hover, &:focus {
    background: #db8a52 !important;
    border-color: #db8a52 !important;
  }
}

.el-button--success {
  background: var(--accent-jade) !important;
  border-color: var(--accent-jade) !important;
  color: var(--text-inverse) !important;
  border-radius: var(--radius-md) !important;
}

.el-button--danger {
  background: var(--accent-cinnabar) !important;
  border-color: var(--accent-cinnabar) !important;
  border-radius: var(--radius-md) !important;
}

.el-button--warning {
  background: var(--accent-ember) !important;
  border-color: var(--accent-ember) !important;
  border-radius: var(--radius-md) !important;
}

.el-button.is-plain {
  border-radius: var(--radius-md) !important;
}

.el-tag {
  border-radius: var(--radius-sm) !important;
  font-family: var(--font-ui);
}

.el-input__wrapper {
  border-radius: var(--radius-md) !important;
  background: var(--bg-elevated) !important;
  box-shadow: 0 0 0 1px var(--border-default) inset !important;

  &:focus-within, &.is-focus {
    box-shadow: 0 0 0 1px var(--border-active) inset !important;
  }
}

.el-select .el-input__wrapper {
  border-radius: var(--radius-md) !important;
}

.el-drawer {
  background: var(--bg-surface) !important;
}

.el-drawer__header {
  font-family: var(--font-ui);
  color: var(--text-primary) !important;
}

.el-progress-bar__outer {
  border-radius: var(--radius-sm) !important;
  background-color: var(--bg-elevated) !important;
}

.el-progress-bar__inner {
  border-radius: var(--radius-sm) !important;
}

.el-radio-button__inner {
  border-radius: var(--radius-md) !important;
  font-family: var(--font-ui);
}

.el-dialog {
  border-radius: var(--radius-lg) !important;
  background: var(--bg-surface) !important;
}

.el-message-box {
  border-radius: var(--radius-lg) !important;
  background: var(--bg-surface) !important;
}

.el-slider__bar {
  background: var(--accent-ember) !important;
}

.el-slider__button {
  border-color: var(--accent-ember) !important;
}

/* === Scrollbar === */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}
::-webkit-scrollbar-track {
  background: var(--bg-void);
}
::-webkit-scrollbar-thumb {
  background: var(--border-default);
  border-radius: 3px;
  &:hover {
    background: var(--text-muted);
  }
}

/* Firefox scrollbar */
* {
  scrollbar-width: thin;
  scrollbar-color: var(--border-default) var(--bg-void);
}
```

- [ ] **Step 4: Build and verify**

Run: `cd /root/lzh/world-novel/web && npm run build`
Expected: Build succeeds. All 38+ components auto-adapt to new token values.

- [ ] **Step 5: Commit**

```bash
git add web/index.html web/src/styles/variables.scss web/src/styles/global.scss
git commit -m "feat: new design system — neutral dark theme, Inter + Noto Serif SC fonts"
```

---

### Task 2: Event Log Store — Remove Emoji, Enhance Phase Descriptions

**Files:**
- Modify: `web/src/stores/eventLog.ts`

- [ ] **Step 1: Rewrite eventLog.ts**

Replace the entire file. Key changes:
1. Remove all emoji from `phaseLabels` and `addEntry` calls
2. Enhanced descriptions for directing/world_building/foreshadow_planning phases
3. `addEntry` no longer takes `icon` param — just `text` and `type`

```typescript
import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface LogEntry {
  time: string
  text: string
  type: string
}

const phaseLabels: Record<string, string> = {
  directing: '导演规划 — 分析命题、设计冲突弧线',
  world_building: '构建世界 — 生成地理、势力、魔法体系',
  foreshadow_planning: '伏笔网络 — 规划植入点和回收时机',
  simulating: '模拟角色场景',
  writing: '撰写章节',
  reviewing: '审校伏笔',
  god_deliberation: '命运裁决',
}

export const useEventLogStore = defineStore('eventLog', () => {
  const entries = ref<LogEntry[]>([])
  const maxEntries = 100

  function addEntry(text: string, type: string = 'info') {
    const now = new Date()
    const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
    entries.value.push({ time, text, type })
    if (entries.value.length > maxEntries) entries.value.shift()
  }

  function clear() {
    entries.value = []
  }

  function pushFromWS(event: any) {
    const t = event.type
    if (t === 'phase_change') {
      const label = phaseLabels[event.phase] || event.phase
      addEntry(`阶段切换: ${label}`, 'phase')
    } else if (t === 'scene_simulated') {
      addEntry(`场景模拟完成: 第${event.chapter + 1}章 场景${event.scene + 1} (${event.action_count}个行动)`, 'scene')
    } else if (t === 'scene_written') {
      addEntry(`场景写作完成: 第${event.chapter + 1}章 场景${event.scene + 1} (${event.word_count}字)`, 'write')
    } else if (t === 'chapter_completed') {
      addEntry(`第${event.chapter + 1}章完成: ${event.title} (${event.word_count}字)`, 'chapter')
    } else if (t === 'god_decision') {
      const events = event.events?.join('、') || ''
      addEntry(`命运裁决: ${events} ${event.guidance?.substring(0, 60) || ''}`, 'god')
    } else if (t === 'checkpoint_saved') {
      addEntry(`检查点已保存 (${event.chapters_completed}章完成)`, 'checkpoint')
    } else if (t === 'generation_started') {
      addEntry('生成流程已启动', 'start')
    } else if (t === 'generation_finished') {
      addEntry(`生成完成 — ${event.status}`, 'done')
    } else if (t === 'generation_error') {
      addEntry(`生成出错: ${event.error}`, 'error')
    } else if (t === 'novel_completed') {
      addEntry(`小说完成: ${event.title} (${event.word_count}字, ${event.total_chapters}章)`, 'done')
    }
  }

  return { entries, addEntry, clear, pushFromWS }
})
```

- [ ] **Step 2: Update OverviewPage addEvent calls**

In `web/src/components/overview/OverviewPage.vue`, the `addEvent` function currently passes `icon` as first arg. Update it to match the new signature (no icon):

Find the `addEvent` function (around line 266) and change it from:
```typescript
function addEvent(icon: string, text: string, type: string = 'info') {
  eventLogStore.addEntry(icon, text, type)
```
to:
```typescript
function addEvent(text: string, type: string = 'info') {
  eventLogStore.addEntry(text, type)
```

Then update ALL calls to `addEvent` in the same file — remove the first emoji argument from each call. There are 7 calls:

- Line ~353: `addEvent('🚀', '创世请求...')` → `addEvent('生成请求已发送，等待响应...', 'start')`
- Line ~358: `addEvent('❌', ...)` → `addEvent(`启动失败: ${res.error}`, 'error')`
- Line ~374: `addEvent('▶', ...)` → `addEvent(`从第${worldStatus.chapters_completed + 1}章继续生成`, 'start')`
- Line ~380: `addEvent('❌', ...)` → `addEvent(`恢复失败: ${res.error}`, 'error')`
- Line ~395: `addEvent('⏸', ...)` → `addEvent('生成已暂停', 'phase')`
- Line ~414: `addEvent('▶', ...)` → `addEvent(`从第${worldStatus.chapters_completed + 1}章继续生成`, 'start')`

- [ ] **Step 3: Build and verify**

Run: `cd /root/lzh/world-novel/web && npm run build`
Expected: Build succeeds with no type errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/stores/eventLog.ts web/src/components/overview/OverviewPage.vue
git commit -m "feat: remove emoji from event log, enhance phase descriptions"
```

---

### Task 3: DashboardLayout — Sidebar Overhaul with Mini Event Feed

**Files:**
- Modify: `web/src/layouts/DashboardLayout.vue`

This is the biggest single-file rewrite. Changes:
1. Remove emoji from nav tabs
2. Add historian shortcut button
3. Add mini event feed (last 5 entries from eventLogStore)
4. Unified status text (待命/生成中/已暂停/已完成/出错)
5. Button text: "继续生成第X章"

- [ ] **Step 1: Rewrite DashboardLayout.vue template + script + style**

The complete rewrite is large. Key template sections:

**Sidebar header** — merge status + progress into one line:
```html
<div class="simulation-status" v-if="novelStore.activeNovelId">
  <span class="status-dot" :class="statusClass">●</span>
  <span class="status-text">{{ statusLabel }}</span>
</div>
```

**Nav items** — remove icon span, text-only:
```typescript
const tabs = [
  { name: 'overview',    label: '概览' },
  { name: 'world-view',  label: '世界观' },
  { name: 'characters',  label: '角色' },
  { name: 'timeline',    label: '大纲与时间线' },
  { name: 'foreshadows', label: '伏笔' },
  { name: 'chapters',    label: '章节' },
  { name: 'novel',       label: '成书' },
  { name: 'tokens',      label: 'Token 统计' },
  { name: 'control',     label: '控制台' },
]
```

**Historian shortcut** — between nav and footer:
```html
<div class="historian-shortcut" @click="onTabChange('historian')">
  与史官对话
</div>
```

**Mini event feed** — in footer, after progress bar:
```html
<div class="mini-events" v-if="recentEvents.length > 0">
  <div v-for="evt in recentEvents" :key="evt.time + evt.text" class="mini-event" @click="onTabChange('overview')">
    <span class="mini-time">{{ evt.time.substring(0, 5) }}</span>
    <span class="mini-text">{{ evt.text.substring(0, 30) }}</span>
  </div>
</div>
```

**Status computed**:
```typescript
const statusClass = computed(() => {
  if (progressStore.phase === 'error') return 'error'
  if (progressStore.phase === 'done') return 'done'
  if (progressStore.paused) return 'paused'
  if (isRunning.value) return 'running'
  return 'idle'
})

const statusLabel = computed(() => {
  if (progressStore.phase === 'error') return '● 出错'
  if (progressStore.phase === 'done') return `● 已完成 · ${progressStore.completed}/${progressStore.total}章`
  if (progressStore.paused) return `● 已暂停 · ${progressStore.completed}/${progressStore.total}章`
  if (isRunning.value) return `● 生成中 · ${progressStore.completed}/${progressStore.total}章`
  return '● 待命'
})

const recentEvents = computed(() => {
  return eventLogStore.entries.slice(-5).reverse()
})
```

Import `useEventLogStore`:
```typescript
import { useEventLogStore } from '@/stores/eventLog'
const eventLogStore = useEventLogStore()
```

- [ ] **Step 2: Build and verify**

Run: `cd /root/lzh/world-novel/web && npm run build`

- [ ] **Step 3: Commit**

```bash
git add web/src/layouts/DashboardLayout.vue
git commit -m "feat: sidebar overhaul — no emoji, mini event feed, historian shortcut, unified status"
```

---

### Task 4: OverviewPage — Status Text Unification and Event Log Color Bars

**Files:**
- Modify: `web/src/components/overview/OverviewPage.vue`

- [ ] **Step 1: Unify status text**

Replace all status heading text:
- `创世进行中` → `生成中`
- `创世已暂停` → `已暂停`
- `创世完成` → `已完成`
- `开始创世` → `开始生成`

Replace generation panel `gen-panel-inner` background:
```scss
.gen-panel-inner {
  background: var(--bg-surface);  // was: var(--accent-ember-dim)
  border: 1px solid var(--border-default);  // was: var(--border-rule)
  border-radius: var(--radius-lg);
```

- [ ] **Step 2: Event log — replace emoji with color bars**

In the event log template, replace the `event-icon` span with a colored bar:

```html
<div
  v-for="(evt, i) in eventLogStore.entries"
  :key="i"
  :class="['event-item', `event-${evt.type}`]"
>
  <span class="event-bar"></span>
  <span class="event-time">{{ evt.time }}</span>
  <span class="event-text">{{ evt.text }}</span>
</div>
```

Add CSS for the bar:
```scss
.event-bar {
  width: 3px;
  min-height: 16px;
  border-radius: 2px;
  flex-shrink: 0;
  background: var(--text-muted);
}

&.event-phase .event-bar { background: var(--accent-blue); }
&.event-chapter .event-bar { background: var(--accent-ember); }
&.event-done .event-bar { background: var(--accent-jade); }
&.event-error .event-bar { background: var(--accent-cinnabar); }
&.event-start .event-bar { background: var(--accent-aurora); }
&.event-god .event-bar { background: var(--accent-ember); }
&.event-scene .event-bar,
&.event-write .event-bar { background: var(--text-muted); }
```

- [ ] **Step 3: Update button text and messages**

- `'创世已启动！'` → `'生成已启动！'`
- `'继续生成已启动！新设定将自动融入后续章节'` → `'继续生成已启动'`
- `'继续生成，导演建议已注入！'` → `'继续生成，建议已注入'`
- `'继续生成下一章！'` → `'继续生成'`

- [ ] **Step 4: Build and verify**

Run: `cd /root/lzh/world-novel/web && npm run build`

- [ ] **Step 5: Commit**

```bash
git add web/src/components/overview/OverviewPage.vue
git commit -m "feat: overview — unified status text, event log color bars, card-style panel"
```

---

### Task 5: NovelPage — Notion-Style Left TOC + Right Reader

**Files:**
- Modify: `web/src/components/novel/NovelPage.vue`
- Modify: `web/src/components/novel/NovelReader.vue`

- [ ] **Step 1: Rewrite NovelPage.vue**

Replace the entire template, script, and style. The key structure is:

```html
<template>
  <div class="novel-page" v-loading="loading">
    <!-- Header -->
    <div class="novel-header ledger-rule" v-if="hasChapters">
      <div class="header-info">
        <h2>{{ novelFull.title }}</h2>
        <span class="novel-meta font-data">{{ novelFull.chapters.length }}章 · {{ formatWordCount(novelFull.word_count) }}</span>
      </div>
    </div>

    <!-- Main: TOC + Reader side by side -->
    <div class="novel-layout" v-if="hasChapters">
      <!-- Left: TOC -->
      <aside class="novel-toc">
        <span class="section-label">目录</span>
        <nav class="toc-list">
          <a v-for="ch in novelFull.chapters" :key="ch.chapter_index"
             class="toc-item" :class="{ active: activeIndex === ch.chapter_index }"
             @click="goToChapter(ch.chapter_index)">
            <span class="toc-num">第{{ ch.chapter_index + 1 }}章</span>
            <span class="toc-title" v-if="ch.title">{{ ch.title }}</span>
            <span class="toc-words font-data">{{ ch.word_count.toLocaleString() }}字</span>
          </a>
        </nav>
        <!-- Export dropdown -->
        <div class="toc-footer">
          <el-dropdown trigger="click">
            <el-button size="small">导出</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="downloadMarkdown">Markdown</el-dropdown-item>
                <el-dropdown-item @click="downloadJSON">JSON</el-dropdown-item>
                <el-dropdown-item @click="copyAll">复制全文</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </aside>

      <!-- Right: Reader -->
      <div class="novel-reader-area">
        <NovelReader v-if="activeChapter" :chapter="activeChapter" />
        <div class="chapter-nav">
          <el-button :disabled="activeIndex <= 0" @click="goToChapter(activeIndex - 1)">上一章</el-button>
          <span class="nav-pos font-data">{{ activeIndex + 1 }}/{{ novelFull.chapters.length }}章</span>
          <el-button :disabled="activeIndex >= novelFull.chapters.length - 1" @click="goToChapter(activeIndex + 1)">下一章</el-button>
        </div>
      </div>
    </div>

    <!-- Empty states -->
    <div class="empty-state" v-if="!loading && !hasChapters">
      <!-- generating vs idle -->
    </div>
  </div>
</template>
```

Key CSS:
```scss
.novel-layout {
  display: flex;
  gap: var(--sp-xl);
}

.novel-toc {
  width: 200px;
  min-width: 200px;
  flex-shrink: 0;
  position: sticky;
  top: var(--sp-xl);
  max-height: calc(100vh - 120px);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}

.toc-item {
  display: flex;
  flex-direction: column;
  padding: var(--sp-sm);
  cursor: pointer;
  border-left: 2px solid transparent;

  &.active {
    border-left-color: var(--accent-ember);
    background: var(--accent-ember-dim);
  }
}

.novel-reader-area {
  flex: 1;
  min-width: 0;
  max-width: 720px;
}
```

- [ ] **Step 2: Update NovelReader.vue**

Change line-height from 2.0 to 1.8, change footer from centered decoration to right-aligned:

```scss
.chapter-body {
  line-height: 1.8;  // was 2.0
}

.chapter-paragraph {
  margin: 0 0 1em 0;  // was 1.2em
}

.chapter-footer {
  text-align: right;  // was center
  padding-top: var(--sp-md);
  margin-top: var(--sp-lg);
}

.word-count {
  font-size: var(--fs-xs);
  color: var(--text-muted);
  // Remove letter-spacing: 0.1em
}
```

Change the template footer from `── X 字 ──` to just `X 字`:
```html
<div class="chapter-footer">
  <span class="word-count font-data">{{ chapter.word_count.toLocaleString() }} 字</span>
</div>
```

- [ ] **Step 3: Build and verify**

Run: `cd /root/lzh/world-novel/web && npm run build`

- [ ] **Step 4: Commit**

```bash
git add web/src/components/novel/NovelPage.vue web/src/components/novel/NovelReader.vue
git commit -m "feat: novel page — Notion-style TOC + reader layout"
```

---

### Task 6: RelationshipGraph — Adaptive Height, Playback, Click-to-Detail

**Files:**
- Modify: `web/src/components/characters/RelationshipGraph.vue`
- Modify: `web/src/components/characters/CharactersPage.vue`

- [ ] **Step 1: Update RelationshipGraph container height**

In the style section, change `.relationship-graph` height:

```scss
.relationship-graph {
  width: 100%;
  min-height: 400px;
  height: calc(100vh - 280px);
  max-height: 800px;
  background: var(--bg-surface);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-lg);
}
```

- [ ] **Step 2: Enhance slider controls with playback**

Replace the graph-controls template section:

```html
<div class="graph-controls" v-if="maxChapter > 0">
  <span class="control-label">第{{ sliderChapter + 1 }}章关系快照</span>
  <el-slider
    v-model="sliderChapter"
    :min="0"
    :max="maxChapter"
    :step="1"
    :format-tooltip="formatSliderTooltip"
    size="small"
    style="flex: 1; margin: 0 12px;"
    @change="onSliderChange"
  />
  <el-button size="small" @click="togglePlayback" :type="isPlaying ? 'danger' : 'primary'">
    {{ isPlaying ? '停止' : '演进' }}
  </el-button>
  <el-button size="small" @click="resetToLatest">最新</el-button>
</div>
```

Add playback state and methods in script:

```typescript
const isPlaying = ref(false)
let playTimer: ReturnType<typeof setInterval> | null = null

function togglePlayback() {
  if (isPlaying.value) {
    stopPlayback()
  } else {
    startPlayback()
  }
}

function startPlayback() {
  isPlaying.value = true
  sliderChapter.value = 0
  loadHistoryForChapter(0)

  playTimer = setInterval(() => {
    if (sliderChapter.value >= maxChapter.value) {
      stopPlayback()
      return
    }
    sliderChapter.value++
    loadHistoryForChapter(sliderChapter.value)
  }, 1500)
}

function stopPlayback() {
  isPlaying.value = false
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
}
```

Clean up timer in `onUnmounted`:
```typescript
onUnmounted(() => {
  unsub()
  stopPlayback()
})
```

- [ ] **Step 3: Add click-to-open-drawer interaction**

After building the network in `buildGraph()`, add a click handler:

```typescript
network.on('click', (params: any) => {
  if (params.nodes.length > 0) {
    const nodeId = params.nodes[0]
    emit('node-click', nodeId)
  }
})
```

Add emit declaration:
```typescript
const emit = defineEmits<{
  'node-click': [characterId: string]
}>()
```

In `CharactersPage.vue`, handle the event:
```html
<RelationshipGraph @node-click="onGraphNodeClick" />
```

```typescript
function onGraphNodeClick(characterId: string) {
  const char = characterStore.characters.find(c => c.id === characterId)
  if (char) {
    openCharacter(char)
  }
}
```

- [ ] **Step 4: Update vis-network font references**

In `buildGraph()`, update hardcoded font references from old design system:
- `'Instrument Sans, PingFang SC, sans-serif'` → `'Inter, PingFang SC, sans-serif'`
- `'#ede6d8'` → `'#e6edf3'` (text-primary)
- `'#09080c'` → `'#0d1117'` (bg-void)
- `'#12101a'` → `'#161b22'` (bg-surface)
- `'#9e8fa3'` → `'#8b949e'` (text-secondary)

- [ ] **Step 5: Build and verify**

Run: `cd /root/lzh/world-novel/web && npm run build`

- [ ] **Step 6: Commit**

```bash
git add web/src/components/characters/RelationshipGraph.vue web/src/components/characters/CharactersPage.vue
git commit -m "feat: relationship graph — adaptive height, playback, click-to-detail"
```

---

### Task 7: HorizontalTimeline — New Component

**Files:**
- Create: `web/src/components/timeline/HorizontalTimeline.vue`
- Modify: `web/src/components/timeline/TimelinePage.vue`

- [ ] **Step 1: Create HorizontalTimeline.vue**

```vue
<template>
  <div class="horizontal-timeline" v-if="totalChapters > 0">
    <div class="timeline-scroll" ref="scrollContainer">
      <div class="timeline-track" :style="{ width: trackWidth + 'px' }">
        <!-- Main axis line -->
        <div class="axis-line"></div>

        <!-- Chapter markers -->
        <div
          v-for="ch in totalChapters"
          :key="ch"
          class="chapter-marker"
          :class="{ current: ch <= completedChapters, active: ch === activeChapter }"
          :style="{ left: markerLeft(ch) + 'px' }"
          @click="$emit('select-chapter', ch)"
        >
          <div class="marker-dot"></div>
          <span class="marker-label">{{ ch }}</span>
        </div>

        <!-- Event nodes -->
        <div
          v-for="(node, i) in eventNodes"
          :key="'evt-' + i"
          class="event-node"
          :class="node.kind"
          :style="{ left: markerLeft(node.chapter) + 'px' }"
          @mouseenter="hoveredNode = node"
          @mouseleave="hoveredNode = null"
          @click="$emit('select-event', node)"
        >
          <div class="node-dot"></div>
          <span class="node-label">{{ node.title.substring(0, 8) }}</span>
        </div>
      </div>
    </div>

    <!-- Tooltip -->
    <div class="timeline-tooltip" v-if="hoveredNode">
      <strong>{{ hoveredNode.title }}</strong>
      <span class="tooltip-meta">第{{ hoveredNode.chapter }}章 · {{ hoveredNode.kind === 'decision' ? '命运裁决' : hoveredNode.eventType || '事件' }}</span>
      <p v-if="hoveredNode.description">{{ hoveredNode.description.substring(0, 120) }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { TimelineEvent, GodDecision } from '@/api/types'

const props = defineProps<{
  events: TimelineEvent[]
  decisions: GodDecision[]
  totalChapters: number
  completedChapters: number
}>()

defineEmits<{
  'select-chapter': [chapter: number]
  'select-event': [node: EventNode]
}>()

interface EventNode {
  chapter: number
  title: string
  description: string
  kind: 'event' | 'decision'
  eventType?: string
}

const hoveredNode = ref<EventNode | null>(null)
const scrollContainer = ref<HTMLElement | null>(null)
const activeChapter = ref(0)

const MARKER_GAP = 100  // px between chapter markers
const MARGIN = 40

const trackWidth = computed(() => MARGIN * 2 + props.totalChapters * MARKER_GAP)

function markerLeft(chapter: number): number {
  return MARGIN + (chapter - 1) * MARKER_GAP
}

const eventNodes = computed<EventNode[]>(() => {
  const nodes: EventNode[] = []

  for (const e of props.events) {
    nodes.push({
      chapter: (e.chapter_index ?? 0) + 1,
      title: e.title,
      description: e.description,
      kind: 'event',
      eventType: e.event_type,
    })
  }

  for (const d of props.decisions) {
    const events = (d as any).world_events || []
    const title = events.length > 0 ? events.map((e: any) => e.title || '').join(', ') : '命运裁决'
    nodes.push({
      chapter: (d.chapter_index ?? 0) + 1,
      title: title,
      description: (d as any).next_chapter_guidance || d.description || '',
      kind: 'decision',
    })
  }

  return nodes.sort((a, b) => a.chapter - b.chapter)
})
</script>

<style scoped lang="scss">
.horizontal-timeline {
  position: relative;
  margin-bottom: var(--sp-lg);
}

.timeline-scroll {
  overflow-x: auto;
  padding: var(--sp-lg) 0 var(--sp-2xl) 0;
}

.timeline-track {
  position: relative;
  height: 80px;
  min-width: 100%;
}

.axis-line {
  position: absolute;
  top: 20px;
  left: 30px;
  right: 30px;
  height: 2px;
  background: var(--border-default);
}

.chapter-marker {
  position: absolute;
  top: 12px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;

  .marker-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--border-default);
    border: 2px solid var(--bg-void);
    z-index: 1;
  }

  .marker-label {
    font-family: var(--font-data);
    font-size: 10px;
    color: var(--text-muted);
    margin-top: 4px;
  }

  &.current .marker-dot {
    background: var(--accent-jade);
  }

  &.active .marker-dot {
    background: var(--accent-ember);
    box-shadow: 0 0 8px rgba(212, 121, 58, 0.4);
  }
}

.event-node {
  position: absolute;
  top: 42px;
  transform: translateX(-50%);
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;

  .node-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-jade);
  }

  .node-label {
    font-family: var(--font-ui);
    font-size: 9px;
    color: var(--text-muted);
    margin-top: 2px;
    white-space: nowrap;
    max-width: 60px;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  &.decision .node-dot {
    width: 12px;
    height: 12px;
    background: var(--accent-ember);
  }

  &:hover .node-dot {
    transform: scale(1.4);
  }
}

.timeline-tooltip {
  position: absolute;
  bottom: 0;
  left: var(--sp-md);
  right: var(--sp-md);
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: var(--radius-md);
  padding: var(--sp-sm) var(--sp-md);
  z-index: 10;

  strong {
    display: block;
    font-size: var(--fs-sm);
    color: var(--text-primary);
    margin-bottom: 2px;
  }

  .tooltip-meta {
    font-size: var(--fs-xs);
    color: var(--text-muted);
    display: block;
    margin-bottom: 4px;
  }

  p {
    font-size: var(--fs-xs);
    color: var(--text-secondary);
    line-height: 1.4;
    margin: 0;
  }
}
</style>
```

- [ ] **Step 2: Integrate into TimelinePage.vue**

Add import and usage at the top of the timeline section (before the `<!-- Single-column vertical timeline -->` comment, around line 91):

```typescript
import HorizontalTimeline from './HorizontalTimeline.vue'
import { useProgressStore } from '@/stores/progress'
const progressStore = useProgressStore()
```

Insert the component in the template between the outline section and the vertical timeline:

```html
<!-- Horizontal Timeline Overview -->
<div class="timeline-overview" style="margin-bottom: var(--sp-lg)">
  <span class="section-label">时间轴概览</span>
  <HorizontalTimeline
    :events="timelineStore.events"
    :decisions="timelineStore.decisions"
    :total-chapters="chapters.length || progressStore.total"
    :completed-chapters="progressStore.completed"
  />
</div>
```

- [ ] **Step 3: Remove emoji from TimelinePage**

In the template, remove `📍` from scene locations (line ~48, ~76):
- `<span class="scene-location">📍 {{ scene.location }}</span>` → `<span class="scene-location">{{ scene.location }}</span>`

Remove `🔄` from refresh button (line ~7):
- `🔄 刷新` → `刷新`

- [ ] **Step 4: Build and verify**

Run: `cd /root/lzh/world-novel/web && npm run build`

- [ ] **Step 5: Commit**

```bash
git add web/src/components/timeline/HorizontalTimeline.vue web/src/components/timeline/TimelinePage.vue
git commit -m "feat: horizontal timeline visualization + emoji removal"
```

---

### Task 8: Historian Chat — Dynamic Suggestions

**Files:**
- Modify: `web/src/components/historian/HistorianChat.vue`

- [ ] **Step 1: Add dynamic suggestions**

Import progressStore and replace hardcoded suggestions with computed:

```typescript
import { useProgressStore } from '@/stores/progress'
const progressStore = useProgressStore()

const suggestions = computed(() => {
  const chapter = progressStore.completed
  const dynamic: string[] = []
  if (chapter > 0) {
    dynamic.push(`分析第${chapter}章中角色的关系变化`)
    dynamic.push(`第${chapter}章有哪些伏笔被埋下了？`)
  }
  return [
    ...dynamic,
    '帮我梳理当前所有角色的关系变化',
    '分析目前的伏笔哪些还没回收',
    '建议下一章的剧情走向',
  ]
})
```

Remove the old `const suggestions = [...]` array (lines 54-60).

Add `computed` to the import from vue:
```typescript
import { ref, nextTick, onMounted, watch, computed } from 'vue'
```

- [ ] **Step 2: Build and verify**

Run: `cd /root/lzh/world-novel/web && npm run build`

- [ ] **Step 3: Commit**

```bash
git add web/src/components/historian/HistorianChat.vue
git commit -m "feat: historian chat — dynamic context-aware suggestions"
```

---

### Task 9: DESIGN.md — New Design Direction Document

**Files:**
- Modify: `DESIGN.md`

- [ ] **Step 1: Rewrite DESIGN.md**

Replace the entire file with the new design system documentation reflecting the Professional SaaS direction. Include:
- New color palette (GitHub Dark style)
- New font stack (Inter + Noto Serif SC)
- Layout rules (sidebar + content, card-based panels)
- Status text conventions
- Component patterns

- [ ] **Step 2: Commit**

```bash
git add DESIGN.md
git commit -m "docs: rewrite design system — professional SaaS direction"
```

---

### Task 10: Final Build Verification and Status Text Sweep

**Files:**
- Various — grep-based sweep

- [ ] **Step 1: Full build**

Run: `cd /root/lzh/world-novel/web && npm run build`
Expected: No errors.

- [ ] **Step 2: Grep for remaining emoji in Vue templates**

Run: `grep -rn '[📖🌍👥📋🔮📝📚📜🪙⚙️📥📦📋🚀🎉❌💾🔄🎭✍️📖🔮📚]' web/src/components/ web/src/layouts/ web/src/stores/`

Fix any remaining emoji in nav labels, event log text, button text, or section headers. (Emoji in user-facing content like historian chat welcome message can stay if appropriate.)

- [ ] **Step 3: Grep for inconsistent status text**

Run: `grep -rn '创世\|模拟运行' web/src/`

Replace any remaining `创世进行中` → `生成中`, `模拟运行中` → `生成中`, etc.

- [ ] **Step 4: Commit any remaining fixes**

```bash
git add -A
git commit -m "fix: final emoji and status text sweep"
```
