from __future__ import annotations

from pathlib import Path

from src.registry.skills import SkillRegistry


class SkillRuntimeService:
    def __init__(self, skill_registry: SkillRegistry) -> None:
        self._skill_registry = skill_registry
        self._skills_root = Path(__file__).resolve().parents[2] / "SKILLS"

    def build_prompt_blocks(self, skill_keys: list[str]) -> list[str]:
        blocks: list[str] = []
        for skill in self._skill_registry.get_many(skill_keys):
            skill_file = self._skills_root / skill.key / "SKILL.md"
            if skill_file.exists():
                content = skill_file.read_text(encoding="utf-8")
                blocks.append(
                    f"## Skill: {skill.name}\n"
                    f"Source: {skill_file}\n"
                    f"{content.strip()}"
                )
                continue
            blocks.append(
                f"- {skill.name}: {skill.description} "
                f"(focus tags: {', '.join(skill.tags) or 'general'})"
            )
        return blocks
