<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useMessage } from "naive-ui";

import { api } from "../../../services/api";
import type { ApiDocRecord } from "../../../types";
import { formatServerDateTime } from "../../../utils/datetime";

const toast = useMessage();

const docs = ref<ApiDocRecord[]>([]);
const loading = ref(false);
const error = ref("");
const selectedDoc = ref<ApiDocRecord | null>(null);
const previewOpen = ref(false);
const previewLoading = ref(false);
const savingMetadata = ref(false);
const deletingId = ref("");
const uploadOpen = ref(false);
const uploadLoading = ref(false);
const uploadFile = ref<File | null>(null);
const uploadTitle = ref("");
const uploadProjectName = ref("");
const editTitle = ref("");
const editProjectName = ref("");

const hasDocs = computed(() => docs.value.length > 0);
const projectNameSuggestions = computed(() =>
  Array.from(
    new Set(
      docs.value
        .map((doc) => doc.project_name?.trim())
        .filter((value): value is string => Boolean(value)),
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
  uploadFile.value = null;
  uploadTitle.value = "";
  uploadProjectName.value = "";
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

async function submitUpload() {
  if (!uploadFile.value) {
    toast.error("请选择要上传的 API 文档文件");
    return;
  }

  uploadLoading.value = true;
  try {
    const contentBase64 = await fileToBase64(uploadFile.value);
    const created = await api.uploadApiDoc({
      filename: uploadFile.value.name,
      content_base64: contentBase64,
      source: "tools_api_docs",
      title: uploadTitle.value.trim() || null,
      project_name: uploadProjectName.value.trim() || null,
    });
    upsertDoc(created);
    await loadDocs();
    toast.success("API 文档已上传并加入文档管理", {
      duration: 2200,
    });
    setTimeout(() => {
      closeUpload();
    }, 300);
  } catch (err) {
    toast.error(err instanceof Error ? err.message : "上传 API 文档失败");
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

onMounted(() => {
  void loadDocs();
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
          统一管理通过“添加文档源”上传到 MinIO 的 OpenAPI、Swagger、Postman 与文本接口文档，并为后续接口测试模式维护所属项目。
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
      <strong>还没有上传任何 API 文档</strong>
      <span>这里展示的是明确加入“API 接口文档管理”的文件，聊天框 Attachments 上传的会话附件不会默认出现在这里。</span>
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
            <label class="upload-field">
              文档标题
              <input v-model="editTitle" placeholder="例如：用户中心 OpenAPI v2">
            </label>
            <label class="upload-field">
              所属项目
              <input
                v-model="editProjectName"
                list="api-doc-project-suggestions"
                placeholder="例如：mall-order-service"
              >
              <small v-if="projectNameSuggestions.length" class="upload-hint">
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
            <h3>上传 API 文档</h3>
            <p>支持 OpenAPI、Swagger、Postman Collection、Markdown、JSON、YAML 等文本文件，文件会保存到 MinIO。</p>
          </div>
          <button class="icon-btn" @click="closeUpload"><i class="fa-solid fa-xmark"></i></button>
        </header>

        <label class="upload-drop">
          <i class="fa-solid fa-file-arrow-up"></i>
          <strong>{{ uploadFile?.name || "选择要上传的文档文件" }}</strong>
          <span>推荐上传 JSON / YAML / Markdown / TXT / Postman Collection</span>
          <input type="file" accept=".json,.yaml,.yml,.txt,.md,.csv,.xml,.html" @change="onUploadFileChange">
        </label>

        <label class="upload-field">
          文档标题（可选）
          <input v-model="uploadTitle" placeholder="例如：用户中心 OpenAPI v2">
        </label>

        <label class="upload-field">
          所属项目（建议填写）
          <input
            v-model="uploadProjectName"
            list="api-doc-project-suggestions"
            placeholder="例如：mall-order-service"
          >
          <small v-if="projectNameSuggestions.length" class="upload-hint">
            可直接输入新项目名，也可从已有项目中选择
          </small>
        </label>

        <datalist id="api-doc-project-suggestions">
          <option
            v-for="projectName in projectNameSuggestions"
            :key="projectName"
            :value="projectName"
          />
        </datalist>

        <div class="modal-actions">
          <button class="secondary-btn" @click="closeUpload">取消</button>
          <button class="primary-btn" :disabled="uploadLoading" @click="submitUpload">
            {{ uploadLoading ? "上传中..." : "上传到 MinIO" }}
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
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.42) transparent;
  scrollbar-gutter: stable;
  border-radius: 24px;
  background: #ffffff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
}

.tools-modal::-webkit-scrollbar {
  width: 8px;
}

.tools-modal::-webkit-scrollbar-track {
  background: transparent;
}

.tools-modal::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.34);
}

.tools-modal::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 116, 139, 0.52);
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

.preview-inline-error {
  margin: 20px 28px 0;
  padding: 12px 14px;
  border-radius: 14px;
  background: rgba(239, 68, 68, 0.08);
  color: #b91c1c;
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
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.38) transparent;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.72;
  color: #0f172a;
  font-family: "Consolas", "SFMono-Regular", monospace;
}

.preview-code::-webkit-scrollbar {
  width: 8px;
}

.preview-code::-webkit-scrollbar-track {
  background: transparent;
}

.preview-code::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.32);
}

.preview-code::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 116, 139, 0.48);
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

.upload-field {
  display: grid;
  gap: 8px;
  margin: 16px 28px 0;
  font-size: 13px;
  color: #475569;
}

.upload-field input {
  width: 100%;
  border: 1px solid rgba(15, 23, 42, 0.1);
  border-radius: 12px;
  padding: 11px 12px;
  font-size: 14px;
}

.upload-hint {
  color: #64748b;
  font-size: 12px;
  line-height: 1.5;
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
