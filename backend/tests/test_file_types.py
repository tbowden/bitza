"""
Unit tests for app.core.file_types — content sniffing of uploaded documents.

These exercise the detector directly on files in pytest's tmp_path; the
upload endpoint's use of it (415s, stored type, on-disk extension, cleanup)
is covered in test_documents.py.
"""

import io
import zipfile

import pytest

from app.core import file_types
from app.core.file_types import (
    ACCEPTED_MEDIA_TYPES,
    ALL_TYPES,
    DOCX,
    GIF,
    IMAGE_TYPES,
    JPEG,
    ODP,
    ODS,
    ODT,
    PDF,
    PNG,
    PPTX,
    SNIFF_BYTES,
    TEXT,
    WEBP,
    XLSX,
    ZIP,
    UnsupportedFileType,
    detect_document_type,
    detect_image_type,
)


def _detect(tmp_path, content: bytes):
    path = tmp_path / "upload.part"
    path.write_bytes(content)
    return detect_document_type(path)


def _zip(members: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return buf.getvalue()


class TestBinarySignatures:
    def test_pdf_at_offset_zero(self, tmp_path):
        assert _detect(tmp_path, b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n") is PDF

    def test_pdf_with_a_little_leading_junk(self, tmp_path):
        assert _detect(tmp_path, b"\r\n  junk\x00\x01" + b"%PDF-1.4\n" + b"\x00" * 50) is PDF

    def test_pdf_header_beyond_the_first_kilobyte_is_not_a_pdf(self, tmp_path):
        with pytest.raises(UnsupportedFileType):
            _detect(tmp_path, b"\x00" * 2000 + b"%PDF-1.4")

    def test_png(self, tmp_path):
        assert _detect(tmp_path, b"\x89PNG\r\n\x1a\n" + b"\x00" * 8) is PNG

    def test_jpeg(self, tmp_path):
        assert _detect(tmp_path, b"\xff\xd8\xff\xe1" + b"\x00" * 8) is JPEG

    @pytest.mark.parametrize("header", [b"GIF87a", b"GIF89a"])
    def test_gif(self, tmp_path, header):
        assert _detect(tmp_path, header + b"\x01\x00\x01\x00") is GIF

    def test_webp(self, tmp_path):
        assert _detect(tmp_path, b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"\x00" * 8) is WEBP

    def test_riff_that_is_not_webp_is_rejected(self, tmp_path):
        # e.g. a WAV file
        with pytest.raises(UnsupportedFileType):
            _detect(tmp_path, b"RIFF\x24\x00\x00\x00WAVEfmt " + b"\x00" * 8)

    @pytest.mark.parametrize(
        "content",
        [
            b"MZ\x90\x00" + b"\x00" * 32,  # PE executable
            b"\x7fELF" + b"\x00" * 32,  # ELF executable
            b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 32,  # legacy Office / OLE2
            b"\x1f\x8b\x08\x00" + b"\x00" * 32,  # gzip
            b"\x00" * 64,
        ],
    )
    def test_other_binary_formats_are_rejected(self, tmp_path, content):
        with pytest.raises(UnsupportedFileType) as exc:
            _detect(tmp_path, content)
        assert "Accepted" in str(exc.value)


class TestZipContainers:
    def test_docx(self, tmp_path):
        assert _detect(tmp_path, _zip({"[Content_Types].xml": b"x", "word/document.xml": b"x"})) is DOCX

    def test_xlsx(self, tmp_path):
        assert _detect(tmp_path, _zip({"[Content_Types].xml": b"x", "xl/workbook.xml": b"x"})) is XLSX

    def test_pptx(self, tmp_path):
        content = _zip({"[Content_Types].xml": b"x", "ppt/presentation.xml": b"x"})
        assert _detect(tmp_path, content) is PPTX

    @pytest.mark.parametrize(
        ("mimetype", "expected"),
        [
            (b"application/vnd.oasis.opendocument.text", ODT),
            (b"application/vnd.oasis.opendocument.spreadsheet", ODS),
            (b"application/vnd.oasis.opendocument.presentation", ODP),
            (b"application/vnd.oasis.opendocument.graphics", ZIP),  # not accepted specially
            (b"something else entirely", ZIP),
        ],
    )
    def test_opendocument_by_mimetype_member(self, tmp_path, mimetype, expected):
        assert _detect(tmp_path, _zip({"mimetype": mimetype, "content.xml": b"x"})) is expected

    def test_content_types_without_a_known_root_is_a_plain_zip(self, tmp_path):
        assert _detect(tmp_path, _zip({"[Content_Types].xml": b"x", "other/a.xml": b"x"})) is ZIP

    def test_plain_zip(self, tmp_path):
        assert _detect(tmp_path, _zip({"a.txt": b"hello"})) is ZIP

    def test_member_names_are_not_confused_by_prefix(self, tmp_path):
        # "word/" must be a directory prefix; "wordlist.txt" is not Word content.
        content = _zip({"[Content_Types].xml": b"x", "wordlist.txt": b"x"})
        assert _detect(tmp_path, content) is ZIP

    def test_truncated_zip_is_rejected(self, tmp_path):
        good = _zip({"a.txt": b"hello" * 100})
        with pytest.raises(UnsupportedFileType) as exc:
            _detect(tmp_path, good[: len(good) // 2])
        assert "corrupt" in str(exc.value)

    def test_zip_signature_with_garbage_is_rejected(self, tmp_path):
        with pytest.raises(UnsupportedFileType):
            _detect(tmp_path, b"PK\x03\x04" + b"garbage" * 20)


class TestText:
    def test_plain_text(self, tmp_path):
        assert _detect(tmp_path, b"LM358 dual op-amp\r\nVcc: 3 V to 32 V\n") is TEXT

    def test_utf8_with_bom_and_non_ascii(self, tmp_path):
        assert _detect(tmp_path, "\ufeffDatenblätter µC — 5 Ω\n".encode()) is TEXT

    def test_csv_and_tabs_and_formfeeds_are_fine(self, tmp_path):
        assert _detect(tmp_path, b"part,qty\tnote\f\nLM358,10\n") is TEXT

    def test_utf8_sequence_cut_by_the_sample_boundary_is_accepted(self, tmp_path):
        # A big file whose 8 KiB sample ends in the middle of a 2-byte character.
        content = ("a" + "é" * 5000).encode()
        assert len(content) > SNIFF_BYTES
        assert content[:SNIFF_BYTES][-1] >= 0xC0  # sample really ends on a lead byte
        assert _detect(tmp_path, content) is TEXT

    def test_dangling_utf8_lead_byte_in_a_small_file_is_rejected(self, tmp_path):
        with pytest.raises(UnsupportedFileType):
            _detect(tmp_path, b"abc\xc3")

    def test_invalid_utf8_is_rejected(self, tmp_path):
        with pytest.raises(UnsupportedFileType):
            _detect(tmp_path, b"caf\xe9 au lait")  # Latin-1, not UTF-8

    def test_utf16_text_is_rejected(self, tmp_path):
        with pytest.raises(UnsupportedFileType):
            _detect(tmp_path, "hello".encode("utf-16"))

    def test_control_characters_are_rejected(self, tmp_path):
        with pytest.raises(UnsupportedFileType):
            _detect(tmp_path, b"abc\x01\x02def")

    @pytest.mark.parametrize(
        "content",
        [
            b"<!DOCTYPE html><html></html>",
            b"  \n<html><body>Access denied</body></html>",
            b"<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'/>",
            b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>",
            "\ufeff<html>".encode(),
            b"<script>alert(1)</script>",
        ],
    )
    def test_markup_is_rejected_with_a_helpful_message(self, tmp_path, content):
        with pytest.raises(UnsupportedFileType) as exc:
            _detect(tmp_path, content)
        assert "web page" in str(exc.value)

    def test_text_that_merely_mentions_markup_later_is_fine(self, tmp_path):
        assert _detect(tmp_path, b"Notes: the <html> tag is not used here\n") is TEXT


class TestImageDetection:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, PNG),
            (b"\xff\xd8\xff\xdb" + b"\x00" * 8, JPEG),
            (b"GIF87a" + b"\x00" * 8, GIF),
            (b"GIF89a" + b"\x00" * 8, GIF),
            (b"RIFF\x24\x00\x00\x00WEBPVP8L" + b"\x00" * 8, WEBP),
        ],
    )
    def test_accepted_image_types(self, content, expected):
        assert detect_image_type(content) is expected

    @pytest.mark.parametrize(
        "content",
        [
            b"",
            b"%PDF-1.7\n",  # a valid *document*, but not an image
            b"just text",
            b"<svg xmlns='http://www.w3.org/2000/svg'/>",
            b"<!DOCTYPE html><html></html>",
            b"PK\x03\x04" + b"\x00" * 16,
            b"RIFF\x24\x00\x00\x00WAVEfmt ",
            b"GIF90a",
            b"\x89PNG",  # truncated signature
            b"\xff\xd8",  # truncated signature
        ],
    )
    def test_everything_else_is_rejected(self, content):
        with pytest.raises(UnsupportedFileType) as exc:
            detect_image_type(content)
        assert "image" in str(exc.value)

    def test_image_types_are_a_subset_of_the_document_types(self):
        assert set(IMAGE_TYPES) <= set(ALL_TYPES)
        assert {t.media_type for t in IMAGE_TYPES} == file_types.ACCEPTED_IMAGE_MEDIA_TYPES

    def test_document_and_image_detection_agree_on_images(self, tmp_path):
        for content, expected in [
            (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, PNG),
            (b"\xff\xd8\xff\xe0" + b"\x00" * 8, JPEG),
        ]:
            assert _detect(tmp_path, content) is detect_image_type(content) is expected


class TestTable:
    def test_accepted_media_types_match_the_table(self):
        assert {t.media_type for t in ALL_TYPES} == ACCEPTED_MEDIA_TYPES
        assert len(ACCEPTED_MEDIA_TYPES) == len(ALL_TYPES)

    @pytest.mark.parametrize("detected", ALL_TYPES, ids=lambda t: t.media_type)
    def test_each_type_has_a_consistent_extension_set(self, detected):
        assert detected.extension in detected.extensions
        assert all(ext.startswith(".") and ext == ext.lower() for ext in detected.extensions)
        # No script-capable extension can ever be considered "consistent".
        assert not detected.extensions & {".html", ".htm", ".svg", ".xml", ".js", ".php"}

    def test_media_types_fit_the_content_type_column(self):
        # bitza_documents.content_type is String(100)
        assert all(len(t.media_type) <= 100 for t in ALL_TYPES)

    def test_sniff_window_covers_the_pdf_header_window(self):
        assert file_types.SNIFF_BYTES >= file_types._PDF_HEADER_WINDOW
