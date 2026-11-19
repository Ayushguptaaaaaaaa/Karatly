def test_login_roles(client):
    r = client.post("/api/v1/auth/login", json={"username": "owner", "password": "owner", "role": "OWNER"})
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "OWNER"
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin", "role": "ADMIN"})
    assert r.status_code == 200


def test_wrong_password_and_role_mismatch(client):
    r = client.post("/api/v1/auth/login", json={"username": "owner", "password": "nope", "role": "OWNER"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "INVALID_CREDENTIALS"
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin", "role": "OWNER"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "ROLE_MISMATCH"


def test_protected_requires_token(client):
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/categories").status_code == 401
