"""Aliyun DirectMail transactional-send adapter.

Ported verbatim from ``tool_runtime_service._send_via_aliyun_directmail`` to
preserve the exact signing and request behavior.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import httpx

from src.application.mail.contracts import (
    MailCapability,
    MailProviderAdapter,
    MailSendRequest,
    MailSendResult,
)

if TYPE_CHECKING:
    from src.schemas.email_config import EmailConfigRecord


class AliyunMailAdapter(MailProviderAdapter):
    """Sends mail via Aliyun DirectMail SingleSendMail API. Send-only."""

    provider_key = "aliyun"

    def capabilities(self) -> set[MailCapability]:
        return {MailCapability.SEND}

    def send(self, record: "EmailConfigRecord", request: MailSendRequest) -> MailSendResult:
        if not record.api_key or not record.secret_key or not record.sender_email:
            raise RuntimeError("Selected Aliyun email configuration is incomplete.")

        html_body = request.content_html or request.content
        for recipient in request.recipients:
            params = {
                "Action": "SingleSendMail",
                "AccountName": record.sender_email,
                "ReplyToAddress": "false",
                "AddressType": "1",
                "ToAddress": recipient,
                "Subject": request.subject,
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
                raise RuntimeError(
                    f"Aliyun DirectMail failed: {payload.get('Message') or payload['Code']}"
                )

        return MailSendResult(
            sent=True,
            provider=record.provider,
            from_email=record.sender_email or record.smtp_username or "",
            recipient_count=len(request.recipients),
        )
