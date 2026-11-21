"""Writes examples/village_plan.png, a painted layout for examples/village_plan.md.

Plain Python (no Blender): python examples/make_village_plan.py
Row 0 of the picture is the top of the map (+Y, the back).
"""

import os
import struct
import zlib

W = H = 128
COL = {"ground": (255, 255, 255), "water": (0, 0, 255), "forest": (0, 128, 0), "road": (128, 128, 128),
       "house": (255, 0, 0), "rock": (128, 64, 0), "field": (255, 160, 0),
       "path": (210, 180, 140), "wall": (64, 64, 64), "bridge": (255, 0, 255)}


def kind(x, y):
    if abs(y - (96 - x * 0.35)) < 6:                      # river across the lower half
        return "bridge" if abs(x - 64) < 3 else "water"   # the north-south road crosses it
    if abs(x - 64) < 3 or abs(y - 60) < 2:                # crossing roads
        return "road"
    for hx, hy in ((52, 50), (76, 50), (52, 70), (38, 50), (90, 50)):
        if abs(x - hx) < 4 and abs(y - hy) < 3:
            return "house"
    if 30 <= x <= 33 and 30 <= y < 48:                    # path north from the west house
        return "path"
    if 72 < x < 120 and y in (74, 75) or x in (71, 72) and 74 <= y < 87:   # wall along the fields
        return "wall"
    if 80 <= x <= 118 and abs(y - 10 - (x - 80) * 0.8) < 1.0:   # diagonal paddock wall, north-east
        return "wall"
    if x < 40 and y > 66:                                 # forest, lower left
        return "forest"
    if x > 100 and y > 80:                                # rocky corner
        return "rock"
    if 72 < x < 120 and 75 < y < 110:                     # fields
        return "field"
    return "ground"


rows = b"".join(b"\x00" + bytes(c for x in range(W) for c in COL[kind(x, y)]) for y in range(H))


def chunk(tag, data):
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
       + chunk(b"IDAT", zlib.compress(rows, 9)) + chunk(b"IEND", b""))
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "village_plan.png")
with open(out, "wb") as f:
    f.write(png)
print("wrote", out)
