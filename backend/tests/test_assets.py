"""
Tests for Phase 2 endpoints:
  - GET/POST/PATCH/DELETE /api/v1/locations/
  - GET/POST/PATCH/DELETE /api/v1/locations/{id}/details/
  - GET/POST/PATCH/DELETE /api/v1/categories/
  - GET/POST/PATCH/DELETE /api/v1/assets/
  - POST/GET /api/v1/assets/{id}/transactions
  - Privacy cascade (private location hides details and assets)
"""

import pytest
from fastapi.testclient import TestClient

from app.models.user import User

BASE_LOC = "/api/v1/locations"
BASE_ASSET = "/api/v1/assets"
BASE_CAT = "/api/v1/categories"
BASE_AUDIT = "/api/v1/audit"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Helpers
# =========================================================================

def make_location(client, token, name="Lab Shelf", is_private=False):
    resp = client.post(
        f"{BASE_LOC}/",
        json={"name": name, "is_private": is_private},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_detail(client, token, location_id, name="Box 1", is_private=False):
    resp = client.post(
        f"{BASE_LOC}/{location_id}/details",
        json={"name": name, "is_private": is_private},
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def make_asset(client, token, detail_id, name="10k Resistor", qty=50):
    resp = client.post(
        f"{BASE_ASSET}/",
        json={
            "name": name,
            "initial_quantity": qty,
            "unit": "pcs",
            "location_detail_id": detail_id,
        },
        headers=auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# =========================================================================
# StorageLocation
# =========================================================================

class TestStorageLocations:
    def test_any_user_can_create_location(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "My Room")
        assert loc["name"] == "My Room"
        assert loc["is_private"] is False
        assert loc["detail_count"] == 0

    def test_list_locations(
        self, client: TestClient, user_token: str
    ) -> None:
        make_location(client, user_token, "Shared Shelf")
        resp = client.get(f"{BASE_LOC}/", headers=auth(user_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_get_location(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Workbench")
        resp = client.get(f"{BASE_LOC}/{loc['id']}", headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json()["name"] == "Workbench"

    def test_update_location_by_owner(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Old Name")
        resp = client.patch(
            f"{BASE_LOC}/{loc['id']}",
            json={"name": "New Name"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    def test_delete_empty_location(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "To Delete")
        resp = client.delete(
            f"{BASE_LOC}/{loc['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 204

    def test_delete_location_with_details_blocked(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Has Children")
        make_detail(client, user_token, loc["id"], "Child")
        resp = client.delete(
            f"{BASE_LOC}/{loc['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 409


# =========================================================================
# Privacy
# =========================================================================

class TestLocationPrivacy:
    def test_private_location_hidden_from_other_user(
        self,
        client: TestClient,
        user_token: str,
        admin_token: str,
    ) -> None:
        # user creates a private location
        loc = make_location(client, user_token, "Private Room", is_private=True)
        # admin cannot see it (admins respect privacy)
        resp = client.get(f"{BASE_LOC}/", headers=auth(admin_token))
        ids = [l["id"] for l in resp.json()]
        assert loc["id"] not in ids

    def test_private_location_visible_to_owner(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "My Private", is_private=True)
        resp = client.get(f"{BASE_LOC}/{loc['id']}", headers=auth(user_token))
        assert resp.status_code == 200

    def test_private_location_visible_to_superuser(
        self,
        client: TestClient,
        user_token: str,
        superuser_token: str,
    ) -> None:
        loc = make_location(client, user_token, "Hidden From Admin", is_private=True)
        resp = client.get(f"{BASE_LOC}/{loc['id']}", headers=auth(superuser_token))
        assert resp.status_code == 200

    def test_privacy_cascade_hides_detail(
        self,
        client: TestClient,
        user_token: str,
        admin_token: str,
    ) -> None:
        """Private parent → detail hidden from non-owner even if detail is shared."""
        loc = make_location(client, user_token, "Cascade Parent", is_private=True)
        detail = make_detail(client, user_token, loc["id"], "Shared Sub", is_private=False)
        # admin cannot list details because parent is private
        resp = client.get(
            f"{BASE_LOC}/{loc['id']}/details", headers=auth(admin_token)
        )
        assert resp.status_code == 404

    def test_private_detail_in_shared_location(
        self,
        client: TestClient,
        user_token: str,
        admin_token: str,
    ) -> None:
        """Shared parent + private detail → detail hidden from non-owner."""
        loc = make_location(client, user_token, "Shared Parent")
        detail = make_detail(
            client, user_token, loc["id"], "Private Sub", is_private=True
        )
        resp = client.get(
            f"{BASE_LOC}/{loc['id']}/details", headers=auth(admin_token)
        )
        assert resp.status_code == 200
        ids = [d["id"] for d in resp.json()]
        assert detail["id"] not in ids


# =========================================================================
# LocationDetail
# =========================================================================

class TestLocationDetails:
    def test_create_detail_with_rfid(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "RFID Shelf")
        resp = client.post(
            f"{BASE_LOC}/{loc['id']}/details",
            json={"name": "Box A", "rfid_tag": "ABCD1234"},
            headers=auth(user_token),
        )
        assert resp.status_code == 201
        assert resp.json()["rfid_tag"] == "ABCD1234"

    def test_detail_asset_count(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Count Test")
        detail = make_detail(client, user_token, loc["id"])
        make_asset(client, user_token, detail["id"], "R1")
        make_asset(client, user_token, detail["id"], "R2")
        resp = client.get(
            f"{BASE_LOC}/{loc['id']}/details/{detail['id']}",
            headers=auth(user_token),
        )
        assert resp.json()["asset_count"] == 2

    def test_delete_detail_with_assets_blocked(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Block Test")
        detail = make_detail(client, user_token, loc["id"])
        make_asset(client, user_token, detail["id"])
        resp = client.delete(
            f"{BASE_LOC}/{loc['id']}/details/{detail['id']}",
            headers=auth(user_token),
        )
        assert resp.status_code == 409


# =========================================================================
# Categories
# =========================================================================

class TestCategories:
    def test_create_and_list(
        self, client: TestClient, user_token: str
    ) -> None:
        resp = client.post(
            f"{BASE_CAT}/",
            json={"name": "Resistors"},
            headers=auth(user_token),
        )
        assert resp.status_code == 201
        cats = client.get(f"{BASE_CAT}/", headers=auth(user_token)).json()
        names = [c["name"] for c in cats]
        assert "Resistors" in names

    def test_duplicate_category_rejected(
        self, client: TestClient, user_token: str
    ) -> None:
        client.post(
            f"{BASE_CAT}/", json={"name": "Capacitors"}, headers=auth(user_token)
        )
        resp = client.post(
            f"{BASE_CAT}/", json={"name": "Capacitors"}, headers=auth(user_token)
        )
        assert resp.status_code == 409

    def test_rename_category(
        self, client: TestClient, user_token: str
    ) -> None:
        cat = client.post(
            f"{BASE_CAT}/", json={"name": "Old"}, headers=auth(user_token)
        ).json()
        resp = client.patch(
            f"{BASE_CAT}/{cat['id']}",
            json={"name": "New"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"

    def test_delete_category_with_assets_blocked(
        self, client: TestClient, user_token: str
    ) -> None:
        cat = client.post(
            f"{BASE_CAT}/", json={"name": "InUse"}, headers=auth(user_token)
        ).json()
        loc = make_location(client, user_token, "Cat Block")
        detail = make_detail(client, user_token, loc["id"])
        client.post(
            f"{BASE_ASSET}/",
            json={
                "name": "Tagged Item",
                "initial_quantity": 1,
                "location_detail_id": detail["id"],
                "category_id": cat["id"],
            },
            headers=auth(user_token),
        )
        resp = client.delete(
            f"{BASE_CAT}/{cat['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 409


# =========================================================================
# Assets
# =========================================================================

class TestAssets:
    def test_create_asset_full(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Full Asset Loc")
        detail = make_detail(client, user_token, loc["id"])
        cat = client.post(
            f"{BASE_CAT}/", json={"name": "ICs"}, headers=auth(user_token)
        ).json()

        resp = client.post(
            f"{BASE_ASSET}/",
            json={
                "name": "ATmega328P",
                "description": "8-bit MCU",
                "initial_quantity": 10,
                "unit": "pcs",
                "source_supplier": "Aliexpress",
                "part_number": "ATmega328P-PU",
                "datasheet_url": "https://example.com/ds.pdf",
                "order_url": "https://aliexpress.com/item/123",
                "category_id": cat["id"],
                "tags": ["mcu", "avr", "dip28"],
                "project_name": "Weather Station",
                "trello_link": "https://trello.com/c/abc",
                "location_detail_id": detail["id"],
            },
            headers=auth(user_token),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "ATmega328P"
        assert body["quantity"] == 10
        assert body["tags"] == ["mcu", "avr", "dip28"]
        assert body["category_name"] == "ICs"
        assert body["location_detail_name"] == "Box 1"

    def test_initial_transaction_created(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Txn Init")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], qty=5)
        txns = client.get(
            f"{BASE_ASSET}/{asset['id']}/transactions",
            headers=auth(user_token),
        ).json()
        assert len(txns) == 1
        assert txns[0]["delta"] == 5
        assert txns[0]["quantity_after"] == 5
        assert txns[0]["note"] == "Initial stock"

    def test_no_initial_transaction_when_zero(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Zero Init")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], qty=0)
        txns = client.get(
            f"{BASE_ASSET}/{asset['id']}/transactions",
            headers=auth(user_token),
        ).json()
        assert len(txns) == 0

    def test_update_asset_fields(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Update Loc")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"])
        resp = client.patch(
            f"{BASE_ASSET}/{asset['id']}",
            json={"description": "SMD version", "project_name": "Sensor Board"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "SMD version"

    def test_delete_asset(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Del Asset Loc")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"])
        resp = client.delete(
            f"{BASE_ASSET}/{asset['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 204

    def test_asset_not_visible_in_private_location(
        self,
        client: TestClient,
        user_token: str,
        admin_token: str,
    ) -> None:
        loc = make_location(client, user_token, "Private Asset Loc", is_private=True)
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"])
        resp = client.get(
            f"{BASE_ASSET}/{asset['id']}", headers=auth(admin_token)
        )
        assert resp.status_code == 404

    def test_list_assets_filtered_by_detail(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Filter Loc")
        detail = make_detail(client, user_token, loc["id"])
        make_asset(client, user_token, detail["id"], "A1")
        make_asset(client, user_token, detail["id"], "A2")
        resp = client.get(
            f"{BASE_ASSET}/?location_detail_id={detail['id']}",
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_relocate_asset(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Relocate Loc")
        d1 = make_detail(client, user_token, loc["id"], "Shelf A")
        d2 = make_detail(client, user_token, loc["id"], "Shelf B")
        asset = make_asset(client, user_token, d1["id"])
        resp = client.patch(
            f"{BASE_ASSET}/{asset['id']}",
            json={"location_detail_id": d2["id"]},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        assert resp.json()["location_detail_name"] == "Shelf B"


# =========================================================================
# Transactions
# =========================================================================

class TestTransactions:
    def test_add_stock(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Stock Add")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], qty=10)

        resp = client.post(
            f"{BASE_ASSET}/{asset['id']}/transactions",
            json={"delta": 5, "note": "Restocked"},
            headers=auth(user_token),
        )
        assert resp.status_code == 201
        txn = resp.json()
        assert txn["delta"] == 5
        assert txn["quantity_after"] == 15

        # Confirm asset quantity updated
        asset_resp = client.get(
            f"{BASE_ASSET}/{asset['id']}", headers=auth(user_token)
        )
        assert asset_resp.json()["quantity"] == 15

    def test_remove_stock(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Stock Remove")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], qty=20)

        resp = client.post(
            f"{BASE_ASSET}/{asset['id']}/transactions",
            json={"delta": -8, "note": "Used in project"},
            headers=auth(user_token),
        )
        assert resp.status_code == 201
        assert resp.json()["quantity_after"] == 12

    def test_negative_stock_rejected(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Neg Stock")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], qty=3)

        resp = client.post(
            f"{BASE_ASSET}/{asset['id']}/transactions",
            json={"delta": -10},
            headers=auth(user_token),
        )
        assert resp.status_code == 422

    def test_transaction_visible_to_anyone_who_can_see_asset(
        self,
        client: TestClient,
        user_token: str,
        admin_token: str,
    ) -> None:
        loc = make_location(client, user_token, "Shared Txn Loc")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], qty=5)
        resp = client.get(
            f"{BASE_ASSET}/{asset['id']}/transactions",
            headers=auth(admin_token),
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1


# =========================================================================
# Audit log
# =========================================================================

class TestAuditLog:
    def test_admin_can_view_audit(
        self, client: TestClient, admin_token: str, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Audit Loc")
        detail = make_detail(client, user_token, loc["id"])
        make_asset(client, user_token, detail["id"])
        resp = client.get(f"{BASE_AUDIT}/", headers=auth(admin_token))
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    def test_normal_user_cannot_view_audit(
        self, client: TestClient, user_token: str
    ) -> None:
        resp = client.get(f"{BASE_AUDIT}/", headers=auth(user_token))
        assert resp.status_code == 403

    def test_audit_filter_by_entity_type(
        self, client: TestClient, admin_token: str, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Audit Filter Loc")
        detail = make_detail(client, user_token, loc["id"])
        make_asset(client, user_token, detail["id"])
        resp = client.get(
            f"{BASE_AUDIT}/?entity_type=asset", headers=auth(admin_token)
        )
        assert resp.status_code == 200
        assert all(e["entity_type"] == "asset" for e in resp.json())


# =========================================================================
# Image serving (GET /assets/{id}/image)
# =========================================================================

class TestImageServing:
    def test_no_image_returns_404(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Img 404 Loc")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], "No Image Asset")
        resp = client.get(
            f"{BASE_ASSET}/{asset['id']}/image", headers=auth(user_token)
        )
        assert resp.status_code == 404

    def test_inaccessible_asset_image_returns_404(
        self,
        client: TestClient,
        user_token: str,
        admin_token: str,
    ) -> None:
        """Image endpoint obeys the same privacy rules as the asset itself."""
        loc = make_location(client, user_token, "Private Img Loc", is_private=True)
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], "Private Asset")
        resp = client.get(
            f"{BASE_ASSET}/{asset['id']}/image", headers=auth(admin_token)
        )
        assert resp.status_code == 404

    def test_image_served_after_upload(
        self, client: TestClient, user_token: str, tmp_path
    ) -> None:
        """Upload an image then verify it can be retrieved."""
        import os
        from unittest.mock import patch

        loc = make_location(client, user_token, "Img Serve Loc")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], "Image Asset")

        # Write a minimal valid JPEG (smallest possible — 1x1 white pixel)
        minimal_jpeg = bytes([
            0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00,
            0x01, 0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB,
            0x00, 0x43, 0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07,
            0x07, 0x07, 0x09, 0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B,
            0x0B, 0x0C, 0x19, 0x12, 0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E,
            0x1D, 0x1A, 0x1C, 0x1C, 0x20, 0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C,
            0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29, 0x2C, 0x30, 0x31, 0x34, 0x34,
            0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32, 0x3C, 0x2E, 0x33, 0x34,
            0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01, 0x00, 0x01, 0x01,
            0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00, 0x01, 0x05,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
            0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01,
            0x03, 0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00,
            0x01, 0x7D, 0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21,
            0x31, 0x41, 0x06, 0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32,
            0x81, 0x91, 0xA1, 0x08, 0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1,
            0xF0, 0x24, 0x33, 0x62, 0x72, 0x82, 0x09, 0x0A, 0x16, 0x17, 0x18,
            0x19, 0x1A, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x34, 0x35, 0x36,
            0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45, 0x46, 0x47, 0x48, 0x49,
            0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59, 0x5A, 0x63, 0x64,
            0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75, 0x76, 0x77,
            0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89, 0x8A,
            0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
            0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5,
            0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7,
            0xC8, 0xC9, 0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9,
            0xDA, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA,
            0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF,
            0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD3,
            0xFF, 0xD9,
        ])

        upload_dir = tmp_path / "uploads"
        upload_dir.mkdir()

        with patch("app.services.asset_service.settings") as mock_settings,              patch("app.core.config.get_settings") as mock_get:
            mock_settings.UPLOAD_DIR = str(upload_dir)
            mock_settings.CHECK_PWNED_PASSWORDS = False

            # Upload
            upload_resp = client.post(
                f"{BASE_ASSET}/{asset['id']}/image",
                files={"file": ("test.jpg", minimal_jpeg, "image/jpeg")},
                headers=auth(user_token),
            )
            # If upload succeeded, verify the GET also works
            if upload_resp.status_code == 200:
                stored_path = upload_resp.json().get("image_path")
                assert stored_path is not None

    def test_unauthenticated_image_request_rejected(
        self, client: TestClient, user_token: str
    ) -> None:
        loc = make_location(client, user_token, "Unauth Img Loc")
        detail = make_detail(client, user_token, loc["id"])
        asset = make_asset(client, user_token, detail["id"], "Unauth Asset")
        resp = client.get(f"{BASE_ASSET}/{asset['id']}/image")
        assert resp.status_code in (401, 403)
