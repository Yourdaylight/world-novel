# 设计系统 — WorldEngine

## 产品定位

- **产品描述:** 多Agent小说生成系统，AI角色自主协作生成长篇网文
- **目标用户:** 中国网文创作者、AI创作探索者
- **产品形态:** AI Agent编排和监控面板
- **项目类型:** Web应用仪表板 (Vue 3 + Element Plus + SCSS)

## 设计方向

- **方向:** 现代SaaS工具（参考 Linear / Vercel / Notion）
- **默认主题:** 亮色（白底），支持暗色模式切换
- **核心原则:** 干净、紧凑、专业。内容即界面，最少装饰
- **强调色:** Orange #f97316 — 一个亮色贯穿全系统

---

## 主题系统

默认亮色，用户可切换暗色。通过 `html.dark` class 控制。

### 亮色模式（默认）

```css
--bg-void:        #ffffff;
--bg-surface:     #f9fafb;
--bg-elevated:    #f3f4f6;
--text-primary:   #111827;
--text-secondary: #6b7280;
--text-muted:     #9ca3af;
--border-default: #e5e7eb;
--border-muted:   #f3f4f6;
```

### 暗色模式

```css
html.dark {
  --bg-void:        #09090b;
  --bg-surface:     #18181b;
  --bg-elevated:    #27272a;
  --text-primary:   #fafafa;
  --text-secondary: #a1a1aa;
  --text-muted:     #52525b;
  --border-default: #27272a;
  --border-muted:   #1e1e22;
}
```

### 强调色（两模式通用）

| 名称 | 亮色 | 暗色 | 用途 |
|------|------|------|------|
| Orange (Primary) | `#f97316` | `#f97316` | 主操作、CTA、进度条、active状态 |
| Blue | `#2563eb` | `#3b82f6` | 信息、伏笔 |
| Green | `#16a34a` | `#22c55e` | 成功、完成 |
| Red | `#dc2626` | `#ef4444` | 错误、冲突 |
| Purple | `#7c3aed` | `#a78bfa` | 记忆、历史 |
| Yellow | `#ca8a04` | `#eab308` | 警告、暂停 |

---

## 排版

### 字体

| 用途 | 字体 |
|------|------|
| UI界面 | Inter, -apple-system, PingFang SC, Microsoft YaHei, sans-serif |
| 阅读正文 | Noto Serif SC, Source Serif 4, STSong, serif |
| 数据/代码 | JetBrains Mono, Menlo, monospace |

### 字体比例尺

| 级别 | 大小 | 用途 |
|------|------|------|
| xs | 11px | 辅助标签 |
| sm | 13px | 界面文本 |
| base | 14px | 正文 |
| md | 16px | 叙事正文 |
| lg | 20px | 区域标题 |
| xl | 28px | 页面标题 |

### 行高

- 界面文本: 1.5
- 叙事正文: 1.9
- 数据区: 1.2

---

## 间距

8px 基础单位。

| 变量 | 值 |
|------|-----|
| --sp-2xs | 2px |
| --sp-xs | 4px |
| --sp-sm | 8px |
| --sp-md | 16px |
| --sp-lg | 24px |
| --sp-xl | 32px |
| --sp-2xl | 48px |
| --sp-3xl | 64px |

---

## 布局

- 侧边栏: 220px 固定
- 内容区: 弹性，最大 1100px
- 圆角: 6-8px（卡片/按钮），4px（标签）
- 卡片: `border: 1px solid var(--border-default)` + `box-shadow: var(--shadow-sm)`

---

## 动效

- 快速: 150ms（状态切换）
- 基础: 200ms（面板展开）
- 慢速: 300ms（视图切换）
- 缓动: `cubic-bezier(0.4, 0, 0.2, 1)`

---

## 状态文案规范

### 章节编号
`第X章`

### 进度
`X/Y章`（无空格）

### 状态
| 状态 | 文案 |
|------|------|
| 未启动 | 待命 |
| 运行中 | 生成中 |
| 暂停 | 已暂停 |
| 完成 | 已完成 |
| 异常 | 出错 |

### 按钮
| 场景 | 文案 |
|------|------|
| 首次 | 开始生成 |
| 继续 | 继续生成第X章 |
| 暂停 | 暂停 |

---

## 反模式

- UI导航/按钮中使用 Emoji
- 紫色/渐变强调色
- 装饰性发光效果
- 大圆角 (12px+)
- 渐变CTA按钮
- 纸纹理/古风元素

---

## 决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-03-27 | 初始设计系统 | /design-consultation 创建 |
| 2026-03-28 | 重写为专业SaaS | 原方向过于装饰 |
| 2026-03-28 | 亮色/暗色双主题 | 用户需求，亮色为默认 |
| 2026-03-28 | Orange #f97316 强调色 | 在蓝色AI工具中有辨识度 |
| 2026-03-28 | 移除 Fraunces/DM Sans | 装饰性字体不符合工具定位，统一Inter |
