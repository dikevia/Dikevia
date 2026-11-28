"""Fail-closed malware scanning and bounded text extraction for private documents."""
from __future__ import annotations

import hashlib
import socket
import struct
import zipfile
from dataclasses import dataclass
from io import BytesIO
from defusedxml import ElementTree


class ScannerUnavailable(RuntimeError):
    pass


class MalwareDetected(RuntimeError):
    pass


class OCRUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class ScanResult:
    status: str
    engine: str


def scan_with_clamav(data: bytes, host: str, port: int = 3310, timeout: float = 8.0) -> ScanResult:
    """Use clamd INSTREAM. No scanner, malformed response, or timeout is a hard failure."""
    if not host:
        raise ScannerUnavailable("ClamAV is not configured")
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            sock.sendall(b"zINSTREAM\0")
            view = memoryview(data)
            for offset in range(0, len(view), 1024 * 1024):
                chunk = view[offset:offset + 1024 * 1024]
                sock.sendall(struct.pack("!I", len(chunk)))
                sock.sendall(chunk)
            sock.sendall(struct.pack("!I", 0))
            response = bytearray()
            while len(response) < 4096:
                part = sock.recv(1024)
                if not part:
                    break
                response.extend(part)
                if b"\0" in part or b"\n" in part:
                    break
    except (OSError, TimeoutError) as exc:
        raise ScannerUnavailable("ClamAV scan could not be completed") from exc

    answer = bytes(response).strip(b"\0\r\n").decode("utf-8", "replace")
    if answer.endswith(": OK") or answer == "OK":
        return ScanResult(status="CLEAN", engine="ClamAV")
    if "FOUND" in answer:
        raise MalwareDetected("Malware detected by ClamAV")
    raise ScannerUnavailable(f"Unexpected ClamAV response: {answer[:200]}")


def extract_document_text(data: bytes, mime: str, max_chars: int = 2_000_000) -> tuple[str, str]:
    """Extract text without executing embedded content. Returns (text, status)."""
    try:
        if mime == "application/pdf":
            from pypdf import PdfReader
            reader = PdfReader(BytesIO(data), strict=False)
            if reader.is_encrypted:
                return "", "ENCRYPTED"
            parts: list[str] = []
            pages_needing_ocr: list[int] = []
            total = 0
            for page_index, page in enumerate(reader.pages):
                value = page.extract_text() or ""
                if value.strip():
                    remaining = max_chars - total
                    if remaining <= 0:
                        break
                    parts.append(value[:remaining])
                    total += min(len(value), remaining)
                else:
                    pages_needing_ocr.append(page_index)

            ocr_status = "NOT_NEEDED"
            if pages_needing_ocr and total < max_chars:
                page_limit = 10
                selected_pages = pages_needing_ocr[:page_limit]
                try:
                    ocr_text, ocr_failed = _ocr_pdf_pages(data, selected_pages, max_chars - total)
                    if ocr_text:
                        parts.append(ocr_text)
                        total += len(ocr_text)
                        ocr_status = "PARTIAL_OCR_LIMIT" if len(pages_needing_ocr) > page_limit else "OCR_EXTRACTED"
                    elif ocr_failed:
                        ocr_status = "OCR_FAILED"
                    else:
                        ocr_status = "OCR_NO_TEXT"
                    if len(pages_needing_ocr) > page_limit and not ocr_text:
                        ocr_status = "OCR_LIMIT"
                except OCRUnavailable:
                    ocr_status = "PARTIAL_OCR_UNAVAILABLE" if total else "OCR_UNAVAILABLE"

            text = "\n\n".join(parts).strip()
            if ocr_status != "NOT_NEEDED":
                if not text:
                    return "", ocr_status
                if ocr_status != "OCR_EXTRACTED":
                    return text[:max_chars], ocr_status
        elif mime in {"image/jpeg", "image/png", "image/webp"}:
            try:
                from PIL import Image, ImageOps
                import pytesseract
                with Image.open(BytesIO(data)) as source_image:
                    if source_image.width * source_image.height > 40_000_000:
                        return "", "IMAGE_TOO_LARGE"
                    image = ImageOps.exif_transpose(source_image).convert("RGB")
                image.thumbnail((3200, 3200))
                try:
                    text = pytesseract.image_to_string(
                        image, lang="fra+eng", config="--psm 6", timeout=8,
                    )[:max_chars].strip()
                finally:
                    image.close()
            except ImportError as exc:
                raise OCRUnavailable("Image OCR dependencies are unavailable") from exc
            except Exception as exc:
                if exc.__class__.__name__ in {"TesseractNotFoundError", "TesseractError"}:
                    raise OCRUnavailable("Image OCR engine is unavailable") from exc
                return "", "OCR_FAILED"
        elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            with zipfile.ZipFile(BytesIO(data)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > 20 * 1024 * 1024:
                    return "", "TOO_LARGE_TO_EXTRACT"
                # ElementTree is imported from defusedxml, not the standard library.
                root = ElementTree.fromstring(archive.read("word/document.xml"))  # nosec B314
                namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
                paragraphs = []
                for paragraph in root.iter(namespace + "p"):
                    value = "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
                    if value:
                        paragraphs.append(value)
                text = "\n".join(paragraphs)[:max_chars].strip()
        else:
            return "", "UNSUPPORTED"
    except Exception:
        return "", "FAILED"

    if not text:
        return "", "NO_TEXT"
    status = "OCR_EXTRACTED" if mime == "application/pdf" and ocr_status == "OCR_EXTRACTED" else "EXTRACTED"
    return text[:max_chars], status



def _ocr_pdf_pages(data: bytes, page_indices: list[int], max_chars: int) -> tuple[str, bool]:
    """OCR only pages with no text, with strict page, time and output bounds."""
    try:
        import pypdfium2 as pdfium
        import pytesseract
    except ImportError as exc:
        raise OCRUnavailable("Local OCR dependencies are unavailable") from exc

    document = None
    extracted: list[str] = []
    total = 0
    failed = False
    try:
        document = pdfium.PdfDocument(data)
        for page_index in page_indices:
            if total >= max_chars:
                break
            page = bitmap = image = None
            try:
                page = document[page_index]
                bitmap = page.render(scale=1.5)
                image = bitmap.to_pil()
                value = pytesseract.image_to_string(image, lang="fra+eng", config="--psm 6", timeout=3).strip()
                if value:
                    value = value[:max_chars - total]
                    extracted.append(value)
                    total += len(value)
            except Exception as exc:
                if exc.__class__.__name__ == "TesseractNotFoundError":
                    raise OCRUnavailable("Local Tesseract executable is unavailable") from exc
                failed = True
            finally:
                for resource in (image, bitmap, page):
                    close = getattr(resource, "close", None)
                    if callable(close):
                        close()
    except OCRUnavailable:
        raise
    except Exception:
        failed = True
    finally:
        close = getattr(document, "close", None)
        if callable(close):
            close()
    return "\n\n".join(extracted), failed


def document_sha256_matches(data: bytes, expected: str | None) -> bool:
    """Return whether stored bytes match the immutable digest recorded at upload."""
    if not expected or len(expected) != 64:
        return False
    return hashlib.sha256(data).hexdigest() == expected.lower()
