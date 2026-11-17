"""Fail-closed malware scanning and bounded text extraction for private documents."""
from __future__ import annotations

import socket
import struct
import zipfile
from dataclasses import dataclass
from io import BytesIO
from xml.etree import ElementTree


class ScannerUnavailable(RuntimeError):
    pass


class MalwareDetected(RuntimeError):
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
            total = 0
            for page in reader.pages:
                value = page.extract_text() or ""
                if value:
                    remaining = max_chars - total
                    if remaining <= 0:
                        break
                    parts.append(value[:remaining])
                    total += min(len(value), remaining)
            text = "\n\n".join(parts).strip()
        elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            with zipfile.ZipFile(BytesIO(data)) as archive:
                info = archive.getinfo("word/document.xml")
                if info.file_size > 20 * 1024 * 1024:
                    return "", "TOO_LARGE_TO_EXTRACT"
                root = ElementTree.fromstring(archive.read("word/document.xml"))
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
    return text[:max_chars], "EXTRACTED"
