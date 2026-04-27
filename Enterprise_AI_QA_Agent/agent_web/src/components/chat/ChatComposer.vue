<script setup lang="ts">
import type { KeyboardEvent } from "vue";
import { computed, ref } from "vue";
import { NDropdown } from "naive-ui";

import { api } from "../../services/api";
import { useSessionStore } from "../../stores/session";
import type { ApiDocRecord, InputAttachment } from "../../types";

const props = defineProps<{
  docked?: boolean;
}>();

const sessionStore = useSessionStore();
const draft = ref("");
const fileInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
const uploadMessage = ref("");
const uploadError = ref("");
const pendingAttachments = ref<InputAttachment[]>([]);

const dockedPlaceholder = "给御策天检发送消息，按 Enter 快速发送，Shift+Enter 换行";
const heroPlaceholder = "例如：帮我测试后台管理系统的登录功能，覆盖各种异常输入和边界情况";
const busyTitle = "正在处理当前任务";
const idleTitle = "发送指令";
const placeholder = computed(() => (props.docked ? dockedPlaceholder : heroPlaceholder));
const buttonTitle = computed(() => (sessionStore.isBusy ? busyTitle : idleTitle));
const activeModeLabel = computed(() => sessionStore.activeMode?.name ?? "默认模式");
const activeModeSummary = computed(() => sessionStore.activeMode?.summary ?? "选择当前会话的执行模式");
const modeOptions = computed(() =>
  sessionStore.modes.map((mode) => ({
    label: mode.placeholder ? `${mode.name}（占位）` : mode.name,
    key: mode.key,
  })),
);

function handleModeSelect(key: string | number) {
  sessionStore.setModeKey(String(key));
}

function openFilePicker() {
  if (uploading.value) {
    return;
  }
  fileInput.value?.click();
}

function removeAttachment(index: number) {
  pendingAttachments.value.splice(index, 1);
}

function toInputAttachment(doc: ApiDocRecord): InputAttachment {
  return {
    kind: "file",
    name: doc.filename,
    uri: doc.storage_uri,
    content_type: doc.content_type,
    text_excerpt: doc.preview_text ? doc.preview_text.slice(0, 1200) : null,
    metadata: {
      api_doc_id: doc.id,
      title: doc.title,
      source: doc.source,
      format_label: doc.format_label,
      uploaded_at: doc.uploaded_at,
      preview_truncated: doc.preview_truncated,
      size_bytes: doc.size_bytes,
    },
  };
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

async function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = "";
  if (!files.length) {
    return;
  }

  uploading.value = true;
  uploadMessage.value = "";
  uploadError.value = "";

  try {
    const uploadedDocs: ApiDocRecord[] = [];
    for (const file of files) {
      const contentBase64 = await fileToBase64(file);
      const uploaded = await api.uploadApiDoc({
        filename: file.name,
        content_base64: contentBase64,
        source: "chat_attachment",
      });
      uploadedDocs.push(uploaded);
    }

    const nextAttachments = uploadedDocs.map(toInputAttachment);
    const existingUris = new Set(
      pendingAttachments.value.map((item) => String(item.uri || "")),
    );
    for (const attachment of nextAttachments) {
      const uri = String(attachment.uri || "");
      if (!uri || !existingUris.has(uri)) {
        pendingAttachments.value.push(attachment);
        if (uri) {
          existingUris.add(uri);
        }
      }
    }
    uploadMessage.value = `已上传 ${uploadedDocs.length} 个文件，可在“API 接口文档”中统一管理。`;
  } catch (error) {
    uploadError.value = error instanceof Error ? error.message : "上传文件失败";
  } finally {
    uploading.value = false;
  }
}

async function handleSubmit() {
  if (sessionStore.isBusy || !sessionStore.session) {
    return;
  }
  const content = draft.value;
  const attachments = pendingAttachments.value.map((item) => ({ ...item, metadata: { ...item.metadata } }));
  if (!content.trim() && attachments.length === 0) {
    return;
  }

  draft.value = "";
  pendingAttachments.value = [];
  uploadMessage.value = "";
  uploadError.value = "";
  await sessionStore.sendMessage(content, attachments);
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
    return;
  }

  event.preventDefault();
  void handleSubmit();
}

function formatAttachmentSize(value: unknown) {
  const size = Number(value || 0);
  if (!Number.isFinite(size) || size <= 0) {
    return "";
  }
  if (size >= 1024 * 1024) {
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }
  if (size >= 1024) {
    return `${Math.round(size / 1024)} KB`;
  }
  return `${size} B`;
}
</script>

<template>
  <div class="home-composer" :class="{ 'home-composer-docked': docked }">
    <textarea
      v-model="draft"
      class="home-textarea"
      :placeholder="placeholder"
      @keydown="handleKeydown"
    />

    <div v-if="pendingAttachments.length" class="home-attachments">
      <div
        v-for="(attachment, index) in pendingAttachments"
        :key="`${attachment.uri || attachment.name}-${index}`"
        class="home-attachment-chip"
      >
        <div class="home-attachment-main">
          <i class="fa-solid fa-file-lines"></i>
          <div class="home-attachment-copy">
            <strong>{{ attachment.name }}</strong>
            <span>
              {{ String(attachment.metadata?.format_label || "文档附件") }}
              <template v-if="formatAttachmentSize(attachment.metadata?.size_bytes)">
                · {{ formatAttachmentSize(attachment.metadata?.size_bytes) }}
              </template>
            </span>
          </div>
        </div>
        <button
          class="home-attachment-remove"
          type="button"
          title="移除附件"
          @click="removeAttachment(index)"
        >
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    </div>

    <div class="home-composer-footer">
      <div class="home-toolbar">
        <button class="home-tool-btn" type="button" :disabled="uploading" @click="openFilePicker">
          <i class="fa-solid" :class="uploading ? 'fa-spinner fa-spin' : 'fa-paperclip'"></i>
          {{ uploading ? "上传中..." : "Attachments" }}
        </button>
        <input
          ref="fileInput"
          class="home-file-input"
          type="file"
          multiple
          @change="handleFileChange"
        >
        <n-dropdown trigger="click" placement="top-start" :options="modeOptions" @select="handleModeSelect">
          <button class="home-tool-btn home-mode-btn" type="button" :title="activeModeSummary">
            <i class="fa-solid fa-sitemap"></i>
            {{ activeModeLabel }}
            <i class="fa-solid fa-chevron-down home-mode-caret"></i>
          </button>
        </n-dropdown>
      </div>

      <div class="home-send-group">
        <button
          class="home-send-btn"
          :disabled="sessionStore.isBusy || !sessionStore.session || (!draft.trim() && pendingAttachments.length === 0)"
          @click="handleSubmit"
          :title="buttonTitle"
          type="button"
        >
          <i class="fa-solid" :class="sessionStore.isBusy ? 'fa-spinner fa-spin' : 'fa-arrow-up'"></i>
        </button>
      </div>
    </div>

    <div v-if="uploadError" class="home-upload-notice home-upload-notice-error">{{ uploadError }}</div>
    <div v-else-if="uploadMessage" class="home-upload-notice home-upload-notice-success">{{ uploadMessage }}</div>
  </div>
</template>

<style scoped>
.home-file-input {
  display: none;
}

.home-attachments {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin: 0 20px 14px;
}

.home-attachment-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 240px;
  max-width: 360px;
  padding: 10px 12px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 14px;
  background: rgba(248, 250, 252, 0.96);
}

.home-attachment-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.home-attachment-main i {
  color: #2563eb;
}

.home-attachment-copy {
  min-width: 0;
}

.home-attachment-copy strong,
.home-attachment-copy span {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-attachment-copy strong {
  font-size: 13px;
  color: #0f172a;
}

.home-attachment-copy span {
  margin-top: 2px;
  font-size: 12px;
  color: #64748b;
}

.home-attachment-remove {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  transition: background 0.16s ease, color 0.16s ease;
}

.home-attachment-remove:hover {
  background: rgba(15, 23, 42, 0.06);
  color: #0f172a;
}

.home-upload-notice {
  margin: 12px 20px 0;
  padding: 10px 12px;
  border-radius: 12px;
  font-size: 13px;
}

.home-upload-notice-success {
  background: rgba(16, 185, 129, 0.08);
  color: #047857;
}

.home-upload-notice-error {
  background: rgba(239, 68, 68, 0.1);
  color: #b91c1c;
}
</style>
