"""앱 아이콘 PNG를 만든다. `python frontend/scripts/make_icons.py`로 실행한다."""
import struct
import zlib
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent.parent / "public"
BLUE = (0x24, 0x53, 0xD6)
WHITE = (255, 255, 255)
# 로고의 세 줄. (시작 x, 끝 x, 중심 y) 비율
BARS = ((0.27, 0.73, 0.33), (0.27, 0.60, 0.50), (0.27, 0.50, 0.67))
THICKNESS = 0.055


def inside_bar(x: float, y: float) -> bool:
    for start, end, center in BARS:
        nearest = min(max(x, start), end)
        if (x - nearest) ** 2 + (y - center) ** 2 <= (THICKNESS) ** 2:
            return True
    return False


def pixel(x: int, y: int, size: int) -> bytes:
    # 4배 샘플링으로 가장자리를 부드럽게 한다.
    hits = sum(
        inside_bar((x + (i + 0.5) / 4) / size, (y + (j + 0.5) / 4) / size)
        for i in range(4) for j in range(4)
    )
    ratio = hits / 16
    return bytes(round(b + (w - b) * ratio) for b, w in zip(BLUE, WHITE))


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png(size: int) -> bytes:
    rows = b"".join(b"\0" + b"".join(pixel(x, y, size) for x in range(size)) for y in range(size))
    header = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))


for name, size in (("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)):
    (PUBLIC / name).write_bytes(png(size))
