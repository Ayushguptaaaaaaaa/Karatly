from __future__ import annotations

import os

os.environ["LLM_MOCK_MODE"] = "true"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import config as config_module  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    config_module.get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("PHOTO_DIR", str(tmp_path / "photos"))
    monkeypatch.setenv("LLM_MOCK_MODE", "true")
    config_module.get_settings.cache_clear()

    from app.core import database

    database.init_engine(config_module.get_settings().database_url)
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c
    database.get_engine().dispose()
    config_module.get_settings.cache_clear()


def _login(client, username, role):
    r = client.post("/api/v1/auth/login", json={"username": username, "password": username, "role": role})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def owner(client):
    return _login(client, "owner", "OWNER")


@pytest.fixture()
def admin(client):
    return _login(client, "admin", "ADMIN")


class Api:
    def __init__(self, client, headers):
        self.c, self.h = client, headers

    def get(self, url, **kw):
        return self.c.get("/api/v1" + url, headers=self.h, **kw)

    def post(self, url, json=None, **kw):
        return self.c.post("/api/v1" + url, json=json, headers=self.h, **kw)

    def patch(self, url, json=None):
        return self.c.patch("/api/v1" + url, json=json, headers=self.h)

    def delete(self, url):
        return self.c.delete("/api/v1" + url, headers=self.h)

    # factories
    def category(self, name="Earrings", **kw):
        r = self.post("/categories", {"name": name, "icon": kw.pop("icon", "earring"), **kw})
        assert r.status_code == 201, r.text
        return r.json()

    def designs(self, category_id, rows, **kw):
        r = self.post("/designs/bulk", {"category_id": category_id, "designs": rows, **kw})
        assert r.status_code == 201, r.text
        return r.json()["created"]

    def move(self, design_id, mtype, qty, **kw):
        return self.post("/stock/movements", {"design_id": design_id, "type": mtype, "quantity": qty, **kw})


@pytest.fixture()
def api(client, owner):
    return Api(client, owner)


@pytest.fixture()
def admin_api(client, admin):
    return Api(client, admin)
