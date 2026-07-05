const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("qaAgentDesktop", {
  isDesktop: true,
  notify(payload) {
    return ipcRenderer.invoke("desktop:notify", payload);
  },
});
