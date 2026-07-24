from fastapi.testclient import TestClient

from tradingos.api.main import app

client = TestClient(app)


def test_register_returns_access_token():
    response = client.post("/auth/register", json={"email": "a@example.com", "password": "hunter22"})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_register_rejects_duplicate_email():
    client.post("/auth/register", json={"email": "dup@example.com", "password": "hunter22"})
    response = client.post("/auth/register", json={"email": "dup@example.com", "password": "otherpass1"})
    assert response.status_code == 409


def test_register_rejects_short_password():
    response = client.post("/auth/register", json={"email": "b@example.com", "password": "short"})
    assert response.status_code == 400


def test_login_succeeds_with_correct_credentials():
    client.post("/auth/register", json={"email": "c@example.com", "password": "hunter22"})
    response = client.post("/auth/login", json={"email": "c@example.com", "password": "hunter22"})
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_login_rejects_wrong_password():
    client.post("/auth/register", json={"email": "d@example.com", "password": "hunter22"})
    response = client.post("/auth/login", json={"email": "d@example.com", "password": "wrongpass"})
    assert response.status_code == 401


def test_login_rejects_unknown_email():
    response = client.post("/auth/login", json={"email": "noexiste@example.com", "password": "hunter22"})
    assert response.status_code == 401


def test_me_requires_token():
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_me_returns_current_user_with_valid_token():
    register = client.post("/auth/register", json={"email": "e@example.com", "password": "hunter22"})
    token = register.json()["access_token"]

    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "e@example.com"


def test_me_rejects_garbage_token():
    response = client.get("/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert response.status_code == 401
