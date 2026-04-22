from __future__ import annotations

import asyncio
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

from src.core.config import Settings


@dataclass
class PlaywrightCliCommandResult:
    command: list[str]
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    artifacts: list[dict[str, str]] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "artifacts": self.artifacts,
        }


@dataclass
class _BrowserSession:
    name: str
    playwright: Any
    browser: Any
    context: Any
    page: Any
    output_dir: Path
    persistent: bool = False
    ref_map: dict[str, str] = field(default_factory=dict)
    console_messages: list[dict[str, Any]] = field(default_factory=list)
    network_events: list[dict[str, Any]] = field(default_factory=list)


class PythonPlaywrightCliRuntime:
    """Python implementation of the playwright-cli command contract.

    This runtime intentionally mirrors the CLI shape used by Claude Code skills:
    model output can be represented as small commands such as `open`, `snapshot`,
    `click e3`, or `eval "document.title"`, while the implementation stays fully
    inside the Agent_Server Python process.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._sessions: dict[str, _BrowserSession] = {}
        self._lock = asyncio.Lock()

    async def run(
        self,
        session_name: str,
        args: list[str],
        cwd: Path,
        raw: bool = False,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any]:
        timeout = timeout_seconds or int(self._settings.browser_action_timeout_seconds or 30)
        timeout = max(1, min(timeout, 300))
        try:
            return await asyncio.wait_for(
                self._run_locked(session_name=session_name, args=args, cwd=cwd, raw=raw),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return PlaywrightCliCommandResult(
                command=self._format_command(session_name, args, raw),
                exit_code=124,
                stderr=f"python playwright-cli command timed out after {timeout}s",
                timed_out=True,
            ).model_dump()

    async def _run_locked(self, session_name: str, args: list[str], cwd: Path, raw: bool) -> dict[str, Any]:
        async with self._lock:
            command = self._format_command(session_name, args, raw)
            if not args:
                return self._success(command, self._help_text())

            normalized_args, global_raw = self._strip_global_options(args)
            raw = raw or global_raw
            verb = normalized_args[0].strip().lower()
            rest = normalized_args[1:]

            try:
                if verb in {"--help", "-h", "help"}:
                    return self._success(command, self._help_text())
                if verb in {"--version", "-v", "version"}:
                    return self._success(command, "0.1.7-python\n")
                if verb == "list":
                    return self._success(command, self._list_sessions(raw))
                if verb == "close-all":
                    await self.close_all()
                    return self._success(command, "" if raw else "Closed all browser sessions.\n")
                if verb == "kill-all":
                    await self.close_all()
                    return self._success(command, "" if raw else "Killed all browser sessions.\n")

                session = await self._ensure_session(session_name, cwd, rest if verb == "open" else [])
                stdout, artifacts = await self._execute(session, verb, rest, cwd, raw)
                return self._success(command, stdout, artifacts)
            except Exception as exc:
                return PlaywrightCliCommandResult(
                    command=command,
                    exit_code=1,
                    stderr=f"{type(exc).__name__}: {exc}",
                ).model_dump()

    async def close_all(self) -> None:
        for session_name in list(self._sessions):
            await self._close_session(session_name)

    async def _ensure_session(self, session_name: str, cwd: Path, open_args: list[str]) -> _BrowserSession:
        if session_name in self._sessions:
            return self._sessions[session_name]

        try:
            from playwright.async_api import async_playwright
        except Exception as exc:
            raise RuntimeError(
                "Python Playwright is not installed in the Agent_Server Python environment. "
                "Install it with: python -m pip install playwright && python -m playwright install"
            ) from exc

        browser_name = self._option_value(open_args, "--browser") or self._settings.browser_default_name or "chromium"
        browser_name = browser_name.lower()
        headed = "--headed" in open_args or not bool(self._settings.browser_headless)
        persistent = "--persistent" in open_args or bool(self._option_value(open_args, "--profile"))
        profile = self._option_value(open_args, "--profile")
        output_dir = cwd / ".playwright-cli" / self._slug(session_name)
        output_dir.mkdir(parents=True, exist_ok=True)

        playwright = await async_playwright().start()
        viewport = {
            "width": int(self._settings.browser_window_width or 1440),
            "height": int(self._settings.browser_window_height or 960),
        }
        launch_options: dict[str, Any] = {"headless": not headed}
        browser_type_name = browser_name
        if browser_name in {"chrome", "msedge"}:
            browser_type_name = "chromium"
            launch_options["channel"] = browser_name
        if browser_name == "edge":
            browser_type_name = "chromium"
            launch_options["channel"] = "msedge"
        browser_type = getattr(playwright, browser_type_name, playwright.chromium)

        if persistent:
            profile_dir = Path(profile) if profile else output_dir / "profile"
            context = await browser_type.launch_persistent_context(
                str(profile_dir),
                viewport=viewport,
                **launch_options,
            )
            browser = None
            page = context.pages[0] if context.pages else await context.new_page()
        else:
            browser = await browser_type.launch(**launch_options)
            context = await browser.new_context(viewport=viewport)
            page = await context.new_page()

        session = _BrowserSession(
            name=session_name,
            playwright=playwright,
            browser=browser,
            context=context,
            page=page,
            output_dir=output_dir,
            persistent=persistent,
        )
        self._wire_session_events(session)
        self._sessions[session_name] = session
        return session

    def _wire_session_events(self, session: _BrowserSession) -> None:
        def on_console(message: Any) -> None:
            session.console_messages.append(
                {
                    "type": message.type,
                    "text": message.text,
                    "location": message.location,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            )

        def on_request(request: Any) -> None:
            session.network_events.append(
                {
                    "method": request.method,
                    "url": request.url,
                    "resource_type": request.resource_type,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                }
            )

        session.page.on("console", on_console)
        session.page.on("request", on_request)

    async def _execute(
        self,
        session: _BrowserSession,
        verb: str,
        args: list[str],
        cwd: Path,
        raw: bool,
    ) -> tuple[str, list[dict[str, str]]]:
        page = session.page
        if verb == "open":
            url = self._first_positional(args)
            if url:
                await page.goto(self._normalize_url(url), wait_until="domcontentloaded")
            return await self._page_output(session, raw)
        if verb == "goto":
            self._require_args(args, 1, "goto <url>")
            await page.goto(self._normalize_url(args[0]), wait_until="domcontentloaded")
            return await self._page_output(session, raw)
        if verb == "close":
            await self._close_session(session.name)
            return ("" if raw else f"Closed browser session '{session.name}'.\n", [])
        if verb == "delete-data":
            output_dir = session.output_dir
            await self._close_session(session.name)
            if output_dir.exists():
                shutil.rmtree(output_dir, ignore_errors=True)
            return ("" if raw else f"Deleted user data for {session.name}.\n", [])
        if verb == "resize":
            self._require_args(args, 2, "resize <width> <height>")
            width, height = int(args[0]), int(args[1])
            await page.set_viewport_size({"width": width, "height": height})
            return await self._page_output(session, raw)
        if verb == "snapshot":
            target, filename, depth = self._parse_snapshot_args(args)
            text = await self._snapshot(session, target=target, depth=depth)
            artifacts = []
            if filename:
                path = cwd / filename
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                artifacts.append({"type": "snapshot", "path": str(path)})
            return (text if raw else self._with_page_header(session, f"### Snapshot\n{text}", artifacts), artifacts)
        if verb == "screenshot":
            target, filename = self._parse_target_filename(args, default_name="screenshot.png")
            path = cwd / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            if target:
                await self._locator(session, target).screenshot(path=str(path))
            else:
                await page.screenshot(path=str(path), full_page=True)
            return ("" if raw else f"Saved screenshot to {path}\n", [{"type": "screenshot", "path": str(path)}])
        if verb == "pdf":
            filename = self._option_value(args, "--filename") or "page.pdf"
            path = cwd / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            await page.pdf(path=str(path))
            return ("" if raw else f"Saved PDF to {path}\n", [{"type": "pdf", "path": str(path)}])
        if verb == "eval":
            self._require_args(args, 1, "eval <expression> [ref]")
            expression = args[0]
            target = args[1] if len(args) > 1 else ""
            if target:
                result = await self._locator(session, target).evaluate(expression)
            else:
                result = await page.evaluate(expression)
            return (self._format_value(result, raw), [])
        if verb == "click":
            self._require_args(args, 1, "click <ref> [button]")
            await self._locator(session, args[0]).click(button=args[1] if len(args) > 1 else "left")
            return await self._page_output(session, raw)
        if verb == "dblclick":
            self._require_args(args, 1, "dblclick <ref> [button]")
            await self._locator(session, args[0]).dblclick(button=args[1] if len(args) > 1 else "left")
            return await self._page_output(session, raw)
        if verb == "fill":
            self._require_args(args, 2, "fill <ref> <text>")
            await self._locator(session, args[0]).fill(args[1])
            if "--submit" in args:
                await page.keyboard.press("Enter")
            return await self._page_output(session, raw)
        if verb == "type":
            self._require_args(args, 1, "type <text>")
            await page.keyboard.type(args[0])
            return await self._page_output(session, raw)
        if verb == "press":
            self._require_args(args, 1, "press <key>")
            await page.keyboard.press(args[0])
            return await self._page_output(session, raw)
        if verb == "keydown":
            self._require_args(args, 1, "keydown <key>")
            await page.keyboard.down(args[0])
            return await self._page_output(session, raw)
        if verb == "keyup":
            self._require_args(args, 1, "keyup <key>")
            await page.keyboard.up(args[0])
            return await self._page_output(session, raw)
        if verb == "hover":
            self._require_args(args, 1, "hover <ref>")
            await self._locator(session, args[0]).hover()
            return await self._page_output(session, raw)
        if verb == "select":
            self._require_args(args, 2, "select <ref> <value>")
            await self._locator(session, args[0]).select_option(args[1])
            return await self._page_output(session, raw)
        if verb == "check":
            self._require_args(args, 1, "check <ref>")
            await self._locator(session, args[0]).check()
            return await self._page_output(session, raw)
        if verb == "uncheck":
            self._require_args(args, 1, "uncheck <ref>")
            await self._locator(session, args[0]).uncheck()
            return await self._page_output(session, raw)
        if verb == "upload":
            self._require_args(args, 1, "upload <file>")
            await page.locator("input[type=file]").last.set_input_files([str((cwd / item).resolve()) for item in args])
            return await self._page_output(session, raw)
        if verb == "go-back":
            await page.go_back(wait_until="domcontentloaded")
            return await self._page_output(session, raw)
        if verb == "go-forward":
            await page.go_forward(wait_until="domcontentloaded")
            return await self._page_output(session, raw)
        if verb == "reload":
            await page.reload(wait_until="domcontentloaded")
            return await self._page_output(session, raw)
        if verb == "mousemove":
            self._require_args(args, 2, "mousemove <x> <y>")
            await page.mouse.move(float(args[0]), float(args[1]))
            return ("", [])
        if verb == "mousedown":
            await page.mouse.down(button=args[0] if args else "left")
            return ("", [])
        if verb == "mouseup":
            await page.mouse.up(button=args[0] if args else "left")
            return ("", [])
        if verb == "mousewheel":
            self._require_args(args, 2, "mousewheel <dx> <dy>")
            await page.mouse.wheel(float(args[0]), float(args[1]))
            return await self._page_output(session, raw)
        if verb == "tab-list":
            rows = [f"{index}: {tab.url} | {await tab.title()}" for index, tab in enumerate(session.context.pages)]
            return ("\n".join(rows) + ("\n" if rows else ""), [])
        if verb == "tab-new":
            new_page = await session.context.new_page()
            session.page = new_page
            self._wire_session_events(session)
            if args:
                await new_page.goto(self._normalize_url(args[0]), wait_until="domcontentloaded")
            return await self._page_output(session, raw)
        if verb == "tab-select":
            self._require_args(args, 1, "tab-select <index>")
            session.page = session.context.pages[int(args[0])]
            await session.page.bring_to_front()
            return await self._page_output(session, raw)
        if verb == "tab-close":
            index = int(args[0]) if args else len(session.context.pages) - 1
            await session.context.pages[index].close()
            pages = session.context.pages
            session.page = pages[min(index, len(pages) - 1)] if pages else await session.context.new_page()
            return await self._page_output(session, raw)
        if verb.startswith("cookie-"):
            return await self._cookies(session, verb, args, raw)
        if verb.startswith("localstorage-"):
            return await self._web_storage(session, "localStorage", verb.replace("localstorage-", ""), args, raw)
        if verb.startswith("sessionstorage-"):
            return await self._web_storage(session, "sessionStorage", verb.replace("sessionstorage-", ""), args, raw)
        if verb == "state-save":
            filename = args[0] if args else "storage-state.json"
            path = cwd / filename
            await session.context.storage_state(path=str(path))
            return ("" if raw else f"Saved storage state to {path}\n", [{"type": "json", "path": str(path)}])
        if verb == "state-load":
            raise RuntimeError("state-load requires creating a new browser context; close and open with the saved state in a future turn.")
        if verb == "console":
            min_level = args[0] if args else "info"
            return (json.dumps(self._filter_console(session.console_messages, min_level), ensure_ascii=False, indent=None if raw else 2) + "\n", [])
        if verb == "network":
            return (json.dumps(session.network_events, ensure_ascii=False, indent=None if raw else 2) + "\n", [])
        if verb in {"dialog-accept", "dialog-dismiss", "route", "route-list", "unroute", "tracing-start", "tracing-stop", "video-start", "video-chapter", "video-stop", "run-code", "show", "attach"}:
            return ("" if raw else f"Command '{verb}' is acknowledged but not yet implemented by the Python runtime.\n", [])
        raise RuntimeError(f"Unsupported playwright-cli command '{verb}'.")

    async def _page_output(self, session: _BrowserSession, raw: bool) -> tuple[str, list[dict[str, str]]]:
        if raw:
            return ("", [])
        snapshot = await self._snapshot(session)
        return (self._with_page_header(session, f"### Snapshot\n{snapshot}", []), [])

    def _with_page_header(self, session: _BrowserSession, body: str, artifacts: list[dict[str, str]]) -> str:
        page = session.page
        artifact_lines = "\n".join(f"- {item['type']}: {item['path']}" for item in artifacts)
        return (
            "### Page\n"
            f"- Page URL: {page.url}\n"
            f"- Page Title: {getattr(page, '_last_known_title', '')}\n"
            f"{body}\n"
            f"{'### Artifacts' + chr(10) + artifact_lines + chr(10) if artifact_lines else ''}"
        )

    async def _snapshot(self, session: _BrowserSession, target: str = "", depth: int | None = None) -> str:
        page = session.page
        title = await page.title()
        setattr(page, "_last_known_title", title)
        selector = session.ref_map.get(target, target) if target else ""
        script = """
        ({ selector, depth }) => {
          const root = selector ? document.querySelector(selector) : document.body;
          if (!root) return [];
          const candidates = Array.from(root.querySelectorAll('a,button,input,textarea,select,[role],[aria-label],h1,h2,h3,label,summary'));
          const cssPath = (el) => {
            if (el.id) return '#' + CSS.escape(el.id);
            const parts = [];
            while (el && el.nodeType === Node.ELEMENT_NODE && el !== document.body) {
              let part = el.nodeName.toLowerCase();
              const parent = el.parentElement;
              if (parent) {
                const same = Array.from(parent.children).filter(c => c.nodeName === el.nodeName);
                if (same.length > 1) part += `:nth-of-type(${same.indexOf(el) + 1})`;
              }
              parts.unshift(part);
              el = parent;
            }
            return parts.length ? parts.join(' > ') : 'body';
          };
          return candidates.slice(0, 120).map((el, index) => ({
            ref: `e${index + 1}`,
            selector: cssPath(el),
            tag: el.tagName.toLowerCase(),
            role: el.getAttribute('role') || '',
            name: el.getAttribute('aria-label') || el.getAttribute('name') || el.getAttribute('placeholder') || '',
            text: (el.innerText || el.value || '').trim().replace(/\\s+/g, ' ').slice(0, 120),
            type: el.getAttribute('type') || '',
            href: el.getAttribute('href') || ''
          }));
        }
        """
        nodes = await page.evaluate(script, {"selector": selector, "depth": depth})
        session.ref_map = {node["ref"]: node["selector"] for node in nodes if node.get("ref") and node.get("selector")}
        lines = [f"- page: {page.url}", f"- title: {title}"]
        for node in nodes:
            label = node.get("text") or node.get("name") or node.get("href") or node.get("tag")
            attrs = []
            if node.get("role"):
                attrs.append(f"role={node['role']}")
            if node.get("type"):
                attrs.append(f"type={node['type']}")
            suffix = f" ({', '.join(attrs)})" if attrs else ""
            lines.append(f"- {node['ref']}: <{node.get('tag')}>{suffix} {label}".rstrip())
        return "\n".join(lines) + "\n"

    def _locator(self, session: _BrowserSession, target: str) -> Any:
        selector = session.ref_map.get(target, target)
        page = session.page
        role_match = re.fullmatch(r"getByRole\(['\"]([^'\"]+)['\"]\s*,\s*\{\s*name:\s*['\"]([^'\"]+)['\"]\s*\}\)", selector)
        if role_match:
            return page.get_by_role(role_match.group(1), name=role_match.group(2))
        test_id_match = re.fullmatch(r"getByTestId\(['\"]([^'\"]+)['\"]\)", selector)
        if test_id_match:
            return page.get_by_test_id(test_id_match.group(1))
        return page.locator(selector).first

    async def _cookies(self, session: _BrowserSession, verb: str, args: list[str], raw: bool) -> tuple[str, list[dict[str, str]]]:
        action = verb.replace("cookie-", "")
        if action == "list":
            domain = self._option_value(args, "--domain")
            cookies = await session.context.cookies()
            if domain:
                cookies = [item for item in cookies if domain in item.get("domain", "")]
            return (json.dumps(cookies, ensure_ascii=False, indent=None if raw else 2) + "\n", [])
        if action == "get":
            self._require_args(args, 1, "cookie-get <name>")
            cookies = await session.context.cookies()
            value = next((item.get("value", "") for item in cookies if item.get("name") == args[0]), "")
            return (value + ("\n" if value else ""), [])
        if action == "set":
            self._require_args(args, 2, "cookie-set <name> <value>")
            url = session.page.url if session.page.url.startswith("http") else "https://example.com"
            cookie = {"name": args[0], "value": args[1], "url": url}
            domain = self._option_value(args, "--domain")
            if domain:
                cookie.pop("url", None)
                cookie["domain"] = domain
                cookie["path"] = "/"
            cookie["httpOnly"] = "--httpOnly" in args
            cookie["secure"] = "--secure" in args
            await session.context.add_cookies([cookie])
            return ("", [])
        if action == "delete":
            self._require_args(args, 1, "cookie-delete <name>")
            await session.context.clear_cookies(name=args[0])
            return ("", [])
        if action == "clear":
            await session.context.clear_cookies()
            return ("", [])
        raise RuntimeError(f"Unsupported cookie command '{verb}'.")

    async def _web_storage(
        self,
        session: _BrowserSession,
        storage_name: str,
        action: str,
        args: list[str],
        raw: bool,
    ) -> tuple[str, list[dict[str, str]]]:
        if action == "list":
            result = await session.page.evaluate(f"JSON.stringify(Object.fromEntries(Object.entries({storage_name})))")
            return (result + "\n", [])
        if action == "get":
            self._require_args(args, 1, f"{storage_name}-get <key>")
            result = await session.page.evaluate(f"{storage_name}.getItem({json.dumps(args[0])})")
            return ((result or "") + ("\n" if result else ""), [])
        if action == "set":
            self._require_args(args, 2, f"{storage_name}-set <key> <value>")
            await session.page.evaluate(f"{storage_name}.setItem({json.dumps(args[0])}, {json.dumps(args[1])})")
            return ("", [])
        if action == "delete":
            self._require_args(args, 1, f"{storage_name}-delete <key>")
            await session.page.evaluate(f"{storage_name}.removeItem({json.dumps(args[0])})")
            return ("", [])
        if action == "clear":
            await session.page.evaluate(f"{storage_name}.clear()")
            return ("", [])
        raise RuntimeError(f"Unsupported storage command '{storage_name}-{action}'.")

    async def _close_session(self, session_name: str) -> None:
        session = self._sessions.pop(session_name, None)
        if not session:
            return
        try:
            await session.context.close()
        finally:
            if session.browser:
                await session.browser.close()
            await session.playwright.stop()

    def _success(
        self,
        command: list[str],
        stdout: str,
        artifacts: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        return PlaywrightCliCommandResult(
            command=command,
            exit_code=0,
            stdout=stdout,
            artifacts=artifacts or [],
        ).model_dump()

    def _list_sessions(self, raw: bool) -> str:
        data = [
            {
                "name": name,
                "url": session.page.url,
                "output_dir": str(session.output_dir),
                "persistent": session.persistent,
            }
            for name, session in sorted(self._sessions.items())
        ]
        if raw:
            return json.dumps(data, ensure_ascii=False) + "\n"
        if not data:
            return "No active browser sessions.\n"
        return "\n".join(f"{item['name']}: {item['url']} ({item['output_dir']})" for item in data) + "\n"

    def _format_command(self, session_name: str, args: list[str], raw: bool) -> list[str]:
        command = ["python-playwright-cli", f"-s={session_name}"]
        if raw:
            command.append("--raw")
        command.extend(args)
        return command

    def _help_text(self) -> str:
        return (
            "python-playwright-cli commands:\n"
            "  open [url], goto <url>, close, delete-data, list, close-all\n"
            "  snapshot [ref] [--filename=file] [--depth=N], screenshot [ref] [--filename=file]\n"
            "  click <ref>, dblclick <ref>, fill <ref> <text> [--submit], type <text>, press <key>\n"
            "  eval <expression> [ref], resize <w> <h>, mousewheel <dx> <dy>\n"
            "  tab-list, tab-new [url], tab-select <index>, tab-close [index]\n"
        )

    def _strip_global_options(self, args: list[str]) -> tuple[list[str], bool]:
        stripped: list[str] = []
        raw = False
        for arg in args:
            if arg == "--raw":
                raw = True
            elif arg.startswith("-s="):
                continue
            else:
                stripped.append(arg)
        return stripped, raw

    def _parse_snapshot_args(self, args: list[str]) -> tuple[str, str | None, int | None]:
        target = ""
        filename = self._option_value(args, "--filename")
        depth_value = self._option_value(args, "--depth")
        for arg in args:
            if not arg.startswith("--"):
                target = arg
                break
        return target, filename, int(depth_value) if depth_value else None

    def _parse_target_filename(self, args: list[str], default_name: str) -> tuple[str, str]:
        filename = self._option_value(args, "--filename") or default_name
        target = ""
        for arg in args:
            if not arg.startswith("--"):
                target = arg
                break
        return target, filename

    def _option_value(self, args: list[str], name: str) -> str | None:
        prefix = f"{name}="
        for index, arg in enumerate(args):
            if arg.startswith(prefix):
                return arg[len(prefix) :]
            if arg == name and index + 1 < len(args):
                return args[index + 1]
        return None

    def _first_positional(self, args: list[str]) -> str:
        for arg in args:
            if not arg.startswith("--"):
                return arg
        return ""

    def _normalize_url(self, value: str) -> str:
        if value.startswith("data:text/html,"):
            payload = value[len("data:text/html,") :]
            if any(ord(ch) > 127 for ch in payload):
                return "data:text/html;charset=utf-8," + quote(payload, safe="/:=?&%#[]@!$&'()*+,;<>\" ")
        if value.startswith(("http://", "https://", "file://", "data:", "about:")):
            return value
        return f"https://{value}"

    def _require_args(self, args: list[str], count: int, usage: str) -> None:
        positional = [arg for arg in args if not arg.startswith("--")]
        if len(positional) < count:
            raise ValueError(f"Usage: playwright-cli {usage}")

    def _format_value(self, value: Any, raw: bool) -> str:
        if isinstance(value, str):
            return value + ("\n" if value else "")
        return json.dumps(value, ensure_ascii=False, indent=None if raw else 2) + "\n"

    def _filter_console(self, messages: list[dict[str, Any]], min_level: str) -> list[dict[str, Any]]:
        order = {"debug": 0, "info": 1, "log": 1, "warning": 2, "error": 3}
        threshold = order.get(min_level, 1)
        return [item for item in messages if order.get(str(item.get("type")), 1) >= threshold]

    def _slug(self, value: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
        return slug[:96] or "default"
