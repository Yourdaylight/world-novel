import { defineConfig } from 'vitepress'

// 独立部署：默认按主站子路径 /docs/ 部署（nginx location /docs/）。
// GitHub Pages / 独立子域部署时用环境变量覆盖：
//   DOCS_BASE=/            独立子域 docs.world-novel.programtree.cn
//   DOCS_BASE=/world-novel/  GitHub Pages（仓库名路径）
const base = process.env.DOCS_BASE || '/docs/'

// cleanUrls（无扩展名 URL）需要服务器支持 .html 回退（nginx try_files）。
// GitHub Pages 等纯静态托管不支持 → 构建时关闭：DOCS_CLEAN_URLS=false
const cleanUrls = process.env.DOCS_CLEAN_URLS !== 'false'

export default defineConfig({
  lang: 'zh-CN',
  title: 'WorldNovel',
  description: '多 Agent 协作的长篇小说自动生成系统 — 使用文档',
  base,
  // 纯静态产物（docs-site/dist），任意静态服务器可直接托管，无后端依赖
  outDir: 'dist',
  emptyOutDir: true,
  cleanUrls,
  lastUpdated: true,
  // 文档中的本地服务地址示例不参与死链检查
  ignoreDeadLinks: [/^https?:\/\/localhost/, /^https?:\/\/127\.0\.0\.1/],

  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: `${base}favicon.svg` }],
    // 国内网络友好：不引用任何外部 CDN / Google Fonts，全部走系统字体栈
  ],

  themeConfig: {
    logo: undefined,
    siteTitle: 'WorldNovel',

    nav: [
      { text: '指南', link: '/guide/quickstart', activeMatch: '/guide/' },
      { text: 'API 参考', link: '/reference/api', activeMatch: '/reference/' },
      { text: '产品文档', link: '/product/', activeMatch: '/product/' },
      { text: 'FAQ', link: '/guide/faq' },
      {
        text: '链接',
        items: [
          {
            text: 'GitHub 仓库',
            link: 'https://github.com/Yourdaylight/world-novel',
          },
          { text: '文档首页', link: '/' },
        ],
      },
    ],

    sidebar: {
      '/guide/': [
        {
          text: '快速上手',
          items: [
            { text: '快速开始', link: '/guide/quickstart' },
            { text: '认证配置（jwt / casdoor）', link: '/guide/auth' },
            { text: '常见问题 FAQ', link: '/guide/faq' },
          ],
        },
        {
          text: '成书与分发',
          items: [
            { text: '一键发布（番茄 / 七猫）', link: '/guide/publish' },
            { text: '分享与注册阅读', link: '/guide/share' },
          ],
        },
        {
          text: '部署',
          items: [{ text: '部署指南', link: '/guide/deploy' }],
        },
      ],
      '/product/': [
        {
          text: '产品设计文档',
          items: [
            { text: '文档总览', link: '/product/' },
            { text: '01 产品愿景', link: '/product/01-vision' },
            { text: '02 系统架构', link: '/product/02-architecture' },
            { text: '03 用户旅程', link: '/product/03-user-journey' },
            { text: '04 功能清单', link: '/product/04-features' },
            { text: '05 工作台设计', link: '/product/05-workspace' },
            { text: '06 商业模式', link: '/product/06-pricing' },
            { text: '07 页面设计', link: '/product/07-pages' },
            { text: '08 里程碑路线图', link: '/product/08-roadmap' },
            { text: '09 数据库抽象', link: '/product/09-database-abstraction' },
            { text: '10 认知架构', link: '/product/10-cognition-architecture' },
            { text: '11 记忆增强', link: '/product/11-memory-enhancement' },
            { text: '12 记忆密钥交换', link: '/product/12-memory-key-exchange' },
            { text: '13 通用认知套件', link: '/product/13-generic-cognition-kit' },
            { text: '14 记忆与政治架构', link: '/product/14-memory-and-political-architecture' },
          ],
        },
      ],
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/Yourdaylight/world-novel' },
    ],

    // 本地搜索 — 不依赖外部服务，离线/国内网络可用
    search: {
      provider: 'local',
      options: {
        locales: {
          root: {
            translations: {
              button: { buttonText: '搜索文档', buttonAriaLabel: '搜索文档' },
              modal: {
                noResultsText: '无匹配结果',
                resetButtonTitle: '清除查询条件',
                footer: { selectText: '选择', navigateText: '切换', closeText: '关闭' },
              },
            },
          },
        },
      },
    },

    outline: { level: [2, 3], label: '本页目录' },
    docFooter: { prev: '上一篇', next: '下一篇' },
    lastUpdated: { text: '最后更新' },
    returnToTopLabel: '回到顶部',
    sidebarMenuLabel: '菜单',
    darkModeSwitchLabel: '主题',

    footer: {
      message: 'WorldNovel — 多 Agent 长篇小说自动生成系统（开源）',
      copyright: 'MIT License',
    },
  },
})
