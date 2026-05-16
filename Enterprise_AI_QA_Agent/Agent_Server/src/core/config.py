from __future__ import annotations
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    app_name: str = "Enterprise AI QA Agent"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    data_dir: str = "data"
    llm_request_timeout_seconds: float = 60.0
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3307
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "QA_Agent"
    mysql_charset: str = "utf8mb4"
    postgres_host: str = "127.0.0.1"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_database: str = "QA-Agent"
    postgres_connect_timeout_seconds: float = 5.0
    postgres_pool_size: int = 12
    postgres_memory_table: str = "agent_memories"
    postgres_session_table: str = "agent_sessions"
    postgres_message_table: str = "agent_session_messages"
    postgres_event_table: str = "agent_session_events"
    postgres_snapshot_table: str = "agent_session_snapshots"
    postgres_approval_table: str = "agent_session_approvals"
    postgres_tool_job_table: str = "agent_tool_jobs"
    postgres_tool_artifact_table: str = "agent_tool_artifacts"
    postgres_vector_dimension: int = 1536
    memgraph_host: str = "127.0.0.1"
    memgraph_port: int = 7687
    memgraph_user: str = ""
    memgraph_password: str = ""
    llm_model_table: str = "llm_model_config"
    email_config_table: str = "system_email_config"
    memory_backend: str = "postgres"
    session_backend: str = "postgres"
    tool_job_backend: str = "postgres"
    ui_graph_backend: str = "memgraph"
    artifact_root_dir: str = "data/artifacts"
    artifact_storage_backend: str = "minio"
    artifact_keep_local_copy: bool = False
    minio_endpoint: str = "127.0.0.1:9000"
    minio_access_key: str = ""
    minio_secret_key: str = ""
    minio_bucket: str = "qa-agent"
    minio_secure: bool = False
    minio_upload_temp_bucket: str = "upload-temp"
    minio_upload_safe_bucket: str = "upload-safe"
    minio_upload_quarantine_bucket: str = "upload-quarantine"
    upload_scan_max_bytes: int = 10 * 1024 * 1024
    upload_scan_medium_risk_threshold: int = 30
    upload_scan_high_risk_threshold: int = 70
    security_runner_backend: str = "local"
    security_runner_docker_image: str = "vxcontrol/kali-linux"
    security_runner_docker_container_prefix: str = "qa-security-runner"
    security_runner_docker_workdir: str = "/work"
    security_runner_docker_network: str = ""
    security_runner_docker_net_raw: bool = True
    security_runner_docker_net_admin: bool = False
    security_runner_docker_pull_policy: str = "never"
    security_runner_container_reuse: bool = True
    security_runner_docker_cleanup_after_run: bool | None = None
    security_runner_wrap_timeout: bool = True
    memory_top_k: int = 6
    tool_job_heartbeat_timeout_seconds: int = 90
    browser_backend: str = "playwright-cli"
    browser_default_name: str = "chromium"
    browser_headless: bool = True
    browser_window_width: int = 1440
    browser_window_height: int = 960
    browser_action_timeout_seconds: int = 15
    runtime_max_iterations: int = 8
    coordinator_max_workers: int = 4
    cors_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    # OAuth 2.0 Provider Credentials
    oauth_azure_ad_client_id: str = ""
    oauth_azure_ad_client_secret: str = ""
    oauth_azure_ad_tenant_id: str = ""
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_google_project_id: str = ""
    oauth_github_client_id: str = ""
    oauth_github_client_secret: str = ""
    oauth_codebuddy_client_id: str = ""
    oauth_codebuddy_client_secret: str = ""
    oauth_codebuddy_poll_url: str = ""
    oauth_codebuddy_models_endpoint: str = ""
    oauth_trae_client_id: str = ""
    oauth_trae_client_secret: str = ""
    oauth_codex_client_id: str = ""
    oauth_codex_client_secret: str = ""

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("postgres_pool_size")
    @classmethod
    def validate_postgres_pool_size(cls, value: int) -> int:
        return max(1, value)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
