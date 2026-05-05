<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useMessage } from "naive-ui";

import { api } from "../../../services/api";
import type {
  ApiDocRecord,
  IntegrationImportSourceDescriptor,
  IntegrationImportSourcesResponse,
  IntegrationRecord,
} from "../../../types";
import { formatServerDateTime } from "../../../utils/datetime";

type ImportMode = "local" | "url" | "integration";

const toast = useMessage();

const docs = ref<ApiDocRecord[]>([]);
const integrations = ref<IntegrationRecord[]>([]);
const loading = ref(false);
const error = ref("");
const selectedDoc = ref<ApiDocRecord | null>(null);
const previewOpen = ref(false);
const previewLoading = ref(false);
const savingMetadata = ref(false);
const deletingId = ref("");
const uploadOpen = ref(false);
const uploadLoading = ref(false);
const uploadMode = ref<ImportMode>("local");

const uploadFile = ref<File | null>(null);
const uploadTitle = ref("");
const uploadProjectName = ref("");
const remoteUrl = ref("");
const selectedIntegrationId = ref("");
const integrationDocumentUrl = ref("");
const selectedWorkspaceId = ref("");
const selectedImportSourceId = ref("");
const integrationImportCatalog = ref<IntegrationImportSourcesResponse | null>(null);
const integrationImportLoading = ref(false);

const editTitle = ref("");
const editProjectName = ref("");

const hasDocs = computed(() => docs.value.length > 0);
const importableIntegrations = computed(() =>
  integrations.value.filter((item) => item.enabled && (item.kind === "api" || item.kind === "mcp")),
);
const selectedIntegration = computed(
  () => importableIntegrations.value.find((item) => item.id === selectedIntegrationId.value) ?? null,
);
const selectedIntegrationIsMcp = computed(() => selectedIntegration.value?.kind === "mcp");
const workspaceOptions = computed(() => integrationImportCatalog.value?.workspaces ?? []);
const integrationImportSources = computed(() => integrationImportCatalog.value?.sources ?? []);
const filteredImportSources = computed(() => {
  if (!integrationImportCatalog.value) {
    return [];
  }
  if (!integrationImportCatalog.value.supports_workspace_selection) {
    return integrationImportCatalog.value.sources;
  }
  if (!selectedWorkspaceId.value) {
    return [];
  }
  return integrationImportCatalog.value.sources.filter((source) => source.workspace_id === selectedWorkspaceId.value);
});
const selectedImportSource = computed<IntegrationImportSourceDescriptor | null>(
  () => filteredImportSources.value.find((item) => item.id === selectedImportSourceId.value) ?? null,
);
const integrationImportHint = computed(() => {
  if (!selectedIntegration.value) {
    return "";
  }
  if (integrationImportLoading.value) {
    return "正在加载可导入的工作区和接口文档...";
  }
  if (!integrationImportCatalog.value) {
    return "";
  }
  if (integrationImportCatalog.value.supports_workspace_selection && !workspaceOptions.value.length) {
    return "这个 MCP 接入已启用工作区导入模式，但还没有配置任何可用工作区。";
  }
  if (integrationImportCatalog.value.supports_workspace_selection && workspaceOptions.value.length && !selectedWorkspaceId.value) {
    return "请先选择工作区，再选择该工作区下的接口文档。";
  }
  if (!filteredImportSources.value.length) {
    return selectedIntegration.value.kind === "mcp"
      ? "当前接入还没有可导入的接口文档源。"
      : "当前接入没有可导入的文档地址，请补充默认文档地址或导入源配置。";
  }
  return "";
});
const canSubmitIntegrationImport = computed(() => {
  if (uploadMode.value !== "integration") {
    return true;
  }
  if (!selectedIntegrationId.value || integrationImportLoading.value) {
    return false;
  }
  if (!integrationImportCatalog.value) {
    return false;
  }
  if (integrationImportCatalog.value.supports_workspace_selection) {
    return Boolean(selectedWorkspaceId.value && selectedImportSourceId.value);
  }
  return Boolean(selectedImportSourceId.value || integrationDocumentUrl.value.trim() || selectedIntegration.value?.document_url);
});
const projectNameSuggestions = computed(() =>
  Array.from(
    new Set(
      [
        ...docs.value.map((doc) => doc.project_name?.trim()),
        ...integrations.value.map((integration) => integration.project_name?.trim()),
      ].filter((value): value is string => Boolean(value)),
    ),
  ).sort((a, b) => a.localeCompare(b, "zh-CN")),
);

function formatBytes(value: number) {
  if (value >= 1024 * 1024) {
    return `${(value / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (value >= 1024) {
    return `${Math.round(value / 1024)} KB`;
  }
  return `${value} B`;
}

function resetUploadForm() {
  uploadMode.value = "local";
  uploadFile.value = null;
  uploadTitle.value = "";
  uploadProjectName.value = "";
  remoteUrl.value = "";
  selectedIntegrationId.value = "";
  integrationDocumentUrl.value = "";
  selectedWorkspaceId.value = "";
  selectedImportSourceId.value = "";
  integrationImportCatalog.value = null;
}

function resetPreviewForm() {
  editTitle.value = "";
  editProjectName.value = "";
}

function syncPreviewForm(doc: ApiDocRecord | null) {
  editTitle.value = doc?.title || "";
  editProjectName.value = doc?.project_name || "";
}

function upsertDoc(doc: ApiDocRecord) {
  const index = docs.value.findIndex((item) => item.id === doc.id);
  if (index >= 0) {
    const next = [...docs.value];
    next[index] = doc;
    docs.value = next;
    return;
  }
  docs.value = [doc, ...docs.value];
}

function handleOpenUpload() {
  uploadOpen.value = true;
  resetUploadForm();
}

function handleExternalOpenUpload() {
  handleOpenUpload();
}

function closeUpload() {
  uploadOpen.value = false;
  resetUploadForm();
}

function closePreview() {
  previewOpen.value = false;
  selectedDoc.value = null;
  resetPreviewForm();
}

function onUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  uploadFile.value = input.files?.[0] ?? null;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = () => reject(reader.error || new Error("读取文件失败"));
    reader.readAsDataURL(file);
  });
}

async function loadDocs() {
  loading.value = true;
  error.value = "";
  try {
    docs.value = await api.listApiDocs();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "加载 API 文档失败";
  } finally {
    loading.value = false;
  }
}

async function loadIntegrations() {
  try {
    integrations.value = await api.listIntegrations();
  } catch {
    integrations.value = [];
  }
}

async function loadIntegrationImportCatalog(integrationId: string, workspaceId?: string | null) {
  integrationImportLoading.value = true;
  if (!workspaceId) {
    selectedWorkspaceId.value = "";
    selectedImportSourceId.value = "";
    integrationImportCatalog.value = null;
  } else {
    selectedImportSourceId.value = "";
  }
  try {
    integrationImportCatalog.value = await api.listIntegrationImportSources(integrationId, workspaceId ?? null);
    if (
      !workspaceId &&
      integrationImportCatalog.value.supports_workspace_selection &&
      integrationImportCatalog.value.workspaces.length === 1
    ) {
      selectedWorkspaceId.value = integrationImportCatalog.value.workspaces[0].id;
    }
    if (
      !integrationImportCatalog.value.supports_workspace_selection &&
      integrationImportCatalog.value.sources.length === 1
    ) {
      selectedImportSourceId.value = integrationImportCatalog.value.sources[0].id;
    }
  } catch (err) {
    integrationImportCatalog.value = null;
    toast.error(err instanceof Error ? err.message : "加载接入导入源失败");
  } finally {
    integrationImportLoading.value = false;
  }
}

async function submitUpload() {
  uploadLoading.value = true;
  try {
    let created: ApiDocRecord;
    if (uploadMode.value === "local") {
      if (!uploadFile.value) {
        toast.error("请选择要导入的本地 API 文档文件");
        return;
      }
      const contentBase64 = await fileToBase64(uploadFile.value);
      created = await api.uploadApiDoc({
        filename: uploadFile.value.name,
        content_base64: contentBase64,
        source: "tools_api_docs_local",
        title: uploadTitle.value.trim() || null,
        project_name: uploadProjectName.value.trim() || null,
      });
    } else if (uploadMode.value === "url") {
      if (!remoteUrl.value.trim()) {
        toast.error("请填写要导入的文档 URL");
        return;
      }
      created = await api.importApiDocFromUrl({
        url: remoteUrl.value.trim(),
        title: uploadTitle.value.trim() || null,
        project_name: uploadProjectName.value.trim() || null,
        source: "tools_api_docs_url",
      });
    } else {
      if (!selectedIntegrationId.value) {
        toast.error("请选择一个第三方接入源");
        return;
      }
      if (!canSubmitIntegrationImport.value) {
        toast.error(integrationImportHint.value || "当前接入还没有准备好可导入的接口文档源");
        return;
      }
      created = await api.importApiDocFromIntegration({
        integration_id: selectedIntegrationId.value,
        title: uploadTitle.value.trim() || null,
        project_name: uploadProjectName.value.trim() || null,
        document_url: integrationDocumentUrl.value.trim() || null,
        workspace_id: selectedWorkspaceId.value || null,
        import_source_id: selectedImportSourceId.value || null,
        source: "tools_api_docs_integration",
      });
    }

    upsertDoc(created);
    await loadDocs();
    toast.success("API 文档已导入并加入文档管理", { duration: 2200 });
    setTimeout(() => closeUpload(), 280);
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "导入 API 文档失败");
  } finally {
    uploadLoading.value = false;
  }
}

async function openPreview(docId: string) {
  previewOpen.value = true;
  previewLoading.value = true;
  error.value = "";
  try {
    selectedDoc.value = await api.getApiDoc(docId);
    syncPreviewForm(selectedDoc.value);
  } catch (err) {
    const detail = err instanceof Error ? err.message : "加载文档详情失败";
    error.value = detail;
    selectedDoc.value = null;
    resetPreviewForm();
    toast.error(detail);
  } finally {
    previewLoading.value = false;
  }
}

async function saveDocMetadata() {
  if (!selectedDoc.value || savingMetadata.value) {
    return;
  }

  savingMetadata.value = true;
  error.value = "";
  try {
    const updated = await api.updateApiDoc(selectedDoc.value.id, {
      title: editTitle.value.trim() || null,
      project_name: editProjectName.value.trim() || null,
    });
    selectedDoc.value = updated;
    syncPreviewForm(updated);
    upsertDoc(updated);
    toast.success("API 文档信息已更新", { duration: 2200 });
  } catch (err) {
    const detail = err instanceof Error ? err.message : "更新 API 文档失败";
    error.value = detail;
    toast.error(detail);
  } finally {
    savingMetadata.value = false;
  }
}

async function deleteDoc(doc: ApiDocRecord) {
  if (deletingId.value) {
    return;
  }

  deletingId.value = doc.id;
  error.value = "";
  try {
    await api.deleteApiDoc(doc.id);
    docs.value = docs.value.filter((item) => item.id !== doc.id);
    if (selectedDoc.value?.id === doc.id) {
      closePreview();
    }
    toast.success(`已删除文档：${doc.title}`, { duration: 2200 });
  } catch (err) {
    const detail = err instanceof Error ? err.message : "删除文档失败";
    error.value = detail;
    toast.error(detail);
  } finally {
    deletingId.value = "";
  }
}

watch(selectedIntegrationId, async (integrationId) => {
  integrationDocumentUrl.value = "";
  selectedWorkspaceId.value = "";
  selectedImportSourceId.value = "";
  integrationImportCatalog.value = null;
  if (!integrationId || uploadMode.value !== "integration") {
    return;
  }
  await loadIntegrationImportCatalog(integrationId);
});

watch(selectedWorkspaceId, async (workspaceId) => {
  if (!workspaceId) {
    selectedImportSourceId.value = "";
    return;
  }
  if (!selectedIntegrationId.value || uploadMode.value !== "integration") {
    return;
  }
  await loadIntegrationImportCatalog(selectedIntegrationId.value, workspaceId);
  const candidates = filteredImportSources.value;
  if (candidates.length === 1) {
    selectedImportSourceId.value = candidates[0].id;
  }
});

watch(uploadMode, (mode) => {
  if (mode !== "integration") {
    selectedIntegrationId.value = "";
    integrationDocumentUrl.value = "";
    selectedWorkspaceId.value = "";
    selectedImportSourceId.value = "";
    integrationImportCatalog.value = null;
  }
});

onMounted(() => {
  void loadDocs();
  void loadIntegrations();
  window.addEventListener("qa-agent:open-api-doc-upload", handleExternalOpenUpload);
});

onBeforeUnmount(() => {
  window.removeEventListener("qa-agent:open-api-doc-upload", handleExternalOpenUpload);
});
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <div>
        <h3 class="section-title">API 接口文档</h3>
        <p class="head-desc">
          统一管理 OpenAPI、Swagger、Postman 和 Markdown 文档，并为后续接口测试模式维护所属项目与导入来源。
        </p>
      </div>
    </div>

    <div v-if="loading && !hasDocs" class="api-doc-empty">
      <i class="fa-solid fa-spinner fa-spin"></i>
      <span>正在加载 API 文档列表...</span>
    </div>

    <div v-else-if="error && !hasDocs" class="api-doc-empty api-doc-empty--error">
      <i class="fa-solid fa-circle-exclamation"></i>
      <strong>加载失败</strong>
      <span>{{ error }}</span>
    </div>

    <div v-else-if="!hasDocs" class="api-doc-empty">
      <i class="fa-solid fa-file-circle-plus"></i>
      <strong>还没有导入任何 API 文档</strong>
      <span>支持本地文件、URL 地址，以及第三方接入源导入。</span>
    </div>

    <div v-else class="api-docs-list">
      <article v-for="doc in docs" :key="doc.id" class="api-doc-card">
        <div class="api-doc-header-row">
          <div class="api-doc-icon" :class="{ postman: doc.format_label.includes('Postman') }">
            <i class="fa-solid" :class="doc.format_label.includes('Postman') ? 'fa-rocket' : 'fa-file-code'"></i>
          </div>
          <div class="api-doc-actions">
            <button class="icon-btn" title="查看文档详情" @click="openPreview(doc.id)">
              <i class="fa-regular fa-eye"></i>
            </button>
            <button
              class="icon-btn danger"
              :disabled="deletingId === doc.id"
              title="删除文档"
              @click="deleteDoc(doc)"
            >
              <i class="fa-solid" :class="deletingId === doc.id ? 'fa-spinner fa-spin' : 'fa-trash-can'"></i>
            </button>
          </div>
        </div>

        <div class="api-doc-content">
          <div class="api-doc-head">
            <h4>{{ doc.title }}</h4>
            <span class="badge" :class="doc.format_label.includes('Postman') ? 'badge-orange' : 'badge-blue'">
              {{ doc.format_label }}
            </span>
          </div>
          <p>{{ doc.filename }}</p>

          <div class="api-doc-meta">
            <div class="meta-item">
              <i class="fa-solid fa-diagram-project"></i>
              <span>{{ doc.project_name || "未设置所属项目" }}</span>
            </div>
            <div class="meta-item">
              <i class="fa-solid fa-database"></i>
              <span>MinIO 存储 · {{ formatBytes(doc.size_bytes) }}</span>
            </div>
            <div class="meta-item" v-if="doc.endpoint_count !== null && doc.endpoint_count !== undefined">
              <i class="fa-solid fa-link"></i>
              <span>{{ doc.endpoint_count }} 个接口</span>
            </div>
            <div class="meta-item">
              <i class="fa-regular fa-clock"></i>
              <span>{{ formatServerDateTime(doc.updated_at) }}</span>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div v-if="previewOpen" class="tools-modal-backdrop" @click.self="closePreview">
      <section class="tools-modal api-doc-preview-modal">
        <header class="tools-modal-head">
          <div>
            <h3>{{ selectedDoc?.title || "文档内容预览" }}</h3>
            <p v-if="selectedDoc">{{ selectedDoc.filename }} · {{ selectedDoc.format_label }}</p>
          </div>
          <button class="icon-btn" @click="closePreview"><i class="fa-solid fa-xmark"></i></button>
        </header>

        <div v-if="previewLoading" class="api-doc-empty">
          <i class="fa-solid fa-spinner fa-spin"></i>
          <span>正在加载文档详情...</span>
        </div>
        <template v-else-if="selectedDoc">
          <div class="preview-form-grid">
            <label class="field-block">
              <span>文档标题</span>
              <input v-model="editTitle" placeholder="例如：用户中心 OpenAPI v2">
            </label>
            <label class="field-block">
              <span>所属项目</span>
              <input
                v-model="editProjectName"
                list="api-doc-project-suggestions"
                placeholder="例如：mall-order-service"
              >
              <small v-if="projectNameSuggestions.length" class="field-hint">
                可直接输入新项目名，也可复用已有项目：{{ projectNameSuggestions.join(" / ") }}
              </small>
            </label>
          </div>

          <div class="preview-meta-actions">
            <button class="primary-btn" :disabled="savingMetadata" @click="saveDocMetadata">
              {{ savingMetadata ? "保存中..." : "保存文档信息" }}
            </button>
          </div>

          <div class="preview-meta-grid">
            <div><strong>所属项目：</strong>{{ selectedDoc.project_name || "未设置" }}</div>
            <div><strong>内容类型：</strong>{{ selectedDoc.content_type }}</div>
            <div><strong>上传来源：</strong>{{ selectedDoc.source }}</div>
            <div><strong>更新时间：</strong>{{ formatServerDateTime(selectedDoc.updated_at) }}</div>
            <div><strong>MinIO URI：</strong>{{ selectedDoc.storage_uri }}</div>
          </div>

          <div v-if="selectedDoc.preview_error" class="preview-inline-error">{{ selectedDoc.preview_error }}</div>
          <div v-else class="preview-code-shell">
            <div class="preview-toolbar">
              <span>文件内容</span>
              <span v-if="selectedDoc.preview_truncated">已截断显示前 20000 个字符</span>
            </div>
            <pre class="preview-code"><code>{{ selectedDoc.preview_text || "该文档暂时没有可预览内容。" }}</code></pre>
          </div>
        </template>
      </section>
    </div>

    <div v-if="uploadOpen" class="tools-modal-backdrop" @click.self="closeUpload">
      <section class="tools-modal upload-modal">
        <header class="tools-modal-head">
          <div>
            <h3>导入 API 文档</h3>
            <p>支持本地文件导入、URL 地址导入，以及通过第三方接入源导入文档。</p>
          </div>
          <button class="icon-btn" @click="closeUpload"><i class="fa-solid fa-xmark"></i></button>
        </header>

        <div class="import-mode-tabs">
          <button :class="{ active: uploadMode === 'local' }" @click="uploadMode = 'local'">本地文件导入</button>
          <button :class="{ active: uploadMode === 'url' }" @click="uploadMode = 'url'">URL 地址导入</button>
          <button :class="{ active: uploadMode === 'integration' }" @click="uploadMode = 'integration'">第三方平台接入</button>
        </div>

        <template v-if="uploadMode === 'local'">
          <label class="upload-drop">
            <i class="fa-solid fa-file-arrow-up"></i>
            <strong>{{ uploadFile?.name || "选择要导入的本地文档文件" }}</strong>
            <span>推荐上传 JSON / YAML / Markdown / TXT / Postman Collection</span>
            <input type="file" accept=".json,.yaml,.yml,.txt,.md,.csv,.xml,.html" @change="onUploadFileChange">
          </label>
        </template>

        <template v-else-if="uploadMode === 'url'">
          <label class="field-block modal-field">
            <span>文档 URL</span>
            <input v-model="remoteUrl" placeholder="例如：https://example.com/openapi.json">
            <small class="field-hint">后端会直接拉取远程文档并纳入统一管理。</small>
          </label>
        </template>

        <template v-else>
          <label class="field-block modal-field">
            <span>选择接入源</span>
            <select v-model="selectedIntegrationId">
              <option value="">请选择接入源</option>
              <option v-for="integration in importableIntegrations" :key="integration.id" :value="integration.id">
                {{ integration.name }} · {{ integration.kind.toUpperCase() }}
              </option>
            </select>
            <small class="field-hint">这里会展示“插件导入”页中已启用的 MCP / API 接入。</small>
          </label>

          <div v-if="selectedIntegration" class="integration-brief">
            <div><strong>类型：</strong>{{ selectedIntegration.kind.toUpperCase() }}</div>
            <div><strong>默认项目：</strong>{{ selectedIntegration.project_name || "未设置" }}</div>
            <div>
              <strong>{{ selectedIntegrationIsMcp ? "MCP 服务地址" : "默认文档地址" }}：</strong>
              {{ selectedIntegrationIsMcp ? (selectedIntegration.endpoint_url || "未设置") : (selectedIntegration.document_url || "未设置") }}
            </div>
          </div>

          <label v-if="workspaceOptions.length" class="field-block modal-field">
            <span>选择工作区</span>
            <select v-model="selectedWorkspaceId" :disabled="integrationImportLoading">
              <option value="">请选择工作区</option>
              <option v-for="workspace in workspaceOptions" :key="workspace.id" :value="workspace.id">
                {{ workspace.name }} · {{ workspace.document_count }} 份文档
              </option>
            </select>
            <small class="field-hint">MCP 导入会先定位工作区，再从该工作区导入接口文档。</small>
          </label>

          <label v-if="filteredImportSources.length" class="field-block modal-field">
            <span>{{ selectedIntegrationIsMcp ? "选择接口文档" : "选择导入源" }}</span>
            <select v-model="selectedImportSourceId" :disabled="integrationImportLoading">
              <option value="">请选择</option>
              <option v-for="source in filteredImportSources" :key="source.id" :value="source.id">
                {{ source.label }}<template v-if="source.project_name"> · {{ source.project_name }}</template>
              </option>
            </select>
            <small v-if="selectedImportSource?.summary" class="field-hint">{{ selectedImportSource.summary }}</small>
          </label>

          <label v-if="!selectedIntegrationIsMcp" class="field-block modal-field">
            <span>文档地址覆盖（可选）</span>
            <input v-model="integrationDocumentUrl" placeholder="留空则使用接入源默认文档地址">
          </label>

          <div v-if="integrationImportHint" class="integration-inline-hint">
            {{ integrationImportHint }}
          </div>
        </template>

        <label class="field-block modal-field">
          <span>文档标题（可选）</span>
          <input v-model="uploadTitle" placeholder="例如：用户中心 OpenAPI v2">
        </label>

        <label class="field-block modal-field">
          <span>所属项目（建议填写）</span>
          <input
            v-model="uploadProjectName"
            list="api-doc-project-suggestions"
            placeholder="例如：mall-order-service"
          >
          <small v-if="projectNameSuggestions.length" class="field-hint">
            可直接输入新项目名，也可从已有项目中复用
          </small>
        </label>

        <datalist id="api-doc-project-suggestions">
          <option v-for="projectName in projectNameSuggestions" :key="projectName" :value="projectName" />
        </datalist>

        <div class="modal-actions">
          <button class="secondary-btn" @click="closeUpload">取消</button>
          <button class="primary-btn" :disabled="uploadLoading || !canSubmitIntegrationImport" @click="submitUpload">
            {{ uploadLoading ? "导入中..." : "开始导入" }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.tools-tab-pane {
  animation: fadeIn 0.25s ease;
}

.pane-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 24px;
}

.pane-header .section-title {
  margin: 0 0 8px;
  font-size: 18px;
}

.pane-header .head-desc {
  margin: 0;
  max-width: 760px;
  color: var(--muted);
}

.api-doc-empty {
  display: grid;
  place-items: center;
  gap: 10px;
  min-height: 220px;
  border: 1px dashed var(--border);
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.6);
  color: var(--muted);
  text-align: center;
}

.api-doc-empty--error {
  border-color: rgba(239, 68, 68, 0.22);
  background: rgba(254, 242, 242, 0.8);
  color: #991b1b;
}

.api-doc-empty i {
  font-size: 24px;
}

.api-docs-list {
  display: flex;
  flex-wrap: wrap;
  gap: 20px;
}

.api-doc-card {
  display: flex;
  flex-direction: column;
  width: 320px;
  min-height: 310px;
  padding: 20px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  transition: all 0.2s ease;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
}

.api-doc-card:hover {
  border-color: var(--border-strong);
  box-shadow: 0 12px 24px rgba(0, 0, 0, 0.06);
  transform: translateY(-2px);
}

.api-doc-header-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}

.api-doc-icon {
  width: 56px;
  height: 56px;
  border-radius: 14px;
  background: rgba(59, 130, 246, 0.1);
  color: #3b82f6;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
}

.api-doc-icon.postman {
  background: rgba(249, 115, 22, 0.1);
  color: #f97316;
}

.api-doc-actions {
  display: flex;
  gap: 6px;
}

.api-doc-content {
  display: flex;
  flex: 1;
  flex-direction: column;
}

.api-doc-head {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 12px;
}

.api-doc-head h4 {
  margin: 0;
  font-size: 18px;
  line-height: 1.3;
}

.api-doc-content p {
  margin: 0 0 16px;
  font-size: 14px;
  color: var(--muted);
  line-height: 1.6;
  word-break: break-all;
}

.api-doc-meta {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: auto;
  padding-top: 16px;
  border-top: 1px dashed var(--border);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--muted);
  font-family: var(--font-mono, monospace);
}

.badge {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  display: inline-block;
}

.badge-blue {
  background: rgba(59, 130, 246, 0.1);
  color: #2563eb;
}

.badge-orange {
  background: rgba(249, 115, 22, 0.1);
  color: #ea580c;
}

.icon-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--muted);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
}

.icon-btn:hover {
  background: var(--surface-muted);
  color: var(--text);
}

.icon-btn.danger:hover {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.tools-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 2400;
  display: grid;
  place-items: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.36);
}

.tools-modal {
  width: min(960px, 100%);
  max-height: min(88vh, 900px);
  overflow-x: hidden;
  overflow-y: auto;
  border-radius: 24px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
}

.tools-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 24px 28px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.tools-modal-head h3 {
  margin: 0 0 8px;
}

.tools-modal-head p {
  margin: 0;
  color: var(--muted);
}

.api-doc-preview-modal,
.upload-modal {
  padding-bottom: 24px;
}

.preview-form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
  padding-right: 28px;
}

.preview-meta-actions {
  display: flex;
  justify-content: flex-end;
  padding: 16px 28px 0;
}

.preview-meta-grid {
  display: grid;
  gap: 10px;
  padding: 20px 28px 0;
  color: #475569;
}

.preview-inline-error,
.integration-inline-hint {
  margin: 16px 28px 0;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(59, 130, 246, 0.06);
  color: #1e3a8a;
  font-size: 13px;
}

.preview-code-shell {
  margin: 20px 28px 0;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 18px;
  overflow: hidden;
  background: #f8fafc;
}

.preview-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
  font-size: 13px;
  color: #475569;
}

.preview-code {
  margin: 0;
  padding: 18px;
  max-height: 56vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.72;
  color: #0f172a;
  font-family: "Consolas", "SFMono-Regular", monospace;
}

.import-mode-tabs {
  display: flex;
  gap: 10px;
  padding: 20px 28px 0;
}

.import-mode-tabs button {
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 999px;
  padding: 8px 14px;
  background: rgba(248, 250, 252, 0.9);
  color: #475569;
  cursor: pointer;
}

.import-mode-tabs button.active {
  background: #0f172a;
  color: #ffffff;
  border-color: #0f172a;
}

.upload-drop {
  display: grid;
  gap: 8px;
  margin: 24px 28px 0;
  padding: 22px;
  border: 1px dashed rgba(37, 99, 235, 0.34);
  border-radius: 18px;
  background: rgba(239, 246, 255, 0.8);
  cursor: pointer;
}

.upload-drop i {
  font-size: 22px;
  color: #2563eb;
}

.upload-drop strong {
  color: #0f172a;
}

.upload-drop span {
  color: #64748b;
  font-size: 13px;
}

.upload-drop input {
  display: none;
}

.field-block {
  display: grid;
  gap: 8px;
  font-size: 13px;
  color: #475569;
}

.modal-field,
.field-block {
  margin: 16px 28px 0;
}

.field-block span {
  font-weight: 600;
}

.field-block input,
.field-block select {
  width: 100%;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 12px;
  padding: 11px 12px;
  font-size: 14px;
  background: #ffffff;
}

.field-hint {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
}

.integration-brief {
  margin: 16px 28px 0;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(248, 250, 252, 0.8);
  color: #475569;
  display: grid;
  gap: 8px;
  font-size: 13px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 20px 28px 0;
}

@media (max-width: 760px) {
  .api-doc-card {
    width: 100%;
  }

  .preview-form-grid {
    grid-template-columns: 1fr;
    padding-right: 0;
  }

  .import-mode-tabs {
    flex-wrap: wrap;
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
