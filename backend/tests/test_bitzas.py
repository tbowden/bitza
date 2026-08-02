"""
Tests for /api/v1/bitzas endpoints (plus /categories and /audit, which
live in the same router file).

Covers:
- kind-conditional create validation (fixed/mobile/stock)
- parent/child hierarchy, direct-children listing, cycle prevention
- retire/reactivate (open to any user) vs hard delete (admin/superuser only)
- reassign-team with all three cascade scopes
- checkout/checkin state machine
- stock adjustments (exact) and direct fuzzy_state edits
- categories CRUD + delete-blocked-while-in-use
- audit log visibility (admin/superuser only)
"""

from fastapi.testclient import TestClient

from app.models.bitza import Bitza
from app.models.team import Team
from app.models.user import User

BASE = "/api/v1/bitzas"
BASE_TEAM = "/api/v1/teams"
BASE_CAT = "/api/v1/categories"
BASE_AUDIT = "/api/v1/audit"


def _root_id(client, token) -> str:
    """
    Lazily resolve the current test's root bitza id via the ordinary
    root_only=true listing (which, now that only one root can ever
    exist, always returns exactly that one item). Cached as an attribute
    on the client instance itself — not a module-level dict keyed by
    id(client), which caused intermittent "Parent bitza not found"
    failures: once a prior test's client is garbage-collected, Python
    can reuse its memory address for a new client on a fresh database,
    silently returning the previous test's stale root id. An attribute
    on the object doesn't have that failure mode — a reused address
    means a genuinely new object without the attribute set, so the
    cache correctly misses and re-fetches.
    """
    cached = getattr(client, "_root_id_cache", None)
    if cached is None:
        resp = client.get(BASE + "/?root_only=true", headers=auth(token))
        roots = resp.json()
        assert roots, "No root bitza found — the root_bitza fixture should have created one"
        cached = roots[0]["id"]
        client._root_id_cache = cached
    return cached


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def make_fixed(client, token, team_id, name="Workshop", parent_id=None):
    resp = client.post(
        BASE + "/",
        json={
            "name": name,
            "kind": "fixed",
            "responsible_team_id": team_id,
            "parent_id": parent_id or _root_id(client, token),
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_mobile(client, token, team_id, name="Multimeter", parent_id=None):
    resp = client.post(
        BASE + "/",
        json={
            "name": name,
            "kind": "mobile",
            "responsible_team_id": team_id,
            "parent_id": parent_id or _root_id(client, token),
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_exact_stock(client, token, team_id, name="Resistors", qty=50, parent_id=None):
    resp = client.post(
        BASE + "/",
        json={
            "name": name,
            "kind": "stock",
            "responsible_team_id": team_id,
            "parent_id": parent_id or _root_id(client, token),
            "stock_mode": "exact",
            "quantity": qty,
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# =========================================================================
# Create — kind-conditional validation
# =========================================================================

class TestCreateValidation:
    def test_create_fixed(self, client: TestClient, user_token: str, default_team: Team) -> None:
        b = make_fixed(client, user_token, default_team.id)
        assert b["kind"] == "fixed"
        assert b["responsible_team_id"] == default_team.id
        assert b["status"] == "active"

    def test_create_mobile(self, client: TestClient, user_token: str, default_team: Team) -> None:
        b = make_mobile(client, user_token, default_team.id)
        assert b["kind"] == "mobile"
        assert b["is_checked_out"] is False

    def test_create_exact_stock(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        b = make_exact_stock(client, user_token, default_team.id, qty=20)
        assert b["stock_mode"] == "exact"
        assert b["quantity"] == 20

    def test_create_fuzzy_stock(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        resp = client.post(
            BASE + "/",
            json={
                "name": "Heatshrink",
                "kind": "stock",
                "responsible_team_id": default_team.id,
                "parent_id": _root_id(client, user_token),
                "stock_mode": "fuzzy",
                "fuzzy_state": "plentiful",
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["fuzzy_state"] == "plentiful"

    def test_missing_responsible_team_rejected(
        self, client: TestClient, user_token: str
    ) -> None:
        resp = client.post(
            BASE + "/",
            json={"name": "No Team", "kind": "fixed"},
            headers=auth(user_token),
        )
        assert resp.status_code == 422

    def test_stock_without_stock_mode_rejected(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        resp = client.post(
            BASE + "/",
            json={
                "name": "Bad Stock",
                "kind": "stock",
                "responsible_team_id": default_team.id,
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 422

    def test_exact_stock_requires_quantity(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        resp = client.post(
            BASE + "/",
            json={
                "name": "Bad Exact",
                "kind": "stock",
                "responsible_team_id": default_team.id,
                "stock_mode": "exact",
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 422

    def test_fixed_kind_rejects_stock_fields(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        resp = client.post(
            BASE + "/",
            json={
                "name": "Bad Fixed",
                "kind": "fixed",
                "responsible_team_id": default_team.id,
                "quantity": 5,
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 422

    def test_nonexistent_team_rejected(self, client: TestClient, user_token: str, root_bitza) -> None:
        resp = client.post(
            BASE + "/",
            json={
                "name": "Ghost Team",
                "kind": "fixed",
                "responsible_team_id": "00000000-0000-0000-0000-000000000000",
                "parent_id": root_bitza.id,
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 404

    def test_purchased_by_defaults_to_creator(
        self, client: TestClient, user_token: str, default_team: Team, normal_user: User
    ) -> None:
        b = make_mobile(client, user_token, default_team.id)
        assert b["purchased_by_user_id"] == normal_user.id


# =========================================================================
# Hierarchy
# =========================================================================

class TestHierarchy:
    def test_list_direct_children(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        parent = make_fixed(client, user_token, default_team.id, name="Shelf 4")
        make_mobile(client, user_token, default_team.id, name="Torque Wrench", parent_id=parent["id"])
        make_mobile(client, user_token, default_team.id, name="Multimeter 2", parent_id=parent["id"])

        resp = client.get(f"{BASE}/?parent_id={parent['id']}", headers=auth(user_token))
        assert resp.status_code == 200
        names = {b["name"] for b in resp.json()}
        assert names == {"Torque Wrench", "Multimeter 2"}

    def test_moving_container_does_not_touch_children(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        room_a = make_fixed(client, user_token, default_team.id, name="Study")
        room_b = make_fixed(client, user_token, default_team.id, name="James Room")
        toolbox = make_fixed(client, user_token, default_team.id, name="Toolbox 3", parent_id=room_a["id"])
        tool = make_mobile(client, user_token, default_team.id, name="Screwdriver", parent_id=toolbox["id"])

        resp = client.patch(
            f"{BASE}/{toolbox['id']}", json={"parent_id": room_b["id"]}, headers=auth(user_token)
        )
        assert resp.status_code == 200
        assert resp.json()["parent_id"] == room_b["id"]

        # The tool inside the toolbox never changed — still points at the
        # toolbox, which now just resolves to a different room.
        tool_resp = client.get(f"{BASE}/{tool['id']}", headers=auth(user_token))
        assert tool_resp.json()["parent_id"] == toolbox["id"]

    def test_cannot_move_bitza_under_its_own_descendant(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        parent = make_fixed(client, user_token, default_team.id, name="Cabinet")
        child = make_fixed(client, user_token, default_team.id, name="Drawer", parent_id=parent["id"])

        resp = client.patch(
            f"{BASE}/{parent['id']}", json={"parent_id": child["id"]}, headers=auth(user_token)
        )
        assert resp.status_code == 409

    def test_delete_blocked_with_children(
        self, client: TestClient, admin_token: str, user_token: str, default_team: Team
    ) -> None:
        parent = make_fixed(client, user_token, default_team.id, name="Non-empty")
        make_mobile(client, user_token, default_team.id, name="Inside", parent_id=parent["id"])

        resp = client.delete(f"{BASE}/{parent['id']}", headers=auth(admin_token))
        assert resp.status_code == 409

    def test_cannot_create_under_stock_parent(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        """Stock bitzas are quantity-only leaves — nothing can be created underneath one."""
        stock = make_exact_stock(client, user_token, default_team.id, qty=10)
        resp = client.post(
            BASE + "/",
            json={
                "name": "Should Not Fit",
                "kind": "fixed",
                "responsible_team_id": default_team.id,
                "parent_id": stock["id"],
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 409

    def test_cannot_move_bitza_under_stock_parent(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        stock = make_exact_stock(client, user_token, default_team.id, qty=10)
        shelf = make_fixed(client, user_token, default_team.id, name="Loose Shelf")
        resp = client.patch(
            f"{BASE}/{shelf['id']}", json={"parent_id": stock["id"]}, headers=auth(user_token)
        )
        assert resp.status_code == 409


class TestAncestors:
    """GET /{bitza_id}/ancestors — exposes BitzaRepository.get_ancestors()
    (previously used internally only, for update_bitza's cycle-detection
    check) so the frontend breadcrumb can replace N sequential
    GET /bitzas/{id} calls with one."""

    def test_ancestors_ordered_nearest_parent_first(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        root_id = _root_id(client, user_token)
        grandparent = make_fixed(client, user_token, default_team.id, name="Garage")
        parent = make_fixed(
            client, user_token, default_team.id, name="Toolbox", parent_id=grandparent["id"]
        )
        child = make_mobile(
            client, user_token, default_team.id, name="Screwdriver", parent_id=parent["id"]
        )

        resp = client.get(f"{BASE}/{child['id']}/ancestors", headers=auth(user_token))
        assert resp.status_code == 200
        ids = [row["id"] for row in resp.json()]
        assert ids == [parent["id"], grandparent["id"], root_id]

    def test_ancestors_empty_for_root(self, client: TestClient, user_token: str) -> None:
        root_id = _root_id(client, user_token)
        resp = client.get(f"{BASE}/{root_id}/ancestors", headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_ancestors_404_for_missing_bitza(self, client: TestClient, user_token: str) -> None:
        resp = client.get(f"{BASE}/does-not-exist/ancestors", headers=auth(user_token))
        assert resp.status_code == 404


# =========================================================================
# The single, permanent root bitza — see SystemConfig's model docstring
# for the "no per-row flag" design rationale.
# =========================================================================

class TestRootBitza:
    def test_create_without_parent_rejected(self, client: TestClient, user_token: str, default_team: Team) -> None:
        """
        parent_id is required on BitzaCreate — the ordinary API can never
        produce a second root-level bitza. Rejected by Pydantic itself,
        before the request reaches the service layer at all.
        """
        resp = client.post(
            BASE + "/",
            json={"name": "Another Root?", "kind": "fixed", "responsible_team_id": default_team.id},
            headers=auth(user_token),
        )
        assert resp.status_code == 422

    def test_root_flagged_is_root_true(
        self, client: TestClient, user_token: str, root_bitza: Bitza
    ) -> None:
        resp = client.get(f"{BASE}/{root_bitza.id}", headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json()["is_root"] is True

    def test_ordinary_bitza_flagged_is_root_false(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        ordinary = make_fixed(client, user_token, default_team.id, name="Ordinary Shelf")
        resp = client.get(f"{BASE}/{ordinary['id']}", headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json()["is_root"] is False

    def test_root_only_listing_returns_exactly_the_root(
        self, client: TestClient, user_token: str, root_bitza: Bitza, default_team: Team
    ) -> None:
        """
        Even after ordinary bitzas exist elsewhere in the tree, root_only
        listing returns exactly the one root — there's no longer any way
        for a second root-level item to sneak in via the ordinary API.
        """
        make_fixed(client, user_token, default_team.id, name="Somewhere Under Root")
        resp = client.get(f"{BASE}/?root_only=true", headers=auth(user_token))
        assert resp.status_code == 200
        ids = [b["id"] for b in resp.json()]
        assert ids == [root_bitza.id]

    def test_root_cannot_be_deleted_even_by_superuser(
        self, client: TestClient, superuser_token: str, root_bitza: Bitza
    ) -> None:
        """
        Unconditional protection — unlike every other permission floor in
        this app (role-based), this applies regardless of who's asking.
        """
        resp = client.delete(f"{BASE}/{root_bitza.id}", headers=auth(superuser_token))
        assert resp.status_code == 409

    def test_root_cannot_be_retired(
        self, client: TestClient, user_token: str, root_bitza: Bitza
    ) -> None:
        resp = client.post(
            f"{BASE}/{root_bitza.id}/retire",
            json={"reason": "lost"},
            headers=auth(user_token),
        )
        assert resp.status_code == 409

    def test_root_parent_id_change_rejected_for_non_admin(
        self, client: TestClient, user_token: str, root_bitza: Bitza, default_team: Team
    ) -> None:
        """
        A non-admin touching the root at all is rejected on the role
        check before the field-level guard even runs — 403, not the 409
        an admin gets for the identical payload (see the admin case
        below) — role wins when both problems are present at once.
        """
        somewhere = make_fixed(client, user_token, default_team.id, name="Somewhere")
        resp = client.patch(
            f"{BASE}/{root_bitza.id}", json={"parent_id": somewhere["id"]}, headers=auth(user_token)
        )
        assert resp.status_code == 403

    def test_root_parent_id_change_rejected_for_admin(
        self,
        client: TestClient,
        admin_token: str,
        user_token: str,
        root_bitza: Bitza,
        default_team: Team,
    ) -> None:
        """The root can never be reparented — it's the tree's permanent
        anchor — even for an admin, who clears the role check but is
        still rejected for the field itself."""
        somewhere = make_fixed(client, user_token, default_team.id, name="Somewhere")
        resp = client.patch(
            f"{BASE}/{root_bitza.id}", json={"parent_id": somewhere["id"]}, headers=auth(admin_token)
        )
        assert resp.status_code == 409

    def test_root_name_editable_by_admin(
        self, client: TestClient, admin_token: str, root_bitza: Bitza
    ) -> None:
        """Name is the one field the root's PATCH lockdown still allows — for an admin."""
        resp = client.patch(
            f"{BASE}/{root_bitza.id}", json={"name": "Renamed Root"}, headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed Root"

    def test_root_name_edit_rejected_for_non_admin(
        self, client: TestClient, user_token: str, root_bitza: Bitza
    ) -> None:
        """Even the one field that's ever editable on the root is admin/superuser-only."""
        resp = client.patch(
            f"{BASE}/{root_bitza.id}", json={"name": "Renamed Root"}, headers=auth(user_token)
        )
        assert resp.status_code == 403

    def test_root_non_name_field_rejected_for_admin(
        self, client: TestClient, admin_token: str, root_bitza: Bitza
    ) -> None:
        """Any field other than name is rejected outright, even for an
        admin who's cleared the role check — the whole request is
        rejected, not partially applied."""
        resp = client.patch(
            f"{BASE}/{root_bitza.id}",
            json={"description": "New description"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 409

    def test_root_reassign_team_rejected(
        self, client: TestClient, admin_token: str, root_bitza: Bitza, default_team: Team
    ) -> None:
        """
        reassign-team changes responsible_team_id directly and doesn't
        route through update_bitza's guard at all — checked separately
        so this endpoint can't undo the PATCH lockdown above. Unconditional,
        like delete/retire/move, since the root's team is never
        legitimately editable — not even for an admin.
        """
        resp = client.post(
            f"{BASE}/{root_bitza.id}/reassign-team",
            json={"team_id": default_team.id, "cascade_scope": "none"},
            headers=auth(admin_token),
        )
        assert resp.status_code == 409


# =========================================================================
# Delete permission (admin/superuser only) vs retire (any user)
# =========================================================================

class TestDeleteVsRetire:
    def test_normal_user_cannot_hard_delete(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        b = make_mobile(client, user_token, default_team.id)
        resp = client.delete(f"{BASE}/{b['id']}", headers=auth(user_token))
        assert resp.status_code == 403

    def test_admin_can_hard_delete(
        self, client: TestClient, admin_token: str, user_token: str, default_team: Team
    ) -> None:
        b = make_mobile(client, user_token, default_team.id)
        resp = client.delete(f"{BASE}/{b['id']}", headers=auth(admin_token))
        assert resp.status_code == 204

    def test_any_user_can_retire(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        b = make_mobile(client, user_token, default_team.id)
        resp = client.post(
            f"{BASE}/{b['id']}/retire",
            json={"reason": "lost"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "retired"
        assert resp.json()["retired_reason"] == "lost"

    def test_reactivate_clears_retired_fields(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        b = make_mobile(client, user_token, default_team.id)
        client.post(
            f"{BASE}/{b['id']}/retire",
            json={"reason": "broken", "note": "dropped it"},
            headers=auth(user_token),
        )
        resp = client.post(f"{BASE}/{b['id']}/reactivate", headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        assert resp.json()["retired_reason"] is None

    def test_retired_items_filterable(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        b = make_mobile(client, user_token, default_team.id, name="Broken Drill")
        client.post(
            f"{BASE}/{b['id']}/retire",
            json={"reason": "broken"},
            headers=auth(user_token),
        )
        resp = client.get(f"{BASE}/?status=retired", headers=auth(user_token))
        assert resp.status_code == 200
        assert any(x["id"] == b["id"] for x in resp.json())


# =========================================================================
# Team reassignment cascade
# =========================================================================

class TestReassignTeam:
    def test_scope_none_only_changes_this_row(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        other_team = client.post(
            BASE_TEAM + "/", json={"name": "Battery"}, headers=auth(user_token)
        ).json()
        cupboard = make_fixed(client, user_token, default_team.id, name="Brown Cupboard")
        shelf = make_fixed(client, user_token, default_team.id, name="Shelf 3", parent_id=cupboard["id"])

        resp = client.post(
            f"{BASE}/{cupboard['id']}/reassign-team",
            json={"team_id": other_team["id"], "cascade_scope": "none"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["updated_count"] == 1

        shelf_after = client.get(f"{BASE}/{shelf['id']}", headers=auth(user_token)).json()
        assert shelf_after["responsible_team_id"] == default_team.id

    def test_scope_direct_children(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        other_team = client.post(
            BASE_TEAM + "/", json={"name": "Suspension"}, headers=auth(user_token)
        ).json()
        cupboard = make_fixed(client, user_token, default_team.id, name="Cupboard2")
        shelf = make_fixed(client, user_token, default_team.id, name="Shelf X", parent_id=cupboard["id"])
        toolbox = make_fixed(client, user_token, default_team.id, name="Toolbox Y", parent_id=shelf["id"])

        resp = client.post(
            f"{BASE}/{cupboard['id']}/reassign-team",
            json={"team_id": other_team["id"], "cascade_scope": "direct_children"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["updated_count"] == 2  # cupboard + shelf, not toolbox

        shelf_after = client.get(f"{BASE}/{shelf['id']}", headers=auth(user_token)).json()
        toolbox_after = client.get(f"{BASE}/{toolbox['id']}", headers=auth(user_token)).json()
        assert shelf_after["responsible_team_id"] == other_team["id"]
        assert toolbox_after["responsible_team_id"] == default_team.id

    def test_scope_all_descendants(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        other_team = client.post(
            BASE_TEAM + "/", json={"name": "Powertrain"}, headers=auth(user_token)
        ).json()
        toolbox = make_fixed(client, user_token, default_team.id, name="Toolbox Z")
        drawer = make_fixed(client, user_token, default_team.id, name="Drawer Z", parent_id=toolbox["id"])
        tool = make_mobile(client, user_token, default_team.id, name="Pliers", parent_id=drawer["id"])

        resp = client.post(
            f"{BASE}/{toolbox['id']}/reassign-team",
            json={"team_id": other_team["id"], "cascade_scope": "all_descendants"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["updated_count"] == 3

        tool_after = client.get(f"{BASE}/{tool['id']}", headers=auth(user_token)).json()
        assert tool_after["responsible_team_id"] == other_team["id"]

    def test_cascade_scope_is_required(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        b = make_fixed(client, user_token, default_team.id)
        resp = client.post(
            f"{BASE}/{b['id']}/reassign-team",
            json={"team_id": default_team.id},
            headers=auth(user_token),
        )
        assert resp.status_code == 422


# =========================================================================
# Checkout / checkin
# =========================================================================

class TestCheckout:
    def test_checkout_and_checkin(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        resp = client.post(
            f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(user_token)
        )
        assert resp.status_code == 201
        assert resp.json()["checked_in_at"] is None

        after_checkout = client.get(f"{BASE}/{tool['id']}", headers=auth(user_token)).json()
        assert after_checkout["is_checked_out"] is True

        checkin_resp = client.post(
            f"{BASE}/{tool['id']}/checkin", json={}, headers=auth(user_token)
        )
        assert checkin_resp.status_code == 200
        assert checkin_resp.json()["checked_in_at"] is not None

        after_checkin = client.get(f"{BASE}/{tool['id']}", headers=auth(user_token)).json()
        assert after_checkin["is_checked_out"] is False

    def test_cannot_checkout_already_checked_out(
        self, client: TestClient, user_token: str, second_user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        client.post(f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(user_token))
        resp = client.post(
            f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(second_user_token)
        )
        assert resp.status_code == 409

    def test_cannot_checkin_when_not_checked_out(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        resp = client.post(f"{BASE}/{tool['id']}/checkin", json={}, headers=auth(user_token))
        assert resp.status_code == 409

    def test_cannot_checkout_fixed_bitza(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        room = make_fixed(client, user_token, default_team.id)
        resp = client.post(f"{BASE}/{room['id']}/checkout", json={}, headers=auth(user_token))
        assert resp.status_code == 409

    def test_team_context_snapshot_survives_membership_change(
        self, client: TestClient, user_token: str, default_team: Team, normal_user: User
    ) -> None:
        team = client.post(
            BASE_TEAM + "/", json={"name": "Snapshot Team"}, headers=auth(user_token)
        ).json()
        client.post(
            f"{BASE_TEAM}/{team['id']}/members",
            json={"user_id": normal_user.id, "is_primary": True},
            headers=auth(user_token),
        )
        tool = make_mobile(client, user_token, default_team.id)
        checkout = client.post(
            f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(user_token)
        ).json()
        assert checkout["team_context"] == "Snapshot Team"

        # Now remove the membership entirely — the checkout record must
        # be untouched, since team_context was a snapshot, not a live FK.
        client.delete(
            f"{BASE_TEAM}/{team['id']}/members/{normal_user.id}", headers=auth(user_token)
        )
        history = client.get(f"{BASE}/{tool['id']}/checkouts", headers=auth(user_token)).json()
        assert history[0]["team_context"] == "Snapshot Team"

    def test_checkout_history_lists_newest_first(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        client.post(f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(user_token))
        client.post(f"{BASE}/{tool['id']}/checkin", json={}, headers=auth(user_token))
        client.post(f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(user_token))

        resp = client.get(f"{BASE}/{tool['id']}/checkouts", headers=auth(user_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 2
        assert resp.json()[0]["checked_in_at"] is None


# =========================================================================
# My checkouts (/me landing page)
# =========================================================================

class TestMyCheckouts:
    def test_list_my_checkouts_returns_open_only(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id, name="Drill")
        client.post(f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(user_token))

        resp = client.get("/api/v1/checkouts/mine", headers=auth(user_token))
        assert resp.status_code == 200
        assert len(resp.json()) == 1
        assert resp.json()[0]["bitza_name"] == "Drill"
        assert resp.json()[0]["bitza_kind"] == "mobile"

    def test_checked_in_items_excluded(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        client.post(f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(user_token))
        client.post(f"{BASE}/{tool['id']}/checkin", json={}, headers=auth(user_token))

        resp = client.get("/api/v1/checkouts/mine", headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_only_returns_current_users_checkouts(
        self,
        client: TestClient,
        user_token: str,
        second_user_token: str,
        default_team: Team,
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        client.post(f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(user_token))

        resp = client.get("/api/v1/checkouts/mine", headers=auth(second_user_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_spans_whole_tree_not_one_subtree(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        """A user's checked-out items can live anywhere in the hierarchy —
        this must not be scoped to a single parent's subtree."""
        room = make_fixed(client, user_token, default_team.id, name="Garage")
        tool_a = make_mobile(
            client, user_token, default_team.id, name="Multimeter", parent_id=room["id"]
        )
        tool_b = make_mobile(client, user_token, default_team.id, name="Drill")
        client.post(f"{BASE}/{tool_a['id']}/checkout", json={}, headers=auth(user_token))
        client.post(f"{BASE}/{tool_b['id']}/checkout", json={}, headers=auth(user_token))

        resp = client.get("/api/v1/checkouts/mine", headers=auth(user_token))
        assert resp.status_code == 200
        names = {row["bitza_name"] for row in resp.json()}
        assert names == {"Multimeter", "Drill"}


# =========================================================================
# Stock adjustments
# =========================================================================

class TestStockAdjustments:
    def test_add_stock(self, client: TestClient, user_token: str, default_team: Team) -> None:
        stock = make_exact_stock(client, user_token, default_team.id, qty=10)
        resp = client.post(
            f"{BASE}/{stock['id']}/stock-adjustments",
            json={"delta": 5, "note": "Restocked"},
            headers=auth(user_token),
        )
        assert resp.status_code == 201
        assert resp.json()["quantity_after"] == 15

        after = client.get(f"{BASE}/{stock['id']}", headers=auth(user_token)).json()
        assert after["quantity"] == 15

    def test_negative_result_rejected(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        stock = make_exact_stock(client, user_token, default_team.id, qty=3)
        resp = client.post(
            f"{BASE}/{stock['id']}/stock-adjustments",
            json={"delta": -10},
            headers=auth(user_token),
        )
        assert resp.status_code == 422

    def test_adjustment_blocked_on_non_stock(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        resp = client.post(
            f"{BASE}/{tool['id']}/stock-adjustments",
            json={"delta": 1},
            headers=auth(user_token),
        )
        assert resp.status_code == 409

    def test_fuzzy_state_edited_directly_no_log(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        resp = client.post(
            BASE + "/",
            json={
                "name": "Zip Ties",
                "kind": "stock",
                "responsible_team_id": default_team.id,
                "parent_id": _root_id(client, user_token),
                "stock_mode": "fuzzy",
                "fuzzy_state": "plentiful",
            },
            headers=auth(user_token),
        )
        stock = resp.json()
        patch_resp = client.patch(
            f"{BASE}/{stock['id']}", json={"fuzzy_state": "low"}, headers=auth(user_token)
        )
        assert patch_resp.status_code == 200
        assert patch_resp.json()["fuzzy_state"] == "low"

    def test_fuzzy_state_rejected_on_exact_mode_stock(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        """Guards against exactly the gap the stock_mode-inert-during-edit
        frontend bug could otherwise exploit: flipping the (now read-only
        on edit) stock tracking dropdown used to let fuzzy_state slip
        into the update payload for a bitza that's actually exact-mode."""
        stock = make_exact_stock(client, user_token, default_team.id, qty=5)
        patch_resp = client.patch(
            f"{BASE}/{stock['id']}", json={"fuzzy_state": "low"}, headers=auth(user_token)
        )
        assert patch_resp.status_code == 409

    def test_fuzzy_state_rejected_on_non_stock(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        patch_resp = client.patch(
            f"{BASE}/{tool['id']}", json={"fuzzy_state": "low"}, headers=auth(user_token)
        )
        assert patch_resp.status_code == 409


# =========================================================================
# Kind editability (conditional — see bitza_project_context.md's `kind`
# section). kind/stock_mode transitions are guarded by history, not by
# permission level — any authenticated user who can PATCH a bitza at all
# can attempt one; the guard is what protects the data.
# =========================================================================

class TestKindEditability:
    def test_fixed_to_mobile_allowed(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        shelf = make_fixed(client, user_token, default_team.id)
        resp = client.patch(f"{BASE}/{shelf['id']}", json={"kind": "mobile"}, headers=auth(user_token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["kind"] == "mobile"

    def test_mobile_to_fixed_blocked_with_checkout_history(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        client.post(f"{BASE}/{tool['id']}/checkout", json={}, headers=auth(user_token))
        client.post(f"{BASE}/{tool['id']}/checkin", json={}, headers=auth(user_token))

        resp = client.patch(f"{BASE}/{tool['id']}", json={"kind": "fixed"}, headers=auth(user_token))
        assert resp.status_code == 409

    def test_mobile_to_fixed_allowed_without_checkout_history(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        resp = client.patch(f"{BASE}/{tool['id']}", json={"kind": "fixed"}, headers=auth(user_token))
        assert resp.status_code == 200, resp.text
        assert resp.json()["kind"] == "fixed"

    def test_change_to_stock_requires_stock_mode(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        shelf = make_fixed(client, user_token, default_team.id)
        resp = client.patch(f"{BASE}/{shelf['id']}", json={"kind": "stock"}, headers=auth(user_token))
        assert resp.status_code == 422

    def test_fixed_to_stock_blocked_with_children(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        parent = make_fixed(client, user_token, default_team.id, name="Non-empty Shelf")
        make_mobile(client, user_token, default_team.id, name="Inside", parent_id=parent["id"])

        resp = client.patch(
            f"{BASE}/{parent['id']}",
            json={"kind": "stock", "stock_mode": "exact", "quantity": 0},
            headers=auth(user_token),
        )
        assert resp.status_code == 409

    def test_fixed_to_stock_exact_allowed(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        shelf = make_fixed(client, user_token, default_team.id)
        resp = client.patch(
            f"{BASE}/{shelf['id']}",
            json={"kind": "stock", "stock_mode": "exact", "quantity": 10},
            headers=auth(user_token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["kind"] == "stock"
        assert body["quantity"] == 10

    def test_fixed_to_stock_fuzzy_allowed(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        shelf = make_fixed(client, user_token, default_team.id)
        resp = client.patch(
            f"{BASE}/{shelf['id']}",
            json={"kind": "stock", "stock_mode": "fuzzy", "fuzzy_state": "plentiful"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["fuzzy_state"] == "plentiful"

    def test_stock_to_fixed_nulls_stock_fields(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        stock = make_exact_stock(client, user_token, default_team.id, qty=5)
        resp = client.patch(f"{BASE}/{stock['id']}", json={"kind": "fixed"}, headers=auth(user_token))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["kind"] == "fixed"
        assert body["quantity"] is None
        assert body["fuzzy_state"] is None

    def test_stock_exact_to_fixed_blocked_with_adjustment_history(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        stock = make_exact_stock(client, user_token, default_team.id, qty=5)
        client.post(
            f"{BASE}/{stock['id']}/stock-adjustments",
            json={"delta": 3, "note": "restock"},
            headers=auth(user_token),
        )
        resp = client.patch(f"{BASE}/{stock['id']}", json={"kind": "fixed"}, headers=auth(user_token))
        assert resp.status_code == 409

    def test_stock_exact_to_fixed_allowed_without_adjustment_history(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        """Setting the initial quantity at creation doesn't write a
        StockLog row (only POST .../stock-adjustments does) — an
        exact-mode item that's never been adjusted is still switchable."""
        stock = make_exact_stock(client, user_token, default_team.id, qty=5)
        resp = client.patch(f"{BASE}/{stock['id']}", json={"kind": "fixed"}, headers=auth(user_token))
        assert resp.status_code == 200, resp.text

    def test_stock_mode_exact_to_fuzzy_without_kind_change(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        stock = make_exact_stock(client, user_token, default_team.id, qty=5)
        resp = client.patch(
            f"{BASE}/{stock['id']}",
            json={"stock_mode": "fuzzy", "fuzzy_state": "low"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["kind"] == "stock"
        assert body["stock_mode"] == "fuzzy"
        assert body["fuzzy_state"] == "low"
        assert body["quantity"] is None

    def test_stock_mode_change_blocked_with_adjustment_history(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        stock = make_exact_stock(client, user_token, default_team.id, qty=5)
        client.post(
            f"{BASE}/{stock['id']}/stock-adjustments",
            json={"delta": -2},
            headers=auth(user_token),
        )
        resp = client.patch(
            f"{BASE}/{stock['id']}",
            json={"stock_mode": "fuzzy", "fuzzy_state": "low"},
            headers=auth(user_token),
        )
        assert resp.status_code == 409

    def test_stock_mode_fuzzy_to_exact_allowed(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        stock = client.post(
            BASE + "/",
            json={
                "name": "Zip Ties",
                "kind": "stock",
                "responsible_team_id": default_team.id,
                "parent_id": _root_id(client, user_token),
                "stock_mode": "fuzzy",
                "fuzzy_state": "plentiful",
            },
            headers=auth(user_token),
        ).json()
        resp = client.patch(
            f"{BASE}/{stock['id']}",
            json={"stock_mode": "exact", "quantity": 20},
            headers=auth(user_token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["stock_mode"] == "exact"
        assert body["quantity"] == 20
        assert body["fuzzy_state"] is None

    def test_stock_mode_without_kind_rejected_when_not_already_stock(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        tool = make_mobile(client, user_token, default_team.id)
        resp = client.patch(
            f"{BASE}/{tool['id']}",
            json={"stock_mode": "exact", "quantity": 5},
            headers=auth(user_token),
        )
        assert resp.status_code == 409

    def test_quantity_alone_still_rejected(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        """Ongoing exact-mode quantity changes must still go through
        stock-adjustments — quantity is only ever accepted here as a
        transition's starting value, alongside kind or stock_mode."""
        stock = make_exact_stock(client, user_token, default_team.id, qty=5)
        resp = client.patch(f"{BASE}/{stock['id']}", json={"quantity": 99}, headers=auth(user_token))
        assert resp.status_code == 422

    def test_kind_change_writes_dedicated_audit_entry(
        self, client: TestClient, admin_token: str, user_token: str, default_team: Team
    ) -> None:
        shelf = make_fixed(client, user_token, default_team.id, name="Audited Shelf")
        client.patch(f"{BASE}/{shelf['id']}", json={"kind": "mobile"}, headers=auth(user_token))

        resp = client.get(f"{BASE_AUDIT}/?entity_id={shelf['id']}", headers=auth(admin_token))
        kind_entries = [e for e in resp.json() if e["action"] == "CHANGE_KIND"]
        assert len(kind_entries) == 1
        update_entries = [e for e in resp.json() if e["action"] == "UPDATE"]
        assert len(update_entries) == 0, "kind change should not also log a generic UPDATE entry"


# =========================================================================
# Categories
# =========================================================================

class TestCategories:
    def test_create_and_list(self, client: TestClient, user_token: str) -> None:
        resp = client.post(BASE_CAT + "/", json={"name": "Resistors"}, headers=auth(user_token))
        assert resp.status_code == 201
        names = [c["name"] for c in client.get(BASE_CAT + "/", headers=auth(user_token)).json()]
        assert "Resistors" in names

    def test_delete_blocked_while_in_use(
        self, client: TestClient, user_token: str, default_team: Team
    ) -> None:
        cat = client.post(
            BASE_CAT + "/", json={"name": "ICs"}, headers=auth(user_token)
        ).json()
        create_resp = client.post(
            BASE + "/",
            json={
                "name": "ATmega328P",
                "kind": "stock",
                "responsible_team_id": default_team.id,
                "parent_id": _root_id(client, user_token),
                "category_id": cat["id"],
                "stock_mode": "exact",
                "quantity": 4,
            },
            headers=auth(user_token),
        )
        assert create_resp.status_code == 201, create_resp.text
        resp = client.delete(f"{BASE_CAT}/{cat['id']}", headers=auth(user_token))
        assert resp.status_code == 409


# =========================================================================
# Audit log
# =========================================================================

class TestAuditLog:
    def test_admin_can_view(
        self, client: TestClient, admin_token: str, user_token: str, default_team: Team
    ) -> None:
        make_mobile(client, user_token, default_team.id)
        resp = client.get(BASE_AUDIT + "/", headers=auth(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_normal_user_cannot_view(self, client: TestClient, user_token: str) -> None:
        resp = client.get(BASE_AUDIT + "/", headers=auth(user_token))
        assert resp.status_code == 403

    def test_reassign_team_logs_one_summary_entry(
        self, client: TestClient, admin_token: str, user_token: str, default_team: Team
    ) -> None:
        other_team = client.post(
            BASE_TEAM + "/", json={"name": "Audit Team"}, headers=auth(user_token)
        ).json()
        cupboard = make_fixed(client, user_token, default_team.id, name="Audited Cupboard")
        make_fixed(client, user_token, default_team.id, name="Audited Shelf", parent_id=cupboard["id"])

        client.post(
            f"{BASE}/{cupboard['id']}/reassign-team",
            json={"team_id": other_team["id"], "cascade_scope": "direct_children"},
            headers=auth(user_token),
        )
        resp = client.get(
            f"{BASE_AUDIT}/?entity_id={cupboard['id']}", headers=auth(admin_token)
        )
        reassign_entries = [e for e in resp.json() if e["action"] == "REASSIGN_TEAM"]
        assert len(reassign_entries) == 1
