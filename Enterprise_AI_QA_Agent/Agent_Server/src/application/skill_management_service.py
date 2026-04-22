from __future__ import annotations

import re
import shutil
import urllib.request
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from src.registry.skills import SkillRegistry


class SkillManagementService:
    """Manage filesystem skills under Agent_Server/src/SKILLS."""

    def __init__(self, skill_registry: SkillRegistry) -> None:
        self._skill_registry = skill_registry
        self._skills_root = Path(__file__).resolve().parents[1] / "SKILLS"
        self._skills_root.mkdir(parents=True, exist_ok=True)

    def list_skills(self) -> list[dict[str, Any]]:
        self._skill_registry.reload()
        descriptors = {item.key: item for item in self._skill_registry.list()}
        items: list[dict[str, Any]] = []
        for key, descriptor in sorted(descriptors.items()):
            skill_dir = self._skills_root / key
            skill_file = skill_dir / "SKILL.md"
            items.append(
                {
                    **descriptor.model_dump(mode="python"),
                    "installed": skill_file.exists(),
                    "managed_root": str(self._skills_root),
                    "path": str(skill_file) if skill_file.exists() else "",
                    "source": "filesystem" if skill_file.exists() else "builtin-fallback",
                    "references": self._list_references(skill_dir),
                }
            )
        return items

    def get_skill(self, key: str) -> dict[str, Any]:
        safe_key = self._safe_key(key)
        skill_dir = self._skills_root / safe_key
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            descriptor = self._skill_registry.get(safe_key)
            return {
                **descriptor.model_dump(mode="python"),
                "installed": False,
                "managed_root": str(self._skills_root),
                "path": "",
                "content": "",
                "references": [],
            }
        descriptor = self._skill_registry.get(safe_key)
        return {
            **descriptor.model_dump(mode="python"),
            "installed": True,
            "managed_root": str(self._skills_root),
            "path": str(skill_file),
            "content": skill_file.read_text(encoding="utf-8"),
            "references": self._list_references(skill_dir),
        }

    def upsert_skill(self, key: str, content: str) -> dict[str, Any]:
        safe_key = self._safe_key(key)
        if not content.strip():
            raise ValueError("Skill content cannot be empty.")
        if not self._has_skill_frontmatter(content):
            raise ValueError("Skill content must start with SKILL.md frontmatter containing name and description.")
        skill_dir = self._skills_root / safe_key
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(content.rstrip() + "\n", encoding="utf-8")
        self._skill_registry.reload()
        return self.get_skill(safe_key)

    def delete_skill(self, key: str) -> dict[str, Any]:
        safe_key = self._safe_key(key)
        skill_dir = self._skills_root / safe_key
        self._ensure_within_root(skill_dir)
        if not skill_dir.exists():
            return {"ok": True, "message": f"Skill '{safe_key}' is already absent."}
        shutil.rmtree(skill_dir)
        self._skill_registry.reload()
        return {"ok": True, "message": f"Skill '{safe_key}' was deleted from src/SKILLS."}

    def install_from_path(self, source_path: str, key: str | None = None, overwrite: bool = False) -> dict[str, Any]:
        source = Path(source_path).expanduser().resolve()
        if not source.exists():
            raise ValueError(f"Source path does not exist: {source}")
        if source.is_file() and source.name.lower() == "skill.md":
            install_key = self._safe_key(key or source.parent.name)
            return self.upsert_skill(install_key, source.read_text(encoding="utf-8"))
        if source.is_dir():
            skill_file = source / "SKILL.md"
            if not skill_file.exists():
                raise ValueError(f"Source directory must contain SKILL.md: {source}")
            install_key = self._safe_key(key or source.name)
            return self._copy_skill_dir(source, install_key, overwrite)
        if source.is_file() and source.suffix.lower() == ".zip":
            with TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(source) as archive:
                    archive.extractall(temp_dir)
                extracted = self._find_skill_source(Path(temp_dir))
                install_key = self._safe_key(key or extracted.name)
                return self._copy_skill_dir(extracted, install_key, overwrite)
        raise ValueError("Source path must be a skill directory, SKILL.md file, or .zip archive.")

    def install_from_url(self, url: str, key: str | None = None, overwrite: bool = False) -> dict[str, Any]:
        if not url.startswith(("http://", "https://")):
            raise ValueError("Only http:// and https:// URLs are supported.")
        with TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "skill-download"
            with urllib.request.urlopen(url, timeout=30) as response:
                data = response.read()
            if url.lower().endswith(".zip"):
                zip_path = target.with_suffix(".zip")
                zip_path.write_bytes(data)
                with zipfile.ZipFile(zip_path) as archive:
                    archive.extractall(target)
                source = self._find_skill_source(target)
                install_key = self._safe_key(key or source.name)
                return self._copy_skill_dir(source, install_key, overwrite)
            content = data.decode("utf-8")
            install_key = self._safe_key(key or self._name_from_content(content) or "downloaded-skill")
            return self.upsert_skill(install_key, content)

    def _copy_skill_dir(self, source: Path, key: str, overwrite: bool) -> dict[str, Any]:
        target = self._skills_root / key
        self._ensure_within_root(target)
        if target.exists():
            if not overwrite:
                raise ValueError(f"Skill '{key}' already exists. Pass overwrite=true to replace it.")
            shutil.rmtree(target)
        shutil.copytree(source, target)
        if not (target / "SKILL.md").exists():
            raise ValueError("Installed skill is invalid because SKILL.md is missing.")
        self._skill_registry.reload()
        return self.get_skill(key)

    def _find_skill_source(self, root: Path) -> Path:
        candidates = [path.parent for path in root.rglob("SKILL.md")]
        if not candidates:
            raise ValueError("Downloaded archive does not contain SKILL.md.")
        return sorted(candidates, key=lambda item: len(item.parts))[0]

    def _list_references(self, skill_dir: Path) -> list[str]:
        references_dir = skill_dir / "references"
        if not references_dir.exists():
            return []
        return [str(path) for path in sorted(references_dir.rglob("*")) if path.is_file()]

    def _has_skill_frontmatter(self, content: str) -> bool:
        return bool(re.match(r"^---\s*\n(?=.*\bname\s*:)(?=.*\bdescription\s*:).*?\n---", content, re.S))

    def _name_from_content(self, content: str) -> str:
        match = re.search(r"^name\s*:\s*(.+)$", content, re.M)
        return self._safe_key(match.group(1)) if match else ""

    def _safe_key(self, value: str) -> str:
        key = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value).strip()).strip("-").lower()
        if not key:
            raise ValueError("Skill key cannot be empty.")
        return key[:96]

    def _ensure_within_root(self, path: Path) -> None:
        root = self._skills_root.resolve()
        target = path.resolve()
        if root != target and root not in target.parents:
            raise ValueError("Refusing to write outside Agent_Server/src/SKILLS.")
