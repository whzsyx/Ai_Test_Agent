from __future__ import annotations

from datetime import datetime
import json

import pymysql

from src.core.config import Settings
from src.schemas.email_config import (
    EmailConfigCreateRequest,
    EmailConfigPublic,
    EmailConfigRecord,
    EmailConfigUpdateRequest,
)

DEFAULT_CYBERMAIL_HOST = "mail.cyberpersons.com"
DEFAULT_CYBERMAIL_PORT = 587

PROVIDER_DEFAULT_NAMES = {
    "aliyun": "阿里云邮件推送",
    "cybermail": "CyberMail SMTP",
    "tencent_ses": "腾讯云 SES",
    "sendgrid": "SendGrid",
    "mailgun": "Mailgun",
    "postmark": "Postmark",
    "resend": "Resend",
    "brevo": "Brevo",
    "mailchimp": "Mailchimp",
    "zoho_campaigns": "Zoho Campaigns",
}


class MySQLEmailConfigStore:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def initialize(self) -> None:
        with self._connect() as conn:
            with conn.cursor() as cur:
                if not self._table_exists(cur):
                    self._create_table(cur)
                    conn.commit()
                    return

                columns = self._list_columns(cur)
                if "config_json" in columns:
                    self._migrate_legacy_table(cur)
                    conn.commit()
                    return

                self._ensure_columns(cur, columns)
            conn.commit()

    def list_all(self) -> list[EmailConfigRecord]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, config_name, provider, api_key, secret_key, sender_email, test_email,
                           test_mode, enabled, is_default, description, smtp_host, smtp_port,
                           smtp_username, extra_config_json, created_at, updated_at
                    FROM `{self._settings.email_config_table}`
                    ORDER BY is_default DESC, enabled DESC, id ASC
                    """
                )
                rows = cur.fetchall()
        return [self._row_to_record(row) for row in rows]

    def get_by_id(self, config_id: int) -> EmailConfigRecord:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, config_name, provider, api_key, secret_key, sender_email, test_email,
                           test_mode, enabled, is_default, description, smtp_host, smtp_port,
                           smtp_username, extra_config_json, created_at, updated_at
                    FROM `{self._settings.email_config_table}`
                    WHERE id=%s
                    """,
                    (config_id,),
                )
                row = cur.fetchone()
        if not row:
            raise KeyError(config_id)
        return self._row_to_record(row)

    def create(self, payload: EmailConfigCreateRequest) -> EmailConfigRecord:
        values = self._payload_to_values(payload)
        with self._connect() as conn:
            with conn.cursor() as cur:
                if payload.is_default:
                    cur.execute(
                        f"UPDATE `{self._settings.email_config_table}` SET enabled=0, is_default=0"
                    )
                cur.execute(
                    f"""
                    INSERT INTO `{self._settings.email_config_table}`
                    (config_name, provider, api_key, secret_key, sender_email, test_email, test_mode,
                     enabled, is_default, description, smtp_host, smtp_port, smtp_username, extra_config_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    values,
                )
                config_id = int(cur.lastrowid)
            conn.commit()
        return self.get_by_id(config_id)

    def update(self, config_id: int, payload: EmailConfigUpdateRequest) -> EmailConfigRecord:
        existing = self.get_by_id(config_id)
        merged = self._merge_update(existing, payload)

        with self._connect() as conn:
            with conn.cursor() as cur:
                if merged.is_default:
                    cur.execute(
                        f"UPDATE `{self._settings.email_config_table}` SET enabled=0, is_default=0"
                    )
                cur.execute(
                    f"""
                    UPDATE `{self._settings.email_config_table}`
                    SET config_name=%s,
                        provider=%s,
                        api_key=%s,
                        secret_key=%s,
                        sender_email=%s,
                        test_email=%s,
                        test_mode=%s,
                        enabled=%s,
                        is_default=%s,
                        description=%s,
                        smtp_host=%s,
                        smtp_port=%s,
                        smtp_username=%s,
                        extra_config_json=%s
                    WHERE id=%s
                    """,
                    (
                        merged.config_name,
                        merged.provider,
                        merged.api_key,
                        merged.secret_key,
                        merged.sender_email,
                        merged.test_email,
                        int(merged.test_mode),
                        int(merged.enabled),
                        int(merged.is_default),
                        merged.description,
                        merged.smtp_host,
                        merged.smtp_port,
                        merged.smtp_username,
                        json.dumps(merged.extra_config, ensure_ascii=False),
                        config_id,
                    ),
                )
            conn.commit()
        return self.get_by_id(config_id)

    def activate(self, config_id: int) -> EmailConfigRecord:
        self.get_by_id(config_id)
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"UPDATE `{self._settings.email_config_table}` SET enabled=0, is_default=0"
                )
                cur.execute(
                    f"""
                    UPDATE `{self._settings.email_config_table}`
                    SET enabled=1, is_default=1
                    WHERE id=%s
                    """,
                    (config_id,),
                )
            conn.commit()
        return self.get_by_id(config_id)

    def delete(self, config_id: int) -> tuple[EmailConfigRecord, EmailConfigRecord | None]:
        deleted = self.get_by_id(config_id)
        replacement: EmailConfigRecord | None = None
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM `{self._settings.email_config_table}` WHERE id=%s",
                    (config_id,),
                )
                if deleted.is_default:
                    cur.execute(
                        f"""
                        SELECT id
                        FROM `{self._settings.email_config_table}`
                        ORDER BY id ASC
                        LIMIT 1
                        """
                    )
                    row = cur.fetchone()
                    if row:
                        next_id = int(row["id"])
                        cur.execute(
                            f"""
                            UPDATE `{self._settings.email_config_table}`
                            SET enabled=1, is_default=1
                            WHERE id=%s
                            """,
                            (next_id,),
                        )
                        replacement = self.get_by_id(next_id)
            conn.commit()
        return deleted, replacement

    def to_public(self, record: EmailConfigRecord) -> EmailConfigPublic:
        return EmailConfigPublic(
            id=int(record.id or 0),
            config_name=record.config_name,
            provider=record.provider,
            enabled=record.enabled,
            is_default=record.is_default,
            sender_email=record.sender_email,
            test_email=record.test_email,
            test_mode=record.test_mode,
            description=record.description,
            smtp_host=record.smtp_host,
            smtp_port=record.smtp_port,
            smtp_username=record.smtp_username,
            extra_config=record.extra_config,
            has_api_key=bool(record.api_key),
            has_secret_key=bool(record.secret_key),
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def _table_exists(self, cur) -> bool:
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM information_schema.tables
            WHERE table_schema=%s AND table_name=%s
            """,
            (self._settings.mysql_database, self._settings.email_config_table),
        )
        return bool(cur.fetchone()["total"])

    def _list_columns(self, cur) -> set[str]:
        cur.execute(
            """
            SELECT COLUMN_NAME
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            """,
            (self._settings.mysql_database, self._settings.email_config_table),
        )
        return {row["COLUMN_NAME"] for row in cur.fetchall()}

    def _create_table(self, cur) -> None:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS `{self._settings.email_config_table}` (
                `id` BIGINT NOT NULL AUTO_INCREMENT,
                `config_name` VARCHAR(120) NOT NULL,
                `provider` VARCHAR(64) NOT NULL,
                `api_key` VARCHAR(255) NULL,
                `secret_key` VARCHAR(255) NULL,
                `sender_email` VARCHAR(255) NOT NULL,
                `test_email` VARCHAR(255) NULL,
                `test_mode` TINYINT(1) NOT NULL DEFAULT 0,
                `enabled` TINYINT(1) NOT NULL DEFAULT 0,
                `is_default` TINYINT(1) NOT NULL DEFAULT 0,
                `description` TEXT NULL,
                `smtp_host` VARCHAR(255) NULL,
                `smtp_port` INT NULL,
                `smtp_username` VARCHAR(255) NULL,
                `extra_config_json` TEXT NULL,
                `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uniq_email_config_name` (`config_name`)
            ) ENGINE=InnoDB DEFAULT CHARSET={self._settings.mysql_charset}
            """
        )

    def _ensure_columns(self, cur, columns: set[str]) -> None:
        required_columns = {
            "id": "ALTER TABLE `{table}` ADD COLUMN `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY FIRST",
            "config_name": "ALTER TABLE `{table}` ADD COLUMN `config_name` VARCHAR(120) NOT NULL DEFAULT '' AFTER `id`",
            "api_key": "ALTER TABLE `{table}` ADD COLUMN `api_key` VARCHAR(255) NULL AFTER `provider`",
            "secret_key": "ALTER TABLE `{table}` ADD COLUMN `secret_key` VARCHAR(255) NULL AFTER `api_key`",
            "sender_email": "ALTER TABLE `{table}` ADD COLUMN `sender_email` VARCHAR(255) NOT NULL DEFAULT '' AFTER `secret_key`",
            "test_email": "ALTER TABLE `{table}` ADD COLUMN `test_email` VARCHAR(255) NULL AFTER `sender_email`",
            "test_mode": "ALTER TABLE `{table}` ADD COLUMN `test_mode` TINYINT(1) NOT NULL DEFAULT 0 AFTER `test_email`",
            "enabled": "ALTER TABLE `{table}` ADD COLUMN `enabled` TINYINT(1) NOT NULL DEFAULT 0 AFTER `test_mode`",
            "is_default": "ALTER TABLE `{table}` ADD COLUMN `is_default` TINYINT(1) NOT NULL DEFAULT 0 AFTER `enabled`",
            "description": "ALTER TABLE `{table}` ADD COLUMN `description` TEXT NULL AFTER `is_default`",
            "smtp_host": "ALTER TABLE `{table}` ADD COLUMN `smtp_host` VARCHAR(255) NULL AFTER `description`",
            "smtp_port": "ALTER TABLE `{table}` ADD COLUMN `smtp_port` INT NULL AFTER `smtp_host`",
            "smtp_username": "ALTER TABLE `{table}` ADD COLUMN `smtp_username` VARCHAR(255) NULL AFTER `smtp_port`",
            "extra_config_json": "ALTER TABLE `{table}` ADD COLUMN `extra_config_json` TEXT NULL AFTER `smtp_username`",
        }
        for name, statement in required_columns.items():
            if name not in columns:
                cur.execute(statement.format(table=self._settings.email_config_table))
        cur.execute(
            f"""
            UPDATE `{self._settings.email_config_table}`
            SET config_name = CASE
                WHEN config_name IS NULL OR config_name = '' THEN CONCAT(provider, '-', id)
                ELSE config_name
            END
            """
        )

    def _migrate_legacy_table(self, cur) -> None:
        legacy_rows = self._fetch_legacy_rows(cur)
        backup_name = (
            f"{self._settings.email_config_table}_legacy_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        cur.execute(f"RENAME TABLE `{self._settings.email_config_table}` TO `{backup_name}`")
        self._create_table(cur)
        for row in legacy_rows:
            self._insert_record(cur, self._legacy_row_to_record(row))

    def _fetch_legacy_rows(self, cur) -> list[dict]:
        cur.execute(
            f"""
            SELECT provider, enabled, is_default, from_email, from_name, reply_to, config_json, created_at, updated_at
            FROM `{self._settings.email_config_table}`
            ORDER BY provider ASC
            """
        )
        return cur.fetchall()

    def _legacy_row_to_record(self, row: dict) -> EmailConfigRecord:
        config = json.loads(row.get("config_json") or "{}")
        provider = str(row["provider"]).strip().lower()
        return EmailConfigRecord(
            config_name=PROVIDER_DEFAULT_NAMES.get(provider, provider),
            provider=provider,
            api_key=_clean_str(config.get("access_key_id")) or _clean_str(config.get("smtp_password")),
            secret_key=_clean_str(config.get("access_key_secret")),
            sender_email=row.get("from_email") or "",
            test_email=None,
            test_mode=False,
            enabled=bool(row.get("enabled")),
            is_default=bool(row.get("is_default")),
            description=None,
            smtp_host=_clean_str(config.get("smtp_host")) or (
                DEFAULT_CYBERMAIL_HOST if provider == "cybermail" else None
            ),
            smtp_port=(
                int(config.get("smtp_port") or DEFAULT_CYBERMAIL_PORT)
                if provider == "cybermail" or config.get("smtp_port")
                else None
            ),
            smtp_username=_clean_str(config.get("smtp_username")),
            extra_config=_extract_legacy_extra_config(provider, config),
            created_at=_to_datetime(row.get("created_at")),
            updated_at=_to_datetime(row.get("updated_at")),
        )

    def _insert_record(self, cur, record: EmailConfigRecord) -> None:
        cur.execute(
            f"""
            INSERT INTO `{self._settings.email_config_table}`
            (config_name, provider, api_key, secret_key, sender_email, test_email, test_mode,
             enabled, is_default, description, smtp_host, smtp_port, smtp_username, extra_config_json, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.config_name,
                record.provider,
                record.api_key,
                record.secret_key,
                record.sender_email,
                record.test_email,
                int(record.test_mode),
                int(record.enabled),
                int(record.is_default),
                record.description,
                record.smtp_host,
                record.smtp_port,
                record.smtp_username,
                json.dumps(record.extra_config, ensure_ascii=False),
                record.created_at or datetime.utcnow(),
                record.updated_at or datetime.utcnow(),
            ),
        )

    def _merge_update(self, existing: EmailConfigRecord, payload: EmailConfigUpdateRequest) -> EmailConfigRecord:
        if payload.provider == "cybermail":
            smtp_host = _clean_str(payload.smtp_host) or DEFAULT_CYBERMAIL_HOST
            smtp_port = int(payload.smtp_port or DEFAULT_CYBERMAIL_PORT)
            smtp_username = _clean_str(payload.smtp_username)
        else:
            smtp_host = None
            smtp_port = None
            smtp_username = None

        return EmailConfigRecord(
            id=existing.id,
            config_name=payload.config_name.strip(),
            provider=payload.provider,
            api_key=payload.api_key.strip() if payload.api_key else existing.api_key,
            secret_key=payload.secret_key.strip() if payload.secret_key else existing.secret_key,
            sender_email=payload.sender_email.strip(),
            test_email=_clean_str(payload.test_email),
            test_mode=bool(payload.test_mode),
            enabled=bool(payload.enabled or payload.is_default),
            is_default=bool(payload.is_default),
            description=_clean_str(payload.description),
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            extra_config=_clean_extra_config(payload.extra_config),
            created_at=existing.created_at,
            updated_at=existing.updated_at,
        )

    def _payload_to_values(self, payload: EmailConfigCreateRequest):
        if payload.provider == "cybermail":
            smtp_host = _clean_str(payload.smtp_host) or DEFAULT_CYBERMAIL_HOST
            smtp_port = int(payload.smtp_port or DEFAULT_CYBERMAIL_PORT)
            smtp_username = _clean_str(payload.smtp_username)
        else:
            smtp_host = None
            smtp_port = None
            smtp_username = None

        enabled = bool(payload.enabled or payload.is_default)
        return (
            payload.config_name.strip(),
            payload.provider,
            _clean_str(payload.api_key),
            _clean_str(payload.secret_key),
            payload.sender_email.strip(),
            _clean_str(payload.test_email),
            int(payload.test_mode),
            int(enabled),
            int(payload.is_default),
            _clean_str(payload.description),
            smtp_host,
            smtp_port,
            smtp_username,
            json.dumps(_clean_extra_config(payload.extra_config), ensure_ascii=False),
        )

    def _row_to_record(self, row: dict | None) -> EmailConfigRecord:
        if row is None:
            raise KeyError("email config row not found")

        provider = str(row["provider"]).strip().lower()
        smtp_host = _clean_str(row.get("smtp_host"))
        smtp_port = row.get("smtp_port")
        smtp_username = _clean_str(row.get("smtp_username"))

        if provider == "cybermail":
            smtp_host = smtp_host or DEFAULT_CYBERMAIL_HOST
            smtp_port = int(smtp_port or DEFAULT_CYBERMAIL_PORT)

        return EmailConfigRecord(
            id=int(row["id"]),
            config_name=row.get("config_name") or PROVIDER_DEFAULT_NAMES.get(provider, provider),
            provider=provider,
            api_key=_clean_str(row.get("api_key")),
            secret_key=_clean_str(row.get("secret_key")),
            sender_email=row.get("sender_email") or "",
            test_email=_clean_str(row.get("test_email")),
            test_mode=bool(row.get("test_mode")),
            enabled=bool(row.get("enabled")),
            is_default=bool(row.get("is_default")),
            description=_clean_str(row.get("description")),
            smtp_host=smtp_host,
            smtp_port=int(smtp_port) if smtp_port is not None else None,
            smtp_username=smtp_username,
            extra_config=_parse_extra_config(row.get("extra_config_json")),
            created_at=_to_datetime(row.get("created_at")),
            updated_at=_to_datetime(row.get("updated_at")),
        )

    def _connect(self):
        return pymysql.connect(
            host=self._settings.mysql_host,
            port=self._settings.mysql_port,
            user=self._settings.mysql_user,
            password=self._settings.mysql_password,
            database=self._settings.mysql_database,
            charset=self._settings.mysql_charset,
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )


def _clean_str(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clean_extra_config(value):
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _parse_extra_config(value):
    if not value:
        return {}
    if isinstance(value, dict):
        return _clean_extra_config(value)
    try:
        return _clean_extra_config(json.loads(str(value)))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _extract_legacy_extra_config(provider: str, config: dict) -> dict:
    if provider == "aliyun":
        return {
            "mode": "directmail_api",
            "domain": config.get("domain"),
        }
    if provider == "cybermail":
        return {
            "mode": "smtp",
        }
    return {}


def _to_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))
