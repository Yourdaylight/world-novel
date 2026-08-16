---
layout: home

hero:
  name: WorldNovel
  text: 多 Agent 协作长篇小说自动生成
  tagline: 每个角色都是拥有记忆、情感与关系网络的独立 AI Agent，由 LangGraph 七阶段流水线自动演化成书。
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/quickstart
    - theme: alt
      text: GitHub
      link: https://github.com/Yourdaylight/world-novel
    - theme: alt
      text: Star
      link: https://github.com/Yourdaylight/world-novel

features:
  - title: 多 Agent 世界演化
    details: 导演、角色、作家、上帝 Agent 协作，角色拥有分层记忆、情感状态、关系网络与自主议程。
  - title: 成书一键发布
    details: 发布前质量门禁（空章/断章/字数/敏感词），按番茄、七猫等平台规范导出 TXT/GB18030、EPUB、Word 与全格式 ZIP。
  - title: 公开分享 · 注册阅读
    details: 生成不可枚举的公开链接，匿名试读、邀请码注册即解锁全书；作者可关闭分享、配置试读策略、查看统计。
  - title: 认证可配置
    details: jwt 邀请码（开源默认）、Casdoor Sidecar（企业自托管）、disabled（开发）三态切换。
  - title: 作者工作台
    details: Vue 3 工作台：世界观、角色、时间线、伏笔、章节、Token 统计、控制台，亮/暗双主题。
  - title: 独立部署
    details: 后端 FastAPI + 每书独立 SQLite；本文档站为纯静态产物，不依赖后端，GitHub Pages / nginx / 对象存储均可托管。
---

<div class="github-cta">
  <a class="gh-btn" href="https://github.com/Yourdaylight/world-novel" target="_blank" rel="noreferrer">
    <span class="gh-icon"><!-- github mark --></span>
    在 GitHub 上查看 / Star
  </a>
  <span class="gh-note">开源地址：github.com/Yourdaylight/world-novel</span>
</div>

<style>
.github-cta {
  text-align: center;
  margin: 48px 0 24px;
}
.gh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 22px;
  border: 1px solid var(--vp-c-border, #ccc);
  border-radius: 10px;
  font-weight: 600;
  color: var(--vp-c-text-1);
  text-decoration: none;
  transition: border-color .2s, transform .2s;
}
.gh-btn:hover { border-color: var(--vp-c-brand-1); transform: translateY(-1px); }
.gh-note { display: block; margin-top: 12px; font-size: 13px; color: var(--vp-c-text-2); }
</style>
