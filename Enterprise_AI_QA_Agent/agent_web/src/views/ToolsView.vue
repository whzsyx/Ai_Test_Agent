<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { api } from "../services/api";
import { t } from "../services/i18n";
import { toolsPlugins, type ToolsPluginKey } from "../features/tools/plugins";
import type { SkillMarketplaceItem, SkillMarketplaceSource } from "../types";

const defaultPlugin = toolsPlugins[0];
const activeTab = ref<ToolsPluginKey>(defaultPlugin.key);
const skillsRefreshKey = ref(0);

/** 插件导入页内子 Tab：api / mcp / managed，由 PluginsPlugin 广播 */
const pluginsIntegrationPane = ref<"api" | "mcp" | "managed">("api");

const marketplaceOpen = ref(false);
const marketplaceSource = ref<SkillMarketplaceSource>("anthropic");
const marketplaceQuery = ref("");
const marketplaceResults = ref<SkillMarketplaceItem[]>([]);
const selectedMarketplaceSkill = ref<SkillMarketplaceItem | null>(null);
const marketplaceLoading = ref(false);
const marketplaceInstallingId = ref("");
const marketplaceMessage = ref("");
const marketplaceError = ref("");
const marketplaceInstallKey = ref("");
const marketplaceOverwrite = ref(false);

const uploadOpen = ref(false);
const uploadFile = ref<File | null>(null);
const uploadKey = ref("");
const uploadOverwrite = ref(false);
const uploadLoading = ref(false);
const uploadMessage = ref("");
const uploadError = ref("");

const activePlugin = computed(
  () => toolsPlugins.find((item) => item.key === activeTab.value) ?? defaultPlugin,
);

function installedSkillMessage(result: unknown) {
  const item = result as { key?: string; installed_count?: number; failed_count?: number; summary?: string };
  if (typeof item.installed_count === "number") {
    return item.summary || t("tools.installed_count", { count: String(item.installed_count) });
  }
  return t("tools.installed_key", { key: item.key || "skill" });
}

function openMarketplace() {
  marketplaceOpen.value = true;
  marketplaceSource.value = "anthropic";
  marketplaceQuery.value = "";
  marketplaceResults.value = [];
  selectedMarketplaceSkill.value = null;
  marketplaceMessage.value = "";
  marketplaceError.value = "";
  marketplaceInstallKey.value = "";
  marketplaceOverwrite.value = false;
}

function closeMarketplace() {
  marketplaceOpen.value = false;
}

async function searchMarketplace() {
  marketplaceLoading.value = true;
  marketplaceError.value = "";
  marketplaceMessage.value = "";
  try {
    const response = await api.searchSkillMarketplace(
      marketplaceSource.value,
      marketplaceQuery.value.trim(),
      30,
    );
    marketplaceResults.value = response.items || [];
    selectedMarketplaceSkill.value = marketplaceResults.value[0] ?? null;
  } catch (error) {
    marketplaceError.value = error instanceof Error ? error.message : t("tools.search_skill_failed");
  } finally {
    marketplaceLoading.value = false;
  }
}

function switchMarketplaceSource(source: SkillMarketplaceSource) {
  marketplaceSource.value = source;
  marketplaceResults.value = [];
  selectedMarketplaceSkill.value = null;
  marketplaceError.value = "";
  marketplaceMessage.value = "";
}

async function installMarketplaceSkill(skill: SkillMarketplaceItem) {
  marketplaceInstallingId.value = skill.id;
  marketplaceError.value = "";
  marketplaceMessage.value = "";
  try {
    const installed = await api.installMarketplaceSkill({
      source: marketplaceSource.value,
      skill_id: skill.id,
      url: skill.url || null,
      key: marketplaceInstallKey.value.trim() || null,
      overwrite: marketplaceOverwrite.value,
    });
    marketplaceMessage.value = installedSkillMessage(installed);
    skillsRefreshKey.value += 1;
  } catch (error) {
    marketplaceError.value = error instanceof Error ? error.message : t("tools.install_skill_failed");
  } finally {
    marketplaceInstallingId.value = "";
  }
}

function openUpload() {
  uploadOpen.value = true;
  uploadFile.value = null;
  uploadKey.value = "";
  uploadOverwrite.value = false;
  uploadMessage.value = "";
  uploadError.value = "";
}

function closeUpload() {
  uploadOpen.value = false;
}

function handleUploadFile(event: Event) {
  const input = event.target as HTMLInputElement;
  uploadFile.value = input.files?.[0] ?? null;
  uploadError.value = "";
  uploadMessage.value = "";
}

async function uploadSkillPackage() {
  if (!uploadFile.value) {
    uploadError.value = t("tools.upload_select_file");
    return;
  }
  uploadLoading.value = true;
  uploadError.value = "";
  uploadMessage.value = "";
  try {
    const contentBase64 = await fileToBase64(uploadFile.value);
    const installed = await api.uploadSkill({
      filename: uploadFile.value.name,
      content_base64: contentBase64,
      key: uploadKey.value.trim() || null,
      overwrite: uploadOverwrite.value,
    });
    uploadMessage.value = installedSkillMessage(installed);
    skillsRefreshKey.value += 1;
  } catch (error) {
    uploadError.value = error instanceof Error ? error.message : t("tools.upload_skill_failed");
  } finally {
    uploadLoading.value = false;
  }
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      resolve(result.includes(",") ? result.split(",")[1] : result);
    };
    reader.onerror = () => reject(reader.error || new Error(t("tools.read_file_failed")));
    reader.readAsDataURL(file);
  });
}

function openApiDocUpload() {
  window.dispatchEvent(new CustomEvent("qa-agent:open-api-doc-upload"));
}

function openIntegrationCreate(kind: "api" | "mcp") {
  window.dispatchEvent(new CustomEvent("qa-agent:open-integration-create", { detail: { kind } }));
}

function onPluginsIntegrationPaneEvent(ev: Event) {
  const tab = (ev as CustomEvent<{ tab?: string }>).detail?.tab;
  if (tab === "api" || tab === "mcp" || tab === "managed") {
    pluginsIntegrationPane.value = tab;
  }
}

onMounted(() => {
  window.addEventListener("qa-agent:plugins-integration-pane", onPluginsIntegrationPaneEvent);
});

onBeforeUnmount(() => {
  window.removeEventListener("qa-agent:plugins-integration-pane", onPluginsIntegrationPaneEvent);
});
</script>

<template>
  <section class="view-page tools-page">
    <div class="page-head">
      <div>
        <h2>{{ t("tools.title") }}</h2>
        <p class="head-desc">{{ t("tools.page_desc") }}</p>
      </div>
      <div class="page-head-actions">
        <template v-if="activeTab === 'skills'">
          <button class="secondary-btn" @click="openMarketplace">
            <i class="fa-brands fa-github"></i> {{ t("tools.github_import") }}
          </button>
          <button class="primary-btn" @click="openUpload">
            <i class="fa-solid fa-upload"></i> {{ t("tools.upload_skill_package") }}
          </button>
        </template>
        <template v-else-if="activeTab === 'apidocs'">
          <button class="primary-btn" @click="openApiDocUpload"><i class="fa-solid fa-plus"></i> {{ t("tools.add_doc_source") }}</button>
        </template>
        <template v-else-if="activeTab === 'plugins'">
          <button
            v-if="pluginsIntegrationPane === 'api'"
            class="primary-btn"
            @click="openIntegrationCreate('api')"
          >
            <i class="fa-solid fa-plus"></i> {{ t("tools.add_api_integration") }}
          </button>
          <button
            v-else-if="pluginsIntegrationPane === 'mcp'"
            class="primary-btn"
            @click="openIntegrationCreate('mcp')"
          >
            <i class="fa-solid fa-plus"></i> {{ t("tools.add_mcp_integration") }}
          </button>
        </template>
      </div>
    </div>

    <nav class="tools-secondary-nav">
      <button
        v-for="plugin in toolsPlugins"
        :key="plugin.key"
        class="tools-tab-btn"
        :class="{ active: activeTab === plugin.key }"
        @click="activeTab = plugin.key"
      >
        <i :class="[`fa-${plugin.iconType}`, plugin.icon]"></i>
        <span>{{ t(plugin.labelKey) }}</span>
      </button>
    </nav>

    <div class="tools-content-area">
      <component
        :is="activePlugin.component"
        :key="activePlugin.key === 'skills' ? `skills-${skillsRefreshKey}` : activePlugin.key"
      />
    </div>

    <div v-if="marketplaceOpen" class="tools-modal-backdrop" @click.self="closeMarketplace">
      <section class="tools-modal marketplace-modal">
        <header class="tools-modal-head">
          <div>
            <h3>{{ t("tools.import_skills") }}</h3>
            <p>{{ t("tools.import_skills_desc") }}</p>
          </div>
          <button class="icon-btn" @click="closeMarketplace"><i class="fa-solid fa-xmark"></i></button>
        </header>

        <div class="marketplace-source-tabs">
          <button :class="{ active: marketplaceSource === 'anthropic' }" @click="switchMarketplaceSource('anthropic')">
            Anthropic
          </button>
          <button :class="{ active: marketplaceSource === 'skillsmp' }" @click="switchMarketplaceSource('skillsmp')">
            SkillsMP
          </button>
        </div>

        <div class="marketplace-search">
          <input
            v-model="marketplaceQuery"
            :placeholder="t('tools.search_skill_placeholder')"
            @keydown.enter="searchMarketplace"
          >
          <button class="primary-btn" :disabled="marketplaceLoading" @click="searchMarketplace">
            {{ marketplaceLoading ? t("tools.searching") : t("common.search") }}
          </button>
        </div>

        <div v-if="marketplaceError" class="modal-notice error">{{ marketplaceError }}</div>
        <div v-if="marketplaceMessage" class="modal-notice success">{{ marketplaceMessage }}</div>

        <div class="marketplace-body">
          <div class="marketplace-results">
            <button
              v-for="skill in marketplaceResults"
              :key="`${skill.source}-${skill.id}`"
              class="marketplace-result"
              :class="{ active: selectedMarketplaceSkill?.id === skill.id }"
              @click="selectedMarketplaceSkill = skill"
            >
              <strong>{{ skill.name || skill.id }}</strong>
              <span>{{ skill.description || t("tools.no_description") }}</span>
              <small>{{ skill.source }} / {{ skill.id }}</small>
            </button>
            <div v-if="!marketplaceLoading && !marketplaceResults.length" class="marketplace-empty">
              {{ t("tools.search_hint") }}
            </div>
          </div>

          <aside class="marketplace-preview">
            <template v-if="selectedMarketplaceSkill">
              <div class="preview-header">
                <h4>{{ selectedMarketplaceSkill.name || selectedMarketplaceSkill.id }}</h4>
                <div class="tag-row" v-if="selectedMarketplaceSkill.tags?.length">
                  <span v-for="tag in selectedMarketplaceSkill.tags" :key="tag">{{ tag }}</span>
                </div>
              </div>
              
              <div class="preview-scroll-area">
                <p class="preview-desc">{{ selectedMarketplaceSkill.description || t("tools.no_description") }}</p>
                <pre v-if="selectedMarketplaceSkill.content">{{ selectedMarketplaceSkill.content }}</pre>
              </div>

              <div class="preview-actions">
                <label class="install-name-field">
                  {{ t("tools.install_name") }}
                  <input v-model="marketplaceInstallKey" :placeholder="selectedMarketplaceSkill.key || selectedMarketplaceSkill.id">
                </label>
                <div class="preview-actions-row">
                  <label class="check-row">
                    <input v-model="marketplaceOverwrite" type="checkbox">
                    {{ t("tools.overwrite_skill") }}
                  </label>
                  <button
                    class="primary-btn"
                    :disabled="marketplaceInstallingId === selectedMarketplaceSkill.id"
                    @click="installMarketplaceSkill(selectedMarketplaceSkill)"
                  >
                    {{ marketplaceInstallingId === selectedMarketplaceSkill.id ? t("tools.installing") : t("tools.install_skill") }}
                  </button>
                </div>
              </div>
            </template>
            <div v-else class="marketplace-empty">
              <i class="fa-solid fa-cube" style="font-size: 32px; margin-bottom: 12px; opacity: 0.5;"></i>
              <div>{{ t("tools.select_result_hint") }}</div>
            </div>
          </aside>
        </div>
      </section>
    </div>

    <div v-if="uploadOpen" class="tools-modal-backdrop" @click.self="closeUpload">
      <section class="tools-modal upload-modal">
        <header class="tools-modal-head">
          <div>
            <h3>{{ t("tools.upload_skill_package") }}</h3>
            <p>{{ t("tools.upload_skill_desc") }}</p>
          </div>
          <button class="icon-btn" @click="closeUpload"><i class="fa-solid fa-xmark"></i></button>
        </header>

        <label class="upload-drop">
          <i class="fa-solid fa-file-arrow-up"></i>
          <strong>{{ uploadFile?.name || t("tools.select_skill_file") }}</strong>
          <span>{{ t("tools.upload_target_desc") }}</span>
          <input type="file" accept=".md,.zip" @change="handleUploadFile">
        </label>

        <label class="upload-field">
          {{ t("tools.optional_install_name") }}
          <input v-model="uploadKey" :placeholder="t('tools.install_name_placeholder')">
        </label>
        <label class="check-row">
          <input v-model="uploadOverwrite" type="checkbox">
          {{ t("tools.overwrite_skill") }}
        </label>

        <div v-if="uploadError" class="modal-notice error">{{ uploadError }}</div>
        <div v-if="uploadMessage" class="modal-notice success">{{ uploadMessage }}</div>

        <div class="modal-actions">
          <button class="secondary-btn" @click="closeUpload">{{ t("common.cancel") }}</button>
          <button class="primary-btn" :disabled="uploadLoading" @click="uploadSkillPackage">
            {{ uploadLoading ? t("tools.uploading") : t("tools.upload_and_install") }}
          </button>
        </div>
      </section>
    </div>
  </section>
</template>

<style scoped>
.tools-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 24px 32px;
}

.page-head {
  margin-bottom: 16px;
  padding-bottom: 12px;
}

.page-head h2 {
  font-size: 24px;
  margin-bottom: 4px;
}

.head-desc {
  font-size: 13px;
  margin: 0;
}

.tools-secondary-nav {
  display: flex;
  gap: 8px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
}

.tools-tab-btn {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  padding: 12px 16px;
  font-size: 14px;
  font-weight: 600;
  color: var(--muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: color 0.2s, border-color 0.2s;
  margin-bottom: -1px;
}

.tools-tab-btn i {
  font-size: 15px;
}

.tools-tab-btn:hover {
  color: var(--text);
}

.tools-tab-btn.active {
  color: var(--text);
  border-bottom-color: var(--text);
}

.tools-content-area {
  flex: 1;
  overflow-y: auto;
}

.tools-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
  background: rgba(15, 23, 42, 0.24);
  backdrop-filter: blur(3px);
}

.tools-modal {
  width: min(1040px, 94vw);
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: var(--surface);
  box-shadow: var(--shadow-panel);
}

.marketplace-modal {
  height: min(760px, 88vh);
}

.upload-modal {
  width: min(560px, 94vw);
  padding-bottom: 18px;
}

.tools-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 18px;
  border-bottom: 1px solid var(--border);
}

.tools-modal-head h3 {
  margin: 0 0 6px;
  font-size: 18px;
}

.tools-modal-head p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}

.marketplace-source-tabs,
.marketplace-search {
  display: flex;
  gap: 10px;
  padding: 14px 18px 0;
}

.marketplace-source-tabs button {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 8px 12px;
  color: var(--muted);
  background: var(--surface-soft);
  cursor: pointer;
}

.marketplace-source-tabs button.active {
  border-color: var(--text);
  color: var(--surface);
  background: var(--text);
}

.marketplace-search input,
.marketplace-preview input,
.upload-field input {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  color: var(--text);
  background: var(--surface-soft);
}

.marketplace-search input:focus,
.marketplace-preview input:focus,
.upload-field input:focus {
  border-color: var(--text);
  outline: none;
}

.marketplace-body {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(360px, 1fr);
  gap: 20px;
  padding: 20px;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.marketplace-results {
  min-height: 0;
  max-height: 100%;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding-right: 8px;
}

.marketplace-result {
  display: flex;
  flex-direction: column;
  gap: 8px;
  text-align: left;
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.marketplace-result:hover {
  transform: translateY(-1px);
  border-color: var(--border-strong);
  box-shadow: var(--shadow-soft);
}

.marketplace-result.active {
  border-color: var(--text);
  box-shadow: 0 0 0 1px var(--text);
}

.marketplace-result span {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: 13px;
  line-height: 1.5;
  color: var(--muted);
}

.marketplace-result small {
  font-size: 11px;
  color: var(--muted);
  opacity: 0.8;
}

.marketplace-result span,
.marketplace-result small,
.marketplace-empty {
  color: var(--muted);
}

.marketplace-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
}

.marketplace-preview {
  display: flex;
  flex-direction: column;
  min-height: 0;
  max-height: 100%;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface-soft);
  overflow: hidden;
}

.preview-header {
  padding: 20px 20px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.preview-header h4 {
  font-size: 18px;
  margin: 0;
  color: var(--text);
}

.preview-scroll-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.preview-desc {
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
  color: var(--muted);
}

.preview-scroll-area pre {
  margin: 16px 0 0;
  padding: 14px;
  border-radius: 10px;
  font-size: 13px;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  white-space: pre-wrap;
  word-break: break-all;
}

.preview-actions {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
  background: var(--surface);
  display: flex;
  flex-direction: column;
  gap: 16px;
  flex-shrink: 0;
}

.install-name-field {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.install-name-field input {
  flex: 1;
}

.upload-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.preview-actions-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-row span {
  padding: 3px 8px;
  border-radius: 999px;
  color: var(--muted);
  background: var(--surface-muted);
  font-size: 12px;
}

.check-row {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--muted);
  font-weight: 500;
}

.check-row input {
  width: auto;
}

.upload-drop {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 18px;
  min-height: 170px;
  border: 1px dashed var(--border-strong);
  border-radius: 16px;
  color: var(--muted);
  background: var(--surface-soft);
  cursor: pointer;
}

.upload-drop i {
  font-size: 28px;
  color: var(--text);
}

.upload-drop strong {
  color: var(--text);
}

.upload-drop input {
  display: none;
}

.upload-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  margin: 16px 18px;
}

.upload-modal .check-row,
.modal-notice,
.modal-actions {
  margin-left: 18px;
  margin-right: 18px;
}

.modal-notice {
  margin-top: 12px;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
}

.modal-notice.error {
  color: #991b1b;
  background: #fee2e2;
}

.modal-notice.success {
  color: #166534;
  background: #dcfce7;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.primary-btn:disabled,
.secondary-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@media (max-width: 900px) {
  .marketplace-body {
    grid-template-columns: 1fr;
  }
}
</style>
