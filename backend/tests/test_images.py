"""
Tests for /api/v1/bitzas/{id}/images — photos attached to a bitza.

Focus is the upload check: the image's type is sniffed from its bytes, not
taken from the client's Content-Type or filename, and that decides the
on-disk extension and so the Content-Type the image is served with. Also
covers the surrounding behaviour (first image becomes primary, list, set
primary, delete, auth) which previously had no backend tests.

Every test runs against a throwaway UPLOAD_DIR under pytest's tmp_path.
"""

import pytest

from app.models.bitza import BitzaImage
from app.models.project import Project
from app.services import bitza_service
from tests.test_bitzas import BASE, auth, make_exact_stock

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 16
GIF = b"GIF89a\x01\x00\x01\x00" + b"\x00" * 8
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 16
HTML = b"<!DOCTYPE html><html><script>alert(1)</script></html>"
SVG = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"
PDF = b"%PDF-1.4\n%%EOF\n"


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
    content=PNG,
    filename="photo.png",
    content_type="image/png",
    **fields,
):
    return client.post(
        f"{BASE}/{bitza_id}/images",
        files={"file": (filename, content, content_type)},
        data=fields,
        headers=auth(token),
    )


def _fetch(client, token, bitza_id, image_id):
    return client.get(f"{BASE}/{bitza_id}/images/{image_id}", headers=auth(token))


@pytest.fixture()
def stock_item(client, user_token, default_project: Project):
    return make_exact_stock(client, user_token, default_project.id, name="Resistor 10k")


# =========================================================================
# Upload: content sniffing
# =========================================================================

class TestUploadSniffing:
    @pytest.mark.parametrize(
        ("content", "media_type", "suffix"),
        [
            (PNG, "image/png", ".png"),
            (JPEG, "image/jpeg", ".jpg"),
            (GIF, "image/gif", ".gif"),
            (WEBP, "image/webp", ".webp"),
        ],
        ids=["png", "jpeg", "gif", "webp"],
    )
    def test_each_accepted_type_is_stored_and_served_correctly(
        self, client, user_token, stock_item, upload_dir, content, media_type, suffix
    ):
        # Filename and claimed type are deliberately unhelpful.
        resp = _upload(
            client, user_token, stock_item["id"],
            content=content, filename="whatever", content_type="application/octet-stream",
        )
        assert resp.status_code == 201, resp.text
        (stored,) = _files_on_disk(upload_dir)
        assert stored.suffix == suffix
        assert stored.read_bytes() == content

        fetched = _fetch(client, user_token, stock_item["id"], resp.json()["id"])
        assert fetched.status_code == 200
        assert fetched.headers["content-type"].startswith(media_type)
        assert fetched.content == content

    def test_client_claim_does_not_matter_when_content_is_a_real_image(
        self, client, user_token, stock_item, upload_dir
    ):
        resp = _upload(
            client, user_token, stock_item["id"],
            content=JPEG, filename="photo.png", content_type="image/png",
        )
        assert resp.status_code == 201, resp.text
        (stored,) = _files_on_disk(upload_dir)
        assert stored.suffix == ".jpg"  # follows the content, not the client's ".png"

    def test_client_extension_kept_when_consistent_with_content(
        self, client, user_token, stock_item, upload_dir
    ):
        resp = _upload(
            client, user_token, stock_item["id"],
            content=JPEG, filename="Board.JPEG", content_type="image/jpeg",
        )
        assert resp.status_code == 201, resp.text
        (stored,) = _files_on_disk(upload_dir)
        assert stored.suffix == ".jpeg"

    def test_dangerous_client_extension_is_never_used_on_disk(
        self, client, user_token, stock_item, upload_dir
    ):
        resp = _upload(
            client, user_token, stock_item["id"], content=PNG, filename="evil.html"
        )
        assert resp.status_code == 201, resp.text
        (stored,) = _files_on_disk(upload_dir)
        assert stored.suffix == ".png"

    @pytest.mark.parametrize(
        "content",
        [HTML, SVG, PDF, b"just some text", b"MZ\x90\x00" + b"\x00" * 32, b""],
        ids=["html", "svg", "pdf", "text", "executable", "empty"],
    )
    def test_non_images_are_rejected_even_when_claimed_to_be_images(
        self, client, user_token, stock_item, upload_dir, content
    ):
        resp = _upload(
            client, user_token, stock_item["id"],
            content=content, filename="photo.png", content_type="image/png",
        )
        assert resp.status_code == 415
        assert "Accepted" in resp.json()["detail"]
        assert _files_on_disk(upload_dir) == []
        assert client.get(
            f"{BASE}/{stock_item['id']}/images", headers=auth(user_token)
        ).json() == []

    def test_riff_that_is_not_webp_is_rejected(
        self, client, user_token, stock_item, upload_dir
    ):
        wav = b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 16
        resp = _upload(client, user_token, stock_item["id"], content=wav)
        assert resp.status_code == 415
        assert _files_on_disk(upload_dir) == []

    def test_oversize_rejected_and_nothing_written(
        self, client, user_token, stock_item, upload_dir, monkeypatch
    ):
        monkeypatch.setattr(bitza_service, "_MAX_IMAGE_BYTES", len(PNG))
        resp = _upload(client, user_token, stock_item["id"], content=PNG + b"x")
        assert resp.status_code == 413
        assert _files_on_disk(upload_dir) == []

    def test_unknown_bitza_404_and_nothing_written(self, client, user_token, upload_dir):
        resp = _upload(client, user_token, "no-such-bitza")
        assert resp.status_code == 404
        assert _files_on_disk(upload_dir) == []

    def test_anonymous_cannot_upload(self, client, stock_item, upload_dir):
        resp = client.post(
            f"{BASE}/{stock_item['id']}/images",
            files={"file": ("p.png", PNG, "image/png")},
        )
        assert resp.status_code in (401, 403)
        assert _files_on_disk(upload_dir) == []


# =========================================================================
# Serving
# =========================================================================

class TestServe:
    def test_served_with_nosniff(self, client, user_token, stock_item):
        image = _upload(client, user_token, stock_item["id"]).json()
        resp = _fetch(client, user_token, stock_item["id"], image["id"])
        assert resp.status_code == 200
        assert resp.headers["x-content-type-options"] == "nosniff"

    @pytest.mark.parametrize("name", ["legacy.html", "legacy.svg", "legacy", "legacy.pdf"])
    def test_legacy_files_with_non_image_extensions_are_served_as_opaque_binary(
        self, client, db, user_token, stock_item, upload_dir, name
    ):
        """Files uploaded before sniffing existed kept the client's extension.
        Those must never be served as text/html, image/svg+xml, etc."""
        rel = f"bitzas/{stock_item['id']}/{name}"
        path = upload_dir / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(HTML)
        db.add(BitzaImage(id=f"legacy-{name}", bitza_id=stock_item["id"], image_path=rel))
        db.commit()

        resp = _fetch(client, user_token, stock_item["id"], f"legacy-{name}")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/octet-stream")
        assert resp.headers["x-content-type-options"] == "nosniff"

    def test_unknown_image_404(self, client, user_token, stock_item):
        assert _fetch(client, user_token, stock_item["id"], "nope").status_code == 404

    def test_wrong_bitza_404(self, client, user_token, stock_item, default_project):
        other = make_exact_stock(client, user_token, default_project.id, name="Other")
        image = _upload(client, user_token, stock_item["id"]).json()
        assert _fetch(client, user_token, other["id"], image["id"]).status_code == 404

    def test_file_missing_from_disk_404(self, client, user_token, stock_item, upload_dir):
        image = _upload(client, user_token, stock_item["id"]).json()
        for f in _files_on_disk(upload_dir):
            f.unlink()
        assert _fetch(client, user_token, stock_item["id"], image["id"]).status_code == 404

    def test_requires_auth(self, client, user_token, stock_item):
        image = _upload(client, user_token, stock_item["id"]).json()
        resp = client.get(f"{BASE}/{stock_item['id']}/images/{image['id']}")
        assert resp.status_code in (401, 403)


# =========================================================================
# Primary image, list, delete (existing behaviour, previously untested)
# =========================================================================

class TestPrimaryListDelete:
    def test_first_image_is_primary_regardless_of_flag(self, client, user_token, stock_item):
        first = _upload(client, user_token, stock_item["id"], is_primary="false").json()
        second = _upload(client, user_token, stock_item["id"], filename="b.png").json()
        assert first["is_primary"] is True
        assert second["is_primary"] is False

    def test_uploading_with_is_primary_takes_over(self, client, user_token, stock_item):
        _upload(client, user_token, stock_item["id"])
        newer = _upload(client, user_token, stock_item["id"], is_primary="true").json()
        listed = client.get(f"{BASE}/{stock_item['id']}/images", headers=auth(user_token)).json()
        assert [i["id"] for i in listed if i["is_primary"]] == [newer["id"]]

    def test_deleting_the_primary_promotes_a_remaining_image(
        self, client, user_token, stock_item, upload_dir
    ):
        first = _upload(client, user_token, stock_item["id"]).json()
        second = _upload(client, user_token, stock_item["id"], filename="b.png").json()
        resp = client.delete(
            f"{BASE}/{stock_item['id']}/images/{first['id']}", headers=auth(user_token)
        )
        assert resp.status_code == 204
        assert len(_files_on_disk(upload_dir)) == 1
        listed = client.get(f"{BASE}/{stock_item['id']}/images", headers=auth(user_token)).json()
        assert [(i["id"], i["is_primary"]) for i in listed] == [(second["id"], True)]
