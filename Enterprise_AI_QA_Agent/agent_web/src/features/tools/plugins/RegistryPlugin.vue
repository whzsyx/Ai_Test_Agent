<script setup lang="ts">
import { computed, ref } from "vue";

import { t } from "../../../services/i18n";
import { useSessionStore } from "../../../stores/session";
import type { AgentDescriptor, ToolDescriptor } from "../../../types";

type RegistryDetailRecord =
  | { kind: "agent"; data: AgentDescriptor }
  | { kind: "tool"; data: ToolDescriptor };

interface RegistryGroup<T> {
  key: string;
  label: string;
  items: T[];
}

const sessionStore = useSessionStore();
const detailRecord = ref<RegistryDetailRecord | null>(null);

const agents = computed(() => sessionStore.agents ?? []);
const tools = computed(() => sessionStore.tools ?? []);

const safeTools = computed(() =>
  tools.value.filter((tool) => (tool.permission_level || "safe") === "safe"),
);
const guardedTools = computed(() =>
  tools.value.filter((tool) => (tool.permission_level || "safe") !== "safe"),
);

function toolCategoryLabel(value: string) {
  const text = String(value || "").trim();
  if (!text) {
    return t("registry.category_unclassified");
  }

  const translated = t(`registry.category_${text}`);
  return translated === `registry.category_${text}` ? text : translated;
}

function permissionLabel(value?: ToolDescriptor["permission_level"]) {
  if (value === "ask") {
    return t("registry.permission_ask");
  }
  if (value === "restricted") {
    return t("registry.permission_restricted");
  }
  return t("registry.permission_safe");
}

function buildAgentGroups(items: AgentDescriptor[]): RegistryGroup<AgentDescriptor>[] {
  const groups: RegistryGroup<AgentDescriptor>[] = [
    { key: "coordination", label: "协调 / 规划", items: [] },
    { key: "execution", label: "执行 / 探索", items: [] },
    { key: "review", label: "代码审批", items: [] },
  ];

  for (const agent of items) {
    const text = `${agent.key} ${agent.name} ${agent.role} ${agent.summary} ${agent.description}`.toLowerCase();
    if (
      text.includes("review") ||
      text.includes("synthesizer") ||
      text.includes("code") ||
      text.includes("审批")
    ) {
      groups[2].items.push(agent);
      continue;
    }
    if (
      text.includes("executor") ||
      text.includes("explorer") ||
      text.includes("automation") ||
      text.includes("tester") ||
      text.includes("verifier")
    ) {
      groups[1].items.push(agent);
      continue;
    }
    groups[0].items.push(agent);
  }

  return groups.filter((group) => group.items.length > 0);
}

function buildToolGroups(items: ToolDescriptor[]): RegistryGroup<ToolDescriptor>[] {
  const buckets = new Map<string, ToolDescriptor[]>();
  for (const tool of items) {
    const label = toolCategoryLabel(tool.category);
    const list = buckets.get(label) ?? [];
    list.push(tool);
    buckets.set(label, list);
  }

  return Array.from(buckets.entries())
    .map(([label, groupItems]) => ({
      key: label,
      label,
      items: groupItems.sort((left, right) => left.name.localeCompare(right.name, "zh-CN")),
    }))
    .sort((left, right) => left.label.localeCompare(right.label, "zh-CN"));
}

const agentGroups = computed(() => buildAgentGroups(agents.value));
const safeToolGroups = computed(() => buildToolGroups(safeTools.value));
const guardedToolGroups = computed(() => buildToolGroups(guardedTools.value));

function groupLabel(key: string, fallback: string) {
  const translated = t(`registry.group_${key}`);
  return translated === `registry.group_${key}` ? fallback : translated;
}

function openAgentDetail(agent: AgentDescriptor) {
  detailRecord.value = { kind: "agent", data: agent };
}

function openToolDetail(tool: ToolDescriptor) {
  detailRecord.value = { kind: "tool", data: tool };
}

function closeDetail() {
  detailRecord.value = null;
}

const linkedAgents = computed(() => {
  if (!detailRecord.value || detailRecord.value.kind !== "tool") {
    return [];
  }
  return agents.value.filter((agent) => agent.supported_tools.includes(detailRecord.value!.data.key));
});
</script>

<template>
  <div class="registry-pane">
    <div class="pane-header">
      <h3 class="section-title">{{ t("registry.title") }}</h3>
      <p class="head-desc">{{ t("registry.desc") }}</p>
    </div>

    <div v-if="agents.length || tools.length" class="registry-groups">
      <section class="registry-group">
        <div class="registry-group-head">
          <strong>{{ t("registry.group_agents") }}</strong>
          <span>{{ agents.length }}</span>
        </div>
        <div class="registry-subgroups">
          <div v-for="group in agentGroups" :key="group.key" class="registry-subgroup">
            <div class="registry-subgroup-head">
              <em>{{ groupLabel(group.key, group.label) }}</em>
              <span>{{ group.items.length }}</span>
            </div>
            <div class="registry-tags">
              <button
                v-for="agent in group.items"
                :key="agent.key"
                type="button"
                class="registry-tag registry-tag--agent"
                @click="openAgentDetail(agent)"
              >
                {{ agent.name }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section class="registry-group">
        <div class="registry-group-head">
          <strong>{{ t("registry.group_safe_tools") }}</strong>
          <span>{{ safeTools.length }}</span>
        </div>
        <div class="registry-subgroups">
          <div v-for="group in safeToolGroups" :key="group.key" class="registry-subgroup">
            <div class="registry-subgroup-head">
              <em>{{ group.label }}</em>
              <span>{{ group.items.length }}</span>
            </div>
            <div class="registry-tags">
              <button
                v-for="tool in group.items"
                :key="tool.key"
                type="button"
                class="registry-tag registry-tag--tool"
                @click="openToolDetail(tool)"
              >
                {{ tool.name }}
              </button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="guardedTools.length" class="registry-group">
        <div class="registry-group-head">
          <strong>{{ t("registry.group_guarded_tools") }}</strong>
          <span>{{ guardedTools.length }}</span>
        </div>
        <div class="registry-subgroups">
          <div v-for="group in guardedToolGroups" :key="group.key" class="registry-subgroup">
            <div class="registry-subgroup-head">
              <em>{{ group.label }}</em>
              <span>{{ group.items.length }}</span>
            </div>
            <div class="registry-tags">
              <button
                v-for="tool in group.items"
                :key="tool.key"
                type="button"
                class="registry-tag registry-tag--tool registry-tag--guarded"
                @click="openToolDetail(tool)"
              >
                {{ tool.name }}
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>

    <div v-else class="registry-empty">
      <i class="fa-solid fa-ghost"></i>
      <p>{{ t("registry.empty") }}</p>
    </div>

    <div v-if="detailRecord" class="registry-modal-backdrop" @click.self="closeDetail">
      <section class="registry-modal">
        <header class="registry-modal-head">
          <div>
            <h4>{{ detailRecord.data.name }}</h4>
            <p>{{ detailRecord.data.key }}</p>
          </div>
          <button type="button" class="registry-modal-close" @click="closeDetail">
            <i class="fa-solid fa-xmark"></i>
          </button>
        </header>

        <div v-if="detailRecord.kind === 'agent'" class="registry-modal-body">
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.agent_role") }}</span>
            <strong>{{ detailRecord.data.role }}</strong>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.summary") }}</span>
            <p>{{ detailRecord.data.summary || detailRecord.data.description }}</p>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.default_model") }}</span>
            <strong>{{ detailRecord.data.default_model || t("registry.unspecified") }}</strong>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.supported_tools") }}</span>
            <div class="detail-tags">
              <span
                v-for="toolKey in detailRecord.data.supported_tools"
                :key="toolKey"
                class="detail-chip"
              >
                {{ tools.find((item) => item.key === toolKey)?.name || toolKey }}
              </span>
            </div>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.supported_skills") }}</span>
            <div class="detail-tags">
              <span
                v-for="skillKey in detailRecord.data.supported_skills"
                :key="skillKey"
                class="detail-chip"
              >
                {{ skillKey }}
              </span>
              <span v-if="!detailRecord.data.supported_skills.length" class="detail-empty">{{ t("registry.none") }}</span>
            </div>
          </div>
        </div>

        <div v-else class="registry-modal-body">
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.tool_category") }}</span>
            <strong>{{ toolCategoryLabel(detailRecord.data.category) }}</strong>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.permission") }}</span>
            <strong>{{ permissionLabel(detailRecord.data.permission_level) }}</strong>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.summary") }}</span>
            <p>{{ detailRecord.data.description }}</p>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.streaming") }}</span>
            <strong>{{ detailRecord.data.supports_streaming ? t("registry.streaming_supported") : t("registry.streaming_unsupported") }}</strong>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.enabled_by_default") }}</span>
            <strong>{{ detailRecord.data.enabled_by_default ? t("registry.yes") : t("registry.no") }}</strong>
          </div>
          <div class="detail-item">
            <span class="detail-label">{{ t("registry.linked_agents") }}</span>
            <div class="detail-tags">
              <span v-for="agent in linkedAgents" :key="agent.key" class="detail-chip">
                {{ agent.name }}
              </span>
              <span v-if="!linkedAgents.length" class="detail-empty">{{ t("registry.none") }}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.registry-pane {
  animation: fadeIn 0.25s ease;
}

.pane-header {
  margin-bottom: 24px;
}

.pane-header .section-title {
  margin: 0 0 8px;
  font-size: 18px;
}

.pane-header .head-desc {
  margin: 0;
  color: var(--muted);
  line-height: 1.7;
}

.registry-groups {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.registry-group,
.registry-subgroups,
.registry-subgroup {
  display: flex;
  flex-direction: column;
}

.registry-group {
  gap: 12px;
}

.registry-subgroups {
  gap: 14px;
}

.registry-subgroup {
  gap: 10px;
}

.registry-group-head,
.registry-subgroup-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.registry-group-head strong {
  font-size: 14px;
  color: var(--text);
}

.registry-group-head span,
.registry-subgroup-head span {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 26px;
  height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: var(--surface-muted);
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.registry-subgroup-head em {
  font-style: normal;
  font-size: 13px;
  color: #64748b;
  font-weight: 700;
}

.registry-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 12px;
}

.registry-tag {
  appearance: none;
  border: none;
  display: inline-flex;
  align-items: center;
  min-height: 38px;
  padding: 0 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 700;
  white-space: nowrap;
  cursor: pointer;
  transition: transform 0.15s ease, opacity 0.15s ease;
}

.registry-tag:hover {
  transform: translateY(-1px);
  opacity: 0.92;
}

.registry-tag--agent {
  background: #000000;
  color: #ffffff;
}

.registry-tag--tool {
  background: #f3f4f6;
  color: #111827;
}

.registry-tag--guarded {
  background: #fff7ed;
  color: #9a3412;
}

.registry-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 64px 0;
  color: var(--muted);
  background: var(--surface-muted);
  border-radius: 16px;
  border: 1px dashed var(--border);
}

.registry-empty i {
  font-size: 42px;
  margin-bottom: 14px;
  opacity: 0.5;
}

.registry-modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(4px);
}

.registry-modal {
  width: min(720px, calc(100vw - 48px));
  max-height: calc(100vh - 48px);
  overflow-x: hidden;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(148, 163, 184, 0.42) transparent;
  scrollbar-gutter: stable;
  border-radius: 20px;
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: #ffffff;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
}

.registry-modal::-webkit-scrollbar {
  width: 8px;
}

.registry-modal::-webkit-scrollbar-track {
  background: transparent;
}

.registry-modal::-webkit-scrollbar-thumb {
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.34);
}

.registry-modal::-webkit-scrollbar-thumb:hover {
  background: rgba(100, 116, 139, 0.52);
}

.registry-modal-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px 18px;
  border-bottom: 1px solid rgba(15, 23, 42, 0.08);
}

.registry-modal-head h4 {
  margin: 0 0 6px;
  font-size: 22px;
  color: var(--text);
}

.registry-modal-head p {
  margin: 0;
  color: #64748b;
  font-size: 13px;
  font-family: var(--font-mono, monospace);
}

.registry-modal-close {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 10px;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}

.registry-modal-close:hover {
  background: var(--surface-muted);
  color: var(--text);
}

.registry-modal-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 22px 24px 24px;
}

.detail-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.detail-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: #64748b;
}

.detail-item strong {
  color: var(--text);
}

.detail-item p {
  margin: 0;
  color: #334155;
  line-height: 1.75;
}

.detail-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.detail-chip {
  display: inline-flex;
  align-items: center;
  padding: 6px 10px;
  border-radius: 999px;
  background: var(--surface-muted);
  color: #334155;
  font-size: 12px;
  font-weight: 600;
}

.detail-empty {
  color: #94a3b8;
  font-size: 13px;
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
