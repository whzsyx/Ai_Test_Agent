import { app, BrowserWindow, Menu, shell } from "electron";
import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer, request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { extname, join, normalize, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));
const appRoot = resolve(__dirname, "..");
const rendererRoot = join(appRoot, "dist");
const iconPath = join(appRoot, "desktop-assets", process.platform === "win32" ? "logo.ico" : "logo.png");
const backendOrigin = process.env.QA_AGENT_API_ORIGIN || "http://127.0.0.1:1032";
const desktopDebugEnabled = !app.isPackaged || process.env.QA_AGENT_DESKTOP_DEBUG === "1";

let mainWindow = null;
let staticServer = null;

const mimeTypes = new Map([
  [".html", "text/html; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".gif", "image/gif"],
  [".ico", "image/x-icon"],
  [".woff", "font/woff"],
  [".woff2", "font/woff2"],
]);

function safeRendererPath(urlPath) {
  const decodedPath = decodeURIComponent(urlPath.split("?")[0] || "/");
  const normalizedPath = normalize(decodedPath).replace(/^(\.\.[/\\])+/, "");
  const candidate = join(rendererRoot, normalizedPath);
  const resolvedCandidate = resolve(candidate);

  if (!resolvedCandidate.startsWith(resolve(rendererRoot))) {
    return join(rendererRoot, "index.html");
  }

  if (existsSync(resolvedCandidate) && statSync(resolvedCandidate).isFile()) {
    return resolvedCandidate;
  }

  return join(rendererRoot, "index.html");
}

function writeStaticResponse(response, filePath) {
  const contentType = mimeTypes.get(extname(filePath).toLowerCase()) || "application/octet-stream";
  response.writeHead(200, {
    "content-type": contentType,
    "cache-control": filePath.endsWith("index.html") ? "no-cache" : "public, max-age=31536000",
  });
  createReadStream(filePath).pipe(response);
}

function proxyApiRequest(clientRequest, clientResponse) {
  const targetUrl = new URL(clientRequest.url || "/", backendOrigin);
  const transport = targetUrl.protocol === "https:" ? httpsRequest : httpRequest;
  const upstreamRequest = transport(
    targetUrl,
    {
      method: clientRequest.method,
      headers: {
        ...clientRequest.headers,
        host: targetUrl.host,
        origin: backendOrigin,
      },
    },
    (upstreamResponse) => {
      clientResponse.writeHead(upstreamResponse.statusCode || 502, upstreamResponse.headers);
      upstreamResponse.pipe(clientResponse);
    },
  );

  upstreamRequest.on("error", (error) => {
    clientResponse.writeHead(502, { "content-type": "application/json; charset=utf-8" });
    clientResponse.end(JSON.stringify({ detail: `Desktop proxy failed: ${error.message}` }));
  });

  clientRequest.pipe(upstreamRequest);
}

function startStaticServer() {
  if (!existsSync(join(rendererRoot, "index.html"))) {
    throw new Error("Renderer build not found. Run `npm run build` first.");
  }

  staticServer = createServer((request, response) => {
    const requestUrl = request.url || "/";
    if (requestUrl.startsWith("/api/")) {
      proxyApiRequest(request, response);
      return;
    }

    writeStaticResponse(response, safeRendererPath(requestUrl));
  });

  return new Promise((resolveServer, rejectServer) => {
    staticServer.once("error", rejectServer);
    staticServer.listen(0, "127.0.0.1", () => {
      const address = staticServer.address();
      if (!address || typeof address === "string") {
        rejectServer(new Error("Failed to allocate desktop renderer port."));
        return;
      }
      resolveServer(`http://127.0.0.1:${address.port}`);
    });
  });
}

async function createMainWindow() {
  Menu.setApplicationMenu(null);

  const rendererOrigin = await startStaticServer();
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 1100,
    minHeight: 720,
    title: "御策天检",
    icon: existsSync(iconPath) ? iconPath : undefined,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      devTools: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.setMenuBarVisibility(false);
  mainWindow.loadURL(rendererOrigin);

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.webContents.on("before-input-event", (event, input) => {
    const key = input.key.toLowerCase();
    if (desktopDebugEnabled && (input.key === "F12" || (input.control && input.shift && key === "i"))) {
      mainWindow.webContents.toggleDevTools();
      event.preventDefault();
    }
  });

  if (desktopDebugEnabled) {
    mainWindow.webContents.once("did-finish-load", () => {
      mainWindow.webContents.openDevTools();
    });
  }

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

app.whenReady().then(createMainWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("before-quit", () => {
  staticServer?.close();
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createMainWindow();
  }
});
