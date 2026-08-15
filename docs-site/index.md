---
layout: home

hero:
  name: WorldNovel
  text: 多 Agent 长篇小说自动生成系统
  tagline: 每个角色都是独立 Agent — 他们思考、对话、行动，共同演化出一部完整的长篇网文
  actions:
    - theme: brand
      text: 快速开始
      link: /guide/quickstart
    - theme: alt
      text: ⭐ GitHub 仓库
      link: https://github.com/Yourdaylight/world-novel
    - theme: alt
      text: 使用文档
      link: /guide/quickstart

features:
  - icon: 🌍
    title: 世界演化
    details: 世界观、势力、时间线、伏笔自动构建，七个 LangGraph 阶段流水线驱动成书。
  - icon: 🤖
    title: 多 Agent 协作
    details: 导演、角色、作家、史官、审稿人多角色分工，角色拥有独立记忆与情感系统。
  - icon: 🚀
    title: 一键发布
    details: 质量门禁 + 平台规范导出（番茄 / 七猫 / EPUB），成书直达平台作家后台。
  - icon: 📖
    title: 分享与阅读
    details: 生成公开分享链接，匿名试读、注册即全文，书架与阅读进度同步。
  - icon: 🔐
    title: 灵活认证
    details: jwt 邀请码（开源默认）/ Casdoor 企业 SSO / 关闭认证，三种模式一键切换。
  - icon: 📦
    title: 开箱即部署
    details: FastAPI + Vue3 + SQLite，uv 一键安装，Docker / systemd 部署方案齐备。
---

<div class="vp-doc" style="max-width: 768px; margin: 32px auto; padding: 0 24px;">

## 开源项目

WorldNovel 在 GitHub 上完全开源。欢迎 Star、Fork、提 Issue 与 PR：

**[github.com/Yourdaylight/world-novel](https://github.com/Yourdaylight/world-novel)**

```bash
git clone https://github.com/Yourdaylight/world-novel.git
cd world-novel
cp .env.example .env   # 填入你的 LLM API Key
make install
make dev               # 打开 http://localhost:5173
```

</div>
