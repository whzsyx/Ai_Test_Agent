// Launch the Vite app and the VitePress docs dev servers together.
// Run via `npm run dev`. They remain two separate servers on two ports,
// but you only need one command. Press Ctrl+C once to stop both.
import { spawn } from "node:child_process";

const isWindows = process.platform === "win32";

const targets = [
  { name: "app ", color: "\x1b[36m", script: "dev:app" },   // cyan
  { name: "docs", color: "\x1b[35m", script: "docs:dev" },  // magenta
];

const reset = "\x1b[0m";
const children = [];

function prefix(name, color, line) {
  return `${color}[${name}]${reset} ${line}`;
}

for (const target of targets) {
  // Use `npm run <script>`; shell:true lets Windows resolve npm + local .bin.
  const child = spawn("npm", ["run", target.script], {
    cwd: process.cwd(),
    shell: true,
    env: process.env,
  });

  const pipe = (stream, sink) => {
    stream.setEncoding("utf8");
    let buffer = "";
    stream.on("data", (chunk) => {
      buffer += chunk;
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";
      for (const line of lines) {
        sink.write(prefix(target.name, target.color, line) + "\n");
      }
    });
    stream.on("end", () => {
      if (buffer) sink.write(prefix(target.name, target.color, buffer) + "\n");
    });
  };

  pipe(child.stdout, process.stdout);
  pipe(child.stderr, process.stderr);

  child.on("exit", (code) => {
    process.stdout.write(
      prefix(target.name, target.color, `exited with code ${code ?? 0}`) + "\n",
    );
    shutdown();
  });

  children.push(child);
}

let shuttingDown = false;
function shutdown() {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (child.exitCode === null) {
      if (isWindows) {
        // Ensure the whole child process tree is terminated on Windows.
        spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
          shell: true,
          stdio: "ignore",
        });
      } else {
        child.kill("SIGTERM");
      }
    }
  }
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
