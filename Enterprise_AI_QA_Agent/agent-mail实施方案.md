# Agent Mail 统一接入实施方案

## 1. 产品模型

Agent Mail 是系统级资源，不绑定某一个 Agent。

```text
所有 Agent / 所有运行模式
        ↓
统一 mail-* 工具（通过 mail-capability Skill 延迟加载）
        ↓
MailService 公共安全与确认层
        ↓
全局唯一激活的邮箱配置
        ↓
对应供应商 Adapter
```

系统允许保存多个供应商、多个邮箱配置，但任一时刻只能激活一个。未激活邮箱只能进行配置、授权、状态检查和厂商 Inbox 创建，不允许收信、读信、发信、回复、转发、删除或下载附件。

新建邮箱配置不会自动替换当前邮箱。管理员确认新邮箱可用后，通过“设为当前”完成全局切换。

## 2. 统一公共 API

系统内部只暴露以下供应商无关能力：

```text
mail-status
mail-send
mail-confirm
mail-list
mail-read
mail-search
mail-reply
mail-forward
mail-trash
mail-download-attachment
```

供应商不支持某项能力时统一返回：

```json
{"ok": false, "error": "capability_not_supported"}
```

所有写操作统一采用两阶段确认：

1. `mail-send/reply/forward/trash` 只生成预览与 confirmation token。
2. 用户明确确认后调用 `mail-confirm`。
3. 腾讯 Agent Mail 使用官方 CLI token。
4. REST 厂商使用系统生成的一次性 token。
5. token 有效期内如果全局邮箱发生切换，token 立即失效。

## 3. Provider 目录

所有供应商实现统一位于：

```text
Agent_Server/src/infrastructure/mail/providers/
  tencent_agently.py
  agentmail.py
  robotomail.py
  openmail.py
  dead_simple_email.py
  agenticmail.py
  aws_agent_mailbox.py
  rest_base.py
  configured_rest.py
```

公共契约位于：

```text
Agent_Server/src/application/mail/contracts.py
Agent_Server/src/application/mail/provider_registry.py
Agent_Server/src/application/mail/mail_service.py
```

## 4. 当前供应商适配状态

| Provider | 接入类型 | 实现状态 |
|---|---|---|
| 腾讯 Agent Mail | `agently-cli` + OAuth | 原生适配；CLI 从服务器 PATH 查找，凭据目录按邮箱配置隔离 |
| AgentMail | 官方 REST API | 原生适配；使用 `https://api.agentmail.to/v0/inboxes/{inbox_id}/...`，支持发送、列表、读取、搜索、回复、转发、删除和附件 |
| Robotomail | 官方 REST API | 原生适配；使用 `https://api.robotomail.com/v1/mailboxes/{id}/...`，按 RFC Message-ID 回复；官方未提供转发和消息删除接口 |
| OpenMail | 官方 REST API | 原生适配；使用 `https://api.openmail.sh/v1/...`，发送请求自动携带 `Idempotency-Key`；官方未提供转发和消息删除接口 |
| Dead Simple Email | 官方 REST API | 原生适配；使用 `https://api.deadsimple.email/v1/...`，支持发送、读取、回复、转发和附件；官方未提供消息删除接口 |
| AgenticMail | 自托管 REST | 独立配置型适配器；需填写部署地址、Mailbox ID 和 routes |
| AWS Agent Mailbox | HTTP API | 独立配置型适配器；需填写实际网关、Mailbox ID 和 routes |

四家 REST 原生适配分别以官方文档和 OpenAPI 为准，不再要求用户填写 routes。AgenticMail 和 AWS Agent Mailbox 仍没有已确认的统一公开协议，因此继续使用显式路由映射，避免伪造固定 URL。

官方协议来源：

- OpenMail：<https://docs.openmail.sh/pages/welcome>
- Dead Simple Email：<https://deadsimple.email/api-reference.html>
- Robotomail：<https://robotomail.com/docs>
- AgentMail：<https://docs.agentmail.to/welcome>

路由映射示例：

```json
{
  "base_url": "https://vendor.example/api",
  "mailbox_id": "mbx_123",
  "routes": {
    "send": "/mailboxes/{mailbox_id}/messages",
    "list": "/mailboxes/{mailbox_id}/messages",
    "read": "/mailboxes/{mailbox_id}/messages/{message_id}",
    "search": "/mailboxes/{mailbox_id}/messages/search",
    "reply": "/mailboxes/{mailbox_id}/messages/{message_id}/reply",
    "forward": "/mailboxes/{mailbox_id}/messages/{message_id}/forward",
    "trash": "/mailboxes/{mailbox_id}/messages/{message_id}",
    "attachment": "/mailboxes/{mailbox_id}/messages/{message_id}/attachments/{attachment_id}"
  }
}
```

## 5. 腾讯部署规则

`agently-cli` 是 Agent Server 的部署依赖，不由前端安装，也不允许用户填写本机 CLI Path。

```bash
npm install -g @tencent-qqmail/agently-cli
```

后端只从服务器 PATH 解析命令。OAuth URL 必须原样返回前端，不得重新编码或拼接。

现有服务器 DPAPI 授权可继续使用；新建腾讯邮箱配置使用独立 `AGENTLY_CLI_CONFIG_DIR`，不同邮箱的 OAuth 凭据互不覆盖。

## 6. 设置页面

邮件设置页负责：

- 展示所有供应商邮箱配置。
- 标记唯一“当前使用”邮箱。
- 新建全局邮箱配置，不显示所属 Agent。
- 腾讯邮箱执行 OAuth 登录与状态检查。
- AgentMail 填写 API Key、绑定现有 Inbox 或调用官方 API 创建 Inbox。
- 配置型供应商填写 Base URL、Mailbox ID 与 routes。
- 将已验证的邮箱“设为当前”。
- 删除配置；删除当前邮箱后保持“无当前邮箱”，直到管理员显式选择新的当前邮箱。

## 7. 验收标准

- Provider Registry 注册 7 个 Agent Mail Adapter。
- 设置页没有 Agent 选择器和按 Agent 绑定文案。
- 数据库最多只有一个 `enabled/is_default` 邮箱。
- 未激活邮箱通过 `MailService` 指定 config ID 也会被拒绝。
- 所有模式通过同一个 `mail-capability` Skill 加载邮件工具。
- 所有供应商写操作都必须经过两阶段确认。
- 切换邮箱后旧 confirmation token 失效。
- API Key、OAuth token、服务器凭据目录不通过设置 API 回显。
