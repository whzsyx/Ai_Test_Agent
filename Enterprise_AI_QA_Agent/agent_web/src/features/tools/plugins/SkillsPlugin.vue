<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../../../services/api";
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

async function loadSkills() {
  loading.value = true;
  errorMessage.value = "";
  try {
    skills.value = await api.listSkills();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "读取 Skills 失败";
  } finally {
    loading.value = false;
  }
}

async function selectSkill(skill: SkillDescriptor) {
  errorMessage.value = "";
  selectedSkill.value = await api.getSkill(skill.key);
  editorKey.value = selectedSkill.value.key;
  editorContent.value = selectedSkill.value.content || "";
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
    const saved = await api.upsertSkill(editorKey.value.trim(), { content: editorContent.value });
    successMessage.value = `已保存 ${saved.key}`;
    await loadSkills();
    await selectSkill(saved);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "保存 Skill 失败";
  } finally {
    saving.value = false;
  }
}

async function deleteSkill(skill: SkillDescriptor, event: MouseEvent) {
  event.stopPropagation();
  if (!skill.installed) {
    errorMessage.value = "内置回退 Skill 不能删除";
    return;
  }
  if (!window.confirm(`确认删除 skill：${skill.key}？`)) {
    return;
  }
  deletingSkillKey.value = skill.key;
  errorMessage.value = "";
  successMessage.value = "";
  try {
    await api.deleteSkill(skill.key);
    successMessage.value = `已删除 ${skill.key}`;
    if (selectedSkill.value?.key === skill.key) {
      selectedSkill.value = null;
      editorKey.value = "";
      editorContent.value = "";
    }
    await loadSkills();
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : "删除 Skill 失败";
  } finally {
    deletingSkillKey.value = "";
  }
}

onMounted(loadSkills);
</script>

<template>
  <div class="tools-tab-pane">
    <div class="pane-header">
      <div>
        <h3 class="section-title">已安装 Skills</h3>
        <p class="head-desc">
          统一从 Agent_Server/src/SKILLS 读取和管理。支持安装本地目录、SKILL.md、zip 或 URL。
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
                {{ skill.installed ? "src/SKILLS" : "内置回退" }}
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
            :aria-label="`删除 ${skill.key}`"
            :title="`删除 ${skill.key}`"
            @click="deleteSkill(skill, $event)"
          >
            <i class="fa-regular fa-trash-can"></i>
          </button>
        </article>
      </div>

      <aside class="editor-panel">
        <div class="editor-head">
          <h4>Skill 编辑器</h4>
        </div>
        <input v-model="editorKey" placeholder="skill-key">
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
        <button :disabled="saving" @click="saveSkill">{{ saving ? "保存中..." : "保存 / 创建" }}</button>
      </aside>
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
  border: 1px solid rgba(148, 163, 184, 0.25);
  border-radius: 16px;
  padding: 14px;
  background: #ffffff;
  box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06);
}

.skills-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 0.42fr);
  gap: 18px;
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

.editor-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.editor-head h4 {
  margin: 0;
  color: var(--text);
}

.editor-panel input,
.editor-panel textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 10px 12px;
  color: var(--text);
  background: var(--surface-soft);
}

.editor-panel input:focus,
.editor-panel textarea:focus {
  border-color: var(--text);
  background: var(--surface);
  outline: none;
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--text) 10%, transparent);
}

.editor-panel textarea {
  min-height: 420px;
  margin: 10px 0;
  font-family: "JetBrains Mono", "Cascadia Code", monospace;
  line-height: 1.45;
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

.editor-panel > button {
  border: 0;
  border-radius: 10px;
  padding: 10px 14px;
  color: var(--surface);
  background: var(--text);
  cursor: pointer;
}

.editor-panel > button:hover {
  opacity: 0.88;
}

.editor-panel > button:disabled {
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
