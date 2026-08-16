import { defineConfig } from 'vitepress'

// 部署路径（纯静态产物，三种托管方式）：
//   根路径/独立子域：  DOCS_BASE=/        （默认，本地预览/独立域名）
//   主站子路径：       DOCS_BASE=/docs/   （nginx location /docs/）
//   GitHub Pages：     DOCS_BASE=/world-novel/
const base = process.env.DOCS_BASE || '/'

export default defineConfig({
  base,
  lang: 'zh-CN',
  title: 'WorldNovel',
  description: '多 Agent 协作的 AI 长篇小说生成系统 —— 开源、可自托管',
  // Keep .html extensions: GitHub Pages has no extensionless fallback, and
  // plain file servers work out of the box. nginx try_files is belt-and-braces.
  cleanUrls: false,
  // 产品设计文档（docs/product 同步）中的历史链接不参与死链校验，
  // 手写的 guide/reference 页面仍严格校验
  ignoreDeadLinks: [
    /^\/product\//,
    /^https?:\/\/(localhost|127\.0\.0\.1)/,  // doc examples, checked at runtime
  ],
  // README 是仓库说明，不渲染为站点页面
  srcExclude: ['README.md'],
  // 默认主题不加载任何外部 CDN 字体/脚本，全部资源本地构建，国内可访问
  appearance: true,
  lastUpdated: true,

  head: [
    ['meta', { name: 'viewport', content: 'width=device-width, initial-scale=1' }],
  ],

  themeConfig: {
    siteTitle: 'WorldNovel',
    logo: '/logo.svg',

    nav: [
      { text: '指南', link: '/guide/quickstart', activeMatch: '/guide/' },
      { text: 'API 参考', link: '/reference/api', activeMatch: '/reference/' },
      {
        text: '产品设计',
        items: [
          { text: '产品愿景', link: '/product/01-vision' },
          { text: '系统架构', link: '/product/02-architecture' },
          { text: '里程碑路线图', link: '/product/08-roadmap' },
          { text: '全部文档', link: '/product/README' },
        ],
      },
      {
        text: 'GitHub',
        link: 'https://github.com/Yourdaylight/world-novel',
      },
    ],

    sidebar: {
      '/guide/': [
        {
          text: '使用指南',
          items: [
            { text: '快速开始', link: '/guide/quickstart' },
            { text: '认证配置', link: '/guide/auth' },
            { text: '成书发布', link: '/guide/publish' },
            { text: '分享与注册阅读', link: '/guide/share' },
            { text: 'FAQ', link: '/guide/faq' },
          ],
        },
      ],
      '/reference/': [
        {
          text: '参考',
          items: [
            { text: 'HTTP API', link: '/reference/api' },
            { text: '部署', link: '/guide/quickstart#deploy' },
          ],
        },
      ],
      '/product/': [
        {
          text: '产品设计文档',
          items: [
            { text: '索引', link: '/product/README' },
            { text: '01 产品愿景', link: '/product/01-vision' },
            { text: '02 系统架构', link: '/product/02-architecture' },
            { text: '03 用户旅程', link: '/product/03-user-journey' },
            { text: '04 功能详述', link: '/product/04-features' },
            { text: '05 工作区', link: '/product/05-workspace' },
            { text: '06 商业模式', link: '/product/06-pricing' },
            { text: '07 页面设计', link: '/product/07-pages' },
            { text: '08 里程碑路线图', link: '/product/08-roadmap' },
            { text: '09 数据库抽象', link: '/product/09-database-abstraction' },
            { text: '10 认知架构', link: '/product/10-cognition-architecture' },
            { text: '11 记忆增强', link: '/product/11-memory-enhancement' },
            { text: '12 记忆密钥交换', link: '/product/12-memory-key-exchange' },
            { text: '13 通用认知工具包', link: '/product/13-generic-cognition-kit' },
            { text: '14 记忆与政治架构', link: '/product/14-memory-and-political-architecture' },
            { text: '15 成书发布/分享/文档站需求', link: '/product/15-publish-share-docs' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/Yourdaylight/world-novel' },
    ],

    footer: {
      message: '基于 MIT 许可开源发布',
      copyright: 'Copyright © 2026 WorldNovel contributors',
    },

    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一篇', next: '下一篇' },
    darkModeSwitchLabel: '主题',
    sidebarMenuLabel: '菜单',
    returnToTopLabel: '回到顶部',
    lastUpdatedText: '最后更新',
  },
})
