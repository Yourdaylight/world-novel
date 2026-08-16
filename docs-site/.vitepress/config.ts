import { defineConfig } from 'vitepress'

// 部署路径可通过环境变量调整：
//   根路径部署（GitHub Pages 自定义域 / 独立子域）：DOCS_BASE=/
//   主站子路径部署（world-novel.programtree.cn/docs/）：DOCS_BASE=/docs/
const base = process.env.DOCS_BASE ?? '/'

export default defineConfig({
  base,
  lang: 'zh-CN',
  title: 'WorldNovel',
  description: '多 Agent 世界演化与网文成书系统 — 使用文档',
  // VitePress 默认自托管全部静态资源、使用系统字体栈，无外部 CDN 依赖（离线友好）
  cleanUrls: true,
  lastUpdated: true,
  // localhost 是文档中有意给出的本地地址，不参与死链检查
  ignoreDeadLinks: [/^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/],

  head: [
    ['meta', { name: 'theme-color', content: '#d97706' }],
  ],

  themeConfig: {
    siteTitle: 'WorldNovel 文档',
    // C-1：显眼 GitHub 入口
    socialLinks: [
      { icon: 'github', link: 'https://github.com/Yourdaylight/world-novel' },
    ],

    nav: [
      { text: '指南', link: '/guide/quickstart', activeMatch: '/guide/' },
      { text: 'API 参考', link: '/reference/api', activeMatch: '/reference/' },
      { text: '产品设计', link: '/product/README', activeMatch: '/product/' },
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
            { text: '认证配置（jwt/casdoor/disabled）', link: '/guide/auth' },
            { text: '成书发布（番茄/七猫）', link: '/guide/publish' },
            { text: '分享与注册阅读', link: '/guide/share' },
            { text: '独立部署文档站', link: '/guide/deploy-docs' },
            { text: 'FAQ', link: '/guide/faq' },
          ],
        },
      ],
      '/reference/': [
        {
          text: '参考',
          items: [
            { text: 'API 参考', link: '/reference/api' },
            { text: 'OpenAPI Schema', link: '/openapi.json', target: '_blank' },
          ],
        },
      ],
      '/product/': [
        {
          text: '产品设计文档',
          items: [
            { text: '总览', link: '/product/README' },
            { text: '01 产品愿景', link: '/product/01-vision' },
            { text: '02 系统架构', link: '/product/02-architecture' },
            { text: '03 用户旅程', link: '/product/03-user-journey' },
            { text: '04 功能需求', link: '/product/04-features' },
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
          ],
        },
      ],
    },

    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一篇', next: '下一篇' },
    darkModeSwitchLabel: '主题',
    sidebarMenuLabel: '菜单',
    returnToTopLabel: '回到顶部',

    search: {
      provider: 'local',
      options: {
        translations: {
          button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
          modal: {
            displayDetails: '显示详情',
            resetButtonTitle: '清除查询条件',
            backButtonTitle: '返回',
            noResultsText: '无法找到相关结果',
            footer: {
              selectText: '选择',
              navigateText: '切换',
            },
          },
        },
      },
    },

    editLink: {
      pattern: 'https://github.com/Yourdaylight/world-novel/edit/main/docs-site/:path',
      text: '在 GitHub 上编辑此页',
    },
  },
})
