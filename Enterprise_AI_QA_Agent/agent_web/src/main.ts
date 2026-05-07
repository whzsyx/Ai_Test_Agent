import { createApp } from "vue";
import { createPinia } from "pinia";

import App from "./App.vue";
import router from "./router";
import { useAppStore } from "./stores/app";
import { useGeneralSettingsStore } from "./stores/generalSettings";
import "./styles.css";

const app = createApp(App);
const pinia = createPinia();
app.use(pinia);
app.use(router);
useAppStore(pinia).hydrateTheme();
useGeneralSettingsStore(pinia).hydrateGeneralSettings();
app.mount("#app");
