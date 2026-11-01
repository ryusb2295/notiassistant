"""첨부파일에서 텍스트를 뽑는다. PDF와 이미지는 Claude가 원본을 직접 읽는다."""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
import zlib

import olefile
from openpyxl import load_workbook
from pypdf import PdfReader

IMAGE_MEDIA_TYPES = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}
TEXT_EXTENSIONS = {"hwp", "hwpx", "pdf", "xlsx", "xlsm", "txt"}
HWP_PARA_TEXT = 67
# 8 wchar를 차지하는 HWP 컨트롤 문자
HWP_WIDE_CONTROLS = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}


class UnsupportedAttachment(Exception):
    pass


def extract_text(ext: str, data: bytes) -> str:
    # 문서에 따라 UTF-8로 보낼 수 없는 surrogate 문자가 나올 수 있어 제거한다.
    return _extract(ext.lower(), data).encode("utf-8", "ignore").decode("utf-8")


def _extract(ext: str, data: bytes) -> str:
    if ext == "hwp":
        return hwp_text(data)
    if ext == "hwpx":
        return hwpx_text(data)
    if ext == "pdf":
        return pdf_text(data)
    if ext in ("xlsx", "xlsm"):
        return xlsx_text(data)
    if ext == "txt":
        return data.decode("utf-8", errors="replace")
    raise UnsupportedAttachment(ext)


def hwp_text(data: bytes) -> str:
    ole = olefile.OleFileIO(io.BytesIO(data))
    try:
        compressed = ole.openstream("FileHeader").read()[36] & 1
        sections = [e for e in ole.listdir() if e[0] == "BodyText"]
        sections.sort(key=lambda e: int(e[1].removeprefix("Section")))
        paragraphs: list[str] = []
        for entry in sections:
            raw = ole.openstream(entry).read()
            if compressed:
                raw = zlib.decompress(raw, -15)
            paragraphs.extend(_hwp_paragraphs(raw))
        if paragraphs:
            return "\n".join(paragraphs)
        # 배포용 문서는 본문이 암호화되어 미리보기 텍스트만 읽을 수 있다.
        if ole.exists("PrvText"):
            return ole.openstream("PrvText").read().decode("utf-16-le", errors="ignore")
        return ""
    finally:
        ole.close()


def _hwp_paragraphs(raw: bytes) -> list[str]:
    paragraphs = []
    pos = 0
    while pos + 4 <= len(raw):
        header = int.from_bytes(raw[pos:pos + 4], "little")
        pos += 4
        tag = header & 0x3FF
        size = header >> 20
        if size == 0xFFF:
            size = int.from_bytes(raw[pos:pos + 4], "little")
            pos += 4
        if tag == HWP_PARA_TEXT:
            text = _hwp_para_text(raw[pos:pos + size]).strip()
            if text:
                paragraphs.append(text)
        pos += size
    return paragraphs


def _hwp_para_text(chunk: bytes) -> str:
    out = []
    pos = 0
    while pos + 2 <= len(chunk):
        code = int.from_bytes(chunk[pos:pos + 2], "little")
        if code in HWP_WIDE_CONTROLS:
            pos += 16
            continue
        pos += 2
        if code >= 32:
            out.append(chr(code))
        elif code == 9:
            out.append(" ")
    return "".join(out)


def hwpx_text(data: bytes) -> str:
    paragraphs: list[str] = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = sorted(n for n in archive.namelist()
                       if n.startswith("Contents/section") and n.endswith(".xml"))
        for name in names:
            root = ET.fromstring(archive.read(name))
            for para in root.iter():
                if _local(para.tag) != "p":
                    continue
                # 표 셀은 자체 문단이라 여기서는 문단 바로 아래 run만 읽어 중복을 막는다.
                text = "".join(
                    t.text or ""
                    for run in para if _local(run.tag) == "run"
                    for t in run if _local(t.tag) == "t"
                ).strip()
                if text:
                    paragraphs.append(text)
    return "\n".join(paragraphs)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def pdf_text(data: bytes) -> str:
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages).strip()


def xlsx_text(data: bytes) -> str:
    book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    lines = []
    for sheet in book.worksheets:
        lines.append(f"[{sheet.title}]")
        for row in sheet.iter_rows(values_only=True):
            cells = [str(c) for c in row if c is not None]
            if cells:
                lines.append(" | ".join(cells))
    book.close()
    return "\n".join(lines)
