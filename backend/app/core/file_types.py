"""
Content sniffing for uploaded documents (datasheets, SDS/MSDS, manuals).

The client's claimed Content-Type and filename are never trusted: what a
file *is* is decided here from its leading bytes (and, for ZIP containers,
its member names). The result is what gets stored as the document's
``content_type``, served back on download, and used to pick a safe on-disk
extension.

Policy is a strict allow-list. Anything not recognised is rejected rather
than stored as "unknown". The accepted set is the ``DetectedType`` constants
below; to accept another format, add a constant, a signature test in
``detect_document_type`` and (if it is not a plain ZIP/text variant) a test.

Deliberately NOT accepted: HTML, XML and SVG (script-capable if ever served
inline), executables, legacy binary Office files (``.doc``/``.xls``/``.ppt``;
convert to PDF or OOXML), and anything unrecognised. This is a sanity check on
the first few KB, not a malware scan, and it does not validate the whole file.
"""

import codecs
import unicodedata
import zipfile
from dataclasses import dataclass
from pathlib import Path

# How much of the file is examined. PDF headers may legally sit anywhere in
# the first 1024 bytes; the rest is margin for the text heuristic.
SNIFF_BYTES = 8192
_PDF_HEADER_WINDOW = 1024


@dataclass(frozen=True)
class DetectedType:
    media_type: str
    # Extension used on disk when the client's own extension is missing or
    # doesn't belong to this type.
    extension: str
    # Client-supplied extensions that are consistent with this type and so
    # may be kept on disk.
    extensions: frozenset[str]


PDF = DetectedType("application/pdf", ".pdf", frozenset({".pdf"}))
PNG = DetectedType("image/png", ".png", frozenset({".png"}))
JPEG = DetectedType("image/jpeg", ".jpg", frozenset({".jpg", ".jpeg"}))
GIF = DetectedType("image/gif", ".gif", frozenset({".gif"}))
WEBP = DetectedType("image/webp", ".webp", frozenset({".webp"}))
ZIP = DetectedType("application/zip", ".zip", frozenset({".zip"}))
DOCX = DetectedType(
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".docx",
    frozenset({".docx"}),
)
XLSX = DetectedType(
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xlsx",
    frozenset({".xlsx"}),
)
PPTX = DetectedType(
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".pptx",
    frozenset({".pptx"}),
)
ODT = DetectedType("application/vnd.oasis.opendocument.text", ".odt", frozenset({".odt"}))
ODS = DetectedType("application/vnd.oasis.opendocument.spreadsheet", ".ods", frozenset({".ods"}))
ODP = DetectedType(
    "application/vnd.oasis.opendocument.presentation", ".odp", frozenset({".odp"})
)
TEXT = DetectedType("text/plain", ".txt", frozenset({".txt", ".csv", ".md", ".log"}))

ALL_TYPES: tuple[DetectedType, ...] = (
    PDF, PNG, JPEG, GIF, WEBP, ZIP, DOCX, XLSX, PPTX, ODT, ODS, ODP, TEXT,
)
ACCEPTED_MEDIA_TYPES: frozenset[str] = frozenset(t.media_type for t in ALL_TYPES)

ACCEPTED_DESCRIPTION = (
    "PDF, PNG, JPEG, GIF, WebP, ZIP, Word/Excel/PowerPoint (.docx/.xlsx/.pptx), "
    "OpenDocument (.odt/.ods/.odp) and plain-text (.txt/.csv/.md/.log) files"
)

_OOXML_ROOTS = {"word/": DOCX, "xl/": XLSX, "ppt/": PPTX}
_ODF_MIMETYPES = {t.media_type: t for t in (ODT, ODS, ODP)}
_TEXT_WHITESPACE = "\t\n\r\f"


class UnsupportedFileType(ValueError):
    """The file isn't one of the accepted types. ``str(exc)`` is safe to show
    to the client."""


def detect_document_type(path: Path) -> DetectedType:
    """Classify the file at ``path`` from its content. Raises
    ``UnsupportedFileType`` if it isn't an accepted type."""
    with path.open("rb") as fh:
        head = fh.read(SNIFF_BYTES)
    # If the whole file fit in the sample, a dangling partial UTF-8 sequence
    # at the end is an error; otherwise it's just where the sample was cut.
    whole_file = path.stat().st_size <= SNIFF_BYTES

    # Fixed signatures at offset 0 first...
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return GIF
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return WEBP
    if head.startswith(b"PK\x03\x04"):
        return _classify_zip(path)
    # ...then PDF, whose header may be preceded by a little junk (this is
    # what PDF readers accept too). A plain-text file that merely mentions
    # "%PDF-" early on would be labelled PDF here; that is harmless.
    if b"%PDF-" in head[:_PDF_HEADER_WINDOW]:
        return PDF

    if _decodes_as_text(head, whole_file=whole_file):
        if _starts_with_markup(head):
            raise UnsupportedFileType(
                "This looks like a web page or markup file (HTML/XML/SVG), not a "
                "document. If you downloaded it from a website, the site may have "
                "returned an error page instead of the file."
            )
        return TEXT

    raise UnsupportedFileType(
        f"Unsupported or unrecognised file type. Accepted: {ACCEPTED_DESCRIPTION}."
    )


def _decodes_as_text(head: bytes, *, whole_file: bool) -> bool:
    """UTF-8 text with no NULs and no control characters other than ordinary
    whitespace. (UTF-16 text contains NULs and is therefore not accepted.)"""
    if b"\x00" in head:
        return False
    decoder = codecs.getincrementaldecoder("utf-8")()
    try:
        text = decoder.decode(head, final=whole_file)
    except UnicodeDecodeError:
        return False
    return not any(
        unicodedata.category(ch) == "Cc" and ch not in _TEXT_WHITESPACE for ch in text
    )


def _starts_with_markup(head: bytes) -> bool:
    text = head.decode("utf-8", errors="ignore").lstrip("\ufeff \t\r\n\f")
    return text.startswith("<")


def _classify_zip(path: Path) -> DetectedType:
    """Tell OOXML and OpenDocument files apart from a plain ZIP by looking at
    member names only; nothing is extracted or decompressed beyond ODF's tiny
    ``mimetype`` member."""
    try:
        with zipfile.ZipFile(path) as zf:
            names = zf.namelist()
            if "mimetype" in names:
                try:
                    with zf.open("mimetype") as member:
                        declared = member.read(100).decode("ascii", errors="ignore").strip()
                except (RuntimeError, NotImplementedError):  # encrypted / odd compression
                    declared = ""
                return _ODF_MIMETYPES.get(declared, ZIP)
            if "[Content_Types].xml" in names:
                for root, detected in _OOXML_ROOTS.items():
                    if any(name.startswith(root) for name in names):
                        return detected
            return ZIP
    except zipfile.BadZipFile as exc:
        raise UnsupportedFileType(
            "This ZIP-based file is corrupt or incomplete (could not read its contents list)."
        ) from exc
