"""
Tests for /api/v1/projects endpoints.

Covers:
- Project CRUD, open to any authenticated user
- Membership: add/remove/set-primary, including acting on OTHER users
  (deliberate trust model — see bitza_project_context.md)
- Delete blocked while a bitza still references the project
"""

from fastapi.testclient import TestClient

from app.models.project import Project
from app.models.user import User

BASE = "/api/v1/projects"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestProjectCrud:
    def test_any_user_can_create_project(self, client: TestClient, user_token: str) -> None:
        resp = client.post(BASE + "/", json={"name": "Aero"}, headers=auth(user_token))
        assert resp.status_code == 201, resp.text
        assert resp.json()["name"] == "Aero"
        assert resp.json()["member_count"] == 0

    def test_duplicate_name_rejected(self, client: TestClient, user_token: str) -> None:
        client.post(BASE + "/", json={"name": "Suspension"}, headers=auth(user_token))
        resp = client.post(BASE + "/", json={"name": "Suspension"}, headers=auth(user_token))
        assert resp.status_code == 409

    def test_list_projects(self, client: TestClient, user_token: str) -> None:
        client.post(BASE + "/", json={"name": "Battery"}, headers=auth(user_token))
        resp = client.get(BASE + "/", headers=auth(user_token))
        assert resp.status_code == 200
        names = [t["name"] for t in resp.json()]
        assert "Battery" in names

    def test_get_project(self, client: TestClient, user_token: str) -> None:
        created = client.post(
            BASE + "/", json={"name": "Chassis"}, headers=auth(user_token)
        ).json()
        resp = client.get(f"{BASE}/{created['id']}", headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Chassis"

    def test_update_project(self, client: TestClient, user_token: str) -> None:
        created = client.post(
            BASE + "/", json={"name": "Old Name"}, headers=auth(user_token)
        ).json()
        resp = client.patch(
            f"{BASE}/{created['id']}",
            json={"name": "New Name", "description": "Renamed"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_normal_user_can_delete_empty_project(
        self, client: TestClient, user_token: str
    ) -> None:
        """No admin gate on project delete — only structural: unreferenced."""
        created = client.post(
            BASE + "/", json={"name": "To Delete"}, headers=auth(user_token)
        ).json()
        resp = client.delete(f"{BASE}/{created['id']}", headers=auth(user_token))
        assert resp.status_code == 204

    def test_delete_blocked_while_bitza_references_project(
        self, client: TestClient, user_token: str, root_bitza
    ) -> None:
        project = client.post(
            BASE + "/", json={"name": "In Use"}, headers=auth(user_token)
        ).json()
        bitza_resp = client.post(
            "/api/v1/bitzas/",
            json={
                "name": "Workshop Shelf",
                "kind": "fixed",
                "responsible_project_id": project["id"],
                "parent_id": root_bitza.id,
            },
            headers=auth(user_token),
        )
        assert bitza_resp.status_code == 201, bitza_resp.text

        resp = client.delete(f"{BASE}/{project['id']}", headers=auth(user_token))
        assert resp.status_code == 409


class TestProjectMembership:
    def test_add_member(
        self, client: TestClient, user_token: str, normal_user: User
    ) -> None:
        project = client.post(
            BASE + "/", json={"name": "Aero2"}, headers=auth(user_token)
        ).json()
        resp = client.post(
            f"{BASE}/{project['id']}/members",
            json={"user_id": normal_user.id},
            headers=auth(user_token),
        )
        assert resp.status_code == 201
        assert resp.json()["user_id"] == normal_user.id
        assert resp.json()["is_primary"] is False

    def test_duplicate_membership_rejected(
        self, client: TestClient, user_token: str, normal_user: User
    ) -> None:
        project = client.post(
            BASE + "/", json={"name": "Battery2"}, headers=auth(user_token)
        ).json()
        client.post(
            f"{BASE}/{project['id']}/members",
            json={"user_id": normal_user.id},
            headers=auth(user_token),
        )
        resp = client.post(
            f"{BASE}/{project['id']}/members",
            json={"user_id": normal_user.id},
            headers=auth(user_token),
        )
        assert resp.status_code == 409

    def test_user_can_hold_multiple_project_memberships(
        self, client: TestClient, user_token: str, normal_user: User
    ) -> None:
        """The workshop-manager-plus-regular-project case — a user can be on
        more than one project simultaneously."""
        project_a = client.post(
            BASE + "/", json={"name": "Project A"}, headers=auth(user_token)
        ).json()
        project_b = client.post(
            BASE + "/", json={"name": "Project B"}, headers=auth(user_token)
        ).json()
        client.post(
            f"{BASE}/{project_a['id']}/members",
            json={"user_id": normal_user.id},
            headers=auth(user_token),
        )
        client.post(
            f"{BASE}/{project_b['id']}/members",
            json={"user_id": normal_user.id},
            headers=auth(user_token),
        )
        resp = client.get(f"{BASE}/?user_id={normal_user.id}", headers=auth(user_token))
        assert resp.status_code == 200
        names = {t["name"] for t in resp.json()}
        assert names == {"Project A", "Project B"}

    def test_setting_primary_unsets_other_primary(
        self, client: TestClient, user_token: str, normal_user: User
    ) -> None:
        project_a = client.post(
            BASE + "/", json={"name": "Primary A"}, headers=auth(user_token)
        ).json()
        project_b = client.post(
            BASE + "/", json={"name": "Primary B"}, headers=auth(user_token)
        ).json()
        client.post(
            f"{BASE}/{project_a['id']}/members",
            json={"user_id": normal_user.id, "is_primary": True},
            headers=auth(user_token),
        )
        client.post(
            f"{BASE}/{project_b['id']}/members",
            json={"user_id": normal_user.id},
            headers=auth(user_token),
        )

        # Now flip B to primary — A should be unset.
        resp = client.patch(
            f"{BASE}/{project_b['id']}/members/{normal_user.id}",
            json={"is_primary": True},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["is_primary"] is True

        members_a = client.get(
            f"{BASE}/{project_a['id']}/members", headers=auth(user_token)
        ).json()
        assert all(m["is_primary"] is False for m in members_a)

    def test_any_user_can_remove_another_user_from_a_project(
        self,
        client: TestClient,
        user_token: str,
        second_user_token: str,
        normal_user: User,
        second_user: User,
    ) -> None:
        """Deliberate trust model: removing OTHERS is allowed, no
        self-only restriction — see bitza_project_context.md."""
        project = client.post(
            BASE + "/", json={"name": "Trust Project"}, headers=auth(user_token)
        ).json()
        client.post(
            f"{BASE}/{project['id']}/members",
            json={"user_id": normal_user.id},
            headers=auth(user_token),
        )
        # second_user (not an admin, just another normal member) removes
        # normal_user from the project.
        resp = client.delete(
            f"{BASE}/{project['id']}/members/{normal_user.id}",
            headers=auth(second_user_token),
        )
        assert resp.status_code == 204

    def test_remove_nonexistent_membership_404s(
        self, client: TestClient, user_token: str, normal_user: User
    ) -> None:
        project = client.post(
            BASE + "/", json={"name": "Empty Project"}, headers=auth(user_token)
        ).json()
        resp = client.delete(
            f"{BASE}/{project['id']}/members/{normal_user.id}", headers=auth(user_token)
        )
        assert resp.status_code == 404


# =========================================================================
# My project memberships (/me landing page)
# =========================================================================

class TestMyProjectMemberships:
    def test_list_my_memberships_includes_primary_flag(
        self, client: TestClient, user_token: str, normal_user: User
    ) -> None:
        project_a = client.post(
            BASE + "/", json={"name": "Mine A"}, headers=auth(user_token)
        ).json()
        project_b = client.post(
            BASE + "/", json={"name": "Mine B"}, headers=auth(user_token)
        ).json()
        client.post(
            f"{BASE}/{project_a['id']}/members",
            json={"user_id": normal_user.id, "is_primary": True},
            headers=auth(user_token),
        )
        client.post(
            f"{BASE}/{project_b['id']}/members",
            json={"user_id": normal_user.id},
            headers=auth(user_token),
        )

        resp = client.get(f"{BASE}/mine", headers=auth(user_token))
        assert resp.status_code == 200
        by_name = {m["project_name"]: m["is_primary"] for m in resp.json()}
        assert by_name == {"Mine A": True, "Mine B": False}

    def test_list_my_memberships_empty_when_on_no_projects(
        self, client: TestClient, second_user_token: str
    ) -> None:
        resp = client.get(f"{BASE}/mine", headers=auth(second_user_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_my_memberships_does_not_leak_other_users(
        self,
        client: TestClient,
        user_token: str,
        second_user_token: str,
        normal_user: User,
    ) -> None:
        project = client.post(
            BASE + "/", json={"name": "Only Mine"}, headers=auth(user_token)
        ).json()
        client.post(
            f"{BASE}/{project['id']}/members",
            json={"user_id": normal_user.id},
            headers=auth(user_token),
        )
        # second_user was never added — their "mine" view must be empty.
        resp = client.get(f"{BASE}/mine", headers=auth(second_user_token))
        assert resp.status_code == 200
        assert resp.json() == []
