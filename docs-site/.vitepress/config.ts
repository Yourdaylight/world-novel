import { defineConfig } from 'vitepress'

// Deploy under a sub-path (/docs/) or at a domain root. Build with:
//   DOCS_BASE=/docs/ npm run docs:build   →  world-novel.../docs/
// Default '/' works for GitHub Pages root / standalone static host.
const base = process.env.DOCS_BASE || '/'

// Pure-static site: no backend requests, no external CDN, self-hosted assets.
export default defineConfig({
  title: 'WorldNovel',
  description: '多 Agent 协作长篇小说自动生成系统',
  base,
  outDir: 'dist',
  cleanUrls: true,
  lang: 'zh-CN',
  lastUpdated: true,
  ignoreDeadLinks: false,
  themeConfig: {
    siteTitle: 'WorldNovel',
    search: {
      provider: 'local',
      options: { translations: { button: { buttonText: '搜索文档' } } },
    },
    nav: [
      { text: '指南', link: '/guide/quickstart', activeMatch: '/guide/' },
      { text: 'API', link: '/reference/api', activeMatch: '/reference/' },
      { text: '产品设计', link: '/product/', activeMatch: '/product/' },
      {
        text: '相关链接',
        items: [
          { text: 'GitHub 仓库', link: 'https://github.com/Yourdaylight/world-novel' },
          { text: 'Issue 反馈', link: 'https://github.com/Yourdaylight/world-novel/issues' },
        ],
      },
    ],
    sidebar: {
      '/guide/': [
        {
          text: '使用指南',
          collapsed: false,
          items: [
            { text: '快速开始', link: '/guide/quickstart' },
            { text: '认证配置（jwt / casdoor / disabled）', link: '/guide/auth' },
            { text: '成书一键发布', link: '/guide/publish' },
            { text: '公开分享与注册阅读', link: '/guide/share' },
            { text: '独立部署', link: '/guide/deploy' },
            { text: '常见问题 FAQ', link: '/guide/faq' },
          ],
        },
      ],
      '/reference/': [
        {
          text: '参考',
          items: [
            { text: 'HTTP API', link: '/reference/api' },
            { text: '环境变量', link: '/reference/env' },
          ],
        },
      ],
      '/product/': [
        {
          text: '产品设计文档',
          collapsed: false,
          items: [
            { text: '索引', link: '/product/' },
            { text: '01 产品愿景', link: '/product/01-vision' },
            { text: '02 系统架构', link: '/product/02-architecture' },
            { text: '03 用户旅程', link: '/product/03-user-journey' },
            { text: '04 功能', link: '/product/04-features' },
            { text: '05 工作台', link: '/product/05-workspace' },
            { text: '06 商业模式', link: '/product/06-pricing' },
            { text: '07 页面', link: '/product/07-pages' },
            { text: '08 路线图', link: '/product/08-roadmap' },
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
    socialLinks: [
      { icon: 'github', link: 'https://github.com/Yourdaylight/world-novel' },
    ],
    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一页', next: '下一页' },
    lastUpdatedText: '最后更新',
    returnToTopLabel: '回到顶部',
    darkModeSwitchLabel: '主题',
    sidebarMenuLabel: '菜单',
  },
})
