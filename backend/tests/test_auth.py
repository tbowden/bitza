"""
Tests for POST /api/v1/auth/{login,refresh,logout}

Covers:
- Login by email
- Login by username
- Wrong password → 401
- Suspended user → 403
- Refresh token rotation
- Refresh with revoked token → 401
- Refresh with access token (type mismatch) → 401
- Logout → 204
- Logout idempotency
"""

import pytest
from fastapi.testclient import TestClient

from app.models.user import User

BASE = "/api/v1/auth"


class TestLogin:
    def test_login_by_username(self, client: TestClient, normal_user: User) -> None:
        resp = client.post(
            f"{BASE}/login",
            json={"identifier": "normaluser", "password": "Us3r-C0rrect-Horse!!"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "access_token" in body
        assert "refresh_token" in body
        assert body["token_type"] == "bearer"

    def test_login_by_email(self, client: TestClient, normal_user: User) -> None:
        resp = client.post(
            f"{BASE}/login",
            json={"identifier": "user@example.com", "password": "Us3r-C0rrect-Horse!!"},
        )
        assert resp.status_code == 200

    def test_login_wrong_password(self, client: TestClient, normal_user: User) -> None:
        resp = client.post(
            f"{BASE}/login",
            json={"identifier": "normaluser", "password": "WrongPass!"},
        )
        assert resp.status_code == 401
        assert "Invalid credentials" in resp.json()["detail"]

    def test_login_unknown_identifier(self, client: TestClient) -> None:
        resp = client.post(
            f"{BASE}/login",
            json={"identifier": "ghost@nowhere.com", "password": "Any1!pass"},
        )
        assert resp.status_code == 401

    def test_login_suspended_user(
        self, client: TestClient, suspended_user: User
    ) -> None:
        resp = client.post(
            f"{BASE}/login",
            json={"identifier": "suspendeduser", "password": "Us3r-C0rrect-Horse!!"},
        )
        assert resp.status_code == 403
        assert "suspended" in resp.json()["detail"].lower()


class TestRefresh:
    def test_refresh_returns_new_token_pair(
        self, client: TestClient, normal_user: User
    ) -> None:
        login = client.post(
            f"{BASE}/login",
            json={"identifier": "normaluser", "password": "Us3r-C0rrect-Horse!!"},
        )
        original_refresh = login.json()["refresh_token"]
        original_access = login.json()["access_token"]

        resp = client.post(
            f"{BASE}/refresh", json={"refresh_token": original_refresh}
        )
        assert resp.status_code == 200
        body = resp.json()
        # New tokens must be different from the originals
        assert body["refresh_token"] != original_refresh
        assert body["access_token"] != original_access

    def test_refresh_old_token_is_revoked(
        self, client: TestClient, normal_user: User
    ) -> None:
        """After rotation the original refresh token must be rejected."""
        login = client.post(
            f"{BASE}/login",
            json={"identifier": "normaluser", "password": "Us3r-C0rrect-Horse!!"},
        )
        original_refresh = login.json()["refresh_token"]

        # First refresh — OK
        client.post(f"{BASE}/refresh", json={"refresh_token": original_refresh})

        # Replay the same token — must be rejected
        resp = client.post(
            f"{BASE}/refresh", json={"refresh_token": original_refresh}
        )
        assert resp.status_code == 401

    def test_refresh_with_access_token_rejected(
        self, client: TestClient, normal_user: User
    ) -> None:
        """Access tokens must not be accepted at the refresh endpoint."""
        login = client.post(
            f"{BASE}/login",
            json={"identifier": "normaluser", "password": "Us3r-C0rrect-Horse!!"},
        )
        access_token = login.json()["access_token"]

        resp = client.post(
            f"{BASE}/refresh", json={"refresh_token": access_token}
        )
        assert resp.status_code == 401
        assert "mismatch" in resp.json()["detail"].lower()

    def test_refresh_with_garbage_token(self, client: TestClient) -> None:
        resp = client.post(
            f"{BASE}/refresh", json={"refresh_token": "notavalidtoken"}
        )
        assert resp.status_code == 401


class TestLogout:
    def test_logout_revokes_token(
        self, client: TestClient, normal_user: User
    ) -> None:
        login = client.post(
            f"{BASE}/login",
            json={"identifier": "normaluser", "password": "Us3r-C0rrect-Horse!!"},
        )
        refresh_token = login.json()["refresh_token"]

        # Logout should succeed
        resp = client.post(f"{BASE}/logout", json={"refresh_token": refresh_token})
        assert resp.status_code == 204

        # Refreshing after logout must fail
        resp2 = client.post(
            f"{BASE}/refresh", json={"refresh_token": refresh_token}
        )
        assert resp2.status_code == 401

    def test_logout_idempotent(
        self, client: TestClient, normal_user: User
    ) -> None:
        """Logging out a second time with the same token should not raise."""
        login = client.post(
            f"{BASE}/login",
            json={"identifier": "normaluser", "password": "Us3r-C0rrect-Horse!!"},
        )
        refresh_token = login.json()["refresh_token"]

        client.post(f"{BASE}/logout", json={"refresh_token": refresh_token})
        resp = client.post(f"{BASE}/logout", json={"refresh_token": refresh_token})
        assert resp.status_code == 204

    def test_logout_with_access_token_rejected(
        self, client: TestClient, normal_user: User
    ) -> None:
        login = client.post(
            f"{BASE}/login",
            json={"identifier": "normaluser", "password": "Us3r-C0rrect-Horse!!"},
        )
        access_token = login.json()["access_token"]

        resp = client.post(f"{BASE}/logout", json={"refresh_token": access_token})
        assert resp.status_code == 401
