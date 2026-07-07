"""Tencent Agent Mail provider adapter (CLI + OAuth).

Wraps agently-cli as the transport. All commands output JSON to stdout.
Send/reply/forward use the CLI built-in two-phase confirmation
(first call returns a confirmation_token; second call with that token commits).
This maps directly to the tool runtime waiting_approval mechanism.
"""

from __future__ import annotations

import json
import subprocess
from typing import TYPE_CHECKING, Any

from src.application.mail.contracts import (
    MailCapability,
    MailMessage,
    MailProviderAdapter,
    MailSendRequest,
    MailSendResult,
)

if TYPE_CHECKING:
    from src.schemas.email_config import EmailConfigRecord


class TencentAgentlyMailAdapter(MailProviderAdapter):
    """Full Agent Mailbox provider backed by agently-cli."""

    provider_key = "tencent_agently"

    def capabilities(self) -> set[MailCapability]:
        return {
            MailCapability.SEND,
            MailCapability.LIST,
            MailCapability.READ,
            MailCapability.SEARCH,
            MailCapability.REPLY,
            MailCapability.FORWARD,
            MailCapability.ATTACHMENTS,
        }

    # --- CLI helpers --------------------------------------------------------

    def _cli_path(self, record: "EmailConfigRecord") -> str:
        return (record.extra_config or {}).get("cli_path", "agently-cli")

    def _run_cli(
        self, record: "EmailConfigRecord", args: list[str], *, timeout: int = 30
    ) -> dict[str, Any]:
        cli = self._cli_path(record)
        cmd = [cli] + args
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"agently-cli not found at '{cli}'. "
                "Install it or set extra_config.cli_path."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"agently-cli timed out after {timeout}s.")

        if proc.returncode != 0:
            stderr = (proc.stderr or "").strip()
            raise RuntimeError(
                f"agently-cli error (exit {proc.returncode}): {stderr}"
            )

        try:
            return json.loads(proc.stdout)
        except (json.JSONDecodeError, ValueError):
            raise RuntimeError(
                f"agently-cli returned non-JSON output: {proc.stdout[:500]}"
            )

    # --- send (two-phase) ---------------------------------------------------

    def send(
        self, record: "EmailConfigRecord", request: MailSendRequest
    ) -> MailSendResult:
        args = ["message", "+send"]
        for r in request.recipients:
            args += ["--to", r]
        args += ["--subject", request.subject]
        body = request.content_html or request.content
        args += ["--body", body]
        if request.cc:
            for cc in request.cc:
                args += ["--cc", cc]
        if request.bcc:
            for bcc in request.bcc:
                args += ["--bcc", bcc]
        data = self._run_cli(record, args)
        return self._build_send_result(record, data)

    def send_confirm(
        self, record: "EmailConfigRecord", confirmation_token: str
    ) -> MailSendResult:
        """Phase 2: commit a prepared send with the confirmation token."""
        args = ["message", "+send", "--confirmation-token", confirmation_token]
        data = self._run_cli(record, args)
        return self._build_send_result(record, data)

    def _build_send_result(
        self, record: "EmailConfigRecord", data: dict
    ) -> MailSendResult:
        return MailSendResult(
            sent=not data.get("confirmation_required", False),
            provider=self.provider_key,
            from_email=data.get("from", record.sender_email or ""),
            recipient_count=data.get("recipient_count", 0),
            message_id=data.get("message_id"),
        )

    # --- list ---------------------------------------------------------------

    def list_messages(
        self, record: "EmailConfigRecord", options: dict[str, Any] | None = None
    ) -> list[MailMessage]:
        opts = options or {}
        args = ["message", "+list"]
        if "limit" in opts:
            args += ["--limit", str(opts["limit"])]
        if "cursor" in opts:
            args += ["--cursor", opts["cursor"]]
        if "dir" in opts:
            args += ["--dir", opts["dir"]]
        if opts.get("is_unread"):
            args.append("--is-unread")
        if opts.get("has_attachments"):
            args.append("--has-attachments")
        if "after" in opts:
            args += ["--after", opts["after"]]
        if "before" in opts:
            args += ["--before", opts["before"]]

        data = self._run_cli(record, args)
        messages_raw = data.get("messages") or data.get("data") or []
        return [self._to_mail_message(m) for m in messages_raw]

    # --- read ---------------------------------------------------------------

    def read_message(
        self, record: "EmailConfigRecord", message_id: str
    ) -> MailMessage:
        args = ["message", "+read", "--id", message_id]
        data = self._run_cli(record, args)
        msg_data = data.get("message") or data
        return self._to_mail_message(msg_data)

    # --- search -------------------------------------------------------------

    def search_messages(
        self,
        record: "EmailConfigRecord",
        query: str,
        options: dict[str, Any] | None = None,
    ) -> list[MailMessage]:
        opts = options or {}
        args = ["message", "+search", "--q", query]
        if "limit" in opts:
            args += ["--limit", str(opts["limit"])]
        if "cursor" in opts:
            args += ["--cursor", opts["cursor"]]
        if "from" in opts:
            args += ["--from", opts["from"]]
        if "to" in opts:
            args += ["--to", opts["to"]]
        if "dir" in opts:
            args += ["--dir", opts["dir"]]
        if "search_in" in opts:
            args += ["--search-in", opts["search_in"]]

        data = self._run_cli(record, args)
        messages_raw = data.get("messages") or data.get("data") or []
        return [self._to_mail_message(m) for m in messages_raw]

    # --- reply (two-phase) --------------------------------------------------

    def reply(
        self,
        record: "EmailConfigRecord",
        message_id: str,
        request: MailSendRequest,
    ) -> MailSendResult:
        args = ["message", "+reply", "--id", message_id]
        body = request.content_html or request.content
        args += ["--body", body]
        if request.cc:
            for cc in request.cc:
                args += ["--cc", cc]
        data = self._run_cli(record, args)
        return self._build_send_result(record, data)

    def reply_confirm(
        self, record: "EmailConfigRecord", confirmation_token: str
    ) -> MailSendResult:
        """Phase 2 for reply."""
        args = ["message", "+reply", "--confirmation-token", confirmation_token]
        data = self._run_cli(record, args)
        return self._build_send_result(record, data)

    # --- forward (two-phase) ------------------------------------------------

    def forward(
        self,
        record: "EmailConfigRecord",
        message_id: str,
        request: MailSendRequest,
    ) -> MailSendResult:
        args = ["message", "+forward", "--id", message_id]
        for r in request.recipients:
            args += ["--to", r]
        body = request.content_html or request.content
        if body:
            args += ["--body", body]
        args.append("--include-attachments")
        data = self._run_cli(record, args)
        return self._build_send_result(record, data)

    def forward_confirm(
        self, record: "EmailConfigRecord", confirmation_token: str
    ) -> MailSendResult:
        """Phase 2 for forward."""
        args = ["message", "+forward", "--confirmation-token", confirmation_token]
        data = self._run_cli(record, args)
        return self._build_send_result(record, data)

    # --- attachments --------------------------------------------------------

    def download_attachment(
        self, record: "EmailConfigRecord", message_id: str, attachment_id: str
    ) -> dict[str, Any]:
        args = [
            "attachment", "+download",
            "--msg", message_id,
            "--att", attachment_id,
        ]
        data = self._run_cli(record, args, timeout=60)
        return {
            "ok": True,
            "file_path": data.get("file_path", ""),
            "filename": data.get("filename", ""),
            "size": data.get("size", 0),
        }

    # --- status / auth ------------------------------------------------------

    def status(self, record: "EmailConfigRecord") -> dict[str, Any]:
        try:
            data = self._run_cli(record, ["auth", "status"])
            me_data = self._run_cli(record, ["+me"])
        except RuntimeError as exc:
            return {
                "ok": False,
                "provider": self.provider_key,
                "capabilities": sorted(
                    cap.value for cap in self.capabilities()
                ),
                "error": str(exc),
            }
        return {
            "ok": True,
            "provider": self.provider_key,
            "capabilities": sorted(cap.value for cap in self.capabilities()),
            "auth_status": data.get("status", "unknown"),
            "email": me_data.get("email", ""),
            "aliases": me_data.get("aliases", []),
        }

    # --- normalization helpers ----------------------------------------------

    @staticmethod
    def _to_mail_message(raw: dict[str, Any]) -> MailMessage:
        return MailMessage(
            message_id=raw.get("message_id") or raw.get("id") or "",
            thread_id=raw.get("thread_id"),
            subject=raw.get("subject") or "",
            from_email=raw.get("from") or raw.get("from_email") or "",
            to=raw.get("to") or [],
            snippet=raw.get("snippet") or raw.get("preview") or "",
            body_text=raw.get("body_text") or raw.get("body") or "",
            body_html=raw.get("body_html") or "",
            received_at=raw.get("received_at") or raw.get("date") or None,
            attachments=raw.get("attachments") or [],
            raw=raw,
        )
