import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'

// 该配置在 Node 环境执行;此处声明 process 以避免缺少 @types/node 时的类型告警。
declare const process: { env: Record<string, string | undefined> }

// 系统工作台地址,可通过环境变量覆盖(默认指向本地 dev 端口)。
const APP_HOME_URL = process.env.DOCS_APP_URL ?? 'http://localhost:5175/home'

export default withMermaid(defineConfig({
  title: "御策天检 Docs",
  description: "Enterprise AI QA Agent 文档",
  head: [
    ['link', { rel: 'icon', type: 'image/svg+xml', href: '/logo.svg' }]
  ],
  vite: {
    optimizeDeps: {
      // mermaid 会懒加载 dayjs(CommonJS),必须强制预打包,
      // 否则浏览器端会因缺少 default 导出而报 SyntaxError。
      include: ['mermaid', 'dayjs'],
    },
    ssr: {
      // 让 mermaid 在 SSR 阶段也走打包而非外部化,保证构建一致。
      noExternal: ['mermaid'],
    },
  },
  themeConfig: {
    logo: '/logo.svg',
    nav: [
      { text: '首页', link: '/' },
      { text: '系统使用与开发手册', link: '/docs/1._系统概述' },
      { text: '返回系统', link: APP_HOME_URL, target: '_self', rel: 'noopener' }
    ],
    sidebar: [
      {
        text: '系统使用与开发手册',
        items: [
          { text: '前言', link: '/docs/0.前言与目录' },
          { text: '1. 系统概述', link: '/docs/1._系统概述' },
          { text: '2. 整体架构', link: '/docs/2._整体架构' },
          { text: '3. 快速开始', link: '/docs/3._快速开始' },
          { text: '4. 核心概念', link: '/docs/4._核心概念' },
          { text: '5. 测试模式详解', link: '/docs/5._测试模式详解' },
          { text: '6. 前端工作台指南', link: '/docs/6._前端工作台使用指南' },
          { text: '7. 后端服务与运行时', link: '/docs/7._后端服务与运行时' },
          { text: '8. 能力体系', link: '/docs/8._Agent__Tool__Skill__MCP_能力体系' },
          { text: '9. 配置参考', link: '/docs/9._配置参考' },
          { text: '10. REST API 参考', link: '/docs/10._REST_API_参考' },
          { text: '11. 数据与存储', link: '/docs/11._数据与存储' },
          { text: '12. 二次开发指南', link: '/docs/12._二次开发指南' },
          { text: '13. Harness 工程规范', link: '/docs/13._Harness_工程规范' },
          { text: '14. 常见问题与排障', link: '/docs/14._常见问题与排障' },
          { text: '15. 术语表', link: '/docs/15._术语表' },
        ]
      }
    ]
  }
}))
