"""Render the PWA icons in public/ from the favicon's geometry.

No image library needed: a 4x-supersampled rasteriser writes plain PNGs via
zlib. Re-run after changing the mark: `python3 web/scripts/make-icons.py`.
"""
import struct
import zlib
from pathlib import Path

PUBLIC = Path(__file__).resolve().parent.parent / "public"
BG = (0x0B, 0x0D, 0x10)
FG = (0x34, 0xD3, 0x99)
# favicon.svg bars on a 32-unit canvas: (x, y, w, h), fully rounded ends.
BARS = [(6, 8, 20, 3.8), (9.9, 14, 12.2, 3.8), (13.8, 20, 4.4, 3.8)]
SS = 4


def in_rrect(px, py, x, y, w, h, r):
    cx = min(max(px, x + r), x + w - r)
    cy = min(max(py, y + r), y + h - r)
    return x <= px <= x + w and y <= py <= y + h and (px - cx) ** 2 + (py - cy) ** 2 <= r * r


def render(size, *, corner, inset):
    """corner: bg corner radius in 32-units (0 = full bleed, for maskable).
    inset: fraction of the canvas the mark is shrunk into (maskable safe zone)."""
    scale = size / 32
    rows = []
    for j in range(size):
        row = bytearray([0])
        for i in range(size):
            bg = fg = 0
            for sj in range(SS):
                for si in range(SS):
                    u = (i + (si + 0.5) / SS) / scale
                    v = (j + (sj + 0.5) / SS) / scale
                    if corner and not in_rrect(u, v, 0, 0, 32, 32, corner):
                        continue
                    bg += 1
                    mu = 16 + (u - 16) / inset
                    mv = 16 + (v - 16) / inset
                    if any(in_rrect(mu, mv, x, y, w, h, h / 2) for x, y, w, h in BARS):
                        fg += 1
            n = SS * SS
            a = bg / n
            t = fg / bg if bg else 0
            rgb = [round(BG[k] + (FG[k] - BG[k]) * t) for k in range(3)]
            row += bytes(rgb + [round(a * 255)])
        rows.append(bytes(row))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")


for name, size, corner, inset in [
    ("pwa-192.png", 192, 7, 1.0),
    ("pwa-512.png", 512, 7, 1.0),
    ("pwa-maskable-512.png", 512, 0, 0.8),
    ("apple-touch-icon.png", 180, 0, 0.85),
]:
    (PUBLIC / name).write_bytes(render(size, corner=corner, inset=inset))
    print("wrote", name)
