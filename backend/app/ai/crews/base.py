"""Shared helpers for all @CrewBase crews: LLM injection, skill files, progress callbacks."""
from __future__ import annotations

import inspect
import logging
from pathlib import Path
from typing import Callable

from crewai import Agent, Crew, Process

from app.core.config import get_settings

log = logging.getLogger("app.ai.crews")
SHARED_SKILLS = Path(__file__).parent / "_shared_skills"


def load_skills(crew_dir: Path, names: list[str]) -> str:
    parts = []
    for name in names:
        p = crew_dir / "skills" / name
        if p.exists():
            parts.append(p.read_text(encoding="utf-8").strip())
        else:
            log.warning("Skill file missing: %s", p)
    shared = SHARED_SKILLS / "output_rules.md"
    if shared.exists():
        parts.append(shared.read_text(encoding="utf-8").strip())
    text = "\n\n".join(parts)
    # CrewAI interpolates {placeholders}; skills must never contain braces.
    return text.replace("{", "(").replace("}", ")")


class CrewHelpers:
    def __init__(self, llm, step_callback: Callable | None = None, task_callback: Callable[[str], None] | None = None):
        self.llm = llm
        self._step_callback = step_callback
        self._task_callback = task_callback

    @property
    def crew_dir(self) -> Path:
        return Path(inspect.getfile(type(self))).parent

    def make_agent(self, name: str, skills: list[str], tools: list, max_iter: int | None = None) -> Agent:
        s = get_settings()
        cfg = dict(self.agents_config[name])  # type: ignore[attr-defined]
        skill_text = load_skills(self.crew_dir, skills)
        if skill_text:
            cfg["backstory"] = f"{cfg.get('backstory', '').strip()}\n\n{skill_text}"
        return Agent(config=cfg, tools=tools, llm=self.llm, max_iter=max_iter or s.AGENT_MAX_ITER,
                     allow_delegation=False, verbose=False, max_rpm=s.LLM_MAX_RPM)

    def make_crew(self, agents, tasks) -> Crew:
        s = get_settings()
        kw = {}
        if self._step_callback:
            kw["step_callback"] = self._step_callback
        return Crew(agents=agents, tasks=tasks, process=Process.sequential, verbose=False, max_rpm=s.LLM_MAX_RPM,
                    **kw)

    def task_done(self, key: str):
        def _cb(_output):
            if self._task_callback:
                try:
                    self._task_callback(key)
                except Exception:  # pragma: no cover
                    log.exception("task callback failed")
        return _cb
