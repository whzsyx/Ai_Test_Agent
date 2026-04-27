from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from src.modes.code_review_mode.models import ProjectSource


DEFAULT_IGNORED_NAMES = {
    ".git",
    ".idea",
    ".vscode",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    "coverage",
}


def normalize_project_source(arguments: dict[str, Any]) -> ProjectSource:
    raw_source = arguments.get("project_source")
    ssh_source = {}
    if isinstance(raw_source, dict):
        ssh_source = raw_source.get("ssh") if isinstance(raw_source.get("ssh"), dict) else {}
    source_type = str(
        (raw_source or {}).get("source_type")
        if isinstance(raw_source, dict)
        else arguments.get("source_type")
        or "local"
    ).strip().lower() or "local"
    root_path = _coerce_string(
        (raw_source or {}).get("root_path") if isinstance(raw_source, dict) else None,
        arguments.get("root_path"),
        arguments.get("project_path"),
    )
    branch = _coerce_string(
        (raw_source or {}).get("branch") if isinstance(raw_source, dict) else None,
        arguments.get("branch"),
    )
    commit_range = _coerce_string(
        (raw_source or {}).get("commit_range") if isinstance(raw_source, dict) else None,
        arguments.get("commit_range"),
    )
    project_name = _coerce_string(
        (raw_source or {}).get("project_name") if isinstance(raw_source, dict) else None,
        arguments.get("project_name"),
        project_name_from_path(root_path),
    ) or "Unnamed Project"
    ssh_payload = {
        "host": _coerce_string(ssh_source.get("host"), arguments.get("ssh_host")),
        "port": int(ssh_source.get("port") or arguments.get("ssh_port") or 22),
        "username": _coerce_string(ssh_source.get("username"), arguments.get("ssh_username")),
        "auth_ref": _coerce_string(ssh_source.get("auth_ref"), arguments.get("ssh_auth_ref")),
        "remote_root_path": _coerce_string(
            ssh_source.get("remote_root_path"),
            arguments.get("remote_root_path"),
            root_path,
        ),
    }
    return ProjectSource(
        source_type="ssh" if source_type == "ssh" else "local",
        root_path=root_path,
        project_name=project_name,
        branch=branch,
        commit_range=commit_range,
        ssh=ssh_payload,
    )


def project_name_from_path(path: str) -> str:
    cleaned = path.strip()
    if not cleaned:
        return ""
    if ":" in cleaned[:4] or "\\" in cleaned:
        return PureWindowsPath(cleaned).name
    return PurePosixPath(cleaned).name


def project_source_root(project_source: ProjectSource) -> str:
    return project_source.root_path or project_source.ssh.remote_root_path or project_source.project_name


def resolve_local_project_root(project_source: ProjectSource) -> Path:
    root_value = project_source.root_path.strip()
    if not root_value:
        raise ValueError("Local project source requires a root_path.")
    return Path(root_value).expanduser().resolve()


def resolve_local_project_file(project_source: ProjectSource, file_path: str) -> Path:
    root = resolve_local_project_root(project_source)
    candidate = Path(file_path.strip())
    resolved = candidate.expanduser().resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError(f"File path must stay within the project root: {root}")
    return resolved


def _coerce_string(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "none":
            return text
    return ""
