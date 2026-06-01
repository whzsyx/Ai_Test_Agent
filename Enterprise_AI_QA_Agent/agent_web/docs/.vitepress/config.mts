import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'

export default withMermaid(defineConfig({
  srcDir: '../../docs',
  title: "御策天检 Docs",
  description: "Enterprise AI QA Agent 文档",
  vite: {
    optimizeDeps: {
      include: ['mermaid', 'dayjs']
    }
  },
  themeConfig: {
    nav: [
      { text: '首页', link: '/' },
      { text: '系统使用与开发手册', link: '/manual/1._系统概述' }
    ],
    sidebar: [
      {
        text: '系统使用与开发手册',
        items: [
          { text: '前言', link: '/manual/0.前言与目录' },
          { text: '1. 系统概述', link: '/manual/1._系统概述' },
          { text: '2. 整体架构', link: '/manual/2._整体架构' },
          { text: '3. 快速开始', link: '/manual/3._快速开始' },
          { text: '4. 核心概念', link: '/manual/4._核心概念' },
          { text: '5. 测试模式详解', link: '/manual/5._测试模式详解' },
          { text: '6. 前端工作台指南', link: '/manual/6._前端工作台使用指南' },
          { text: '7. 后端服务与运行时', link: '/manual/7._后端服务与运行时' },
          { text: '8. 能力体系', link: '/manual/8._Agent__Tool__Skill__MCP_能力体系' },
          { text: '9. 配置参考', link: '/manual/9._配置参考' },
          { text: '10. REST API 参考', link: '/manual/10._REST_API_参考' },
          { text: '11. 数据与存储', link: '/manual/11._数据与存储' },
          { text: '12. 二次开发指南', link: '/manual/12._二次开发指南' },
          { text: '13. Harness 工程规范', link: '/manual/13._Harness_工程规范' },
          { text: '14. 常见问题与排障', link: '/manual/14._常见问题与排障' },
          { text: '15. 术语表', link: '/manual/15._术语表' },
        ]
      }
    ]
  }
}))
