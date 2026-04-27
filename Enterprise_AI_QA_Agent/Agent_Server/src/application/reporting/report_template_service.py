from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any


class ReportTemplateService:
    def __init__(self) -> None:
        self._template_dir = Path(__file__).resolve().parents[2] / "templates"
        self._template_paths = {
            "default": self._template_dir / "report_email.html",
            "code_review_debate": self._template_dir / "code_review_debate_report.html",
        }

    def render_report_html(
        self,
        *,
        title: str,
        time_label: str,
        sender: str,
        markdown_content: str,
        template_key: str = "default",
        template_context: dict[str, Any] | None = None,
    ) -> str:
        content_html = self.render_markdown(markdown_content)
        if template_key == "code_review_debate":
            return self.render_code_review_debate_html(
                title=title,
                time_label=time_label,
                sender=sender,
                markdown_content=markdown_content,
                template_context=template_context,
                content_html=content_html,
            )

        replacements = {
            "{{ title }}": html.escape(title),
            "{{ time }}": html.escape(time_label),
            "{{ sender }}": html.escape(sender),
            "{{ content_html }}": content_html,
        }
        return self._render_template("default", replacements)

    def render_code_review_debate_html(
        self,
        *,
        title: str,
        time_label: str,
        sender: str,
        markdown_content: str,
        template_context: dict[str, Any] | None = None,
        content_html: str | None = None,
    ) -> str:
        context = template_context or {}
        content_html = content_html or self.render_markdown(markdown_content)
        result_summary_markdown = str(context.get("result_summary_markdown") or "").strip()
        result_summary_html = (
            self.render_markdown(result_summary_markdown)
            if result_summary_markdown
            else "<p>暂无审批结果摘要。</p>"
        )
        replacements = {
            "{{ title }}": html.escape(title),
            "{{ time }}": html.escape(time_label),
            "{{ sender }}": html.escape(sender),
            "{{ project_name }}": html.escape(str(context.get("project_name") or title)),
            "{{ approval_result }}": html.escape(str(context.get("approval_result") or "待定")),
            "{{ agent_count }}": html.escape(str(context.get("agent_count") or "0")),
            "{{ result_summary_html }}": result_summary_html,
            "{{ content_html }}": content_html,
        }
        return self._render_template("code_review_debate", replacements)

    def render_markdown(self, markdown_text: str) -> str:
        lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        blocks: list[str] = []
        paragraph: list[str] = []
        list_buffer: list[str] = []
        list_type: str | None = None
        quote_buffer: list[str] = []
        table_rows: list[str] = []
        in_code_block = False
        code_lines: list[str] = []

        def flush_paragraph() -> None:
            nonlocal paragraph
            if paragraph:
                text = " ".join(item.strip() for item in paragraph if item.strip())
                if text:
                    blocks.append(f"<p>{self._render_inline(text)}</p>")
                paragraph = []

        def flush_list() -> None:
            nonlocal list_buffer, list_type
            if list_buffer and list_type:
                blocks.append(f"<{list_type}>" + "".join(list_buffer) + f"</{list_type}>")
            list_buffer = []
            list_type = None

        def flush_quote() -> None:
            nonlocal quote_buffer
            if quote_buffer:
                quote_html = "<br>".join(self._render_inline(item) for item in quote_buffer if item)
                blocks.append(f"<blockquote>{quote_html}</blockquote>")
            quote_buffer = []

        def flush_table() -> None:
            nonlocal table_rows
            if table_rows:
                blocks.append(self._render_markdown_table(table_rows))
            table_rows = []

        def flush_code() -> None:
            nonlocal code_lines
            code_text = "\n".join(code_lines)
            blocks.append(f"<pre><code>{html.escape(code_text)}</code></pre>")
            code_lines = []

        def flush_all() -> None:
            flush_paragraph()
            flush_list()
            flush_quote()
            flush_table()

        for raw_line in lines:
            line = raw_line.rstrip()
            stripped = line.strip()

            if in_code_block:
                if stripped.startswith("```"):
                    flush_code()
                    in_code_block = False
                else:
                    code_lines.append(raw_line)
                continue

            if stripped.startswith("```"):
                flush_all()
                in_code_block = True
                code_lines = []
                continue

            if not stripped:
                flush_all()
                continue

            if self._is_markdown_table_row(stripped):
                flush_paragraph()
                flush_list()
                flush_quote()
                table_rows.append(stripped)
                continue

            heading = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if heading:
                flush_all()
                level = len(heading.group(1))
                blocks.append(f"<h{level}>{self._render_inline(heading.group(2).strip())}</h{level}>")
                continue

            if stripped in {"---", "***", "___"}:
                flush_all()
                blocks.append("<hr>")
                continue

            quote_match = re.match(r"^>\s?(.*)$", stripped)
            if quote_match:
                flush_paragraph()
                flush_list()
                flush_table()
                quote_buffer.append(quote_match.group(1))
                continue

            list_match = re.match(r"^([-*+])\s+(.*)$", stripped)
            ordered_match = re.match(r"^(\d+)\.\s+(.*)$", stripped)
            if list_match or ordered_match:
                flush_paragraph()
                flush_quote()
                flush_table()
                next_type = "ul" if list_match else "ol"
                content = list_match.group(2) if list_match else ordered_match.group(2)
                if list_type and list_type != next_type:
                    flush_list()
                list_type = next_type
                list_buffer.append(f"<li>{self._render_inline(content.strip())}</li>")
                continue

            paragraph.append(stripped)

        if in_code_block:
            flush_code()
        flush_all()
        return "\n".join(blocks)

    def _render_inline(self, text: str) -> str:
        escaped = html.escape(text)
        escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)
        escaped = re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<em>\1</em>", escaped)
        escaped = re.sub(
            r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
            r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',
            escaped,
        )
        return escaped

    def _is_markdown_table_row(self, line: str) -> bool:
        return line.startswith("|") and line.endswith("|") and len(line.split("|")) >= 4

    def _is_markdown_table_separator(self, line: str) -> bool:
        cells = self._split_markdown_table_cells(line)
        if not cells:
            return False
        for cell in cells:
            clean_cell = re.sub(r"\s", "", cell)
            if not re.match(r"^:?-{3,}:?$", clean_cell):
                return False
        return True

    def _split_markdown_table_cells(self, line: str) -> list[str]:
        line = re.sub(r"^\|", "", line)
        line = re.sub(r"\|$", "", line)
        return [cell.strip() for cell in line.split("|")]

    def _render_markdown_table(self, rows: list[str]) -> str:
        if len(rows) < 2 or not self._is_markdown_table_separator(rows[1]):
            return "<p>" + "<br>".join(self._render_inline(row) for row in rows) + "</p>"

        headers = self._split_markdown_table_cells(rows[0])
        body_rows = [row for row in rows[2:] if not self._is_markdown_table_separator(row)]
        
        head_html = "".join(f"<th>{self._render_inline(cell)}</th>" for cell in headers)
        body_html = ""
        for row in body_rows:
            cells = self._split_markdown_table_cells(row)
            cells_html = "".join(f"<td>{self._render_inline(cell)}</td>" for cell in cells)
            body_html += f"<tr>{cells_html}</tr>"

        return f'<div class="report-table-shell"><table><thead><tr>{head_html}</tr></thead><tbody>{body_html}</tbody></table></div>'

    def _render_template(self, template_key: str, replacements: dict[str, str]) -> str:
        template = self._load_template(template_key)
        rendered = template
        for key, value in replacements.items():
            rendered = rendered.replace(key, value)
        return rendered

    def _load_template(self, template_key: str) -> str:
        template_path = self._template_paths.get(template_key) or self._template_paths["default"]
        return template_path.read_text(encoding="utf-8")
