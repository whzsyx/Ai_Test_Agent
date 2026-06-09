<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import ApprovalPanel from "../components/chat/ApprovalPanel.vue";
import ChatComposer from "../components/chat/ChatComposer.vue";
import ChatTimeline from "../components/chat/ChatTimeline.vue";
import CompatibilityTestingPanel from "../components/chat/CompatibilityTestingPanel.vue";
import RuntimeStatusPanel from "../components/chat/RuntimeStatusPanel.vue";
import { useSessionStore } from "../stores/session";
import { t } from "../services/i18n";

const sessionStore = useSessionStore();
const hasConversation = computed(() => sessionStore.messages.length > 0);
const hasPendingApprovals = computed(() => sessionStore.pendingApprovals.length > 0);
const isCompatibilityMode = computed(() => sessionStore.selectedModeKey === "compatibility_testing");
const hasCompatibilityJobs = computed(() =>
  sessionStore.recentToolJobs.some((job) => job.tool_key === "compatibility-test-runner"),
);
const showCompatibilityPanel = computed(() => isCompatibilityMode.value || (hasConversation.value && hasCompatibilityJobs.value));
const isWorkbenchActive = computed(() => hasConversation.value || showCompatibilityPanel.value);
const heroTitle = computed(() => t("home.title"));
const heroSubtitle = computed(() => t("home.subtitle"));
const composerAnchorRef = ref<HTMLElement | null>(null);
const composerAnchorHeight = ref(196);
const runtimePanelSize = ref(112);
let resizeObserver: ResizeObserver | null = null;

const layoutStyle = computed(() => ({
  "--composer-safe-space": `${composerAnchorHeight.value + 32}px`,
}));

const composerAnchorStyle = computed(() => ({
  "--runtime-panel-size": `${runtimePanelSize.value}px`,
  "--composer-anchor-height": `${composerAnchorHeight.value}px`,
}));

function updateRuntimeLayout() {
  const height = composerAnchorRef.value?.offsetHeight ?? 0;
  composerAnchorHeight.value = height > 0 ? Math.round(height) : 10;
  runtimePanelSize.value = Math.max(112, Math.round(height || 112));
}

onMounted(() => {
  updateRuntimeLayout();
  if (!composerAnchorRef.value) {
    return;
  }

  resizeObserver = new ResizeObserver(() => {
    updateRuntimeLayout();
  });
  resizeObserver.observe(composerAnchorRef.value);
});

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  resizeObserver = null;
});
</script>

<template>
  <section class="view-home" :class="{ 'view-home-conversation': isWorkbenchActive }">
    <div
      class="home-center-wrap"
      :class="{ 'home-center-wrap-conversation': isWorkbenchActive }"
      :style="layoutStyle"
    >
      <Transition name="home-hero-transition">
        <div v-if="!isWorkbenchActive" class="home-hero">
          <div class="home-logo-box">
            <i class="fa-solid fa-spider"></i>
          </div>
          <h1 class="home-title">{{ heroTitle }}</h1>
          <p class="home-subtitle">{{ heroSubtitle }}</p>
        </div>
      </Transition>

      <div class="home-thread-shell" :class="{ 'home-thread-shell-active': isWorkbenchActive }">
        <CompatibilityTestingPanel v-if="showCompatibilityPanel" />
        <ChatTimeline :messages="sessionStore.messages" />
        <p v-if="sessionStore.error" class="error-text home-inline-error">{{ sessionStore.error }}</p>
      </div>

      <div class="home-composer-dock" :class="{ 'home-composer-dock-active': isWorkbenchActive }">
        <div
          ref="composerAnchorRef"
          class="home-composer-anchor"
          :class="{ 'home-composer-anchor-with-approval': hasPendingApprovals }"
          :style="composerAnchorStyle"
        >
          <Transition name="runtime-panel-transition">
            <RuntimeStatusPanel v-if="hasConversation" />
          </Transition>
          <ChatComposer :docked="isWorkbenchActive" />
          <Transition name="runtime-panel-transition">
            <ApprovalPanel v-if="hasConversation && hasPendingApprovals" />
          </Transition>
        </div>
      </div>
    </div>
  </section>
</template>
