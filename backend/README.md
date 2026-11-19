# Jeweler AI Accountant: Backend (POC)

FastAPI + SQLAlchemy (SQLite) + CrewAI (Gemini free tier). The full design is in [backend_plan.md](backend_plan.md).

## Run

```powershell
cd backend
uv venv --python 3.12        # first time only
.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt   # first time only
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: http://127.0.0.1:8000/docs
- Logins: `owner` / `owner` (Owner) and `admin` / `admin` (Admin)
- The shop starts **blank**. Use the app's *Settings → Load demo data* (or `POST /api/v1/admin/demo-data`) for a 12-month demo shop.

## Test

```powershell
.venv\Scripts\python.exe -m pytest -q
```

Tests run with `LLM_MOCK_MODE=true` (no Gemini calls).

## AI

- Check Gemini access: `.venv\Scripts\python.exe -m app.ai.smoke_test` (add `--fallback` to test only the light model).
- Main model `LLM_MODEL` (Gemini 3.6 Flash, about 20 requests/day free). It falls back to `LLM_FALLBACK_MODEL` (3.1 Flash Lite, about 500/day) on quota (429) or overload (503) errors, and then to rule-based output, so the app never breaks.
- One insights run makes about 8–14 LLM requests and takes about 1–3 minutes at `LLM_MAX_RPM=4`.
- `LLM_MOCK_MODE=true` switches every AI step to the rule-based version (no network).
- Crews live in `app/ai/crews/<crew>/config/{agents,tasks}.yaml` + `skills/*.md` + `crew.py`. The flow is in `app/ai/flows/insights_flow.py`.

## Reset / troubleshooting

- Schema changed? Stop the server and delete `data/jeweler.db*` (it is recreated on start).
- Wipe inventory but keep users: Owner → *Settings → Reset all data* (`POST /api/v1/admin/reset {"confirm":"RESET"}`).
- Model IDs: if Google renames a model, update `LLM_MODEL` / `LLM_FALLBACK_MODEL` in `.env` (see AI Studio → Rate limit).
- Differences from the plan: AI outputs live in one module `app/ai/outputs.py` and tools in `app/ai/tools.py` (not packages). Purchase-plan edits notify the UI without bumping `data_version`, so an AI report is not marked stale by its own plan.
