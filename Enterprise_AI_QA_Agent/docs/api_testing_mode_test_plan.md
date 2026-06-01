# API Testing Mode 测试流程与测试方案

> 版本：v1.0  
> 最后更新：2026-05-11  
> 适用范围：`Agent_Server/src/modes/api_testing_mode` 全模块

---

## 一、测试体系总览

### 1.1 测试分层

```
┌─────────────────────────────────────────────────────────┐
│ Layer 4: 手动验收测试 (Manual Acceptance)                │
│   真实环境 + 真实 API 文档 + 真实 HTTP 调用              │
├─────────────────────────────────────────────────────────┤
│ Layer 3: 端到端集成测试 (E2E Integration)                │
│   Mock ApiDocsService + Mock httpx + 完整状态机流转      │
├─────────────────────────────────────────────────────────┤
│ Layer 2: 模块集成测试 (Module Integration)               │
│   多模块协作验证（如 planner + pool + coordinator）      │
├─────────────────────────────────────────────────────────┤
│ Layer 1: 单元测试 (Unit Tests)                           │
│   单模块逻辑验证，无外部依赖                             │
└─────────────────────────────────────────────────────────┘
```

### 1.2 测试文件清单

| 文件 | 层级 | 测试数 | 覆盖模块 |
|------|------|--------|---------|
| `test_capability_mapper.py` | L1 | 10 | 能力映射规则 |
| `test_selection_resolver.py` | L1 | 12 | 用户选择解析 |
| `test_task_pool.py` | L1 | 7 | 任务状态流转 |
| `test_dependency_planner.py` | L1+L2 | 5 | 依赖图生成 |
| `test_executor.py` | L1 | 11 | 断言评估引擎 |
| `test_coordinator.py` | L2 | 5 | 并发调度 + InputBinding |
| `test_credential_manager.py` | L1 | 8 | 凭证管理 |
| `test_runtime_integration.py` | L3 | 15 | 端到端状态机 |
| **合计** | | **73** | |

---

## 二、单元测试方案 (Layer 1)

### 2.1 capability_mapper 测试

**目标**：验证端点到业务能力的映射规则正确性。

| 用例 ID | 输入 | 期望输出 | 验证点 |
|---------|------|---------|--------|
| CM-01 | `POST /api/auth/login` | `login` | 路径规则匹配 |
| CM-02 | `POST /api/v1/session` + summary="用户登录" | `login` | 摘要关键词匹配 |
| CM-03 | `POST /api/orders` | `create` | POST 方法默认 |
| CM-04 | `GET /api/orders` | `list` | GET 无路径参数 |
| CM-05 | `GET /api/orders/{id}` | `detail` | GET 有路径参数 |
| CM-06 | `DELETE /api/orders/{id}` | `delete` | DELETE 方法 |
| CM-07 | `PUT /api/orders/{id}` | `update` | PUT 方法 |
| CM-08 | `GET /api/orders/search` | `search` | search 路径 |
| CM-09 | `POST /api/payment/pay` | `pay` | pay 路径 |
| CM-10 | 批量 4 个端点 | 正确映射列表 | map_many 批量 |

**运行命令**：
```bash
pytest tests/modes/api_testing_mode/test_capability_mapper.py -v
```

### 2.2 selection_resolver 测试

**目标**：验证用户回复解析的准确性和鲁棒性。

| 用例 ID | 场景 | 输入 | 期望 |
|---------|------|------|------|
| SR-01 | 数字选择 | "1" | 选中第一个选项 |
| SR-02 | 数字选择 | "2" | 选中第二个选项 |
| SR-03 | 确认默认 | "确认" | 选中推荐选项 |
| SR-04 | 名称匹配 | "用户服务" | 匹配对应项目 |
| SR-05 | 无法识别 | "不知道" | resolved=False |
| SR-06 | 核心范围 | "核心接口" | scope=core_only |
| SR-07 | 全部范围 | "全部" | scope=all_related |
| SR-08 | 手动范围 | "手动挑选" | scope=manual_pick |
| SR-09 | 确认范围 | "好的" | 使用推荐范围 |
| SR-10 | Bearer Token | "Bearer eyJ..." | 提取 token |
| SR-11 | 用户名密码 | "username=admin password=123" | 提取 basic auth |
| SR-12 | 裸 Token | 长字符串 | 识别为 bearer |

**运行命令**：
```bash
pytest tests/modes/api_testing_mode/test_selection_resolver.py -v
```

### 2.3 task_pool 测试

**目标**：验证任务生命周期状态机的正确性。

| 用例 ID | 场景 | 验证点 |
|---------|------|--------|
| TP-01 | 初始 ready 任务 | ready_tasks() 返回正确 |
| TP-02 | 完成释放依赖 | blocked → ready |
| TP-03 | 失败跳过依赖 | blocked → skipped（级联） |
| TP-04 | 全部终态 | is_complete = True |
| TP-05 | 有未完成 | is_complete = False |
| TP-06 | 多依赖解锁 | 两个依赖都完成才释放 |
| TP-07 | 状态统计 | summary() 计数正确 |

**运行命令**：
```bash
pytest tests/modes/api_testing_mode/test_task_pool.py -v
```

### 2.4 executor 断言测试

**目标**：验证 7 种断言类型的评估逻辑。

| 用例 ID | 断言类型 | 场景 | 期望 |
|---------|---------|------|------|
| EX-01 | status_code | 200 == 200 | passed |
| EX-02 | status_code | 404 != 200 | failed |
| EX-03 | status_code_range | 201 in [200,201,204] | passed |
| EX-04 | json_field_present | data.id 存在 | passed |
| EX-05 | json_field_present | data.id 不存在 | failed |
| EX-06 | json_field_equals | status == "active" | passed |
| EX-07 | body_contains | 包含 "successfully" | passed |
| EX-08 | response_time_ms | 150ms < 1000ms | passed |
| EX-09 | response_time_ms | 6000ms > 5000ms | failed |
| EX-10 | 无断言 + 200 | 默认 2xx 检查 | passed |
| EX-11 | 无断言 + 500 | 默认 2xx 检查 | failed |

**运行命令**：
```bash
pytest tests/modes/api_testing_mode/test_executor.py -v
```

### 2.5 credential_manager 测试

**目标**：验证凭证创建、存储和检索。

| 用例 ID | 场景 | 验证点 |
|---------|------|--------|
| CR-01 | Bearer Token 创建 | headers 包含 Authorization |
| CR-02 | Basic Auth 创建 | Base64 编码正确 |
| CR-03 | 登录响应提取 | access_token 字段提取 |
| CR-04 | 登录响应 fallback | 扫描含 "token" 的字段 |
| CR-05 | has_valid_session | 有/无凭证判断 |
| CR-06 | build_request_headers | 构建请求头 |
| CR-07 | get_latest | 返回最新凭证 |
| CR-08 | clear | 清空所有凭证 |

**运行命令**：
```bash
pytest tests/modes/api_testing_mode/test_credential_manager.py -v
```

---

## 三、模块集成测试方案 (Layer 2)

### 3.1 dependency_planner 测试

**目标**：验证依赖图构建规则（需要 capability_mapper 协作）。

| 用例 ID | 场景 | 验证点 |
|---------|------|--------|
| DP-01 | 含 login 端点 | auth task 状态为 ready |
| DP-02 | 非 auth 依赖 auth | depends_on 包含 auth task |
| DP-03 | 写任务串行 | 第二个 write 依赖第一个 |
| DP-04 | 读任务独立 | 无依赖，全部 ready |
| DP-05 | base_url 拼接 | full_url 正确生成 |

### 3.2 coordinator 测试

**目标**：验证并发调度策略和数据传递。

| 用例 ID | 场景 | 验证点 |
|---------|------|--------|
| CO-01 | 全部 ready | 并行执行完成 |
| CO-02 | auth 优先 | auth 先执行，其他等待 |
| CO-03 | auth 失败 | 依赖任务被 skip |
| CO-04 | 写串行 | 按顺序执行 |
| CO-05 | InputBinding | {id} 占位符被替换 |

**运行命令**：
```bash
pytest tests/modes/api_testing_mode/test_dependency_planner.py tests/modes/api_testing_mode/test_coordinator.py -v -k "not trio"
```

---

## 四、端到端集成测试方案 (Layer 3)

### 4.1 测试环境

- **ApiDocsService**：Mock 实现，返回预定义的 Markdown 文档
- **httpx**：Mock 实现，返回预定义的 HTTP 响应
- **状态持久化**：通过 `context_bundle` 模拟跨 turn 传递

### 4.2 测试场景矩阵

#### 场景组 A：项目发现与选择

| 用例 ID | 场景 | 前置条件 | 操作 | 期望结果 |
|---------|------|---------|------|---------|
| E2E-A01 | 单项目自动选择 | 1 个项目文档 | 发送"测试订单服务" | 跳过项目选择，进入范围澄清 |
| E2E-A02 | 多项目需澄清 | 2 个项目文档 | 发送"测试接口" | phase=awaiting_project_selection |
| E2E-A03 | 项目选择解析 | 处于 awaiting_project | 发送"1" | 选中第一个项目，推进 |

#### 场景组 B：范围选择

| 用例 ID | 场景 | 前置条件 | 操作 | 期望结果 |
|---------|------|---------|------|---------|
| E2E-B01 | 范围澄清触发 | 7 个端点 | 自动 | phase=awaiting_endpoint_scope |
| E2E-B02 | 核心范围选择 | 处于 awaiting_scope | 发送"核心接口" | 选中 core 端点 |
| E2E-B03 | 全部范围选择 | 处于 awaiting_scope | 发送"全部" | 选中所有端点 |
| E2E-B04 | 手动挑选 | 处于 awaiting_scope | 发送"手动挑选" | phase=awaiting_endpoint_selection |

#### 场景组 C：凭证处理

| 用例 ID | 场景 | 前置条件 | 操作 | 期望结果 |
|---------|------|---------|------|---------|
| E2E-C01 | 认证检测 | 端点需要 auth | 自动 | phase=awaiting_auth_input |
| E2E-C02 | Token 输入 | 处于 awaiting_auth | 发送 Bearer token | 推进到 campaign_ready |

#### 场景组 D：执行与报告

| 用例 ID | 场景 | 前置条件 | 操作 | 期望结果 |
|---------|------|---------|------|---------|
| E2E-D01 | 全量执行 | 凭证就绪 + mock HTTP 200 | 自动 | phase=report_ready + 报告 |
| E2E-D02 | 单端点执行 | 指定 method+path | 自动 | 报告含 1 个 task |

#### 场景组 E：状态恢复

| 用例 ID | 场景 | 前置条件 | 操作 | 期望结果 |
|---------|------|---------|------|---------|
| E2E-E01 | 跨 turn 持久化 | Turn 1 产出 state | Turn 2 读取 | state 正确恢复 |
| E2E-E02 | 终态重置 | phase=report_ready | 新请求 | 重新开始 |

#### 场景组 F：异常处理

| 用例 ID | 场景 | 前置条件 | 操作 | 期望结果 |
|---------|------|---------|------|---------|
| E2E-F01 | 无文档 | 空文档库 | 发送请求 | phase=failed |
| E2E-F02 | 无效选择 | 处于 awaiting | 发送乱码 | 重新提示选择 |

**运行命令**：
```bash
pytest tests/modes/api_testing_mode/test_runtime_integration.py -v -k "not trio"
```

---

## 五、手动验收测试方案 (Layer 4)

### 5.1 前置条件

1. 后端服务启动：`uvicorn src.main:app --reload --port 8000`
2. 前端服务启动：`npm run dev`（agent_web）
3. 至少上传 1 份 API 文档到系统（通过 Tools > API 接口文档）
4. 至少配置 1 个激活的 LLM 模型（通过 Settings > 模型管理）
5. 目标 API 服务可访问

### 5.2 验收场景

#### 场景 1：单项目单接口测试

**步骤**：
1. 在前端选择"API接口测试模式"
2. 输入："帮我测试一下 GET /api/products 接口"
3. 观察系统是否自动识别项目和端点
4. 如果需要凭证，提供 Token
5. 等待执行完成

**验收标准**：
- [ ] 系统正确识别目标端点
- [ ] 如果只有一个项目，不询问项目选择
- [ ] 如果端点不需要 auth，直接执行
- [ ] 报告包含状态码、响应时间、断言结果
- [ ] 报告格式清晰可读

#### 场景 2：多接口核心范围测试

**步骤**：
1. 输入："帮我测试一下订单服务的核心接口"
2. 如果多项目，选择正确项目
3. 确认"核心接口"范围
4. 提供凭证（如需要）
5. 等待并行执行完成

**验收标准**：
- [ ] 系统正确筛选 core 能力端点（login/list/detail/create/search）
- [ ] login 端点最先执行
- [ ] 读接口并行执行
- [ ] 写接口串行执行
- [ ] 报告包含所有 task 的结果汇总

#### 场景 3：全量接口测试

**步骤**：
1. 输入："测试订单服务全部接口"
2. 选择"全部"范围
3. 提供凭证
4. 等待执行

**验收标准**：
- [ ] 所有端点都被测试
- [ ] 依赖关系正确（login → create → query）
- [ ] 并发策略正确（读并行、写串行）
- [ ] 报告包含通过/失败/跳过统计
- [ ] 失败的 task 有错误原因和证据

#### 场景 4：动态登录流

**步骤**：
1. 上传包含 login 接口的 API 文档
2. 输入："测试订单服务"
3. 选择范围后，系统检测到需要 auth
4. 不提供 token，而是让系统自动执行 login 接口

**验收标准**：
- [ ] 系统识别 login 端点
- [ ] 自动执行 login 获取 token
- [ ] token 自动注入后续请求
- [ ] 后续接口正常执行

#### 场景 5：多轮对话状态恢复

**步骤**：
1. Turn 1：输入"测试接口"→ 系统返回项目候选
2. Turn 2：输入"1"→ 选择项目
3. Turn 3：输入"核心接口"→ 选择范围
4. Turn 4：输入 Token → 提供凭证
5. 系统执行并返回报告

**验收标准**：
- [ ] 每一轮的选择都被正确记住
- [ ] 不会重复询问已回答的问题
- [ ] 最终报告反映所有选择

#### 场景 6：错误恢复

**步骤**：
1. 输入无效选择（如在项目选择时输入乱码）
2. 观察系统是否友好提示重新选择
3. 输入正确选择后继续

**验收标准**：
- [ ] 无效输入不会导致系统崩溃
- [ ] 系统给出明确的重新选择提示
- [ ] 正确输入后流程继续

#### 场景 7：目标服务不可达

**步骤**：
1. 配置一个不可达的 project_url
2. 执行测试

**验收标准**：
- [ ] 系统不会无限等待
- [ ] 超时后标记 task 为 failed
- [ ] 报告中明确标注连接/超时错误
- [ ] 验证结论标记为"环境问题"

---

## 六、测试数据准备

### 6.1 标准测试文档

系统中应至少准备以下测试文档：

| 文档 | 内容 | 用途 |
|------|------|------|
| `openapi.md` | 完整的订单服务 API（7+ 端点） | 主要测试文档 |
| `user_api.md` | 用户服务 API（3 端点） | 多项目测试 |
| `simple_api.md` | 单个无 auth 端点 | 最简流程测试 |

### 6.2 Mock HTTP 响应模板

```python
# 成功响应
{"status_code": 200, "body": {"id": 1, "status": "ok"}}

# 认证失败
{"status_code": 401, "body": {"error": "unauthorized"}}

# 服务端错误
{"status_code": 500, "body": {"error": "internal_server_error"}}

# 超时
httpx.TimeoutException("Request timed out")
```

---

## 七、测试执行指南

### 7.1 运行全部自动化测试

```bash
cd Agent_Server
python -m pytest tests/modes/api_testing_mode/ -v -k "not trio"
```

### 7.2 运行特定层级

```bash
# Layer 1: 单元测试
python -m pytest tests/modes/api_testing_mode/ -v -k "not trio and not integration and not coordinator"

# Layer 2: 模块集成
python -m pytest tests/modes/api_testing_mode/test_coordinator.py tests/modes/api_testing_mode/test_dependency_planner.py -v -k "not trio"

# Layer 3: 端到端
python -m pytest tests/modes/api_testing_mode/test_runtime_integration.py -v -k "not trio"
```

### 7.3 运行带覆盖率

```bash
pip install pytest-cov
python -m pytest tests/modes/api_testing_mode/ -v -k "not trio" --cov=src.modes.api_testing_mode --cov-report=term-missing
```

### 7.4 运行特定场景

```bash
# 只跑项目选择相关
python -m pytest tests/modes/api_testing_mode/test_runtime_integration.py -v -k "project"

# 只跑执行相关
python -m pytest tests/modes/api_testing_mode/test_runtime_integration.py -v -k "execution"

# 只跑断言相关
python -m pytest tests/modes/api_testing_mode/test_executor.py -v
```

---

## 八、质量门禁

### 8.1 合并前必须通过

| 检查项 | 标准 | 阻断级别 |
|--------|------|---------|
| 全部自动化测试通过 | 73/73 passed | 🔴 阻断 |
| 无新增 import 错误 | 所有模块可导入 | 🔴 阻断 |
| 核心场景手动验证 | 场景 1-3 通过 | 🔴 阻断 |
| 状态恢复验证 | 场景 5 通过 | 🟠 高优 |
| 错误恢复验证 | 场景 6 通过 | 🟠 高优 |
| 性能基线 | 单端点 < 30s | 🟡 建议 |

### 8.2 回归测试触发条件

以下改动必须重新运行全部测试：

- 修改 `runtime.py`
- 修改 `coordinator.py` 或 `executor.py`
- 修改 `task_pool.py`
- 修改 `campaign_state.py` 或 `contracts.py`
- 修改 `tool_runtime_service.py` 中 api-test-runner 相关代码

---

## 九、已知测试边界

| 边界 | 说明 | 风险 |
|------|------|------|
| 真实 HTTP 未覆盖 | 集成测试使用 mock httpx | 低（executor 逻辑已验证） |
| 并发竞态 | 测试中 asyncio.sleep 模拟 | 中（生产环境需观察） |
| 大文档解析 | 未测试 > 100 端点的文档 | 低（性能问题） |
| 凭证过期 | 未测试 token 过期后重新登录 | 中（后续迭代） |
| 网络抖动 | 未测试间歇性超时 | 低（重试机制已实现） |

---

## 十、测试维护指南

### 10.1 新增端点能力映射规则时

1. 在 `test_capability_mapper.py` 中添加对应用例
2. 确保新规则不破坏已有映射

### 10.2 新增断言类型时

1. 在 `executor.py` 的 `_check_assertion` 中实现
2. 在 `test_executor.py` 中添加 passed + failed 两个用例

### 10.3 修改状态机流转时

1. 更新 `test_runtime_integration.py` 中受影响的场景
2. 确保所有 awaiting phase 都有对应的"选择后推进"测试

### 10.4 新增选择类型时

1. 在 `selection_resolver.py` 中实现解析逻辑
2. 在 `test_selection_resolver.py` 中添加正向 + 负向用例
