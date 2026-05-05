<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useMessage } from "naive-ui";

import { api } from "../../../services/api";
import type {
  IntegrationCreateRequest,
  IntegrationKind,
  IntegrationRecord,
  IntegrationTestResponse,
  IntegrationTransport,
  MCPServerDescriptor,
} from "../../../types";
import { formatServerDateTime } from "../../../utils/datetime";

const toast = useMessage();

const integrations = ref<IntegrationRecord[]>([]);
const builtinMcpServers = ref<MCPServerDescriptor[]>([]);
const loading = ref(false);
const error = ref("");
const saving = ref(false);
const deletingId = ref("");
const testingId = ref("");
const modalOpen = ref(false);
const editingId = ref<string | null>(null);
const testResult = ref<IntegrationTestResponse | null>(null);

const activeTab = ref<"api" | "mcp" | "builtin">("api");

const formKind = ref<IntegrationKind>("api");
const formName = ref("");
const formEnabled = ref(true);
const formDescription = ref("");
const formProjectName = ref("");
const formDocumentUrl = ref("");

const formTransport = ref<IntegrationTransport>("http");
const formEndpointUrl = ref("");
const formCommand = ref("");
const formCapabilities = ref("");
const formHeadersJson = ref("{}");
const formEnvJson = ref("{}");

const formBaseUrl = ref("");
const formAuthType = ref<"none" | "bearer" | "api_key" | "basic">("none");
const formAuthToken = ref("");
const formApiKeyHeader = ref("X-API-Key");
const formUsername = ref("");
const formPassword = ref("");

const mcpIntegrations = computed(() => integrations.value.filter((item) => item.kind === "mcp"));
const apiIntegrations = computed(() => integrations.value.filter((item) => item.kind === "api"));

function resetForm(kind: IntegrationKind = "api") {
  formKind.value = kind;
  formName.value = "";
  formEnabled.value = true;
  formDescription.value = "";
  formProjectName.value = "";
  formDocumentUrl.value = "";
  formTransport.value = "http";
  formEndpointUrl.value = "";
  formCommand.value = "";
  formCapabilities.value = "";
  formHeadersJson.value = "{}";
  formEnvJson.value = "{}";
  formBaseUrl.value = "";
  formAuthType.value = "none";
  formAuthToken.value = "";
  formApiKeyHeader.value = "X-API-Key";
  formUsername.value = "";
  formPassword.value = "";
  testResult.value = null;
}

function openCreate(kind: IntegrationKind = "api") {
  editingId.value = null;
  resetForm(kind);
  modalOpen.value = true;
}

function closeModal() {
  modalOpen.value = false;
  editingId.value = null;
  resetForm("api");
}

function parseJsonMap(label: string, raw: string): Record<string, string> {
  const trimmed = raw.trim();
  if (!trimmed) {
    return {};
  }
  try {
    const parsed = JSON.parse(trimmed) as Record<string, unknown>;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      throw new Error(`${label} 必须是 JSON 对象`);
    }
    const result: Record<string, string> = {};
    Object.entries(parsed).forEach(([key, value]) => {
      const normalizedKey = String(key || "").trim();
      const normalizedValue = String(value ?? "").trim();
      if (normalizedKey && normalizedValue) {
        result[normalizedKey] = normalizedValue;
      }
    });
    return result;
  } catch (err) {
    throw new Error(err instanceof Error ? err.message : `${label} 解析失败`);
  }
}

function toCapabilities() {
  return formCapabilities.value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildPayload(): IntegrationCreateRequest {
  const headers = parseJsonMap("请求头", formHeadersJson.value);
  const env = parseJsonMap("环境变量", formEnvJson.value);
  const payload: IntegrationCreateRequest = {
    name: formName.value.trim(),
    kind: formKind.value,
    enabled: formEnabled.value,
    description: formDescription.value.trim() || null,
    project_name: formProjectName.value.trim() || null,
    document_url: formDocumentUrl.value.trim() || null,
    headers,
    env,
    capabilities: toCapabilities(),
    metadata: {},
  };

  if (formKind.value === "mcp") {
    payload.transport = formTransport.value;
    payload.endpoint_url = formEndpointUrl.value.trim() || null;
    payload.command = formCommand.value.trim() || null;
    payload.base_url = null;
    payload.auth_type = "none";
    payload.auth_config = {};
  } else {
    payload.base_url = formBaseUrl.value.trim() || null;
    payload.transport = null;
    payload.endpoint_url = null;
    payload.command = null;
    payload.auth_type = formAuthType.value;
    if (formAuthType.value === "bearer") {
      payload.auth_config = {
        token: formAuthToken.value.trim(),
      };
    } else if (formAuthType.value === "api_key") {
      payload.auth_config = {
        header_name: formApiKeyHeader.value.trim() || "X-API-Key",
        token: formAuthToken.value.trim(),
      };
    } else if (formAuthType.value === "basic") {
      payload.auth_config = {
        username: formUsername.value.trim(),
        password: formPassword.value,
      };
    } else {
      payload.auth_config = {};
    }
  }

  if (!payload.name) {
    throw new Error("接入名称不能为空");
  }
  return payload;
}

function hydrateForm(record: IntegrationRecord) {
  formKind.value = record.kind;
  formName.value = record.name;
  formEnabled.value = record.enabled;
  formDescription.value = record.description || "";
  formProjectName.value = record.project_name || "";
  formDocumentUrl.value = record.document_url || "";
  formTransport.value = (record.transport || "http") as IntegrationTransport;
  formEndpointUrl.value = record.endpoint_url || "";
  formCommand.value = record.command || "";
  formCapabilities.value = record.capabilities.join(", ");
  formHeadersJson.value = JSON.stringify(record.headers || {}, null, 2);
  formEnvJson.value = JSON.stringify(record.env || {}, null, 2);
  formBaseUrl.value = record.base_url || "";
  formAuthType.value = record.auth_type;
  formAuthToken.value = record.auth_config.token || "";
  formApiKeyHeader.value = record.auth_config.header_name || "X-API-Key";
  formUsername.value = record.auth_config.username || "";
  formPassword.value = record.auth_config.password || "";
}

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    const [integrationItems, mcpItems] = await Promise.all([
      api.listIntegrations(),
      api.listMcpServers(),
    ]);
    integrations.value = integrationItems;
    builtinMcpServers.value = mcpItems;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载第三方接入失败";
  } finally {
    loading.value = false;
  }
}

function upsertIntegration(record: IntegrationRecord) {
  const index = integrations.value.findIndex((item) => item.id === record.id);
  if (index >= 0) {
    const next = [...integrations.value];
    next[index] = record;
    integrations.value = next.sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    return;
  }
  integrations.value = [record, ...integrations.value].sort((a, b) => b.updated_at.localeCompare(a.updated_at));
}

function openEdit(record: IntegrationRecord) {
  editingId.value = record.id;
  hydrateForm(record);
  testResult.value = null;
  modalOpen.value = true;
}

async function saveIntegration() {
  saving.value = true;
  error.value = "";
  try {
    const payload = buildPayload();
    const saved = editingId.value
      ? await api.updateIntegration(editingId.value, payload)
      : await api.createIntegration(payload);
    upsertIntegration(saved);
    toast.success(editingId.value ? "接入已更新" : "接入已创建", { duration: 2200 });
    closeModal();
  } catch (err) {
    const detail = err instanceof Error ? err.message : "保存接入失败";
    error.value = detail;
    toast.error(detail);
  } finally {
    saving.value = false;
  }
}

async function deleteIntegration(record: IntegrationRecord) {
  if (deletingId.value) {
    return;
  }
  deletingId.value = record.id;
  try {
    await api.deleteIntegration(record.id);
    integrations.value = integrations.value.filter((item) => item.id !== record.id);
    toast.success(`已删除接入：${record.name}`, { duration: 2200 });
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "删除接入失败");
  } finally {
    deletingId.value = "";
  }
}

async function testIntegration(record: IntegrationRecord) {
  testingId.value = record.id;
  try {
    const result = await api.testIntegration(record.id);
    testResult.value = result;
    toast[result.ok ? "success" : "warning"](result.message, { duration: 2600 });
  } catch (err) {
    const detail = err instanceof Error ? err.message : "测试接入失败";
    testResult.value = {
      ok: false,
      message: detail,
    };
    toast.error(detail);
  } finally {
    testingId.value = "";
  }
}

function handleOpenCreateEvent(event: Event) {
  const detail = (event as CustomEvent<{ kind?: IntegrationKind }>).detail;
  const kind = detail?.kind || "api";
  activeTab.value = kind === "mcp" ? "mcp" : "api";
  openCreate(kind);
}

onMounted(() => {
  void loadData();
  window.addEventListener("qa-agent:open-integration-create", handleOpenCreateEvent as EventListener);
});

onBeforeUnmount(() => {
  window.removeEventListener("qa-agent:open-integration-create", handleOpenCreateEvent as EventListener);
});
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <div class="header-left">
        <h3 class="section-title">第三方平台接入</h3>
        <p class="head-desc">统一管理 MCP 接入和 API 接入，供 API 文档导入和后续接口测试模式复用。</p>
      </div>
      <div class="pane-actions">
        <button v-if="activeTab === 'mcp'" class="primary-btn" @click="openCreate('mcp')">
          <i class="fa-solid fa-plus"></i> 新增 MCP 接入
        </button>
        <button v-if="activeTab === 'api'" class="primary-btn" @click="openCreate('api')">
          <i class="fa-solid fa-plus"></i> 新增 API 接入
        </button>
      </div>
    </div>

    <div class="main-tabs">
      <button :class="{ active: activeTab === 'api' }" @click="activeTab = 'api'">
        API 接入 <span class="count">{{ apiIntegrations.length }}</span>
      </button>
      <button :class="{ active: activeTab === 'mcp' }" @click="activeTab = 'mcp'">
        MCP 接入 <span class="count">{{ mcpIntegrations.length }}</span>
      </button>
      <button :class="{ active: activeTab === 'builtin' }" @click="activeTab = 'builtin'">
        内置 MCP <span class="count">{{ builtinMcpServers.length }}</span>
      </button>
    </div>

    <div v-if="loading" class="plugins-empty">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <p>正在加载第三方接入...</p>
    </div>
    <div v-else-if="error" class="plugins-empty plugins-empty--error">
      <i class="fa-solid fa-circle-exclamation"></i>
      <p>{{ error }}</p>
    </div>
    <template v-else>
      <!-- API 接入 Tab -->
      <section v-if="activeTab === 'api'" class="panel-section">
        <div v-if="apiIntegrations.length" class="integration-grid">
          <article v-for="item in apiIntegrations" :key="item.id" class="integration-card">
            <div class="integration-card-head">
              <div class="card-title-row">
                <span class="status-dot" :class="{ active: item.enabled }"></span>
                <h5>{{ item.name }}</h5>
              </div>
            </div>
            <p class="card-desc">{{ item.description || "未填写说明" }}</p>
            <div class="integration-meta">
              <div class="meta-item"><i class="fa-solid fa-link"></i> {{ item.base_url || "未设置" }}</div>
              <div class="meta-item"><i class="fa-solid fa-book"></i> {{ item.document_url || "无文档" }}</div>
              <div class="meta-item"><i class="fa-solid fa-key"></i> {{ item.auth_type }}</div>
              <div class="meta-item"><i class="fa-solid fa-folder"></i> {{ item.project_name || "无项目" }}</div>
            </div>
            <div class="integration-actions">
              <button class="ghost-btn" @click="openEdit(item)">编辑</button>
              <button class="ghost-btn" :disabled="testingId === item.id" @click="testIntegration(item)">
                {{ testingId === item.id ? "测试中..." : "测试连接" }}
              </button>
              <button class="ghost-btn danger" :disabled="deletingId === item.id" @click="deleteIntegration(item)">
                {{ deletingId === item.id ? "删除中..." : "删除" }}
              </button>
            </div>
          </article>
        </div>
        <div v-else class="plugins-empty">
          <i class="fa-solid fa-cloud-slash"></i>
          <p>还没有配置 API 接入。</p>
        </div>
      </section>

      <!-- MCP 接入 Tab -->
      <section v-if="activeTab === 'mcp'" class="panel-section">
        <div v-if="mcpIntegrations.length" class="integration-grid">
          <article v-for="item in mcpIntegrations" :key="item.id" class="integration-card">
            <div class="integration-card-head">
              <div class="card-title-row">
                <span class="status-dot" :class="{ active: item.enabled }"></span>
                <h5>{{ item.name }}</h5>
              </div>
            </div>
            <p class="card-desc">{{ item.description || "未填写说明" }}</p>
            <div class="integration-meta">
              <div class="meta-item"><i class="fa-solid fa-network-wired"></i> {{ item.transport || "未设置" }}</div>
              <div class="meta-item"><i class="fa-solid fa-folder"></i> {{ item.project_name || "无项目" }}</div>
              <div class="meta-item"><i class="fa-solid fa-book"></i> {{ item.document_url || item.endpoint_url || "无文档" }}</div>
            </div>
            <div class="integration-actions">
              <button class="ghost-btn" @click="openEdit(item)">编辑</button>
              <button class="ghost-btn" :disabled="testingId === item.id" @click="testIntegration(item)">
                {{ testingId === item.id ? "测试中..." : "测试连接" }}
              </button>
              <button class="ghost-btn danger" :disabled="deletingId === item.id" @click="deleteIntegration(item)">
                {{ deletingId === item.id ? "删除中..." : "删除" }}
              </button>
            </div>
          </article>
        </div>
        <div v-else class="plugins-empty">
          <i class="fa-solid fa-plug-circle-xmark"></i>
          <p>还没有配置自定义 MCP 接入。</p>
        </div>
      </section>

      <!-- 内置 MCP Tab -->
      <section v-if="activeTab === 'builtin'" class="panel-section">
        <div v-if="builtinMcpServers.length" class="builtin-mcp-list">
          <article v-for="server in builtinMcpServers" :key="server.key" class="builtin-mcp-card">
            <div class="builtin-mcp-head">
              <div class="card-title-row">
                <span class="status-dot" :class="{ active: server.enabled }"></span>
                <strong>{{ server.name }}</strong>
              </div>
            </div>
            <p class="card-desc">{{ server.summary }}</p>
            <div class="tag-row">
              <span>{{ server.transport }}</span>
              <span v-for="capability in server.capabilities" :key="capability">{{ capability }}</span>
            </div>
          </article>
        </div>
      </section>
    </template>

    <div v-if="modalOpen" class="tools-modal-backdrop" @click.self="closeModal">
      <section class="tools-modal integration-modal">
        <header class="tools-modal-head">
          <div>
            <h3>{{ editingId ? "编辑接入" : `新增 ${formKind === 'mcp' ? 'MCP' : 'API'} 接入` }}</h3>
            <p>配置完成后可供 API 文档导入页和后续接口测试模式复用。</p>
          </div>
          <button class="icon-btn" @click="closeModal"><i class="fa-solid fa-xmark"></i></button>
        </header>

        <div class="modal-body">
          <!-- 基础设置 -->
          <div class="settings-group">
            <h4 class="group-title">基础设置</h4>
            <div class="settings-list">
              <div class="setting-item">
                <div class="setting-info">
                  <label>接入名称 <span class="required">*</span></label>
                  <p>标识此第三方接入的唯一名称</p>
                </div>
                <div class="setting-control">
                  <input v-model="formName" placeholder="例如：订单中心 OpenAPI" />
                </div>
              </div>

              <div class="setting-item">
                <div class="setting-info">
                  <label>所属项目</label>
                  <p>该接入归属的业务项目（可选）</p>
                </div>
                <div class="setting-control">
                  <input v-model="formProjectName" placeholder="例如：mall-order-service" />
                </div>
              </div>

              <div class="setting-item">
                <div class="setting-info">
                  <label>说明</label>
                  <p>简要描述该接入的服务场景</p>
                </div>
                <div class="setting-control">
                  <input v-model="formDescription" placeholder="说明信息..." />
                </div>
              </div>

              <div class="setting-item">
                <div class="setting-info">
                  <label>启用状态</label>
                  <p>停用后，系统将不会加载此接入</p>
                </div>
                <div class="setting-control control-switch">
                  <label class="switch">
                    <input type="checkbox" v-model="formEnabled">
                    <span class="slider"></span>
                  </label>
                </div>
              </div>
            </div>
          </div>

          <!-- 连接配置 -->
          <div class="settings-group">
            <h4 class="group-title">连接配置</h4>
            <div class="settings-list">
              <template v-if="formKind === 'mcp'">
                <div class="setting-item">
                  <div class="setting-info">
                    <label>传输协议 (Transport)</label>
                    <p>MCP 服务器的通信方式</p>
                  </div>
                  <div class="setting-control">
                    <select v-model="formTransport">
                      <option value="stdio">标准输入输出 (stdio)</option>
                      <option value="http">HTTP</option>
                      <option value="websocket">WebSocket</option>
                    </select>
                  </div>
                </div>

                <div class="setting-item" v-if="formTransport !== 'stdio'">
                  <div class="setting-info">
                    <label>端点地址 (Endpoint URL)</label>
                    <p>MCP 服务的网络地址</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formEndpointUrl" placeholder="http://127.0.0.1:3001/mcp" />
                  </div>
                </div>

                <div class="setting-item" v-if="formTransport === 'stdio'">
                  <div class="setting-info">
                    <label>启动命令 (Command)</label>
                    <p>执行 MCP 服务器的本地命令</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formCommand" placeholder="npx -y @modelcontextprotocol/server-filesystem /path" />
                  </div>
                </div>
              </template>

              <template v-else>
                <div class="setting-item">
                  <div class="setting-info">
                    <label>接口地址 (Base URL) <span class="required">*</span></label>
                    <p>API 服务的根路径</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formBaseUrl" placeholder="https://api.example.com" />
                  </div>
                </div>

                <div class="setting-item">
                  <div class="setting-info">
                    <label>认证方式 (Auth Type)</label>
                    <p>调用 API 时的鉴权策略</p>
                  </div>
                  <div class="setting-control">
                    <select v-model="formAuthType">
                      <option value="none">无 (none)</option>
                      <option value="bearer">Bearer 令牌 (bearer)</option>
                      <option value="api_key">API 密钥 (api_key)</option>
                      <option value="basic">基础认证 (basic)</option>
                    </select>
                  </div>
                </div>

                <div class="setting-item" v-if="formAuthType === 'bearer'">
                  <div class="setting-info">
                    <label>Bearer 令牌</label>
                    <p>访问令牌 (Token)</p>
                  </div>
                  <div class="setting-control">
                    <input v-model="formAuthToken" placeholder="输入 Token" type="password" />
                  </div>
                </div>

                <template v-else-if="formAuthType === 'api_key'">
                  <div class="setting-item">
                    <div class="setting-info">
                      <label>API 密钥请求头</label>
                      <p>Header 名称</p>
                    </div>
                    <div class="setting-control">
                      <input v-model="formApiKeyHeader" placeholder="例如：X-API-Key" />
                    </div>
                  </div>
                  <div class="setting-item">
                    <div class="setting-info">
                      <label>API 密钥值</label>
                      <p>Header 对应的值</p>
                    </div>
                    <div class="setting-control">
                      <input v-model="formAuthToken" placeholder="输入 Key" type="password" />
                    </div>
                  </div>
                </template>

                <template v-else-if="formAuthType === 'basic'">
                  <div class="setting-item">
                    <div class="setting-info">
                      <label>用户名</label>
                      <p>Basic Auth Username</p>
                    </div>
                    <div class="setting-control">
                      <input v-model="formUsername" placeholder="Username" />
                    </div>
                  </div>
                  <div class="setting-item">
                    <div class="setting-info">
                      <label>密码</label>
                      <p>Basic Auth Password</p>
                    </div>
                    <div class="setting-control">
                      <input v-model="formPassword" type="password" placeholder="Password" />
                    </div>
                  </div>
                </template>
              </template>

              <div class="setting-item">
                <div class="setting-info">
                  <label>文档地址 (Document URL)</label>
                  <p>OpenAPI 规范或 MCP 描述文档地址</p>
                </div>
                <div class="setting-control">
                  <input v-model="formDocumentUrl" placeholder="https://example.com/openapi.json" />
                </div>
              </div>
            </div>
          </div>

          <!-- 高级配置 -->
          <div class="settings-group">
            <h4 class="group-title">高级配置</h4>
            <div class="settings-list">
              <div class="setting-item align-top" v-if="formKind === 'mcp'">
                <div class="setting-info">
                  <label>能力列表 (Capabilities)</label>
                  <p>逗号分隔的能力标识</p>
                </div>
                <div class="setting-control">
                  <textarea v-model="formCapabilities" rows="2" placeholder="read-file, list-dir..."></textarea>
                </div>
              </div>

              <div class="setting-item align-top">
                <div class="setting-info">
                  <label>请求头 (Headers)</label>
                  <p>附加的 HTTP Headers (JSON 格式)</p>
                </div>
                <div class="setting-control">
                  <textarea v-model="formHeadersJson" rows="3" spellcheck="false" placeholder='{"X-Custom": "value"}'></textarea>
                </div>
              </div>

              <div class="setting-item align-top">
                <div class="setting-info">
                  <label>环境变量 (Environment)</label>
                  <p>执行命令或请求时的环境变量 (JSON 格式)</p>
                </div>
                <div class="setting-control">
                  <textarea v-model="formEnvJson" rows="3" spellcheck="false" placeholder='{"ENV_VAR": "value"}'></textarea>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="testResult" class="test-result" :class="{ success: testResult.ok, error: !testResult.ok }">
          <strong>{{ testResult.ok ? "测试成功" : "测试失败" }}</strong>
          <span>{{ testResult.message }}</span>
          <small v-if="testResult.target_url">目标：{{ testResult.target_url }}</small>
          <small v-if="testResult.status_code">状态码：{{ testResult.status_code }}</small>
          <small v-if="testResult.latency_ms">耗时：{{ testResult.latency_ms }} ms</small>
        </div>

        <div class="modal-actions">
          <button class="secondary-btn" @click="closeModal">取消</button>
          <button class="primary-btn" :disabled="saving" @click="saveIntegration">
            {{ saving ? "保存中..." : editingId ? "保存修改" : "保存接入" }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tools-tab-pane {
  animation: fadeIn 0.3s ease;
}

.pane-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.section-title {
  margin: 0;
  font-size: 18px;
  color: var(--text);
}

.head-desc {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}

.pane-actions {
  display: flex;
  gap: 10px;
}

/* ── 主标签页 ─────────────────────────────────────────────────── */
.main-tabs {
  display: flex;
  gap: 24px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}

.main-tabs button {
  background: transparent;
  border: none;
  padding: 0 0 12px 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--muted);
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.main-tabs button:hover {
  color: var(--text);
}

.main-tabs button.active {
  color: var(--text);
}

.main-tabs button.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: var(--text);
  border-radius: 2px 2px 0 0;
}

.main-tabs .count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 999px;
  margin-left: 4px;
  font-weight: 600;
}

.main-tabs button.active .count {
  background: var(--text);
  color: var(--bg);
}

/* ── 列表卡片 ─────────────────────────────────────────────────── */
.panel-section {
  animation: fadeIn 0.2s ease;
}

.integration-grid,
.builtin-mcp-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}

.integration-card,
.builtin-mcp-card {
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  padding: 20px;
  display: flex;
  flex-direction: column;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.integration-card:hover,
.builtin-mcp-card:hover {
  border-color: var(--border-strong);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
}

.integration-card-head,
.builtin-mcp-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 8px;
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--border-strong);
}

.status-dot.active {
  background: var(--text);
}

.card-title-row h5,
.card-title-row strong {
  margin: 0;
  font-size: 15px;
  color: var(--text);
}

.card-desc {
  margin: 0 0 16px 0;
  color: var(--muted);
  line-height: 1.5;
  font-size: 13px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.integration-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 20px;
  flex: 1;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
}

.meta-item i {
  width: 14px;
  text-align: center;
  opacity: 0.6;
}

.integration-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.ghost-btn {
  background: transparent;
  border: none;
  color: var(--muted);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: color 0.2s, background 0.2s;
}

.ghost-btn:hover:not(:disabled) {
  color: var(--text);
  background: var(--surface-muted);
}

.ghost-btn.danger:hover:not(:disabled) {
  color: var(--red);
  background: color-mix(in srgb, var(--red) 8%, transparent);
}

.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 14px;
}

.tag-row span {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  background: var(--surface-muted);
  color: var(--muted);
}

/* ── 空状态 ───────────────────────────────────────────────────── */
.plugins-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 0;
  color: var(--muted);
  background: var(--surface-soft);
  border-radius: 12px;
  border: 1px dashed var(--border);
  text-align: center;
}

.plugins-empty--error {
  border-color: color-mix(in srgb, var(--red) 30%, transparent);
  background: color-mix(in srgb, var(--red) 5%, transparent);
  color: var(--red);
}

.plugins-empty i {
  font-size: 32px;
  margin-bottom: 16px;
  opacity: 0.5;
}

/* ── 弹窗 ─────────────────────────────────────────────────────── */
.tools-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2400;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(0, 0, 0, 0.4);
}

.tools-modal {
  width: min(760px, 100%);
  max-height: min(90vh, 800px);
  display: flex;
  flex-direction: column;
  border-radius: 16px;
  background: var(--surface);
  border: 1px solid var(--border);
  box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
  color: var(--text);
}

.tools-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 20px 24px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.tools-modal-head h3 {
  margin: 0 0 4px;
  color: var(--text);
  font-size: 18px;
}

.tools-modal-head p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--muted);
  font-size: 18px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
}

.icon-btn:hover {
  background: var(--surface-muted);
  color: var(--text);
}

.modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.settings-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.group-title {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  padding-left: 4px;
}

.settings-list {
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}

.setting-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  gap: 24px;
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-item.align-top {
  align-items: flex-start;
}

.setting-info {
  flex: 1;
  min-width: 0;
}

.setting-info label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text);
  margin-bottom: 4px;
}

.setting-info .required {
  color: var(--red);
  font-weight: bold;
}

.setting-info p {
  margin: 0;
  font-size: 12px;
  color: var(--muted);
  line-height: 1.4;
}

.setting-control {
  flex-shrink: 0;
  width: 340px;
}

.setting-control input,
.setting-control select,
.setting-control textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 13px;
  background: var(--surface);
  color: var(--text);
  transition: border-color 0.2s;
}

.setting-control textarea {
  resize: vertical;
}

.setting-control input:focus,
.setting-control select:focus,
.setting-control textarea:focus {
  outline: none;
  border-color: var(--text);
}

.control-switch {
  display: flex;
  justify-content: flex-end;
}

/* Toggle Switch CSS */
.switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  cursor: pointer;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: var(--border-strong);
  transition: .3s;
  border-radius: 22px;
}

.slider:before {
  position: absolute;
  content: "";
  height: 16px;
  width: 16px;
  left: 3px;
  bottom: 3px;
  background-color: white;
  transition: .3s;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

input:checked + .slider {
  background-color: var(--text);
}

input:checked + .slider:before {
  transform: translateX(18px);
}

.test-result {
  margin: 0 24px;
  padding: 12px 16px;
  border-radius: 8px;
  display: grid;
  gap: 4px;
  font-size: 13px;
}

.test-result.success {
  background: color-mix(in srgb, var(--text) 4%, transparent);
  color: var(--text);
  border: 1px solid var(--border-strong);
}

.test-result.error {
  background: color-mix(in srgb, var(--red) 6%, transparent);
  color: var(--red);
  border: 1px solid color-mix(in srgb, var(--red) 20%, transparent);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

@media (max-width: 768px) {
  .form-grid {
    grid-template-columns: 1fr;
  }

  .field-span-2 {
    grid-column: span 1;
  }

  .pane-header {
    flex-direction: column;
  }
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>