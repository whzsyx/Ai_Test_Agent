<script setup lang="ts">
import { NModal, NDrawer } from "naive-ui";
import { onMounted, ref } from "vue";
import { api } from "../../../services/api";
import { t } from "../../../services/i18n";
import type { SkillDescriptor } from "../../../types";

const skills = ref<SkillDescriptor[]>([]);
const selectedSkill = ref<SkillDescriptor | null>(null);
const loading = ref(false);
const saving = ref(false);
const deletingSkillKey = ref("");
const errorMessage = ref("");
const successMessage = ref("");
const editorKey = ref("");
const editorContent = ref("");
const editorToolKeys = ref("");
const deleteConfirmOpen = ref(false);
const skillPendingDelete = ref<SkillDescriptor | null>(null);
const editorOpen = ref(false);

async function loadSkills() {
  loading.value = true;
  errorMessage.value = "";
  try {
    skills.value = await api.listSkills();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("skills.load_failed");
  } finally {
    loading.value = false;
  }
}

async function selectSkill(skill: SkillDescriptor) {
  errorMessage.value = "";
  selectedSkill.value = await api.getSkill(skill.key);
  editorKey.value = selectedSkill.value.key;
  editorContent.value = selectedSkill.value.content || "";
  editorToolKeys.value = (selectedSkill.value.tool_keys || []).join(", ");
  editorOpen.value = true;
}

function openNewSkillEditor() {
  selectedSkill.value = null;
  editorKey.value = "";
  editorContent.value = "";
  editorToolKeys.value = "";
  editorOpen.value = true;
}

async function saveSkill() {
  if (!editorKey.value.trim() || !editorContent.value.trim()) {
    errorMessage.value = "Skill key 和内容不能为空";
    return;
  }
  saving.value = true;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    const saved = await api.upsertSkill(editorKey.value.trim(), {
      content: withToolMetadata(editorContent.value, editorToolKeys.value),
    });
    successMessage.value = `${t("skills.saved_prefix")} ${saved.key}`;
    await loadSkills();
    await selectSkill(saved);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("skills.save_failed");
  } finally {
    saving.value = false;
  }
}

function requestDeleteSkill(skill: SkillDescriptor, event: MouseEvent) {
  event.stopPropagation();
  if (!skill.installed) {
    errorMessage.value = t("skills.builtin_cannot_delete");
    return;
  }
  skillPendingDelete.value = skill;
  deleteConfirmOpen.value = true;
}

function closeDeleteConfirm() {
  if (deletingSkillKey.value) {
    return;
  }
  deleteConfirmOpen.value = false;
  skillPendingDelete.value = null;
}

async function confirmDeleteSkill() {
  const skill = skillPendingDelete.value;
  if (!skill) {
    return;
  }
  deletingSkillKey.value = skill.key;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    await api.deleteSkill(skill.key);
    successMessage.value = `${t("skills.deleted_prefix")} ${skill.key}`;
    if (selectedSkill.value?.key === skill.key) {
      selectedSkill.value = null;
      editorKey.value = "";
      editorContent.value = "";
      editorToolKeys.value = "";
    }
    await loadSkills();
    deleteConfirmOpen.value = false;
    skillPendingDelete.value = null;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : t("skills.delete_failed");
  } finally {
    deletingSkillKey.value = "";
  }
}

function withToolMetadata(content: string, rawToolKeys: string): string {
  const tools = rawToolKeys
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
    .filter((item, index, all) => all.indexOf(item) === index);
  const line = `tools: ${tools.join(", ")}`;
  const normalized = content.replace(/\r\n/g, "\n");
  const frontmatter = normalized.match(/^---\n([\s\S]*?)\n---/);
  if (!frontmatter) {
    return normalized;
  }
  const body = frontmatter[1];
  const updatedBody = /^tools\s*:/m.test(body)
    ? body.replace(/^tools\s*:.*$/m, line)
    : `${body}\n${line}`;
  return normalized.replace(frontmatter[0], `---\n${updatedBody}\n---`);
}

onMounted(loadSkills);
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <div>
        <h3 class="section-title">{{ t("skills.installed_title") }}</h3>
        <p class="head-desc">
          {{ t("skills.installed_desc") }}
        </p>
      </div>
    </div>

    <div v-if="errorMessage" class="notice error">{{ errorMessage }}</div>
    <div v-if="successMessage" class="notice success">{{ successMessage }}</div>

    <div class="skills-layout">
      <div class="skills-grid">
        <article
          v-for="skill in skills"
          :key="skill.key"
          class="skill-card"
          :class="{ active: selectedSkill?.key === skill.key }"
          @click="selectSkill(skill)"
        >
          <div class="skill-icon"><i class="fa-brands fa-markdown"></i></div>
          <div class="skill-body">
            <div class="skill-head">
              <h4>{{ skill.name || skill.key }}</h4>
              <span class="skill-state" :class="skill.installed ? 'enabled' : 'disabled'">
                {{ skill.installed ? "src/SKILLS" : t("skills.builtin_fallback") }}
              </span>
            </div>
            <p>{{ skill.description || skill.summary }}</p>
            <div class="tag-row">
              <span v-for="tag in skill.tags" :key="tag">{{ tag }}</span>
            </div>
            <div class="mono muted-small">{{ skill.path || skill.key }}</div>
          </div>
          <button
            v-if="skill.installed"
            class="skill-delete-btn"
            :disabled="deletingSkillKey === skill.key"
            :aria-label="`${t('common.delete')} ${skill.key}`"
            :title="`${t('common.delete')} ${skill.key}`"
            @click="requestDeleteSkill(skill, $event)"
          >
            <i class="fa-regular fa-trash-can"></i>
          </button>
        </article>
      </div>

      <NDrawer v-model:show="editorOpen" :width="500" placement="right">
        <aside class="editor-panel">
          <div class="editor-head">
            <h4>{{ t("skills.editor_title") }}</h4>
            <button class="icon-btn" @click="editorOpen = false"><i class="fa-solid fa-xmark"></i></button>
          </div>
          <div class="editor-body">
            <label class="editor-field">
              {{ t("skills.install_name") }}
              <input v-model="editorKey" placeholder="例如 playwright-cli">
            </label>
            <label class="editor-field">
              {{ t("skills.tool_keys_label") }}
              <input v-model="editorToolKeys" placeholder="mail-status, mail-send, mail-list">
              <span class="field-hint">{{ t("skills.tool_keys_hint") }}</span>
            </label>
            <label class="editor-field editor-field-grow">
              {{ t("skills.content_label") }}
              <textarea
                v-model="editorContent"
                spellcheck="false"
                placeholder="---
                name: my-skill
                description: What this skill does.
                ---

                # My Skill
                "
              />
            </label>
          </div>
          <div class="editor-actions">
            <button class="secondary-btn" @click="editorOpen = false" style="margin-right: 12px;">{{ t("common.cancel") }}</button>
            <button :disabled="saving" class="primary-btn" @click="saveSkill">
              {{ saving ? t("skills.saving") : t("skills.save_create") }}
            </button>
          </div>
        </aside>
      </NDrawer>
    </div>

    <NModal
      v-model:show="deleteConfirmOpen"
      display-directive="show"
      class="skill-confirm-modal"
      :mask-closable="!deletingSkillKey"
      @esc="closeDeleteConfirm"
    >
      <div class="confirm-card">
        <button class="confirm-close" :disabled="Boolean(deletingSkillKey)" @click="closeDeleteConfirm">
          <i class="fa-solid fa-xmark"></i>
        </button>
        <div class="confirm-copy">
          <h3>{{ t("skills.delete_title") }}</h3>
          <p class="confirm-text">
            {{ t("skills.confirm_delete") }} <strong>{{ skillPendingDelete?.key }}</strong>？
          </p>
          <p class="confirm-hint">
            {{ t("skills.delete_hint") }}
          </p>
        </div>
        <div class="confirm-actions">
          <button class="confirm-secondary" :disabled="Boolean(deletingSkillKey)" @click="closeDeleteConfirm">
            {{ t("common.cancel") }}
          </button>
          <button class="confirm-primary" :disabled="Boolean(deletingSkillKey)" @click="confirmDeleteSkill">
            {{ deletingSkillKey ? t("skills.deleting") : t("skills.confirm_delete_btn") }}
          </button>
        </div>
      </div>
    </NModal>
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
  margin-bottom: 20px;
}

.pane-header .section-title {
  margin: 0 0 8px;
  font-size: 18px;
}

.pane-header .head-desc {
  margin: 0;
}

.editor-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface);
}

.editor-head {
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.icon-btn {
  background: transparent;
  border: none;
  color: var(--muted);
  cursor: pointer;
  font-size: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  transition: background 0.2s, color 0.2s;
}

.icon-btn:hover {
  background: var(--surface-muted);
  color: var(--text);
}

.editor-head h4 {
  margin: 0;
  font-size: 18px;
  color: var(--text);
}

.editor-body {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  flex: 1;
  min-height: 0;
}

.editor-field {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}

.editor-field-grow {
  flex: 1;
  min-height: 0;
}

.editor-field input,
.editor-field textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  color: var(--text);
  background: var(--surface);
  font-weight: normal;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.editor-field input:focus,
.editor-field textarea:focus {
  border-color: var(--text);
  outline: none;
  box-shadow: 0 0 0 1px var(--text);
}

.field-hint {
  color: var(--muted);
  font-size: 12px;
  font-weight: 400;
  line-height: 1.4;
}

.editor-field textarea {
  flex: 1;
  min-height: 0;
  font-family: "JetBrains Mono", "Cascadia Code", monospace;
  line-height: 1.45;
  font-size: 13px;
  resize: none;
}

.editor-actions {
  padding: 16px 24px;
  border-top: 1px solid var(--border);
  background: var(--surface);
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
}

.skills-layout {
  display: block;
}

.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 14px;
}

.skill-card {
  cursor: pointer;
  min-width: 0;
  overflow: hidden;
  position: relative;
  padding-bottom: 44px;
  background: var(--surface);
  transition: border-color 0.18s ease, box-shadow 0.18s ease, background 0.18s ease;
}

.skill-card:hover {
  border-color: var(--border-strong);
  box-shadow: var(--shadow-soft);
}

.skill-card.active {
  border-color: var(--text);
  box-shadow: 0 0 0 1px color-mix(in srgb, var(--text) 16%, transparent);
}

.skill-delete-btn {
  position: absolute;
  left: 16px;
  bottom: 12px;
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0;
  color: var(--muted);
  background: var(--surface-soft);
  opacity: 0.78;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease, opacity 0.18s ease;
}

.skill-delete-btn:hover {
  border-color: var(--text);
  color: var(--text);
  background: var(--surface-strong);
  opacity: 1;
}

.skill-delete-btn:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 10px 0;
}

.skill-body {
  min-width: 0;
  overflow: hidden;
}

.skill-head {
  min-width: 0;
}

.skill-head h4 {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.skill-body p {
  display: -webkit-box;
  min-height: 44px;
  margin: 6px 0 0;
  overflow: hidden;
  color: #475569;
  line-height: 1.4;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.tag-row span {
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 12px;
}

:deep(.skill-state.enabled) {
  border-color: var(--border-strong);
  color: var(--text);
  background: var(--surface-muted);
}

.mono.muted-small {
  display: block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}



.notice {
  margin-bottom: 12px;
  border-radius: 10px;
  padding: 10px 12px;
}

.notice.error {
  color: #fecaca;
  background: rgba(127, 29, 29, 0.35);
}

.notice.success {
  color: #bbf7d0;
  background: rgba(20, 83, 45, 0.35);
}



:deep(.skill-confirm-modal) {
  width: min(420px, calc(100vw - 40px));
}

.confirm-card {
  position: relative;
  border-radius: 16px;
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-panel);
  border: 1px solid var(--border);
  padding: 22px;
}

.confirm-close {
  position: absolute;
  right: 14px;
  top: 14px;
  width: 30px;
  height: 30px;
  border: 0;
  border-radius: 999px;
  color: var(--muted);
  background: transparent;
  cursor: pointer;
}

.confirm-close:hover {
  color: var(--text);
  background: var(--surface-muted);
}

.confirm-icon {
  width: 42px;
  height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  border-radius: 12px;
  color: var(--text);
  background: var(--surface-soft);
}

.confirm-copy h3 {
  margin: 14px 0 8px;
  font-size: 18px;
  line-height: 1.3;
}

.confirm-text {
  margin: 0 0 8px;
  color: var(--text);
}

.confirm-hint {
  margin: 0;
  color: var(--muted);
  line-height: 1.6;
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
}

.confirm-primary,
.confirm-secondary {
  border: 1px solid var(--border);
  border-radius: 999px;
  padding: 8px 16px;
  cursor: pointer;
}

.confirm-primary {
  color: var(--surface);
  background: var(--text);
  border-color: var(--text);
}

.confirm-secondary {
  color: var(--text);
  background: var(--surface-soft);
}

.confirm-primary:disabled,
.confirm-secondary:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

@media (max-width: 1100px) {
  .skills-layout {
    grid-template-columns: 1fr;
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
