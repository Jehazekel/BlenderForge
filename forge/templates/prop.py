"""Props: crates, barrels, chests, rocks, weapons, furniture, fences, lights.

`size` is the longest dimension in metres. To add a prop, write a function
`_name(mb, s, m, spec)` and list it in PROPS.
"""

import math

from mathutils import Matrix, Vector

from .. import parts, static
from ..meshkit import TAU, MeshBuilder, Rng, V, X, Y, Z, hash01, name_seed


class Mats:
    """Lazy material set so each prop only creates what it uses."""

    def __init__(self, ctx, spec):
        self.ctx, self.spec, self.cache = ctx, spec, {}

    def get(self, label, kind, default, key=None, **kw):
        if label not in self.cache:
            self.cache[label] = self.ctx.mat(label, kind, self.spec.color(key or label.lower() + "_color", default), **kw)
        return self.cache[label]

    @property
    def wood(self):
        return self.get("Wood", "wood", "#8a5e3b", key="color")

    @property
    def dark_wood(self):
        return self.get("DarkWood", "wood", "#4f3521", key="trim_color")

    @property
    def metal(self):
        return self.get("Metal", "metal", "#8e969e", key="metal_color", roughness=0.35)

    @property
    def stone(self):
        return self.get("Stone", "stone", "#86837d", key="color", blocks=False)


def _crate(mb, s, m, spec):
    mb.box((0, 0, s / 2), (s * 0.92, s * 0.92, s * 0.92), m.wood)
    e = s * 0.09
    for a in (-1, 1):
        for b in (-1, 1):
            mb.box((a * (s - e) / 2, b * (s - e) / 2, s / 2), (e, e, s), m.dark_wood)
            mb.box((a * (s - e) / 2, 0, s / 2 + b * (s - e) / 2), (e, s, e), m.dark_wood)
            mb.box((0, a * (s - e) / 2, s / 2 + b * (s - e) / 2), (s, e, e), m.dark_wood)
    return 0.012 * s


def _barrel(mb, s, m, spec):
    r = s * 0.36
    prof = [(r * 0.82, 0), (r * 0.95, s * 0.2), (r, s * 0.5), (r * 0.95, s * 0.8), (r * 0.82, s)]
    mb.lathe(prof, n=16, mat=m.wood, cap_start=True, cap_end=True)
    for z, rr in ((s * 0.18, r * 0.95), (s * 0.82, r * 0.95), (s * 0.5, r * 1.0)):
        mb.lathe([(rr, z - s * 0.03), (rr + s * 0.012, z - s * 0.03), (rr + s * 0.012, z + s * 0.03), (rr, z + s * 0.03)],
                 n=16, mat=m.metal)
    return 0.0


def _chest(mb, s, m, spec):
    w, d, h = s, s * 0.6, s * 0.4
    mb.box((0, 0, h / 2), (w, d, h), m.wood)
    arc = [V(-w / 2, math.cos(a) * d / 2, h + math.sin(a) * d * 0.4) for a in
           [math.pi * k / 8 for k in range(9)]]
    mb.extrude(arc, X * w, m.wood)
    for x in (-w * 0.36, w * 0.36):
        mb.box((x, 0, h / 2), (w * 0.07, d * 1.03, h * 1.02), m.metal)
        band = [V(x - w * 0.035, math.cos(a) * d * 0.515, h + math.sin(a) * d * 0.415) for a in
                [math.pi * k / 8 for k in range(9)]]
        mb.extrude(band, X * w * 0.07, m.metal)
    gold = m.get("Lock", "metal", "#d4a637", roughness=0.25)
    mb.box((0, -d / 2 - 0.01 * s, h * 0.92), (w * 0.12, 0.03 * s, h * 0.3), gold)
    return 0.01 * s


def _rock(mb, s, m, spec):
    seed = spec.integer("seed", name_seed(spec.name) % 997)
    start = mb.count
    with mb.part(flat=True):
        mb.sphere((0, 0, s * 0.3), (s * 0.5, s * 0.42, s * 0.36), m.stone, n=8, m=5)
    mb.bm.verts.ensure_lookup_table()
    c = Vector((0, 0, s * 0.3))
    for i in range(start, mb.count):
        v = mb.bm.verts[i]
        v.co = c + (v.co - c) * (0.75 + 0.5 * hash01(seed, i))
        v.co.z = max(v.co.z, 0.0)
    return 0.0


def _sword(mb, s, m, spec):
    with mb.part(xform=Matrix.Translation((0, 0, s * 0.16))):
        parts.sword(mb, s, m.get("Blade", "metal", "#cfd6de", roughness=0.18),
                    m.get("Hilt", "metal", "#c9a03a"), m.dark_wood)
    return 0.0


def _shield(mb, s, m, spec):
    style = spec.choice("style", ("round", "heater"), "round")
    with mb.part(xform=Matrix.Translation((0, 0, s * (0.5 if style == "round" else 0.55)))):
        parts.shield(mb, s * 0.5 if style == "round" else s * 0.46, m.get("Face", "wood", "#7a2e2e", key="color"),
                     m.metal, style)
    return 0.0


def _staff(mb, s, m, spec):
    parts.staff(mb, s * 0.93, m.wood, m.get("Gem", "emissive", "#58c8ff"))
    return 0.0


def _axe(mb, s, m, spec):
    with mb.part(xform=Matrix.Translation((0, 0, s * 0.15))):
        parts.axe(mb, s, m.metal, m.wood)
    return 0.0


def _table(mb, s, m, spec):
    h = s * 0.75
    mb.box((0, 0, h - 0.03 * s), (s, s * 0.6, 0.06 * s), m.wood)
    for a in (-1, 1):
        for b in (-1, 1):
            mb.box((a * s * 0.44, b * s * 0.24, (h - 0.06 * s) / 2), (0.07 * s, 0.07 * s, h - 0.06 * s), m.dark_wood)
    mb.box((0, 0, h - 0.1 * s), (s * 0.9, s * 0.5, 0.05 * s), m.dark_wood)
    return 0.008 * s


def _chair(mb, s, m, spec):
    w, sh = s * 0.45, s * 0.45
    mb.box((0, 0, sh), (w, w, 0.05 * s), m.wood)
    for a in (-1, 1):
        mb.box((a * w * 0.44, -w * 0.44, sh / 2), (0.05 * s, 0.05 * s, sh), m.dark_wood)
        mb.box((a * w * 0.44, w * 0.44, s / 2), (0.05 * s, 0.05 * s, s), m.dark_wood)
    for z in (s * 0.7, s * 0.9):
        mb.box((0, w * 0.44, z), (w, 0.03 * s, 0.1 * s), m.wood)
    return 0.006 * s


def _fence(mb, s, m, spec):
    n = max(2, int(round(s / 1.2)) + 1)
    h = spec.num("height", 1.1, 0.2, 10)
    for k in range(n):
        x = -s / 2 + k * s / (n - 1)
        mb.box((x, 0, h / 2), (0.12, 0.12, h), m.dark_wood)
        mb.fan(mb.ring(V(x, 0, h), X * 0.085, Y * 0.085, 4, phase=math.pi / 4), V(x, 0, h + 0.1), m.dark_wood)
    for z in (h * 0.35, h * 0.75):
        mb.box((0, 0, z), (s, 0.05, 0.11), m.wood)
    return 0.01


def _lantern(mb, s, m, spec):
    iron = m.get("Iron", "metal", "#1c1c1f", key="metal_color", roughness=0.5)
    glow = m.get("Glow", "emissive", "#ffc45a", strength=8.0)
    mb.cylinder(V(0, 0, 0), V(0, 0, s * 0.72), s * 0.022, n=8, mat=iron)
    mb.lathe([(s * 0.09, 0), (s * 0.05, s * 0.03), (s * 0.03, s * 0.06)], n=8, mat=iron, cap_start=True)
    z = s * 0.72
    mb.box((0, 0, z + s * 0.01), (s * 0.15, s * 0.15, s * 0.02), iron)
    mb.box((0, 0, z + s * 0.11), (s * 0.10, s * 0.10, s * 0.18), glow)
    for a in (-1, 1):
        for b in (-1, 1):
            mb.box((a * s * 0.06, b * s * 0.06, z + s * 0.11), (s * 0.015, s * 0.015, s * 0.2), iron)
    mb.fan(mb.ring(V(0, 0, z + s * 0.21), X * s * 0.11, Y * s * 0.11, 4, phase=math.pi / 4),
           V(0, 0, z + s * 0.29), iron)
    return 0.0


def _signpost(mb, s, m, spec):
    mb.box((0, 0, s / 2), (0.08 * s, 0.08 * s, s), m.dark_wood)
    mb.box((s * 0.18, -0.05 * s, s * 0.8), (s * 0.55, 0.03 * s, s * 0.18), m.wood)
    pts = [V(s * 0.45, -0.065 * s, s * 0.71), V(s * 0.56, -0.065 * s, s * 0.8), V(s * 0.45, -0.065 * s, s * 0.89)]
    mb.extrude(pts, Y * 0.03 * s, m.wood)
    return 0.004 * s


def _well(mb, s, m, spec):
    r = s * 0.32
    mb.lathe([(r, 0), (r, s * 0.35), (r * 0.78, s * 0.35), (r * 0.78, s * 0.05)], n=16, mat=m.stone)
    water = m.get("Water", "water", "#2a5a78")
    mb.lathe([(r * 0.78, s * 0.2), (0.001, s * 0.2)], n=16, mat=water)
    for a in (-1, 1):
        mb.box((a * r * 0.92, 0, s * 0.55), (0.06 * s, 0.06 * s, s * 0.6), m.dark_wood)
    mb.cylinder(V(-r, 0, s * 0.72), V(r, 0, s * 0.72), 0.03 * s, n=8, mat=m.dark_wood, hint=Z)
    roofm = m.get("Roof", "roof", "#7b3327")
    parts.gable_roof(mb, r * 2.4, r * 1.8, s * 0.82, s * 0.2, roofm, m.wood, overhang=0.04 * s, thick=0.03 * s)
    mb.cylinder(V(0, 0, s * 0.72), V(0, 0, s * 0.5), 0.008 * s, n=4, mat=m.dark_wood)
    mb.lathe([(0.05 * s, s * 0.40), (0.06 * s, s * 0.5)], n=8, mat=m.wood, cap_start=True)
    return 0.0


def _campfire(mb, s, m, spec):
    for k in range(8):
        a = TAU * k / 8
        mb.sphere((math.cos(a) * s * 0.42, math.sin(a) * s * 0.42, s * 0.06),
                  (s * 0.1, s * 0.09, s * 0.07), m.stone, n=6, m=3)
    for k in range(4):
        a = TAU * k / 4 + 0.4
        d = V(math.cos(a), math.sin(a), 0)
        mb.cylinder(d * s * 0.3 + Z * 0.04 * s, -d * s * 0.05 + Z * 0.28 * s, 0.045 * s, n=6, mat=m.dark_wood)
    flame = m.get("Flame", "emissive", "#ff7a1a", strength=12.0)
    core = m.get("FlameCore", "emissive", "#ffe08a", strength=18.0)
    with mb.part(flat=True):
        mb.fan(mb.ring(V(0, 0, s * 0.12), X * s * 0.16, Y * s * 0.16, 6), V(0.02 * s, 0, s * 0.62), flame)
        mb.fan(mb.ring(V(0, 0, s * 0.12), X * s * 0.09, Y * s * 0.09, 5), V(0, 0.01 * s, s * 0.42), core)
    return 0.0


PROPS = {
    "crate": (_crate, 1.0), "barrel": (_barrel, 1.0), "chest": (_chest, 0.9), "rock": (_rock, 1.2),
    "sword": (_sword, 1.0), "shield": (_shield, 0.8), "staff": (_staff, 1.8), "axe": (_axe, 0.9),
    "table": (_table, 1.4), "chair": (_chair, 1.0), "fence": (_fence, 4.0), "lantern": (_lantern, 2.4),
    "signpost": (_signpost, 1.8), "well": (_well, 2.6), "campfire": (_campfire, 1.0),
}
ALIASES = {"box": "crate", "boulder": "rock", "stone": "rock", "lamp": "lantern", "sign": "signpost",
           "fire": "campfire", "treasure_chest": "chest", "prop": "crate"}
NAMES = list(PROPS) + list(ALIASES)


def make(mb, kind, size, m, spec):
    fn, _ = PROPS[ALIASES.get(kind, kind)]
    return fn(mb, size, m, spec)


def build(spec, ctx, type_name):
    kind = ALIASES.get(type_name, type_name)
    fn, default_size = PROPS[kind]
    size = spec.num("size", default_size, 0.02, 200)
    spec.used.add("material")
    mb = MeshBuilder()
    bevel = fn(mb, size, Mats(ctx, spec), spec)
    return static.finish(ctx, spec, mb, bevel=bevel, sharp=40 if kind != "rock" else 180)
