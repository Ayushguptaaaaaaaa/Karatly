"""run_crew_step: one AI step with primary → fallback model → rule-based fallback. Never raises."""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.llm import model_manager
from app.ai.tools import FRIENDLY
from app.services import job_service

log = logging.getLogger("app.ai.runner")
M = TypeVar("M", bound=BaseModel)


def extract_json(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.MULTILINE).strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end > start:
        return t[start:end + 1]
    return t


def _parse(result, task_outputs_wanted: list[type[BaseModel]] | None, output_model: type[M]):
    """Returns the final task's model (and a list of all task models when several are wanted)."""
    def one(task_out, model):
        if task_out is None:
            raise ValueError("No task output")
        p = getattr(task_out, "pydantic", None)
        if isinstance(p, model):
            return p
        if p is not None:
            return model.model_validate(p.model_dump())
        raw = getattr(task_out, "raw", "") or ""
        return model.model_validate_json(extract_json(raw))

    if task_outputs_wanted:
        outs = list(getattr(result, "tasks_output", []) or [])
        if len(outs) < len(task_outputs_wanted):
            raise ValueError("Missing task outputs")
        return [one(o, m) for o, m in zip(outs, task_outputs_wanted)]
    return one(result, output_model)


def step_callback_for(job_id: str | None) -> Callable | None:
    if not job_id:
        return None

    def _cb(step):
        try:
            tool = getattr(step, "tool", None)
            if tool:
                job_service.tool_event(job_id, FRIENDLY.get(str(tool), "Looking up data…"))
        except Exception:  # pragma: no cover
            pass
    return _cb


def run_crew_step(
    *,
    job_id: str | None,
    step_keys: list[str],
    build_crew: Callable,  # (llm, step_callback, task_callback) -> crew object with .crew()
    inputs: dict,
    output_models: list[type[BaseModel]],
    fallback: Callable[[], list[BaseModel]],
    task_callback: Callable[[str], None] | None = None,
) -> tuple[list[BaseModel], str]:
    """Run a crew whose tasks produce `output_models` (in order). Returns (outputs, model_used)."""
    for k in step_keys[:1]:
        if job_id:
            job_service.update_step(job_id, k, "RUNNING")

    def finish(outputs, model_used, note=None):
        if job_id:
            for k in step_keys:
                job_service.update_step(job_id, k, "DONE", model_used=model_used, note=note)
        return outputs, model_used

    for kind in model_manager.usable_kinds():
        if not model_manager.available(kind):
            continue
        model_name = model_manager.model_name(kind)
        for attempt in range(2):
            t0 = time.time()
            try:
                crew_obj = build_crew(model_manager.get_llm(kind), step_callback_for(job_id), task_callback)
                result = crew_obj.crew().kickoff(inputs=inputs)
                parsed = _parse(result, output_models if len(output_models) > 1 else None, output_models[-1])
                outputs = parsed if isinstance(parsed, list) else [parsed]
                log.info("AI step %s ok with %s in %.1fs", step_keys, model_name, time.time() - t0)
                return finish(outputs, model_name)
            except (ValidationError, ValueError, json.JSONDecodeError) as e:
                log.warning("AI step %s parse problem (%s attempt %d): %s", step_keys, model_name, attempt + 1, e)
                if attempt == 0:
                    continue
                break
            except Exception as e:  # noqa: BLE001
                cls = model_manager.report_failure(kind, e)
                if cls in ("quota", "quota_daily", "overload", "auth") or attempt == 1:
                    break
    outputs = fallback()
    return finish(outputs, "rule-based", "Automatic (AI unavailable)")
