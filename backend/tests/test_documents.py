"""
Tests for /api/v1/bitzas/{id}/documents — datasheets, SDS/MSDS and manuals
attached to a bitza.

Covers:
- upload with and without metadata; blank form fields; metadata validation
- file lands on disk under UPLOAD_DIR with the expected size / SHA-256
- unsafe client filenames can't influence the on-disk path
- size cap and empty-file rejection (and no partial file left behind)
- list / download / PATCH (including clearing fields) / delete
- hard-deleting a bitza removes its document files
- any authenticated user may manage documents; anonymous may not

Every test runs against a throwaway UPLOAD_DIR under pytest's tmp_path, so
nothing is ever written into the real ./data/uploads.
"""

import hashlib

import pytest

from app.models.project import Project
from app.services import bitza_service
from tests.test_bitzas import BASE, auth, make_exact_stock, make_mobile

PDF_BYTES = b"%PDF-1.4\n% pretend datasheet\n%%EOF\n"


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(bitza_service.settings, "UPLOAD_DIR", str(tmp_path))
    return tmp_path


def _files_on_disk(upload_dir):
    return sorted(p for p in upload_dir.rglob("*") if p.is_file())


def _upload(
    client,
    token,
    bitza_id,
    *,
    content=PDF_BYTES,
    filename="LM358.pdf",
    content_type="application/pdf",
    **fields,
):
    return client.post(
        f"{BASE}/{bitza_id}/documents",
        files={"file": (filename, content, content_type)},
        data=fields,
        headers=auth(token),
    )


@pytest.fixture()
def stock_item(client, user_token, default_project: Project):
    return make_exact_stock(client, user_token, default_project.id, name="LM358 op-amps")


# =========================================================================
# Upload
# =========================================================================

class TestUpload:
    def test_upload_with_full_metadata(self, client, user_token, stock_item, upload_dir):
        resp = _upload(
            client,
            user_token,
            stock_item["id"],
            doc_type="datasheet",
            title="LM358 datasheet (TI)",
            source_url="https://www.ti.com/lit/ds/symlink/lm358.pdf",
            note="Rev. 2023",
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["bitza_id"] == stock_item["id"]
        assert body["doc_type"] == "datasheet"
        assert body["title"] == "LM358 datasheet (TI)"
        assert body["source_url"] == "https://www.ti.com/lit/ds/symlink/lm358.pdf"
        assert body["note"] == "Rev. 2023"
        assert body["original_filename"] == "LM358.pdf"
        assert body["content_type"] == "application/pdf"
        assert body["size_bytes"] == len(PDF_BYTES)
        assert body["sha256"] == hashlib.sha256(PDF_BYTES).hexdigest()
        assert body["uploaded_by_display_name"] == "Normal User"
        assert "file_path" not in body

    def test_file_is_stored_on_disk_under_upload_dir(
        self, client, user_token, stock_item, upload_dir
    ):
        _upload(client, user_token, stock_item["id"])
        (stored,) = _files_on_disk(upload_dir)
        assert stored.read_bytes() == PDF_BYTES
        assert stored.suffix == ".pdf"
        assert stored.parent == upload_dir / "bitzas" / stock_item["id"] / "documents"

    def test_all_metadata_is_optional(self, client, user_token, stock_item):
        resp = _upload(client, user_token, stock_item["id"])
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["doc_type"] is None
        assert body["title"] is None
        assert body["source_url"] is None
        assert body["note"] is None

    def test_blank_form_fields_become_null(self, client, user_token, stock_item):
        resp = _upload(
            client, user_token, stock_item["id"],
            doc_type="", title="  ", source_url="", note="",
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert (body["doc_type"], body["title"], body["source_url"], body["note"]) == (
            None, None, None, None,
        )

    def test_documents_allowed_on_any_kind(self, client, user_token, default_project):
        mobile = make_mobile(client, user_token, default_project.id)
        resp = _upload(client, user_token, mobile["id"], doc_type="manual")
        assert resp.status_code == 201, resp.text

    def test_multiple_documents_per_bitza(self, client, user_token, stock_item, upload_dir):
        for name in ("a.pdf", "b.pdf"):
            assert _upload(client, user_token, stock_item["id"], filename=name).status_code == 201
        assert len(_files_on_disk(upload_dir)) == 2

    def test_sds_doc_type_accepted(self, client, user_token, stock_item):
        resp = _upload(client, user_token, stock_item["id"], doc_type="sds")
        assert resp.status_code == 201
        assert resp.json()["doc_type"] == "sds"

    def test_invalid_doc_type_rejected(self, client, user_token, stock_item, upload_dir):
        resp = _upload(client, user_token, stock_item["id"], doc_type="blueprint")
        assert resp.status_code == 422
        assert _files_on_disk(upload_dir) == []

    @pytest.mark.parametrize(
        "url",
        ["javascript:alert(1)", "ftp://example.com/x.pdf", "data:text/html,hi", "not a url"],
    )
    def test_non_http_source_url_rejected(self, client, user_token, stock_item, url):
        resp = _upload(client, user_token, stock_item["id"], source_url=url)
        assert resp.status_code == 422

    def test_unknown_bitza_404(self, client, user_token, upload_dir):
        resp = _upload(client, user_token, "no-such-bitza")
        assert resp.status_code == 404
        assert _files_on_disk(upload_dir) == []

    def test_empty_file_rejected_and_nothing_left_behind(
        self, client, user_token, stock_item, upload_dir
    ):
        resp = _upload(client, user_token, stock_item["id"], content=b"")
        assert resp.status_code == 422
        assert _files_on_disk(upload_dir) == []
        assert client.get(
            f"{BASE}/{stock_item['id']}/documents", headers=auth(user_token)
        ).json() == []

    def test_oversize_rejected_and_nothing_left_behind(
        self, client, user_token, stock_item, upload_dir, monkeypatch
    ):
        monkeypatch.setattr(bitza_service.settings, "MAX_DOCUMENT_BYTES", 16)
        resp = _upload(client, user_token, stock_item["id"], content=b"x" * 17)
        assert resp.status_code == 413
        assert _files_on_disk(upload_dir) == []
        assert client.get(
            f"{BASE}/{stock_item['id']}/documents", headers=auth(user_token)
        ).json() == []

    def test_file_exactly_at_limit_accepted(
        self, client, user_token, stock_item, monkeypatch
    ):
        monkeypatch.setattr(bitza_service.settings, "MAX_DOCUMENT_BYTES", 16)
        resp = _upload(client, user_token, stock_item["id"], content=b"x" * 16)
        assert resp.status_code == 201, resp.text

    def test_file_larger_than_one_chunk_is_streamed_intact(
        self, client, user_token, stock_item, upload_dir
    ):
        big = b"abcdefgh" * (bitza_service._DOCUMENT_CHUNK_BYTES // 8 * 2 + 5)  # > 2 chunks
        resp = _upload(client, user_token, stock_item["id"], content=big)
        assert resp.status_code == 201, resp.text
        assert resp.json()["size_bytes"] == len(big)
        assert resp.json()["sha256"] == hashlib.sha256(big).hexdigest()
        (stored,) = _files_on_disk(upload_dir)
        assert stored.read_bytes() == big

    def test_anonymous_cannot_upload(self, client, stock_item, upload_dir):
        resp = client.post(
            f"{BASE}/{stock_item['id']}/documents",
            files={"file": ("x.pdf", PDF_BYTES, "application/pdf")},
        )
        assert resp.status_code in (401, 403)
        assert _files_on_disk(upload_dir) == []


class TestUnsafeFilenames:
    def test_path_components_stripped_from_stored_name(
        self, client, user_token, stock_item, upload_dir
    ):
        resp = _upload(client, user_token, stock_item["id"], filename="../../etc/passwd.pdf")
        assert resp.status_code == 201, resp.text
        assert resp.json()["original_filename"] == "passwd.pdf"
        (stored,) = _files_on_disk(upload_dir)
        assert stored.parent == upload_dir / "bitzas" / stock_item["id"] / "documents"

    def test_windows_style_path_stripped(self, client, user_token, stock_item):
        resp = _upload(client, user_token, stock_item["id"], filename=r"C:\Users\me\sheet.pdf")
        assert resp.json()["original_filename"] == "sheet.pdf"

    def test_odd_extension_is_not_used_on_disk(
        self, client, user_token, stock_item, upload_dir
    ):
        resp = _upload(client, user_token, stock_item["id"], filename="evil.<script>")
        assert resp.status_code == 201, resp.text
        (stored,) = _files_on_disk(upload_dir)
        assert stored.suffix == ""

    def test_no_filename_still_works(self, client, user_token, stock_item):
        resp = _upload(client, user_token, stock_item["id"], filename="")
        # An empty filename means no file part to FastAPI's form parser; either
        # outcome is acceptable as long as it's a clean client error, not a 500.
        assert resp.status_code in (201, 422)


# =========================================================================
# List
# =========================================================================

class TestList:
    def test_list_empty(self, client, user_token, stock_item):
        resp = client.get(f"{BASE}/{stock_item['id']}/documents", headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_is_scoped_to_the_bitza(
        self, client, user_token, stock_item, default_project
    ):
        other = make_exact_stock(client, user_token, default_project.id, name="Other")
        _upload(client, user_token, stock_item["id"], title="mine")
        _upload(client, user_token, other["id"], title="theirs")
        mine = client.get(f"{BASE}/{stock_item['id']}/documents", headers=auth(user_token)).json()
        assert [d["title"] for d in mine] == ["mine"]

    def test_list_unknown_bitza_404(self, client, user_token):
        resp = client.get(f"{BASE}/nope/documents", headers=auth(user_token))
        assert resp.status_code == 404

    def test_list_requires_auth(self, client, stock_item):
        resp = client.get(f"{BASE}/{stock_item['id']}/documents")
        assert resp.status_code in (401, 403)


# =========================================================================
# Download
# =========================================================================

class TestDownload:
    def test_download_returns_the_file(self, client, user_token, stock_item):
        doc = _upload(client, user_token, stock_item["id"]).json()
        resp = client.get(
            f"{BASE}/{stock_item['id']}/documents/{doc['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 200
        assert resp.content == PDF_BYTES
        assert resp.headers["content-type"].startswith("application/pdf")
        disposition = resp.headers["content-disposition"]
        assert disposition.startswith("attachment")
        assert "LM358.pdf" in disposition
        assert resp.headers["x-content-type-options"] == "nosniff"

    def test_download_with_non_ascii_filename(self, client, user_token, stock_item):
        doc = _upload(client, user_token, stock_item["id"], filename="Datenblätter µC.pdf").json()
        assert doc["original_filename"] == "Datenblätter µC.pdf"
        resp = client.get(
            f"{BASE}/{stock_item['id']}/documents/{doc['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 200
        assert resp.headers["content-disposition"].startswith("attachment")

    def test_download_via_wrong_bitza_404(
        self, client, user_token, stock_item, default_project
    ):
        other = make_exact_stock(client, user_token, default_project.id, name="Other")
        doc = _upload(client, user_token, stock_item["id"]).json()
        resp = client.get(f"{BASE}/{other['id']}/documents/{doc['id']}", headers=auth(user_token))
        assert resp.status_code == 404

    def test_download_unknown_document_404(self, client, user_token, stock_item):
        resp = client.get(f"{BASE}/{stock_item['id']}/documents/nope", headers=auth(user_token))
        assert resp.status_code == 404

    def test_download_when_file_missing_from_disk_404(
        self, client, user_token, stock_item, upload_dir
    ):
        doc = _upload(client, user_token, stock_item["id"]).json()
        for f in _files_on_disk(upload_dir):
            f.unlink()
        resp = client.get(
            f"{BASE}/{stock_item['id']}/documents/{doc['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 404

    def test_download_requires_auth(self, client, user_token, stock_item):
        doc = _upload(client, user_token, stock_item["id"]).json()
        resp = client.get(f"{BASE}/{stock_item['id']}/documents/{doc['id']}")
        assert resp.status_code in (401, 403)


# =========================================================================
# PATCH metadata
# =========================================================================

class TestUpdate:
    def _doc(self, client, token, bitza_id):
        return _upload(
            client, token, bitza_id,
            doc_type="datasheet", title="Old", source_url="https://example.com/a.pdf", note="n",
        ).json()

    def test_patch_changes_only_supplied_fields(self, client, user_token, stock_item):
        doc = self._doc(client, user_token, stock_item["id"])
        resp = client.patch(
            f"{BASE}/{stock_item['id']}/documents/{doc['id']}",
            json={"title": "New title", "doc_type": "sds"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["title"] == "New title"
        assert body["doc_type"] == "sds"
        assert body["source_url"] == "https://example.com/a.pdf"   # untouched
        assert body["note"] == "n"                                  # untouched

    def test_patch_null_and_blank_clear_a_field(self, client, user_token, stock_item):
        doc = self._doc(client, user_token, stock_item["id"])
        resp = client.patch(
            f"{BASE}/{stock_item['id']}/documents/{doc['id']}",
            json={"source_url": None, "note": ""},
            headers=auth(user_token),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["source_url"] is None
        assert body["note"] is None
        assert body["title"] == "Old"

    def test_patch_cannot_touch_file_facts(self, client, user_token, stock_item):
        doc = self._doc(client, user_token, stock_item["id"])
        resp = client.patch(
            f"{BASE}/{stock_item['id']}/documents/{doc['id']}",
            json={"size_bytes": 1, "sha256": "x", "file_path": "../../x", "bitza_id": "other"},
            headers=auth(user_token),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["size_bytes"] == doc["size_bytes"]
        assert body["sha256"] == doc["sha256"]
        assert body["bitza_id"] == stock_item["id"]

    def test_patch_invalid_values_rejected(self, client, user_token, stock_item):
        doc = self._doc(client, user_token, stock_item["id"])
        url = f"{BASE}/{stock_item['id']}/documents/{doc['id']}"
        assert client.patch(url, json={"doc_type": "nope"}, headers=auth(user_token)).status_code == 422
        assert client.patch(
            url, json={"source_url": "javascript:alert(1)"}, headers=auth(user_token)
        ).status_code == 422

    def test_patch_wrong_bitza_404(self, client, user_token, stock_item, default_project):
        other = make_exact_stock(client, user_token, default_project.id, name="Other")
        doc = self._doc(client, user_token, stock_item["id"])
        resp = client.patch(
            f"{BASE}/{other['id']}/documents/{doc['id']}",
            json={"title": "x"},
            headers=auth(user_token),
        )
        assert resp.status_code == 404


# =========================================================================
# Delete
# =========================================================================

class TestDelete:
    def test_delete_removes_row_and_file(self, client, user_token, stock_item, upload_dir):
        doc = _upload(client, user_token, stock_item["id"]).json()
        resp = client.delete(
            f"{BASE}/{stock_item['id']}/documents/{doc['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 204
        assert _files_on_disk(upload_dir) == []
        assert client.get(
            f"{BASE}/{stock_item['id']}/documents", headers=auth(user_token)
        ).json() == []

    def test_delete_leaves_other_documents_alone(
        self, client, user_token, stock_item, upload_dir
    ):
        first = _upload(client, user_token, stock_item["id"], title="first").json()
        _upload(client, user_token, stock_item["id"], title="second")
        client.delete(f"{BASE}/{stock_item['id']}/documents/{first['id']}", headers=auth(user_token))
        remaining = client.get(
            f"{BASE}/{stock_item['id']}/documents", headers=auth(user_token)
        ).json()
        assert [d["title"] for d in remaining] == ["second"]
        assert len(_files_on_disk(upload_dir)) == 1

    def test_delete_succeeds_even_if_file_already_gone(
        self, client, user_token, stock_item, upload_dir
    ):
        doc = _upload(client, user_token, stock_item["id"]).json()
        for f in _files_on_disk(upload_dir):
            f.unlink()
        resp = client.delete(
            f"{BASE}/{stock_item['id']}/documents/{doc['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 204

    def test_delete_wrong_bitza_404_and_keeps_file(
        self, client, user_token, stock_item, default_project, upload_dir
    ):
        other = make_exact_stock(client, user_token, default_project.id, name="Other")
        doc = _upload(client, user_token, stock_item["id"]).json()
        resp = client.delete(
            f"{BASE}/{other['id']}/documents/{doc['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 404
        assert len(_files_on_disk(upload_dir)) == 1

    def test_any_authenticated_user_can_delete(
        self, client, user_token, second_user_token, stock_item
    ):
        doc = _upload(client, user_token, stock_item["id"]).json()
        resp = client.delete(
            f"{BASE}/{stock_item['id']}/documents/{doc['id']}", headers=auth(second_user_token)
        )
        assert resp.status_code == 204

    def test_delete_requires_auth(self, client, user_token, stock_item):
        doc = _upload(client, user_token, stock_item["id"]).json()
        resp = client.delete(f"{BASE}/{stock_item['id']}/documents/{doc['id']}")
        assert resp.status_code in (401, 403)


class TestHardDeleteBitza:
    def test_hard_deleting_a_bitza_removes_its_document_files(
        self, client, user_token, admin_token, stock_item, upload_dir
    ):
        _upload(client, user_token, stock_item["id"])
        _upload(client, user_token, stock_item["id"], filename="b.pdf")
        assert len(_files_on_disk(upload_dir)) == 2

        resp = client.delete(f"{BASE}/{stock_item['id']}", headers=auth(admin_token))
        assert resp.status_code == 204, resp.text
        assert _files_on_disk(upload_dir) == []
        assert not (upload_dir / "bitzas" / stock_item["id"] / "documents").exists()

    def test_hard_delete_leaves_other_bitzas_documents(
        self, client, user_token, admin_token, stock_item, default_project, upload_dir
    ):
        other = make_exact_stock(client, user_token, default_project.id, name="Other")
        _upload(client, user_token, stock_item["id"])
        kept = _upload(client, user_token, other["id"]).json()

        client.delete(f"{BASE}/{stock_item['id']}", headers=auth(admin_token))

        assert len(_files_on_disk(upload_dir)) == 1
        resp = client.get(f"{BASE}/{other['id']}/documents/{kept['id']}", headers=auth(user_token))
        assert resp.status_code == 200
        assert resp.content == PDF_BYTES

    def test_hard_delete_of_bitza_without_documents_still_works(
        self, client, admin_token, user_token, stock_item
    ):
        resp = client.delete(f"{BASE}/{stock_item['id']}", headers=auth(admin_token))
        assert resp.status_code == 204
