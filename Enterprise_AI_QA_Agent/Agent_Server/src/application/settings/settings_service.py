from __future__ import annotations

from datetime import datetime, timezone
from email.message import EmailMessage
import smtplib
from time import perf_counter

import httpx

from src.application.model_adapters import AdapterRegistry, build_default_adapter_registry
from src.application.models.model_compatibility import ModelCompatibilityLayer
from src.core.config import Settings
from src.infrastructure.email_config_store import MySQLEmailConfigStore
from src.infrastructure.model_config_store import MySQLModelConfigStore
from src.schemas.email_config import (
    EmailConfigActionResponse,
    EmailConfigConnectionTestResponse,
    EmailConfigCreateRequest,
    EmailConfigPublic,
    EmailConfigUpdateRequest,
)
from src.schemas.model_config import ModelInvocationRequest
from src.schemas.settings import (
    ModelConfigActionResponse,
    ModelConfigConnectionTestResponse,
    ModelConfigUpdateRequest,
)


class SettingsService:
    def __init__(
        self,
        settings: Settings,
        model_config_store: MySQLModelConfigStore,
        email_config_store: MySQLEmailConfigStore,
        adapter_registry: AdapterRegistry | None = None,
    ) -> None:
        self._settings = settings
        self._model_config_store = model_config_store
        self._email_config_store = email_config_store
        self._adapter_registry = adapter_registry or build_default_adapter_registry()
        self._compatibility = ModelCompatibilityLayer(adapter_registry=self._adapter_registry)

    def list_model_configs(self):
        return [self._model_config_store.to_public(item) for item in self._model_config_store.list_all()]

    def update_model_config(self, payload: ModelConfigUpdateRequest):
        return self._model_config_store.upsert(payload)

    def edit_model_config(self, original_model_name: str, payload: ModelConfigUpdateRequest):
        return self._model_config_store.update_existing(original_model_name, payload)

    def activate_model_config(self, model_name: str):
        item = self._model_config_store.activate(model_name)
        return ModelConfigActionResponse(
            ok=True,
            message=f"Model '{item.name}' is now active.",
            item=item,
        )

    def delete_model_config(self, model_name: str):
        deleted, replacement = self._model_config_store.delete(model_name)
        message = f"Model '{deleted.name}' was deleted."
        if replacement is not None:
            message += f" '{replacement.name}' is now active."
        return ModelConfigActionResponse(
            ok=True,
            message=message,
            item=self._model_config_store.to_public(replacement) if replacement else None,
        )

    def test_model_config_connection(self, model_name: str):
        record = self._model_config_store.get_by_name(model_name)
        public_item = self._model_config_store.to_public(record)
        if not record.api_key:
            return ModelConfigConnectionTestResponse(
                ok=False,
                message=f"Model '{record.name}' has no API key configured.",
                item=public_item,
                provider=record.provider,
                api_base_url=record.api_base_url,
            )

        request = ModelInvocationRequest(
            system_prompt="You are a model connection health check. Reply with a short pong.",
            messages=[{"role": "user", "content": "ping"}],
        )
        url = self._compatibility.build_url(record)
        headers = self._compatibility.build_headers(record, record.api_key)
        payload = self._compatibility.build_request(record, request)

        started_at = perf_counter()
        try:
            with httpx.Client(timeout=self._settings.llm_request_timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                parsed = self._compatibility.parse_response(record, response.json())
        except httpx.HTTPError as exc:
            return ModelConfigConnectionTestResponse(
                ok=False,
                message=f"Connection test failed: {exc}",
                item=public_item,
                provider=record.provider,
                api_base_url=record.api_base_url,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

        preview = (parsed.get("text") or "").strip()
        if preview:
            preview = preview[:120]

        return ModelConfigConnectionTestResponse(
            ok=True,
            message=f"Connection test succeeded for '{record.name}'.",
            item=public_item,
            provider=record.provider,
            api_base_url=record.api_base_url,
            latency_ms=int((perf_counter() - started_at) * 1000),
            preview=preview or None,
        )

    def list_email_configs(self):
        return [self._to_email_public(item) for item in self._email_config_store.list_all()]

    def create_email_config(self, payload: EmailConfigCreateRequest):
        return self._to_email_public(self._email_config_store.create(payload))

    def update_email_config(self, config_id: int, payload: EmailConfigUpdateRequest):
        return self._to_email_public(self._email_config_store.update(config_id, payload))

    def activate_email_config(self, config_id: int):
        item = self._email_config_store.activate(config_id)
        return EmailConfigActionResponse(
            ok=True,
            message=f"Email channel '{item.config_name}' is now enabled and set as default.",
            item=self._to_email_public(item),
        )

    def delete_email_config(self, config_id: int):
        deleted, replacement = self._email_config_store.delete(config_id)
        message = f"Email channel '{deleted.config_name}' was deleted."
        if replacement is not None:
            message += f" '{replacement.config_name}' is now enabled as the default channel."
        return EmailConfigActionResponse(
            ok=True,
            message=message,
            item=self._to_email_public(replacement) if replacement else None,
        )

    def test_email_config_connection(self, config_id: int):
        record = self._email_config_store.get_by_id(config_id)
        public_item = self._to_email_public(record)

        extra_config = record.extra_config or {}
        delivery_mode = str(extra_config.get("delivery_mode") or ("smtp" if record.smtp_host else "api")).strip().lower()
        test_email = str(record.test_email or "").strip()

        if not test_email:
            return EmailConfigConnectionTestResponse(
                ok=False,
                message=f"Email channel '{record.config_name}' has no test email configured.",
                item=public_item,
                smtp_host=record.smtp_host,
                smtp_port=record.smtp_port,
            )

        subject, text_body, html_body = self._build_test_email_content(record, test_email)

        started_at = perf_counter()
        try:
            if delivery_mode == "smtp":
                self._send_via_smtp_provider(record, [test_email], subject, text_body, html_body)
                preview = f"Test email sent to {test_email} via SMTP."
            else:
                provider = str(record.provider or "").strip().lower()
                if provider == "aliyun":
                    self._send_via_aliyun_directmail(record, [test_email], subject, html_body)
                    preview = f"Test email sent to {test_email} via Aliyun DirectMail API."
                else:
                    api_check = self._validate_api_email_config(record)
                    if api_check is not None:
                        return EmailConfigConnectionTestResponse(
                            ok=api_check.ok,
                            message=(
                                f"Email channel '{record.config_name}' passed configuration validation, "
                                f"but provider '{provider}' does not support direct test sending yet."
                            )
                            if api_check.ok
                            else api_check.message,
                            item=public_item,
                            smtp_host=record.smtp_host,
                            smtp_port=record.smtp_port,
                            latency_ms=int((perf_counter() - started_at) * 1000),
                            preview=api_check.preview,
                        )
                    return EmailConfigConnectionTestResponse(
                        ok=False,
                        message=f"Email channel '{record.config_name}' cannot determine a supported test delivery mode.",
                        item=public_item,
                        smtp_host=record.smtp_host,
                        smtp_port=record.smtp_port,
                        latency_ms=int((perf_counter() - started_at) * 1000),
                    )
        except (OSError, smtplib.SMTPException, httpx.HTTPError, RuntimeError) as exc:
            return EmailConfigConnectionTestResponse(
                ok=False,
                message=f"Test email failed: {exc}",
                item=public_item,
                smtp_host=record.smtp_host,
                smtp_port=record.smtp_port,
                latency_ms=int((perf_counter() - started_at) * 1000),
            )

        return EmailConfigConnectionTestResponse(
            ok=True,
            message=f"Test email sent successfully for '{record.config_name}'.",
            item=public_item,
            smtp_host=record.smtp_host,
            smtp_port=record.smtp_port,
            latency_ms=int((perf_counter() - started_at) * 1000),
            preview=preview,
        )

    def _validate_api_email_config(self, record) -> EmailConfigConnectionTestResponse | None:
        public_item = self._to_email_public(record)
        provider = str(record.provider or "").strip().lower()
        sending_domain = str((record.extra_config or {}).get("sending_domain") or "").strip()

        def ok(preview: str):
            return EmailConfigConnectionTestResponse(
                ok=True,
                message=f"Configuration check succeeded for '{record.config_name}'.",
                item=public_item,
                preview=preview,
            )

        def fail(detail: str):
            return EmailConfigConnectionTestResponse(
                ok=False,
                message=detail,
                item=public_item,
            )

        if provider == "aliyun":
            if not record.api_key or not record.secret_key or not record.sender_email:
                return fail(
                    f"Email channel '{record.config_name}' is missing AccessKey, SecretKey or sender email."
                )
            return ok("Aliyun DirectMail profile is ready.")

        if provider == "tencent_ses":
            if not record.api_key or not record.secret_key or not record.sender_email:
                return fail(
                    f"Email channel '{record.config_name}' is missing SecretId, SecretKey or sender email."
                )
            return ok("Tencent SES API credentials are ready.")

        if provider in {"sendgrid", "postmark", "resend", "brevo", "mailchimp", "zoho_campaigns"}:
            if not record.api_key:
                return fail(f"Email channel '{record.config_name}' is missing API key.")
            return ok(f"{provider} API key is configured.")

        if provider == "mailgun":
            if not record.api_key or not sending_domain:
                return fail(
                    f"Email channel '{record.config_name}' requires both API key and sending domain."
                )
            return ok("Mailgun API key and sending domain are configured.")

        return None

    def _build_test_email_content(self, record, recipient: str) -> tuple[str, str, str]:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        provider_label = str(record.provider or "").strip() or "unknown"
        subject = f"[Enterprise AI QA Agent] 邮件通道测试 - {record.config_name}"
        text_body = (
            "这是一封来自 Enterprise AI QA Agent 的测试邮件。\n\n"
            f"邮件通道: {record.config_name}\n"
            f"提供商: {provider_label}\n"
            f"发信邮箱: {record.sender_email or '-'}\n"
            f"测试邮箱: {recipient}\n"
            f"发送时间: {timestamp}\n"
        )
        html_body = (
            "<html><body>"
            "<h2>Enterprise AI QA Agent 测试邮件</h2>"
            "<p>这是一封测试邮件，用于验证当前邮件通道配置是否可用。</p>"
            "<ul>"
            f"<li><strong>邮件通道：</strong>{record.config_name}</li>"
            f"<li><strong>提供商：</strong>{provider_label}</li>"
            f"<li><strong>发信邮箱：</strong>{record.sender_email or '-'}</li>"
            f"<li><strong>测试邮箱：</strong>{recipient}</li>"
            f"<li><strong>发送时间：</strong>{timestamp}</li>"
            "</ul>"
            "</body></html>"
        )
        return subject, text_body, html_body

    def _send_via_smtp_provider(
        self,
        record,
        recipients: list[str],
        subject: str,
        content: str,
        content_html: str,
    ) -> None:
        if not record.smtp_host or not record.smtp_port:
            raise RuntimeError("Selected email configuration is missing SMTP host or port.")
        if not record.api_key:
            raise RuntimeError("Selected email configuration is missing SMTP password.")

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = record.sender_email or record.smtp_username or ""
        message["To"] = ", ".join(recipients)
        if content:
            message.set_content(content)
        else:
            message.set_content(" ")
        if content_html:
            message.add_alternative(content_html, subtype="html")

        username = record.smtp_username or record.sender_email
        use_ssl = int(record.smtp_port) == 465
        if use_ssl:
            with smtplib.SMTP_SSL(record.smtp_host, int(record.smtp_port), timeout=15) as client:
                client.login(username, record.api_key or "")
                client.send_message(message)
        else:
            with smtplib.SMTP(record.smtp_host, int(record.smtp_port), timeout=15) as client:
                client.ehlo()
                try:
                    client.starttls()
                    client.ehlo()
                except smtplib.SMTPException:
                    pass
                client.login(username, record.api_key or "")
                client.send_message(message)

    def _send_via_aliyun_directmail(self, record, recipients: list[str], subject: str, html_body: str) -> None:
        import base64
        import hashlib
        import hmac
        import urllib.parse
        import uuid

        if not record.api_key or not record.secret_key or not record.sender_email:
            raise RuntimeError("Selected Aliyun email configuration is incomplete.")

        for recipient in recipients:
            params = {
                "Action": "SingleSendMail",
                "AccountName": record.sender_email,
                "ReplyToAddress": "false",
                "AddressType": "1",
                "ToAddress": recipient,
                "Subject": subject,
                "HtmlBody": html_body,
                "Format": "JSON",
                "Version": "2015-11-23",
                "AccessKeyId": record.api_key,
                "SignatureMethod": "HMAC-SHA1",
                "SignatureVersion": "1.0",
                "SignatureNonce": str(uuid.uuid4()),
                "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            sorted_params = sorted(params.items())
            query_string = urllib.parse.urlencode(sorted_params, quote_via=urllib.parse.quote)
            string_to_sign = "POST&%2F&" + urllib.parse.quote(query_string, safe="")
            sign_key = (record.secret_key + "&").encode("utf-8")
            signature = base64.b64encode(
                hmac.new(sign_key, string_to_sign.encode("utf-8"), hashlib.sha1).digest()
            ).decode("utf-8")
            params["Signature"] = signature

            response = httpx.post("https://dm.aliyuncs.com/", data=params, timeout=15)
            response.raise_for_status()
            payload = response.json()
            if "Code" in payload:
                raise RuntimeError(f"Aliyun DirectMail failed: {payload.get('Message') or payload['Code']}")

    def _to_email_public(self, item) -> EmailConfigPublic:
        if isinstance(item, EmailConfigPublic):
            return item

        public_item = self._email_config_store.to_public(item)
        if isinstance(public_item, EmailConfigPublic):
            return public_item
        if hasattr(public_item, "model_dump"):
            return EmailConfigPublic.model_validate(public_item.model_dump(mode="python"))
        if hasattr(public_item, "__dict__"):
            return EmailConfigPublic.model_validate(vars(public_item))
        return EmailConfigPublic.model_validate(public_item)
