"""Trees: oak (branching trunk + leaf clumps), pine (stacked cones), palm
(curved trunk + fronds) and a bare dead tree. Seeded, so repeatable."""

import math

from mathutils import Vector

from .. import static
from ..core import Entity
from ..meshkit import TAU, MeshBuilder, Rng, V, X, Y, Z, hash01, name_seed, path_sections

NAMES = ["oak", "tree", "pine", "fir", "palm", "dead_tree", "birch", "bush"]


def _trunk(mb, rng, height, radius, bark, lean=0.06, n=8, rings=5):
    pts, rad = [], []
    off = V(0, 0, 0)
    for k in range(rings + 1):
        u = k / rings
        off = off + V(rng.uniform(-lean, lean), rng.uniform(-lean, lean), 0) * height * (0.5 if k else 0)
        pts.append(V(off.x, off.y, u * height))
        rad.append(radius * (1.5 if k == 0 else 1.0 - 0.55 * u))
    mb.loft(path_sections(pts, rad, hint=Y), n=n, mat=bark)
    return pts, rad


def _blob(mb, rng, c, r, mat, seed, n=8, m=5, squash=0.85):
    """Leaf clump: a sphere with radial noise, flat shaded for a carved look."""
    start = mb.count
    with mb.part(flat=True):
        mb.sphere(c, (r, r, r * squash), mat, n=n, m=m)
    mb.bm.verts.ensure_lookup_table()
    c = Vector(c)
    for i in range(start, mb.count):
        v = mb.bm.verts[i]
        d = v.co - c
        v.co = c + d * (0.82 + 0.36 * hash01(seed, i))


def make_tree(mb, kind, height, seed, bark, leaf, extra=None):
    rng = Rng(seed)
    if kind in ("pine", "fir"):
        r = height * 0.035
        mb.cylinder(V(0, 0, 0), V(0, 0, height * 0.95), r * 1.3, r * 0.3, n=8, mat=bark)
        tiers = 5
        with mb.part(flat=True):
            for t in range(tiers):
                u = t / (tiers - 1)
                z = height * (0.22 + 0.60 * u)
                rad = height * (0.26 - 0.17 * u)
                h = height * (0.30 - 0.06 * u)
                ring = mb.ring(V(0, 0, z), X * rad, Y * rad, 10, phase=rng.uniform(0, 1))
                for i, v in enumerate(ring):
                    v.co.z += rng.uniform(-0.02, 0.02) * height
                    v.co.xy = v.co.xy * (0.9 + 0.2 * rng.random())
                mb.fan(ring, V(0, 0, z + h), leaf)
                mb.cap(ring, leaf)
    elif kind == "palm":
        n_seg = 7
        pts = [V(height * 0.16 * (k / n_seg) ** 2, 0, height * 0.82 * k / n_seg) for k in range(n_seg + 1)]
        rad = [height * 0.035 * (1.25 - 0.4 * k / n_seg) * (1.08 if k % 2 else 0.95) for k in range(n_seg + 1)]
        mb.loft(path_sections(pts, rad, hint=Y), n=8, mat=bark)
        top = pts[-1]
        fronds = 8
        with mb.part(flat=True):
            for f in range(fronds):
                a = TAU * f / fronds + rng.uniform(-0.2, 0.2)
                d = V(math.cos(a), math.sin(a), 0)
                side = V(-math.sin(a), math.cos(a), 0)
                length = height * rng.uniform(0.36, 0.46)
                prev = None
                for k in range(6):
                    u = k / 5
                    p = top + d * length * u + Z * length * (0.35 * u - 0.75 * u * u)
                    wdt = length * 0.11 * math.sin(math.pi * min(1.0, u * 0.9 + 0.1))
                    row = [mb.vert(p - side * wdt - Z * wdt * 0.5), mb.vert(p + Z * wdt * 0.2),
                           mb.vert(p + side * wdt - Z * wdt * 0.5)]
                    if prev:
                        mb.face([prev[0], prev[1], row[1], row[0]], leaf)
                        mb.face([prev[1], prev[2], row[2], row[1]], leaf)
                    prev = row
        if extra is not None:
            for k in range(3):
                a = TAU * k / 3
                mb.sphere(top + V(math.cos(a), math.sin(a), -0.6) * height * 0.035, height * 0.028, extra, n=6, m=3)
    elif kind == "bush":
        for k in range(5):
            a = TAU * k / 5
            c = V(math.cos(a), math.sin(a), 0) * height * 0.35 * (k > 0) + Z * height * 0.4
            _blob(mb, rng, c, height * rng.uniform(0.38, 0.52), leaf, seed + k)
    else:   # oak, tree, birch, dead_tree
        slim = kind == "birch"
        th = height * (0.5 if not slim else 0.6)
        pts, rad = _trunk(mb, rng, th, height * (0.05 if not slim else 0.03), bark)
        top = pts[-1]
        branches = 4 if kind != "dead_tree" else 6
        tips = [top + Z * height * 0.12]
        for b in range(branches):
            a = TAU * b / branches + rng.uniform(-0.4, 0.4)
            start = pts[-2 if b % 2 else -1]
            out = V(math.cos(a), math.sin(a), 0)
            length = height * rng.uniform(0.2, 0.3)
            p1 = start + out * length * 0.5 + Z * length * 0.45
            p2 = start + out * length + Z * length * rng.uniform(0.7, 1.0)
            r0 = rad[-1] * 0.8
            mb.loft(path_sections([start, p1, p2], [r0, r0 * 0.65, r0 * 0.3], hint=Y), n=6, mat=bark)
            tips.append(p2)
            if kind == "dead_tree":
                p3 = p2 + out * length * 0.5 + Z * length * 0.5
                mb.loft(path_sections([p2, p3], [r0 * 0.3, r0 * 0.08], hint=Y), n=4, mat=bark)
        if kind != "dead_tree":
            for i, t in enumerate(tips):
                r = height * (0.24 if i == 0 else rng.uniform(0.15, 0.21)) * (0.8 if slim else 1.0)
                _blob(mb, rng, t + Z * r * 0.3, r, leaf, seed + i * 7)


def build(spec, ctx, type_name):
    kind = "oak" if type_name == "tree" else type_name
    height = spec.num("height", {"bush": 1.2, "palm": 7.0, "pine": 8.0, "fir": 8.0}.get(kind, 6.0), 0.2, 120)
    seed = spec.integer("seed", name_seed(spec.name) % 9973 + ctx.seed)
    leaf_d = {"pine": "#2d5a3a", "fir": "#27503a", "palm": "#4c8a3a", "birch": "#8fb04a",
              "bush": "#4c7a35"}.get(kind, "#4a8032")
    bark_d = "#d8d4c8" if kind == "birch" else ("#8a7355" if kind == "palm" else "#5a4030")
    bark = ctx.mat("Bark", "wood", spec.color("trunk", bark_d))
    leaf = ctx.mat("Leaves", "foliage", spec.color("foliage", leaf_d), scale=6.0 / height)
    nut = ctx.mat("Coconut", "plain", (0.16, 0.10, 0.05, 1)) if kind == "palm" else None
    mb = MeshBuilder()
    make_tree(mb, kind, height, seed, bark, leaf, nut)
    obj = mb.to_object(spec.name, ctx.collection)
    return Entity(spec.name, obj, [obj])
