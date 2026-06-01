# 安全测试模式开发进度

## 对照开发文档 23.6 实施顺序

### 第 1 步：contracts.py、campaign_state.py ✅ 已完成

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/modes/security_testing_mode/contracts.py` | ✅ 完成 | Phase 常量、任务状态、风险级别、Surface 类型、工具族映射、Worker 常量 |
| `src/modes/security_testing_mode/campaign_state.py` | ✅ 完成 | 全部 Pydantic 模型：Request、Target、Asset、Fingerprint、Credential、Task、Finding、Evidence、Activity、Campaign、Report、State |

### 第 2 步：runtime.py 基础 phase machine ⏳ 待完成

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/modes/security_testing_mode/runtime.py` | ❌ 未开始 | 模式总入口、状态恢复、phase machine 推进 |

### 第 3 步：tool_catalog.py、command_profiles.py ✅ 已完成

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/application/security/command_profiles.py` | ✅ 完成 | 16 个 Phase 1 命令 profile（nmap×4、httpx、whatweb、ffuf、gobuster、nikto、nuclei×2、sqlmap、sslscan、searchsploit、hydra） |
| `src/application/security/tool_catalog.py` | ✅ 完成 | Surface→Family 映射、Family→Runner 映射、profile 查询 |
| `src/application/security/result_parsers.py` | ✅ 完成 | 11 个解析器（nmap、httpx、whatweb、ffuf、gobuster、nikto、nuclei、sqlmap、hydra、sslscan、searchsploit） |
| `src/application/security/risk_policy.py` | ✅ 完成 | 审批策略、环境限制、并发控制 |
| `src/application/security/finding_normalizer.py` | ✅ 完成 | 从 nmap/nuclei/sqlmap/nikto/hydra/http_headers 归一化为 FindingRecord |
| `src/application/security/__init__.py` | ✅ 完成 | 包初始化 |

### 第 4 步：registry/tools.py 和 tool_runtime_service.py 接通 runner ⏳ 部分完成

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/registry/tools.py` | ✅ 完成 | 7 个安全 runner 工具注册（security-scan-runner、network-recon-runner、web-scan-runner、service-audit-runner、credential-attack-runner、traffic-analysis-runner、exploit-workbench-runner） |
| `src/registry/agents.py` | ✅ 完成 | 10 个安全智能体注册（security-testing-agent + 9 个专家 worker） |
| `src/application/runtime/tool_runtime_service.py` | ⏳ 待更新 | 需要实现 `_run_security_scan_runner` 等 handler 的实际逻辑（当前已有 handler 注册但实现为 placeholder） |

### 第 5 步：task_pool.py 与 subagent_coordinator.py ✅ 已完成

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/modes/security_testing_mode/task_pool.py` | ✅ 完成 | SecurityTaskPool：依赖解析、状态流转、重试、级联跳过 |
| `src/modes/security_testing_mode/subagent_coordinator.py` | ✅ 完成 | SecuritySubagentCoordinator：批量调度、session 轮询、结果回填、活动记录 |

### 第 6 步：report_builder.py、report_template.py ⏳ 部分完成

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/modes/security_testing_mode/report_builder.py` | ✅ 完成 | SecurityReportBuilder：Markdown 报告、JSON payload、artifact 构建 |
| `src/modes/security_testing_mode/report_template.py` | ❌ 未开始 | HTML 报告模板 |
| `src/modes/security_testing_mode/severity_evaluator.py` | ✅ 完成 | SeverityEvaluator：影响/可利用性/置信度评分 |

### 第 7 步：report_template_service.py 与 HTML 模板 ❌ 未开始

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/application/reporting/report_template_service.py` | ❌ 待更新 | 新增 `security_testing_full` 模板键 |
| `src/templates/security_testing_report.html` | ❌ 未开始 | HTML 报告模板 |

### 第 8 步：测试文件 ❌ 未开始

| 文件 | 状态 | 说明 |
|------|------|------|
| `tests/modes/security_testing_mode/test_runtime.py` | ❌ 未开始 | |
| `tests/modes/security_testing_mode/test_task_pool.py` | ❌ 未开始 | |
| `tests/modes/security_testing_mode/test_severity_evaluator.py` | ❌ 未开始 | |
| `tests/modes/security_testing_mode/test_report_builder.py` | ❌ 未开始 | |
| `tests/application/security/test_command_profiles.py` | ❌ 未开始 | |
| `tests/application/security/test_result_parsers.py` | ❌ 未开始 | |

---

## 其他已完成的辅助文件

| 文件 | 状态 | 说明 |
|------|------|------|
| `src/modes/security_testing_mode/manifest.py` | ✅ 完成 | 模式清单（placeholder=False，完整 agent/tool 列表） |
| `src/modes/security_testing_mode/tools.py` | ✅ 完成 | 工具可见性分组（主控/worker/报告） |
| `src/modes/security_testing_mode/agent.py` | ✅ 完成 | Agent key 常量、Surface→Worker 映射 |
| `src/modes/security_testing_mode/prompt_contract.py` | ✅ 完成 | 主控/Worker/失败分析三套提示协议 |
| `src/modes/security_testing_mode/__init__.py` | ⏳ 待更新 | 需要导出 runtime（当前只导出 MODE_MANIFEST） |

---

## 开发文档 23.1 文件级清单对照

| # | 文件 | 状态 |
|---|------|------|
| 1 | manifest.py | ✅ |
| 2 | tools.py | ✅ |
| 3 | agent.py | ✅ |
| 4 | prompt_contract.py | ✅ |
| 5 | contracts.py | ✅ |
| 6 | campaign_state.py | ✅ |
| 7 | request_interpreter.py | ❌ |
| 8 | asset_discovery_service.py | ❌ |
| 9 | recon_planner.py | ❌ |
| 10 | auth_strategy_planner.py | ❌ |
| 11 | vulnerability_planner.py | ❌ |
| 12 | task_pool.py | ✅ |
| 13 | subagent_coordinator.py | ✅ |
| 14 | severity_evaluator.py | ✅ |
| 15 | reflection_service.py | ❌ |
| 16 | report_builder.py | ✅ |
| 17 | report_template.py | ❌ |
| 18 | runtime.py | ❌ |

| # | Application 文件 | 状态 |
|---|------|------|
| 19 | tool_catalog.py | ✅ |
| 20 | command_profiles.py | ✅ |
| 21 | result_parsers.py | ✅ |
| 22 | execution_environment_service.py | ❌ |
| 23 | risk_policy.py | ✅ |
| 24 | finding_normalizer.py | ✅ |

| # | Registry/Runtime 文件 | 状态 |
|---|------|------|
| 25 | registry/agents.py | ✅ |
| 26 | registry/tools.py | ✅ |
| 27 | tool_runtime_service.py handler 实现 | ⏳ |

---

## 总体进度

- **已完成文件**: 18 / 35 (51%)
- **核心骨架**: 已就绪（contracts、state、task_pool、coordinator、report_builder、severity、registry）
- **关键缺失**: runtime.py（模式总入口）、tool_runtime_service handler 实现、HTML 报告模板
- **Phase 1 最小可运行版本还需**: runtime.py + tool_runtime_service handler + __init__.py 更新

---

## 下一步优先级

1. **runtime.py** — 模式总入口，状态机驱动
2. **tool_runtime_service.py** — 安全 runner handler 实际执行逻辑
3. **__init__.py** — 导出 SecurityTestingModeRuntime
4. **report_template.py** — HTML 报告
5. **测试文件** — 验证核心逻辑
