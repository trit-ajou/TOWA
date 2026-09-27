from __future__ import annotations

from fastapi.testclient import TestClient

# conftest sets SERVICE_ENGINE_INVITE_CODES to this for every test.
TEST_INVITE_CODE = "test-invite"
TEST_PASSWORD = "test-password"


def login_as(client: TestClient, email: str = "user@example.com", nickname: str | None = None) -> dict[str, object]:
    """Get a session for `email`, creating the account on first use.

    Replaces the retired /auth/dev/login fixture, which had the same
    create-or-reuse semantics: sign up, and if the email already exists log in.
    """
    body: dict[str, object] = {"email": email, "password": TEST_PASSWORD, "invite_code": TEST_INVITE_CODE}
    if nickname is not None:
        body["nickname"] = nickname
    response = client.post("/auth/signup", json=body)
    if response.status_code == 409:
        response = client.post("/auth/login", json={"email": email, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()
