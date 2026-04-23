# Enterprise AI QA Agent Server

一个面向企业级 Agent 测试平台的后端运行时，目标是用 `FastAPI + LangGraph` 复刻类似 Claude Code 的核心组织方式，并沉淀可观测、可审批、可恢复、可扩展的 QA Agent Harness。

## 当前包含

- 会话管理：创建会话、读取会话、发送消息
- Agent 注册中心：先以内置占位模块呈现，后续可扩展
- Tool 注册中心：维护工具能力声明
- LangGraph 编排：`context_builder -> router -> planner -> permission_gate -> prompt_assembler -> model_invoker -> tool_executor -> finalizer -> responder`
- SSE 事件流：前端可以实时看到节点执行状态
- ArangoDB 会话、事件、快照、审批、工具任务与 Memory 存储
- MySQL 模型配置与邮件通道配置
- 工具审批、恢复、中断、回放与基础验证结果

## 目录结构

```text
src/
  api/            FastAPI 路由层
  application/    应用服务层，按职责拆分为子包
  core/           配置
  domain/         领域模型
  graph/          LangGraph 状态图与节点
  registry/       Agent/Tool 注册中心
  runtime/        存储与流式事件
  schemas/        Pydantic 输入输出
```

`application/` 子包职责：

```text
application/
  artifacts/       Artifact 存储服务
  context/         Memory、MCP、Observation、Transcript Hygiene
  models/          模型运行时与模型兼容性
  model_adapters/  OpenAI/Anthropic/Gemini 等 provider adapter
  orchestration/   输入编排、Coordinator/Worker 调度
  permissions/     工具权限策略与审批请求
  prompting/       Prompt submit 与结构化 prompt 组装
  registries/      Registry 聚合查询服务
  runtime/         Turn runtime、工具运行时、工具任务、Playwright CLI
  sessions/        会话用例服务
  settings/        模型/邮件系统配置服务
  skills/          Skill 运行、管理与 marketplace
  testing/         QA 方向识别、测试路由、验证与 UI 探索
```

说明：`testing/direction_service.py` 与 `testing/router_service.py` 是输入编排的一部分，用于把用户任务识别为 UI/API/安全/性能等 QA 方向并路由到合适 Agent，不是单元测试文件。

## 启动

```bash
cd Agent_Server
uvicorn src.main:app --reload --port 8000
```

## 后续接入建议

1. 在 `src/registry/agents.py` 注册真实 Agent 模块元数据。
2. 在 `src/registry/tools.py` 声明工具协议，并在 `application/runtime/tool_runtime_service.py` 绑定运行时处理器。
3. 在 `application/testing/verification_service.py` 补充工具结果到验证结果的结构化映射。
4. 若需要真正的多 Agent 协同，可继续扩展 `application/orchestration/coordinator_runtime_service.py` 与 `subagent-dispatch`。
