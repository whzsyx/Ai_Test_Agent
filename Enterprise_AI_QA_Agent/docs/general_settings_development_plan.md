# 通用设置后续开发文档

## 当前已完成范围

本阶段先完成前端页面与本地持久化骨架，入口位于设置页侧边栏第一项“通用设置”。

- 前端页面：`agent_web/src/features/settings/plugins/GeneralSettingsPlugin.vue`
- 前端状态：`agent_web/src/stores/generalSettings.ts`
- 插件注册：`agent_web/src/features/settings/plugins.ts`
- 全局加载：`agent_web/src/main.ts`
- 全局样式变量：`agent_web/src/styles.css`

当前持久化方式为浏览器 `localStorage`，key 为：

```text
enterprise-ai-qa-agent-general-settings
```

当前已动态应用的全局能力：

- `document.documentElement.lang`
- `data-app-language`
- `data-app-font`
- `data-reduce-motion`
- `--app-font-family`
- `--app-font-size-scale`

## 设置数据模型

```ts
interface GeneralSettingsSnapshot {
  language: string;
  modelOutputLanguage: string;
  notifySessionCompleteWhenAway: boolean;
  notifyApprovalRequiredWhenAway: boolean;
  notificationsAwayOnly: boolean;
  fontFamily: "system" | "chinese" | "mono";
  fontSize: "compact" | "standard" | "comfortable";
  reduceMotion: boolean;
  lastSavedAt: string;
}
```

## 后端持久化建议

明天可以新增一个轻量用户偏好接口，不需要马上做复杂账号体系。

建议接口：

```text
GET  /api/v1/settings/general
PUT  /api/v1/settings/general
```

建议存储方式：

- 短期：新增 `system_user_settings` 或复用现有配置表，以 `key/value JSON` 形式保存。
- 当前无多用户隔离时：使用固定 key，例如 `default.general_settings`。
- 未来有登录用户后：增加 `user_id` 或 `workspace_id` 维度。

前端迁移方式：

1. 启动时优先拉取后端设置。
2. 后端没有值时读取 `localStorage` 作为迁移来源。
3. 保存成功后同时更新 Pinia 状态和 `localStorage` 缓存。
4. 后端失败时允许回退到本地保存，并给出降级提示。

## 桌面通知接入计划

当前页面只负责保存开关和申请浏览器通知权限，真实弹窗需要接运行时事件。

触发条件：

- `notifySessionCompleteWhenAway = true`
- `notifyApprovalRequiredWhenAway = true`
- 浏览器通知权限为 `granted`
- 当 `notificationsAwayOnly = true` 时，需要满足用户不在当前界面

“不在当前界面”的建议判断：

- `document.visibilityState !== "visible"`
- 或当前路由不是对应会话详情页
- 或当前活跃 session id 与事件 session id 不一致

建议监听事件：

- 会话完成：`runtime.turn_completed`、`turn.completed`、会话状态变为 `completed`
- 审批待处理：`approval.required`、`pending_approvals.length > 0`

建议新增前端服务：

```text
agent_web/src/services/desktopNotifications.ts
```

服务职责：

- 读取 `useGeneralSettingsStore`
- 判断是否允许弹窗
- 统一生成 `new Notification(title, options)`
- 点击通知后跳转到对应会话或审批位置
- 防重复提醒，同一 `turn_id` 或 `approval_id` 只提醒一次

## 字体与语言全局支持计划

当前字体已通过 CSS 变量即时应用，但完整系统语言还需要 i18n。语言设置拆成两层：`language` 控制系统本身界面语言，`modelOutputLanguage` 控制大模型默认输出语言。

建议后续步骤：

1. 引入或整理 i18n 资源文件，例如 `src/locales/zh-CN.ts`、`src/locales/en-US.ts`。
2. 通用设置保存后调用 i18n runtime 切换语言。
3. 模型调用前读取 `modelOutputLanguage`，当不为 `follow-system` 时注入系统提示或 runtime context。
4. 后端返回的系统提示、错误信息逐步增加可翻译 message key。
5. 字体设置继续通过 `--app-font-family` 和 `--app-font-size-scale` 全局应用。

## 数据管理按钮后续接口

当前页面只预留按钮，不执行真实数据操作，避免误清理。

建议接口：

```text
POST /api/v1/data/export
POST /api/v1/data/import
POST /api/v1/data/cleanup/sessions
```

建议安全约束：

- 清理前必须二次确认。
- 清理前建议自动生成一次备份。
- 清理接口支持 dry-run，先返回影响范围。
- 导入接口先校验版本、schema、文件完整性，再写入。
- 所有数据管理操作写入审计日志。

建议导出内容：

- 会话消息
- 运行时事件
- 快照
- 工具任务与文件产物索引
- API 文档元数据
- 用户设置

## 明天开发顺序

1. 后端新增通用设置读写接口。
2. 前端 `generalSettings` store 从 `localStorage-only` 改成 `backend-first`。
3. 接入桌面通知服务，并监听会话完成和审批待处理事件。
4. 数据管理按钮接入后端占位接口，清理操作先做 dry-run 和确认弹窗。
5. 补最小测试：store normalize、接口读写、通知触发条件、数据管理按钮禁误触。
