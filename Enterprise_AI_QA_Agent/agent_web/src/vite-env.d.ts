/// <reference types="vite/client" />

declare module "*.vue" {
  import type { DefineComponent } from "vue";

  const component: DefineComponent<Record<string, never>, Record<string, never>, any>;
  export default component;
}

interface QaAgentDesktopBridge {
  isDesktop: boolean;
  notify(payload: {
    title: string;
    body?: string;
    tag?: string;
    silent?: boolean;
  }): Promise<boolean>;
}

interface Window {
  qaAgentDesktop?: QaAgentDesktopBridge;
}
