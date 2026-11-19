"""python -m app.ai.smoke_test [--fallback] : checks CrewAI + Gemini with one tiny task."""
from __future__ import annotations

import sys
import time

from pydantic import BaseModel

from app.core.config import export_ai_env, get_settings


class Out(BaseModel):
    ok: bool
    model: str


def run(kind: str) -> bool:
    from crewai import Agent, Crew, Task

    from app.ai.llm import classify, model_manager

    name = model_manager.model_name(kind)
    agent = Agent(role="Tester", goal="Answer test prompts", backstory="You are a test assistant.",
                  llm=model_manager.get_llm(kind), max_iter=2, verbose=False)
    task = Task(description=f'Return JSON with ok=true and model="{name}".', expected_output="JSON",
                agent=agent, output_pydantic=Out)
    t0 = time.time()
    try:
        res = Crew(agents=[agent], tasks=[task], verbose=False).kickoff()
        print(f"[OK] {name}: {res.pydantic or res.raw} ({time.time() - t0:.1f}s)")
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[FAIL] {name}: {classify(e)}: {str(e)[:300]}")
        return False


if __name__ == "__main__":
    export_ai_env(get_settings())
    kinds = ["fallback"] if "--fallback" in sys.argv else ["primary", "fallback"]
    for k in kinds:
        if run(k):
            break
