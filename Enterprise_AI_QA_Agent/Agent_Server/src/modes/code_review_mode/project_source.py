from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from src.modes.code_review_mode.models import ProjectSource


DEFAULT_IGNORED_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".vs",
    ".tmp",
    ".temp",
    ".cache",
    ".parcel-cache",
    ".turbo",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    ".eggs",
    "venv",
    "env",
    "vendor",
    "node_modules",
    ".pnpm-store",
    "bower_components",
    "__pycache__",
    "dist",
    "build",
    "out",
    "target",
    "coverage",
    "htmlcov",
    "site",
    ".gradle",
    ".mvn",
    ".serverless",
    ".terraform",
    ".aws-sam",
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


def ignored_names_from_arguments(arguments: dict[str, Any] | None) -> set[str]:
    ignored = set(DEFAULT_IGNORED_NAMES)
    if not isinstance(arguments, dict):
        return ignored
    for key in ("excluded_paths", "ignored_paths", "ignore_paths", "exclude_paths"):
        ignored.update(_coerce_ignored_names(arguments.get(key)))
    raw_source = arguments.get("project_source")
    if isinstance(raw_source, dict):
        for key in ("excluded_paths", "ignored_paths", "ignore_paths", "exclude_paths"):
            ignored.update(_coerce_ignored_names(raw_source.get(key)))
    return {item for item in ignored if item}


def is_ignored_project_path(path: str | Path, ignored_names: Iterable[str] | None = None) -> bool:
    ignored = {str(item).strip().lower() for item in (ignored_names or DEFAULT_IGNORED_NAMES) if str(item).strip()}
    if not ignored:
        return False
    parts = [
        item.strip().lower()
        for item in str(path).replace("\\", "/").split("/")
        if item.strip() and item.strip() not in {".", ".."}
    ]
    return any(part in ignored for part in parts)


def _coerce_string(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if text and text.lower() != "none":
            return text
    return ""


def _coerce_ignored_names(value: Any) -> set[str]:
    if value is None:
        return set()
    raw_items: list[Any]
    if isinstance(value, str):
        raw_items = [item for chunk in value.split(";") for item in chunk.split(",")]
    elif isinstance(value, Iterable):
        raw_items = list(value)
    else:
        raw_items = [value]
    result: set[str] = set()
    for raw_item in raw_items:
        text = str(raw_item or "").strip().replace("\\", "/").strip("/")
        if not text:
            continue
        result.add(PurePosixPath(text).name.lower())
    return result
