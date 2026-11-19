import time

from app.ai import instant_answers


def _wait(api, sid, timeout=20):
    for _ in range(timeout * 10):
        last = api.get(f"/chat/sessions/{sid}").json()["messages"][-1]
        if last["status"] != "PENDING":
            return last
        time.sleep(0.1)
    raise AssertionError("chat did not answer")


def test_instant_answers_while_ai_lock_is_held(api):
    """Chat must not wait for the insights report (which holds the AI lock)."""
    from app.ai.llm import AI_LOCK

    api.post("/admin/demo-data", {})
    sid = api.post("/chat/sessions", {}).json()["id"]
    assert AI_LOCK.acquire(timeout=5)  # simulate an insights report in progress
    try:
        t0 = time.time()
        api.post(f"/chat/sessions/{sid}/messages", {"text": "What was my net profit this month, by category?"})
        last = _wait(api, sid)
        assert time.time() - t0 < 5
    finally:
        AI_LOCK.release()
    assert last["status"] == "COMPLETE" and last["payload"]["model_used"] == "instant"
    assert "net profit" in last["content"].lower() and last["payload"]["table"]["columns"][0] == "Category"


def test_intent_routing(api):
    from app.core.database import SessionLocal
    from app.services.chat_service import shop_snapshot

    api.post("/admin/demo-data", {})
    with SessionLocal() as db:
        snap = shop_snapshot(db)
    assert instant_answers.answer("What should I restock this month and how much money do I need?", snap).table
    assert instant_answers.answer("Which designs are sold out?", snap).table
    assert "Today" in instant_answers.answer("aaj ka profit kitna hua?", snap).answer_markdown
    assert instant_answers.answer("Show net profit by subcategory", snap).table.columns[0] == "Subcategory"
    # reasoning questions and specific labels go to the AI
    assert instant_answers.answer("Why are bangles selling less than necklaces?", snap) is None
    assert instant_answers.answer("How is ER-1005 doing?", snap) is None
    # non-strict fallback always answers
    assert instant_answers.answer("Tell me a joke", snap, strict=False) is not None
