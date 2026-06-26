"""
Tests for /api/v1/users endpoints.

Covers:
- GET /me
- PATCH /me (display_name, password change)
- GET / (list) — admin/superuser only
- POST / (create) — no self-registration, role restrictions
- GET /{id}
- PATCH /{id} — permission matrix
- DELETE /{id} — superuser only
- Suspension rules (superuser cannot be suspended)
"""

import pytest
from fastapi.testclient import TestClient

from app.models.user import User

BASE = "/api/v1/users"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# /me
# ---------------------------------------------------------------------------

class TestGetMe:
    def test_get_own_profile(
        self, client: TestClient, normal_user: User, user_token: str
    ) -> None:
        resp = client.get(f"{BASE}/me", headers=auth(user_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "user@example.com"
        assert body["username"] == "normaluser"
        assert "hashed_password" not in body

    def test_unauthenticated_rejected(self, client: TestClient) -> None:
        resp = client.get(f"{BASE}/me")
        # FastAPI's HTTPBearer returns 403 when the Authorization header is
        # absent (auto_error=True). Versions >= 0.110 return 403; verify the
        # response is a 4xx auth failure regardless of the exact code.
        assert resp.status_code in (401, 403)


class TestSelfUpdate:
    def test_update_display_name(
        self, client: TestClient, normal_user: User, user_token: str
    ) -> None:
        resp = client.patch(
            f"{BASE}/me",
            json={"display_name": "New Name"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "New Name"

    def test_change_password_success(
        self, client: TestClient, normal_user: User, user_token: str
    ) -> None:
        resp = client.patch(
            f"{BASE}/me",
            json={
                "current_password": "Us3r-C0rrect-Horse!!",
                "new_password": "N3w-C0rrect-Horse-9999!",
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 200

        # Verify login works with new password
        login = client.post(
            "/api/v1/auth/login",
            json={"identifier": "normaluser", "password": "N3w-C0rrect-Horse-9999!"},
        )
        assert login.status_code == 200

    def test_change_password_wrong_current(
        self, client: TestClient, normal_user: User, user_token: str
    ) -> None:
        resp = client.patch(
            f"{BASE}/me",
            json={
                "current_password": "WrongCurrent!",
                "new_password": "N3w-C0rrect-Horse-9999!",
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 401

    def test_new_password_without_current_rejected(
        self, client: TestClient, normal_user: User, user_token: str
    ) -> None:
        resp = client.patch(
            f"{BASE}/me",
            json={"new_password": "N3w-C0rrect-Horse-9999!"},
            headers=auth(user_token),
        )
        # Pydantic model validator catches this
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# List users
# ---------------------------------------------------------------------------

class TestListUsers:
    def test_admin_can_list(
        self, client: TestClient, normal_user: User, admin_token: str
    ) -> None:
        resp = client.get(f"{BASE}/", headers=auth(admin_token))
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_normal_user_cannot_list(
        self, client: TestClient, user_token: str
    ) -> None:
        resp = client.get(f"{BASE}/", headers=auth(user_token))
        assert resp.status_code == 403

    def test_superuser_can_list(
        self, client: TestClient, normal_user: User, superuser_token: str
    ) -> None:
        resp = client.get(f"{BASE}/", headers=auth(superuser_token))
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Create user
# ---------------------------------------------------------------------------

class TestCreateUser:
    def _new_user_payload(self, suffix: str = "a") -> dict:
        return {
            "email": f"newuser{suffix}@example.com",
            "username": f"newuser{suffix}",
            "display_name": f"New User {suffix}",
            "password": "V4lid-C0rrect-Horse!",
            "role": "user",
        }

    def test_admin_creates_user(
        self, client: TestClient, admin_user: User, admin_token: str
    ) -> None:
        resp = client.post(
            f"{BASE}/",
            json=self._new_user_payload("b"),
            headers=auth(admin_token),
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "user"

    def test_admin_cannot_create_admin(
        self, client: TestClient, admin_user: User, admin_token: str
    ) -> None:
        payload = self._new_user_payload("c")
        payload["role"] = "admin"
        resp = client.post(f"{BASE}/", json=payload, headers=auth(admin_token))
        assert resp.status_code == 403

    def test_superuser_creates_admin(
        self, client: TestClient, superuser: User, superuser_token: str
    ) -> None:
        payload = self._new_user_payload("d")
        payload["role"] = "admin"
        resp = client.post(f"{BASE}/", json=payload, headers=auth(superuser_token))
        assert resp.status_code == 201
        assert resp.json()["role"] == "admin"

    def test_normal_user_cannot_create(
        self, client: TestClient, user_token: str
    ) -> None:
        resp = client.post(
            f"{BASE}/",
            json=self._new_user_payload("e"),
            headers=auth(user_token),
        )
        assert resp.status_code == 403

    def test_duplicate_email_rejected(
        self, client: TestClient, normal_user: User, admin_token: str
    ) -> None:
        payload = self._new_user_payload("f")
        payload["email"] = "user@example.com"  # already exists
        resp = client.post(f"{BASE}/", json=payload, headers=auth(admin_token))
        assert resp.status_code == 409

    def test_no_self_registration(self, client: TestClient) -> None:
        resp = client.post(
            f"{BASE}/",
            json=self._new_user_payload("g"),
        )
        # No auth header → HTTPBearer rejects before route logic fires.
        assert resp.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Get user by ID
# ---------------------------------------------------------------------------

class TestGetUser:
    def test_admin_can_get_any_user(
        self,
        client: TestClient,
        normal_user: User,
        admin_token: str,
    ) -> None:
        resp = client.get(f"{BASE}/{normal_user.id}", headers=auth(admin_token))
        assert resp.status_code == 200
        assert resp.json()["id"] == normal_user.id

    def test_normal_user_can_get_self(
        self, client: TestClient, normal_user: User, user_token: str
    ) -> None:
        resp = client.get(f"{BASE}/{normal_user.id}", headers=auth(user_token))
        assert resp.status_code == 200

    def test_normal_user_cannot_get_other(
        self,
        client: TestClient,
        normal_user: User,
        admin_user: User,
        user_token: str,
    ) -> None:
        resp = client.get(f"{BASE}/{admin_user.id}", headers=auth(user_token))
        assert resp.status_code == 403

    def test_not_found(self, client: TestClient, superuser_token: str) -> None:
        resp = client.get(
            f"{BASE}/00000000-0000-0000-0000-000000000000",
            headers=auth(superuser_token),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update user (admin/superuser)
# ---------------------------------------------------------------------------

class TestUpdateUser:
    def test_admin_updates_display_name(
        self,
        client: TestClient,
        normal_user: User,
        admin_token: str,
    ) -> None:
        resp = client.patch(
            f"{BASE}/{normal_user.id}",
            json={"display_name": "Updated By Admin"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["display_name"] == "Updated By Admin"

    def test_admin_suspends_normal_user(
        self,
        client: TestClient,
        normal_user: User,
        admin_token: str,
    ) -> None:
        resp = client.patch(
            f"{BASE}/{normal_user.id}",
            json={"is_active": False},
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    def test_admin_cannot_suspend_another_admin(
        self,
        client: TestClient,
        admin_user: User,
        superuser: User,
        admin_token: str,
        superuser_token: str,
    ) -> None:
        # Create a second admin via superuser
        create = client.post(
            f"{BASE}/",
            json={
                "email": "admin2@example.com",
                "username": "admin2",
                "display_name": "Admin 2",
                "password": "Adm1n-C0rrect-Horse!",
                "role": "admin",
            },
            headers=auth(superuser_token),
        )
        assert create.status_code == 201
        admin2_id = create.json()["id"]

        resp = client.patch(
            f"{BASE}/{admin2_id}",
            json={"is_active": False},
            headers=auth(admin_token),
        )
        assert resp.status_code == 403

    def test_admin_cannot_change_role(
        self,
        client: TestClient,
        normal_user: User,
        admin_token: str,
    ) -> None:
        resp = client.patch(
            f"{BASE}/{normal_user.id}",
            json={"role": "admin"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 403

    def test_superuser_changes_role(
        self,
        client: TestClient,
        normal_user: User,
        superuser_token: str,
    ) -> None:
        resp = client.patch(
            f"{BASE}/{normal_user.id}",
            json={"role": "admin"},
            headers=auth(superuser_token),
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    def test_superuser_cannot_be_suspended(
        self,
        client: TestClient,
        superuser: User,
        superuser_token: str,
    ) -> None:
        resp = client.patch(
            f"{BASE}/{superuser.id}",
            json={"is_active": False},
            headers=auth(superuser_token),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Delete user
# ---------------------------------------------------------------------------

class TestDeleteUser:
    def test_superuser_deletes_user(
        self,
        client: TestClient,
        normal_user: User,
        superuser_token: str,
    ) -> None:
        resp = client.delete(
            f"{BASE}/{normal_user.id}", headers=auth(superuser_token)
        )
        assert resp.status_code == 204

    def test_admin_cannot_delete(
        self,
        client: TestClient,
        normal_user: User,
        admin_token: str,
    ) -> None:
        resp = client.delete(
            f"{BASE}/{normal_user.id}", headers=auth(admin_token)
        )
        assert resp.status_code == 403

    def test_superuser_cannot_delete_self(
        self,
        client: TestClient,
        superuser: User,
        superuser_token: str,
    ) -> None:
        resp = client.delete(
            f"{BASE}/{superuser.id}", headers=auth(superuser_token)
        )
        assert resp.status_code == 403


# =========================================================================
# Password policy
# =========================================================================

class TestPasswordPolicy:
    """
    Password strength is enforced on account creation and password change.
    Rules: min 12 chars, max 128 chars, zxcvbn score >= 3.
    """

    def _create_payload(self, password: str, suffix: str = "pw") -> dict:
        return {
            "email": f"pwtest{suffix}@example.com",
            "username": f"pwtest{suffix}",
            "display_name": "PW Test",
            "password": password,
            "role": "user",
        }

    def test_strong_password_accepted(
        self, client: TestClient, admin_user: User, admin_token: str
    ) -> None:
        resp = client.post(
            f"{BASE}/",
            json=self._create_payload("Tr0ub4dor&3-correct-horse", suffix="a"),
            headers=auth(admin_token),
        )
        assert resp.status_code == 201

    def test_too_short_rejected(
        self, client: TestClient, admin_user: User, admin_token: str
    ) -> None:
        """Fewer than 12 characters — rejected by length gate."""
        resp = client.post(
            f"{BASE}/",
            json=self._create_payload("Short1!", suffix="b"),
            headers=auth(admin_token),
        )
        assert resp.status_code == 422
        assert "12" in str(resp.json())  # Pydantic error detail is a list

    def test_weak_but_long_rejected(
        self, client: TestClient, admin_user: User, admin_token: str
    ) -> None:
        """Long enough but trivially weak — rejected by zxcvbn."""
        resp = client.post(
            f"{BASE}/",
            json=self._create_payload("password123456", suffix="c"),
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    def test_too_long_rejected(
        self, client: TestClient, admin_user: User, admin_token: str
    ) -> None:
        """Exceeds 128 characters — schema validator rejects before service."""
        resp = client.post(
            f"{BASE}/",
            json=self._create_payload("A1!" + "x" * 130, suffix="d"),
            headers=auth(admin_token),
        )
        assert resp.status_code == 422

    def test_self_update_weak_password_rejected(
        self, client: TestClient, normal_user: User, user_token: str
    ) -> None:
        resp = client.patch(
            f"{BASE}/me",
            json={
                "current_password": "Us3r-C0rrect-Horse!!",
                "new_password": "password123456",
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 422

    def test_self_update_strong_password_accepted(
        self, client: TestClient, normal_user: User, user_token: str
    ) -> None:
        resp = client.patch(
            f"{BASE}/me",
            json={
                "current_password": "Us3r-C0rrect-Horse!!",
                "new_password": "Tr0ub4dor&3-correct-horse",
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 200
