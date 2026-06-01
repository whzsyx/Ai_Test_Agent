# 安全测试模式靶场测试方案

## 1. 文档目标

本文档用于指导 `security_testing_mode` 的测试与验收，重点说明：

- 应该如何测试安全测试模式
- 应该使用哪些靶场
- 每个靶场适合验证哪些能力
- 如何建立回归测试基线
- 如何避免把高风险自动化直接打到真实目标

本文档配合以下开发文档使用：

- [security_testing_mode_development_guide.md](G:\Code\Python\Python_selenium_test_Agent\Ai_Test_Agent\Enterprise_AI_QA_Agent\Agent_Server\docs\security_testing_mode_development_guide.md)

## 2. 测试原则

### 2.1 总原则

`security_testing_mode` 的验证必须优先使用本地、隔离、可重复的靶场环境，不建议在功能未稳定前直接对真实外部目标执行自动化安全测试。

### 2.2 测试目标

测试不仅要验证“工具能跑”，还要验证以下能力：

- 模式状态机是否正确
- 智能体协同是否真实生效
- 任务调度是否正确
- 工具 runner 是否正确调用底层工具
- 输出解析器是否能生成结构化结果
- 严重级别是否合理
- 报告模板是否完整
- 邮件发送链路是否可用

### 2.3 测试边界

测试环境中允许：

- 信息收集
- 端口扫描
- 服务识别
- Web/API 探测
- 低风险漏洞验证
- 靶场允许范围内的认证测试

默认不建议在首期自动化里开放：

- 大规模爆破
- 持续型流量攻击
- DoS/DDoS
- 长时间驻留
- 横向移动

## 3. 推荐测试分层

### 3.1 单元测试

目标：

- 验证纯 Python 逻辑正确性

覆盖模块：

- `request_interpreter.py`
- `task_pool.py`
- `severity_evaluator.py`
- `result_parsers.py`
- `risk_policy.py`
- `report_builder.py`

### 3.2 集成测试

目标：

- 验证 mode runtime 和 worker 调度链路

覆盖模块：

- `runtime.py`
- `subagent_coordinator.py`
- `tool_runtime_service.py`
- `registry/tools.py`
- `registry/agents.py`

### 3.3 靶场端到端测试

目标：

- 验证真实 runner、真实命令、真实解析、真实报告

覆盖内容：

- `network-recon-runner`
- `web-scan-runner`
- `service-audit-runner`
- `credential-attack-runner`
- `security-scan-runner`
- `report-writer`
- `send-email`

### 3.4 回归测试

目标：

- 确保 prompt、parser、planner、worker 改动后，靶场能力不会回退

形式：

- 固定靶场
- 固定目标 URL/IP
- 固定预期发现集合
- 固定报告字段检查

## 4. 推荐靶场总览

建议将靶场分为三层：

### 4.1 Tier 1：首期必须接入

- OWASP Juice Shop
- OWASP WebGoat
- Metasploitable 2

### 4.2 Tier 2：能力扩展后接入

- DVWA
- Vulhub

### 4.3 Tier 3：后续增强验证

- OWASP Security Shepherd
- PortSwigger Web Security Academy

## 5. 靶场详细方案

### 5.1 OWASP Juice Shop

用途：

- 验证现代 Web + API 的安全测试能力
- 验证鉴权、接口探测、前后端信息泄露、目录与页面发现
- 验证报告模板的完整性

适合测试的 runner：

- `web-scan-runner`
- `security-scan-runner`
- `service-audit-runner`

建议验证点：

- HTTP 头信息收集
- 技术栈识别
- 常见页面探测
- 公开接口探测
- 登录入口识别
- 常见弱点候选识别
- 报告生成功能

建议预期输出：

- 至少生成资产信息
- 至少生成一组页面/API 探测结果
- 至少生成 1 份 Markdown 报告
- 至少生成 1 份 HTML 报告

建议测试级别：

- 端到端必测

### 5.2 OWASP WebGoat

用途：

- 验证按漏洞类别组织的任务规划和报告能力
- 验证智能体是否能根据不同练习场景拆分任务

适合测试的 runner：

- `web-scan-runner`
- `security-scan-runner`

建议验证点：

- 页面和入口识别
- 多步任务拆分
- 风险描述生成
- 严重级别分类
- 复现步骤生成

建议预期输出：

- 报告中应出现“隐患/错误”“严重级别”“怎么复现”“建议”

建议测试级别：

- 端到端必测

### 5.3 Metasploitable 2

用途：

- 验证端口、服务、主机层安全测试能力
- 验证 `network-recon-runner` 与 `service-audit-runner`

适合测试的 runner：

- `network-recon-runner`
- `service-audit-runner`
- `security-scan-runner`

建议验证点：

- TCP 端口扫描
- 服务指纹识别
- 常见弱配置识别
- 服务级漏洞候选发现
- 主机层报告生成

建议预期输出：

- 报告应包含端口清单
- 报告应包含服务识别结果
- 报告应包含至少一组主机层风险条目

建议测试级别：

- 端到端必测

### 5.4 DVWA

用途：

- 验证经典 Web 漏洞的验证能力

适合测试的 runner：

- `web-scan-runner`
- `credential-attack-runner`
- `security-scan-runner`

建议验证点：

- SQL 注入候选
- XSS 候选
- 文件上传风险
- 命令执行风险候选
- 认证相关检查

建议预期输出：

- Finding 中应能区分不同漏洞类别
- 报告中应有可操作的复现步骤

建议测试级别：

- 第二阶段重点靶场

### 5.5 Vulhub

用途：

- 验证 CVE 场景、服务场景、端口场景
- 验证 runner 是否适应不同目标组合

适合测试的 runner：

- `network-recon-runner`
- `service-audit-runner`
- `web-scan-runner`
- `exploit-workbench-runner`

建议验证点：

- 服务暴露发现
- 已知组件识别
- 基线漏洞候选探测
- 特定场景的结构化报告

建议测试级别：

- 第二阶段重点靶场

### 5.6 OWASP Security Shepherd

用途：

- 验证更完整的挑战型任务执行
- 验证多智能体拆分能力

建议测试级别：

- 第三阶段增强靶场

### 5.7 PortSwigger Web Security Academy

用途：

- 作为人工对照基准
- 检查报告分类、复现建议、严重级别是否专业

建议说明：

- 不建议首期把它作为全自动回归靶场
- 更适合作为人工验证参考

## 6. 推荐的测试矩阵

### 6.1 Phase 1 测试矩阵

目标：

- 先打通最小可运行版本

靶场：

- Juice Shop
- WebGoat
- Metasploitable 2

验证能力：

- 基础资产发现
- 端口与服务识别
- 基础 Web 探测
- 多智能体调度
- Markdown/HTML/JSON 报告生成
- 邮件发送

### 6.2 Phase 2 测试矩阵

目标：

- 增加更多工具和 parser 覆盖

靶场：

- DVWA
- Vulhub

验证能力：

- SQLi/XSS 类结果归一化
- 目录探测
- 指纹识别
- CVE 场景报告
- 严重级别评分

### 6.3 Phase 3 测试矩阵

目标：

- 验证高风险工具与审批链

靶场：

- Vulhub
- Metasploitable 2
- Security Shepherd

验证能力：

- 风险审批
- 失败分析
- 高风险 runner 的工具管控
- 复杂报告归档

## 7. 每个靶场建议验证的输出

所有靶场在回归时建议统一验证以下项目：

- 是否创建了 `SecurityCampaign`
- 是否生成了 `SecurityTask`
- 是否真实派发了 worker session
- 是否生成了至少一个 artifact
- 是否生成了至少一个 observation
- 是否输出了 Markdown 报告
- 是否输出了 HTML 报告
- 是否输出了 JSON 结果
- 报告中是否包含名称、日期、时间
- 报告中是否包含智能体列表
- 报告中是否包含每个智能体做了什么
- 报告中是否包含测试结果
- 报告中是否包含隐患或错误
- 报告中是否包含严重级别
- 报告中是否包含复现步骤
- 报告中是否包含建议

## 8. 推荐的回归基线

建议为每个靶场建立固定基线文件，包含：

- 目标地址
- 靶场类型
- 允许的 runner
- 预期至少发现的资产数量
- 预期至少发现的端口数量
- 预期至少输出的 finding 类别
- 预期报告字段列表

建议目录：

- `tests/fixtures/security_labs/`

建议文件：

- `juice_shop_baseline.json`
- `webgoat_baseline.json`
- `metasploitable2_baseline.json`
- `dvwa_baseline.json`
- `vulhub_baseline.json`

## 9. 推荐的测试执行顺序

建议按如下顺序进行：

1. 单元测试
2. 不连靶场的 runtime 集成测试
3. Juice Shop 端到端
4. WebGoat 端到端
5. Metasploitable 2 端到端
6. 报告与邮件发送测试
7. DVWA 与 Vulhub 增量验证

## 10. 测试环境建议

建议准备独立测试环境，特征如下：

- 本地 Docker 可用
- 靶场彼此隔离
- 安全模式运行环境和靶场网络可控
- 工具输出可保存
- 邮件测试可发送到测试邮箱

建议不要把首版测试环境和真实业务网络混合。

## 11. 高风险能力测试建议

对于以下能力，建议默认只在人工确认后开启：

- `hydra`
- `john`
- `hashcat`
- `msfconsole`
- `impacket-*`
- `netexec`
- `certipy-ad`
- `mitmproxy`

建议单独准备实验环境测试，不纳入日常自动回归。

## 12. 最小靶场组合建议

如果只准备一组最小靶场，推荐：

- Juice Shop
- WebGoat
- Metasploitable 2

这组三个靶场已经可以覆盖：

- Web/API
- 页面探测
- 鉴权入口识别
- 端口扫描
- 服务识别
- 主机层风险报告
- 多智能体调度
- 报告交付

## 13. 验收标准

当以下条件满足时，可认为 `security_testing_mode` 具备首版可用性：

- 可以对至少 3 个本地靶场稳定执行
- 可以真实生成 worker 子智能体任务
- 可以稳定输出 Markdown/HTML/JSON 报告
- 报告包含全部必填字段
- 可以把报告通过邮件发送
- 可以把执行记录写入 artifact、observation、memory
- 修改 prompt 或 parser 后能够用固定靶场完成回归

## 14. 结论

靶场测试不是可选项，而是 `security_testing_mode` 成功落地的必要条件。

推荐路线是：

- 先用本地隔离靶场跑通模式闭环
- 再逐步扩大工具覆盖面
- 最后再考虑更强的 PentAGI 风格高风险能力

只有在靶场中稳定验证过的 runner、parser、planner 和报告链路，才应该进入更复杂的安全测试场景。
