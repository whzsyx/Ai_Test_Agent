<script setup lang="ts">
import type { KeyboardEvent } from "vue";
import { computed, ref } from "vue";
import { NDropdown } from "naive-ui";

import { useSessionStore } from "../../stores/session";

const props = defineProps<{
  docked?: boolean;
}>();

const sessionStore = useSessionStore();
const draft = ref("");

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

async function handleSubmit() {
  if (sessionStore.isBusy || !sessionStore.session || !draft.value.trim()) {
    return;
  }

  const content = draft.value;
  draft.value = "";
  await sessionStore.sendMessage(content);
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key !== "Enter" || event.shiftKey || event.isComposing) {
    return;
  }

  event.preventDefault();
  void handleSubmit();
}

function handleModeSelect(key: string | number) {
  sessionStore.setModeKey(String(key));
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

    <div class="home-composer-footer">
      <div class="home-toolbar">
        <button class="home-tool-btn" type="button">
          <i class="fa-solid fa-paperclip"></i>
          Attachments
        </button>
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
          :disabled="sessionStore.isBusy || !sessionStore.session"
          @click="handleSubmit"
          :title="buttonTitle"
          type="button"
        >
          <i class="fa-solid" :class="sessionStore.isBusy ? 'fa-spinner fa-spin' : 'fa-arrow-up'"></i>
        </button>
      </div>
    </div>
  </div>
</template>
