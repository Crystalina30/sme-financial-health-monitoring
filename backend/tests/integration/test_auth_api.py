"""Integration tests for authentication and route protection."""


def test_registration_succeeds(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "full_name": "New User", "password": "a-good-password"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "new@example.com"


def test_password_is_never_returned(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "full_name": "New User", "password": "a-good-password"},
    )
    body = response.json()
    assert "password" not in body
    assert "hashed_password" not in body


def test_password_is_not_stored_in_plaintext(client, db_session):
    from app.models.user import User

    client.post(
        "/api/auth/register",
        json={"email": "new@example.com", "full_name": "New User", "password": "a-good-password"},
    )
    user = db_session.query(User).filter(User.email == "new@example.com").one()
    assert user.hashed_password != "a-good-password"
    assert user.hashed_password.startswith("$2")


def test_duplicate_registration_is_rejected(client):
    payload = {"email": "dup@example.com", "full_name": "Dup", "password": "a-good-password"}
    client.post("/api/auth/register", json=payload)
    assert client.post("/api/auth/register", json=payload).status_code == 409


def test_short_password_is_rejected(client):
    response = client.post(
        "/api/auth/register",
        json={"email": "short@example.com", "full_name": "Short", "password": "abc"},
    )
    assert response.status_code == 422


def test_login_returns_a_token(client):
    client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "full_name": "L", "password": "a-good-password"},
    )
    response = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "a-good-password"}
    )
    assert response.status_code == 200
    assert response.json()["access_token"]


def test_wrong_password_is_rejected(client):
    client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "full_name": "L", "password": "a-good-password"},
    )
    response = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "wrong-password"}
    )
    assert response.status_code == 401


def test_unknown_email_gives_the_same_message_as_a_wrong_password(client):
    client.post(
        "/api/auth/register",
        json={"email": "login@example.com", "full_name": "L", "password": "a-good-password"},
    )
    wrong_password = client.post(
        "/api/auth/login", json={"email": "login@example.com", "password": "wrong-password"}
    )
    unknown_email = client.post(
        "/api/auth/login", json={"email": "nobody@example.com", "password": "a-good-password"}
    )
    assert wrong_password.json()["detail"] == unknown_email.json()["detail"]


def test_protected_route_requires_a_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_protected_route_rejects_a_malformed_token(client):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_protected_route_accepts_a_valid_token(client, auth_headers):
    response = client.get("/api/auth/me", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_health_endpoint_needs_no_authentication(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["database"] == "connected"
