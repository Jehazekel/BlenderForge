"""Maps: a height-field terrain from seeded fractal noise or from an image,
coloured by height and slope, with water and scattered trees, rocks and houses.

An image given as the input file (or `heightmap: file.png`) drives the height
from its brightness; `colors: image` also paints the terrain with its pixels.

`layout: plan.png` is a painted plan: each pixel is matched to the nearest
`legend` colour (water, forest, road, house, rock, sand, field, path, wall, bridge). Water carves
the ground below the water line, forests and rock areas get the scattered trees
and rocks, each house blob gets one house, and roads, sand and fields tint the
ground. Image top is +Y (back), as with heightmaps.
"""

import math
import os
import re

import bpy
from mathutils import Vector

from ..core import Entity
from ..log import ForgeError, warn
from ..meshkit import MeshBuilder, Rng, V, fbm, smooth
from ..parser import Spec, srgb_to_linear
from . import house as house_tpl
from . import prop as prop_tpl
from . import tree as tree_tpl

# type: (relief, noise frequency, island falloff, valley, default water level 0..1)
PRESETS = {
    "terrain": (0.16, 2.2, 0.0, 0.0, 0.0),
    "hills": (0.14, 2.6, 0.0, 0.0, 0.0),
    "mountains": (0.42, 2.8, 0.0, 0.0, 0.0),
    "island": (0.22, 2.4, 1.0, 0.0, 0.30),
    "valley": (0.30, 2.2, 0.0, 1.0, 0.12),
    "plains": (0.04, 1.8, 0.0, 0.0, 0.0),
    "desert": (0.07, 1.6, 0.0, 0.0, 0.0),
}
NAMES = list(PRESETS) + ["map"]
PALETTES = {
    "default": [(0.0, "#c9b98a"), (0.08, "#5f8f3e"), (0.45, "#4c7a35"), (0.70, "#7b756a"), (0.9, "#f0f0f0")],
    "desert": [(0.0, "#d9c28a"), (0.5, "#c9a86a"), (0.85, "#b08a5a"), (1.0, "#e8d8b0")],
    "island": [(0.0, "#d8c690"), (0.12, "#6f9a44"), (0.55, "#4c7a35"), (0.85, "#6b6a5c"), (1.0, "#8a8578")],
}


class HeightImage:
    """Bilinear sampler over an image, shrunk first so pixel access stays cheap."""

    def __init__(self, path, line):
        try:
            img = bpy.data.images.load(path, check_existing=False)
        except RuntimeError:
            raise ForgeError("cannot load heightmap image '%s'" % path, line)
        w, h = img.size
        if w == 0 or h == 0:
            raise ForgeError("heightmap image '%s' is empty or unreadable" % path, line)
        if max(w, h) > 256:
            k = 256.0 / max(w, h)
            img.scale(max(2, int(w * k)), max(2, int(h * k)))
            w, h = img.size
        self.w, self.h = w, h
        self.px = list(img.pixels[:])
        self.ch = img.channels
        bpy.data.images.remove(img)

    def _at(self, x, y):
        i = (min(max(y, 0), self.h - 1) * self.w + min(max(x, 0), self.w - 1)) * self.ch
        p = self.px[i:i + self.ch]
        return (p[0], p[0], p[0]) if self.ch < 3 else (p[0], p[1], p[2])

    def color(self, u, v):
        fx, fy = u * (self.w - 1), v * (self.h - 1)
        x0, y0 = int(fx), int(fy)
        tx, ty = fx - x0, fy - y0
        a, b, c, d = self._at(x0, y0), self._at(x0 + 1, y0), self._at(x0, y0 + 1), self._at(x0 + 1, y0 + 1)
        return tuple((a[i] * (1 - tx) + b[i] * tx) * (1 - ty) + (c[i] * (1 - tx) + d[i] * tx) * ty
                     for i in range(3))

    def height(self, u, v):
        r, g, b = self.color(u, v)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b


# Layout plan: default legend (sRGB hex, as painted) and the ground tint of each
# kind (linear rgb, None = keep the terrain colour).
LEGEND = (("water", "#0000ff"), ("forest", "#008000"), ("road", "#808080"),
          ("house", "#ff0000"), ("rock", "#804000"), ("sand", "#ffff00"), ("field", "#ffa000"),
          ("path", "#d2b48c"), ("wall", "#404040"), ("bridge", "#ff00ff"))
KIND_TINT = {"water": None, "forest": (0.05, 0.12, 0.03), "road": (0.20, 0.18, 0.15),
             "house": (0.26, 0.22, 0.17), "rock": (0.30, 0.29, 0.27), "sand": (0.62, 0.53, 0.33),
             "field": (0.55, 0.45, 0.16), "path": (0.34, 0.27, 0.17), "wall": (0.22, 0.21, 0.20),
             "bridge": None}
LEGEND_TOL = 0.30                       # max sRGB distance to a legend colour; further = unpainted
BLOCKED = ("water", "road", "house", "path", "wall", "bridge")   # nothing is scattered on these
WAYS = ("road", "path", "bridge")       # ground a house turns to face; smoothed under foot
WAY_BLEND = 2.5                         # pixels beyond a way's edge over which ground blends back
WAY_SMOOTH = 3.0                        # pixels of terrain averaged along a way's centre line
LINE_EPS = 0.75                         # Douglas-Peucker tolerance for centre lines (pixels)
FACE_R = 40                             # pixels searched from a house for the nearest way
WALL_H, DECK_T = 1.2, 0.25              # wall height, bridge deck thickness (m)
DENSITY = {"forest": 3.0, "rock": 0.8}  # default items per 100 m2 of a painted zone


def _hex_srgb(text, line):
    from ..parser import NAMED_COLORS
    t = NAMED_COLORS.get(text.strip().lower(), text.strip().lower()).lstrip("#")
    if len(t) == 3:
        t = "".join(ch * 2 for ch in t)
    try:
        if len(t) != 6:
            raise ValueError
        return tuple(int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        raise ForgeError("legend colour '%s' is not #rrggbb, #rgb or a colour name" % text, line)


class LayoutMap:
    """Painted plan classified to legend kinds, sampled nearest-pixel."""

    def __init__(self, image, legend_text, line):
        legend = list(LEGEND)
        if legend_text:
            given = {}
            for part in re.split(r"[\s,;]+", legend_text.strip()):
                if not part:
                    continue
                k, sep, c = part.partition("=")
                k = k.lower()
                if not sep or k not in KIND_TINT:
                    raise ForgeError("legend entry '%s': use kind=#rrggbb with kind one of %s"
                                     % (part, ", ".join(KIND_TINT)), line)
                given[k] = c
            legend = [(k, given.get(k, c)) for k, c in LEGEND]
        cols = [(k, _hex_srgb(c, line)) for k, c in legend]
        self.kinds = [k for k, _ in cols]
        self.w, self.h = image.w, image.h
        self.cls = []
        counts = [0] * len(cols)
        for y in range(self.h):
            row = []
            for x in range(self.w):
                p = image._at(x, y)
                best, bd = -1, LEGEND_TOL * LEGEND_TOL
                for i, (_, c) in enumerate(cols):
                    d = (p[0] - c[0]) ** 2 + (p[1] - c[1]) ** 2 + (p[2] - c[2]) ** 2
                    if d < bd:
                        best, bd = i, d
                row.append(best)
                if best >= 0:
                    counts[best] += 1
            self.cls.append(row)
        total = float(self.w * self.h)
        self.area = {k: counts[i] / total for i, k in enumerate(self.kinds)}

    def _px(self, u, v):
        return (min(max(int(u * self.w), 0), self.w - 1), min(max(int(v * self.h), 0), self.h - 1))

    def at(self, u, v):
        x, y = self._px(u, v)
        i = self.cls[y][x]
        return self.kinds[i] if i >= 0 else None

    def frac(self, u, v, kind, r=1):
        """Share of the (2r+1)^2 pixels around (u, v) painted as `kind` (soft edges)."""
        if not self.area.get(kind):
            return 0.0
        i = self.kinds.index(kind)
        x0, y0 = self._px(u, v)
        hit = n = 0
        for y in range(max(0, y0 - r), min(self.h, y0 + r + 1)):
            for x in range(max(0, x0 - r), min(self.w, x0 + r + 1)):
                n += 1
                hit += self.cls[y][x] == i
        return hit / n

    def frac_any(self, u, v, kinds, r=1):
        """Share of the (2r+1)^2 pixels around (u, v) painted as any of `kinds`."""
        idx = {self.kinds.index(k) for k in kinds if self.area.get(k)}
        if not idx:
            return 0.0
        x0, y0 = self._px(u, v)
        hit = n = 0
        for y in range(max(0, y0 - r), min(self.h, y0 + r + 1)):
            for x in range(max(0, x0 - r), min(self.w, x0 + r + 1)):
                n += 1
                hit += self.cls[y][x] in idx
        return hit / n

    def nearest(self, u, v, kinds, max_r):
        """(du, dv) to the closest pixel of any of `kinds` within max_r pixels, or None."""
        idx = {self.kinds.index(k) for k in kinds if self.area.get(k)}
        if not idx:
            return None
        x0, y0 = self._px(u, v)
        best, bd = None, (max_r + 1) ** 2
        for y in range(max(0, y0 - max_r), min(self.h, y0 + max_r + 1)):
            for x in range(max(0, x0 - max_r), min(self.w, x0 + max_r + 1)):
                d = (x - x0) ** 2 + (y - y0) ** 2
                if d < bd and self.cls[y][x] in idx:
                    best, bd = (x, y), d
        if best is None:
            return None
        return ((best[0] + 0.5) / self.w - u, (best[1] + 0.5) / self.h - v)

    def pixels(self, kind):
        """Centres (u, v) of every pixel of `kind`, row-major."""
        if not self.area.get(kind):
            return []
        i = self.kinds.index(kind)
        return [((x + 0.5) / self.w, (y + 0.5) / self.h)
                for y in range(self.h) for x in range(self.w) if self.cls[y][x] == i]

    def centrelines(self, kinds):
        """Centre lines of the areas painted as any of `kinds`: [(points_uv, width_uv, closed)].

        Zhang-Suen thinning to 1 px, traced into polylines (row-major), short spurs
        pruned, then Douglas-Peucker simplified and Chaikin smoothed (2 passes).
        Width is 2 x the mean distance from the line to the area edge."""
        idx = {self.kinds.index(k) for k in kinds if self.area.get(k)}
        if not idx:
            return []
        w, h = self.w, self.h
        g = [[1 if self.cls[y][x] in idx else 0 for x in range(w)] for y in range(h)]
        dist = _chamfer(g, w, h)
        sk = _thin(g, w, h)
        out = []
        for pix, closed in _trace(sk, dist):
            md = sum(dist[y][x] for x, y in pix) / len(pix)
            wid = max(1.0, 2.0 * (md - 0.5))
            pts = _chaikin(_simplify([(float(x), float(y)) for x, y in pix], LINE_EPS), closed, 2)
            out.append(([((x + 0.5) / w, (y + 0.5) / h) for x, y in pts], wid / w, closed))
        return out

    def blobs(self, kind, min_px=3):
        """Connected (4-neighbour) areas of `kind` as (u, v, pixels), in row-major order."""
        if not self.area.get(kind):
            return []
        i = self.kinds.index(kind)
        seen = [[False] * self.w for _ in range(self.h)]
        out = []
        for y in range(self.h):
            for x in range(self.w):
                if seen[y][x] or self.cls[y][x] != i:
                    continue
                stack, sx, sy, n = [(x, y)], 0, 0, 0
                seen[y][x] = True
                while stack:
                    cx, cy = stack.pop()
                    sx, sy, n = sx + cx, sy + cy, n + 1
                    for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                        if 0 <= nx < self.w and 0 <= ny < self.h and not seen[ny][nx] and self.cls[ny][nx] == i:
                            seen[ny][nx] = True
                            stack.append((nx, ny))
                if n >= min_px:
                    out.append(((sx / n + 0.5) / self.w, (sy / n + 0.5) / self.h, n))
        return out


_N8 = ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))   # P2..P9


def _chamfer(g, w, h):
    """Per-pixel distance (pixels, ~Euclidean) to the nearest unset pixel; the map edge is not an edge."""
    big = float(w + h)
    d = [[big if g[y][x] else 0.0 for x in range(w)] for y in range(h)]
    r2 = math.sqrt(2.0)
    fwd = ((-1, 0, 1.0), (-1, -1, r2), (0, -1, 1.0), (1, -1, r2))
    for y in range(h):
        for x in range(w):
            if d[y][x]:
                for dx, dy, c in fwd:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < w and 0 <= ny < h and d[ny][nx] + c < d[y][x]:
                        d[y][x] = d[ny][nx] + c
    for y in range(h - 1, -1, -1):
        for x in range(w - 1, -1, -1):
            if d[y][x]:
                for dx, dy, c in fwd:
                    nx, ny = x - dx, y - dy
                    if 0 <= nx < w and 0 <= ny < h and d[ny][nx] + c < d[y][x]:
                        d[y][x] = d[ny][nx] + c
    return d


def _thin(g, w, h):
    """Zhang-Suen thinning; pixels past the map edge repeat the edge, so lines run off the map."""
    g = [row[:] for row in g]
    live = [(x, y) for y in range(h) for x in range(w) if g[y][x]]
    for _ in range(4 * (w + h)):
        changed = False
        for step in (0, 1):
            kill = []
            for x, y in live:
                if not g[y][x]:
                    continue
                p = [g[min(max(y + dy, 0), h - 1)][min(max(x + dx, 0), w - 1)] for dx, dy in _N8]
                b = sum(p)
                if b < 2 or b > 6:
                    continue
                if sum(p[i] == 0 and p[(i + 1) % 8] == 1 for i in range(8)) != 1:
                    continue
                if step == 0 and (p[0] * p[2] * p[4] or p[2] * p[4] * p[6]):
                    continue
                if step == 1 and (p[0] * p[2] * p[6] or p[0] * p[4] * p[6]):
                    continue
                kill.append((x, y))
            for x, y in kill:
                g[y][x] = 0
            changed = changed or bool(kill)
        live = [(x, y) for x, y in live if g[y][x]]
        if not changed:
            break
    return set(live)


def _trace(sk, dist):
    """1 px skeleton -> [(pixels, closed)] using m-adjacency; spurs pruned, chains merged."""
    def nbrs(p):
        x, y = p
        out = [q for q in ((x + 1, y), (x, y + 1), (x - 1, y), (x, y - 1)) if q in sk]
        for dx, dy in ((1, 1), (-1, 1), (-1, -1), (1, -1)):
            q = (x + dx, y + dy)
            if q in sk and (x + dx, y) not in sk and (x, y + dy) not in sk:
                out.append(q)
        return out

    def key(p):
        return (p[1], p[0])

    order = sorted(sk, key=key)
    nb = {p: nbrs(p) for p in order}
    deg = {p: len(nb[p]) for p in order}
    used = set()
    edges = []

    def walk(p, q, stop):
        path, prev, cur = [p], p, q
        used.add((min(p, q), max(p, q)))
        while not stop(cur):
            path.append(cur)
            nxt = None
            for n in nb[cur]:
                if n != prev and (min(cur, n), max(cur, n)) not in used:
                    nxt = n
                    break
            if nxt is None:
                return path
            used.add((min(cur, nxt), max(cur, nxt)))
            prev, cur = cur, nxt
        path.append(cur)
        return path

    for p in order:
        if deg[p] != 2:
            for q in nb[p]:
                if (min(p, q), max(p, q)) not in used:
                    edges.append((walk(p, q, lambda c: deg[c] != 2), False))
    for p in order:                                     # loops with no end or junction
        for q in nb[p]:
            if (min(p, q), max(p, q)) not in used:
                path = walk(p, q, lambda c, s=p: c == s)
                edges.append((path[:-1] if path[-1] == p else path, path[-1] == p))
    # prune spurs: a free end joined to a junction, no longer than the area is wide
    keep = []
    for path, closed in edges:
        a, b = path[0], path[-1]
        if not closed and len(path) < 3 and deg[a] <= 1 and deg[b] <= 1:
            continue
        if not closed and (deg[a] == 1) != (deg[b] == 1):
            j = b if deg[a] == 1 else a
            if deg[j] >= 3 and len(path) <= 2.0 * dist[j[1]][j[0]] + 1:
                continue
        keep.append([path, closed])
    # merge chains meeting at a node that now joins exactly two lines
    while True:
        inc = {}
        for i, (path, closed) in enumerate(keep):
            if not closed:
                inc.setdefault(path[0], []).append(i)
                if path[-1] != path[0]:
                    inc.setdefault(path[-1], []).append(i)
        hit = next((n for n in sorted(inc, key=key) if len(inc[n]) == 2), None)
        if hit is None:
            break
        i, j = inc[hit]
        a, b = keep[i][0], keep[j][0]
        if a[-1] != hit:
            a = a[::-1]
        if b[0] != hit:
            b = b[::-1]
        m = a + b[1:]
        keep[i] = [m[:-1], True] if m[0] == m[-1] else [m, False]
        del keep[j]
    return [(p, c) for p, c in keep if len(p) >= 2]


def _simplify(pts, eps):
    """Douglas-Peucker (iterative); keeps both ends."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        (ax, ay), (bx, by) = pts[i], pts[j]
        L = math.hypot(bx - ax, by - ay)
        best, bk = -1.0, -1
        for k in range(i + 1, j):
            px, py = pts[k]
            if L > 1e-9:
                d = abs((bx - ax) * (ay - py) - (ax - px) * (by - ay)) / L
            else:
                d = math.hypot(px - ax, py - ay)
            if d > best:
                best, bk = d, k
        if bk > 0 and best > eps:
            keep[bk] = True
            stack.append((i, bk))
            stack.append((bk, j))
    return [p for p, k in zip(pts, keep) if k]


def _chaikin(pts, closed, passes):
    """Corner cutting; open lines keep their ends."""
    for _ in range(passes):
        if len(pts) < 3:
            return pts
        out = [] if closed else [pts[0]]
        n = len(pts)
        for i in range(n if closed else n - 1):
            (ax, ay), (bx, by) = pts[i], pts[(i + 1) % n]
            out.append((0.75 * ax + 0.25 * bx, 0.75 * ay + 0.25 * by))
            out.append((0.25 * ax + 0.75 * bx, 0.25 * ay + 0.75 * by))
        if not closed:
            out.append(pts[-1])
        pts = out
    return pts


def _resample(pts, step, closed=False, extend=0.0):
    """Points every `step` along a polyline (both ends kept); open ends pushed out by `extend`."""
    pts = list(pts)
    if closed:
        pts.append(pts[0])
    elif extend > 0 and len(pts) >= 2:
        dx, dy = pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]
        L = math.hypot(dx, dy) or 1.0
        pts[0] = (pts[0][0] + dx / L * extend, pts[0][1] + dy / L * extend)
        dx, dy = pts[-1][0] - pts[-2][0], pts[-1][1] - pts[-2][1]
        L = math.hypot(dx, dy) or 1.0
        pts[-1] = (pts[-1][0] + dx / L * extend, pts[-1][1] + dy / L * extend)
    out = [pts[0]]
    carry = 0.0
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        L = math.hypot(bx - ax, by - ay)
        t = step - carry
        while t < L:
            out.append((ax + (bx - ax) * t / L, ay + (by - ay) * t / L))
            t += step
        carry = L - (t - step)
    if math.hypot(out[-1][0] - pts[-1][0], out[-1][1] - pts[-1][1]) > step * 0.25:
        out.append(pts[-1])
    elif len(out) > 1:
        out[-1] = pts[-1]
    if closed and len(out) > 1:
        out.pop()
    return out


def _strip(mb, pts, half, z_lo, z_hi, mi, closed=False):
    """Swept box along world-space (x, y) points: half width `half`, per-point bottom and top z."""
    n = len(pts)
    if n < 2:
        return
    rings = []
    for i in range(n):
        if closed:
            a, b = pts[i - 1], pts[(i + 1) % n]
        else:
            a, b = pts[max(i - 1, 0)], pts[min(i + 1, n - 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        L = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / L * half, tx / L * half
        x, y = pts[i]
        rings.append([mb.vert((x - nx, y - ny, z_lo[i])), mb.vert((x + nx, y + ny, z_lo[i])),
                      mb.vert((x + nx, y + ny, z_hi[i])), mb.vert((x - nx, y - ny, z_hi[i]))])
    for i in range(n if closed else n - 1):
        r, s = rings[i], rings[(i + 1) % n]
        for k in range(4):
            mb.face([r[k], s[k], s[(k + 1) % 4], r[(k + 1) % 4]], mi)
    if not closed:
        mb.face(rings[0][::-1], mi)
        mb.face(rings[-1], mi)


def _load_image(spec, ctx, key):
    path = spec.get(key)
    if not path:
        return None
    if not os.path.isabs(path):
        path = os.path.join(ctx.base_dir, path)
    if not os.path.isfile(path):
        raise ForgeError("%s image not found: %s" % (key, path), spec.line_of(key))
    return HeightImage(path, spec.line_of(key))


def _ramp(stops, t):
    from ..parser import parse_color
    cols = [(p, parse_color(c)) for p, c in stops]
    if t <= cols[0][0]:
        return cols[0][1][:3]
    for (p0, c0), (p1, c1) in zip(cols, cols[1:]):
        if t <= p1:
            k = smooth((t - p0) / max(p1 - p0, 1e-6))
            return tuple(c0[i] + (c1[i] - c0[i]) * k for i in range(3))
    return cols[-1][1][:3]


def build(spec, ctx, type_name):
    if type_name == "map":
        type_name = "terrain"
    relief, freq, island, valley, water_d = PRESETS[type_name]
    name = spec.name
    size = spec.num("size", 60.0, 2, 5000)
    res = spec.integer("resolution", 48 if ctx.spec_lowpoly(spec) else 96, 4, 400)
    height = spec.num("height", size * relief, 0, 2000)
    seed = spec.integer("seed", ctx.seed)
    palette = PALETTES.get(type_name, PALETTES["default"])
    image = _load_image(spec, ctx, "heightmap")
    plan_img = _load_image(spec, ctx, "layout")
    layout = LayoutMap(plan_img, spec.get("legend"), spec.line_of("legend") or spec.line) if plan_img else None
    if layout is not None and not any(layout.area.values()):
        warn("map '%s': no pixel in the layout matches a legend colour" % name, spec.line_of("layout"))
    if layout is not None and (layout.area["water"] or layout.area["bridge"]) and water_d == 0:
        water_d = 0.12                                  # painted water needs a water line
    water = spec.num("water", water_d, 0, 1)            # fraction of the height range
    use_image_colors = image is not None and spec.choice("colors", ("height", "image"), "height") == "image"

    wet = ("water", "bridge")                           # carved to below the water line

    def h01(u, v):
        h = h_base(u, v)
        if layout is not None:
            if way_w is not None:                       # ways: flat across, blended at the edge
                wgt, tw = way_at(u, v)
                if wgt > 1e-6:
                    h = h * (1 - wgt) + tw
            for pu, pv, pr, ph in pads:                 # level ground under houses
                dist = math.hypot(u - pu, v - pv)
                if dist < 2 * pr:
                    k = smooth(2 - dist / pr)
                    h = h * (1 - k) + ph * k
        if layout is not None and water > 0:
            if layout.area["water"] or layout.area["bridge"]:   # only painted water floods
                h = max(h, water + 0.03)
            m = layout.frac_any(u, v, wet)
            if m:
                h = h * (1 - m) + (water - 0.04) * m
        return max(0.0, h)

    def h_base(u, v):
        if image is not None:
            return image.height(u, v)
        n = fbm(u * freq, v * freq, seed, octaves=5)
        n = (n - 0.25) / 0.5
        if type_name == "mountains":
            n = n * n * 1.1
        d = math.hypot(u - 0.5, v - 0.5) * 2.0
        if island:
            n = n * smooth(1.25 - d * 1.25) + 0.05 * (1 - d)
        if valley:
            w = smooth(abs(u - 0.5 + 0.10 * math.sin(v * 5.0 + seed)) * 2.3)
            n = n * (0.22 + 0.70 * w) + 0.10 * w
        return max(0.0, min(1.0, n))

    # Flat pads under painted houses: (u, v, radius, height) in uv units.
    blobs = layout.blobs("house") if layout is not None else []
    pads = []
    for bu, bv, npx in blobs[:500]:
        r = (math.sqrt(npx / math.pi) + 1.5) / layout.w
        pads.append((bu, bv, r, h_base(bu, bv)))

    # Ground under roads and paths: per-pixel target height (terrain sampled along the
    # nearest centre line, averaged along it) and blend weight, built once.
    way_lines = layout.centrelines(WAYS) if layout is not None else []
    way_w = way_wt = None
    if way_lines:
        lw, lh = layout.w, layout.h
        dmin = [[1e9] * lw for _ in range(lh)]
        way_w = [[0.0] * lw for _ in range(lh)]
        way_wt = [[0.0] * lw for _ in range(lh)]
        for pts, wid, closed in way_lines:
            px_pts = _resample([(u * lw - 0.5, v * lh - 0.5) for u, v in pts], 0.5, closed)
            raw = [h_base((x + 0.5) / lw, (y + 0.5) / lh) for x, y in px_pts]
            k, m = int(WAY_SMOOTH / 0.5), len(raw)
            tgt = []
            for i in range(m):
                win = [raw[(i + j) % m] if closed else raw[min(max(i + j, 0), m - 1)] for j in range(-k, k + 1)]
                tgt.append(sum(win) / len(win))
            hw = wid * lw / 2.0
            R = hw + WAY_BLEND
            for (sx, sy), t in zip(px_pts, tgt):
                for y in range(max(0, int(sy - R)), min(lh, int(sy + R) + 2)):
                    for x in range(max(0, int(sx - R)), min(lw, int(sx + R) + 2)):
                        d = math.hypot(x - sx, y - sy)
                        if d < R and d < dmin[y][x]:
                            dmin[y][x] = d
                            wgt = 1.0 if d <= hw else smooth(1.0 - (d - hw) / WAY_BLEND)
                            way_w[y][x], way_wt[y][x] = wgt, wgt * t

    def way_at(u, v):
        """Bilinear (weight, weight x target) from the way grids."""
        lw, lh = layout.w, layout.h
        fx = min(max(u * lw - 0.5, 0.0), lw - 1.0)
        fy = min(max(v * lh - 0.5, 0.0), lh - 1.0)
        x0, y0 = min(int(fx), lw - 2), min(int(fy), lh - 2)
        ax, ay = fx - x0, fy - y0
        out = []
        for gr in (way_w, way_wt):
            a = gr[y0][x0] * (1 - ax) + gr[y0][x0 + 1] * ax
            b = gr[y0 + 1][x0] * (1 - ax) + gr[y0 + 1][x0 + 1] * ax
            out.append(a * (1 - ay) + b * ay)
        return out

    def ground(x, y):
        """World-space height, used to stand other entities on the terrain."""
        u, v = x / size + 0.5, y / size + 0.5
        if not (0 <= u <= 1 and 0 <= v <= 1):
            return 0.0
        return h01(u, v) * height

    # ---- mesh ---------------------------------------------------------------
    n = res + 1
    hs = [[h01(i / res, j / res) for i in range(n)] for j in range(n)]
    verts = [((i / res - 0.5) * size, (j / res - 0.5) * size, hs[j][i] * height)
             for j in range(n) for i in range(n)]
    faces = [(j * n + i, j * n + i + 1, (j + 1) * n + i + 1, (j + 1) * n + i)
             for j in range(res) for i in range(res)]
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.shade_smooth()
    layer = me.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    cell = size / res
    for j in range(n):
        for i in range(n):
            t = hs[j][i]
            if use_image_colors:
                c = tuple(srgb_to_linear(x) for x in image.color(i / res, j / res))
            else:
                dx = (hs[j][min(i + 1, res)] - hs[j][max(i - 1, 0)]) * height / (2 * cell)
                dy = (hs[min(j + 1, res)][i] - hs[max(j - 1, 0)][i]) * height / (2 * cell)
                slope = math.hypot(dx, dy)
                c = _ramp(palette, t)
                if slope > 0.55 and type_name != "desert":       # bare rock on steep ground
                    k = smooth((slope - 0.55) / 0.5)
                    c = tuple(c[q] * (1 - k) + (0.33, 0.31, 0.29)[q] * k for q in range(3))
                if water > 0 and t < water + 0.03:               # shoreline sand
                    k = smooth((water + 0.03 - t) / 0.06)
                    c = tuple(c[q] * (1 - k) + (0.58, 0.50, 0.33)[q] * k for q in range(3))
            if layout is not None:
                kind = layout.at(i / res, j / res)
                tint = KIND_TINT.get(kind)
                if tint:
                    k = layout.frac(i / res, j / res, kind)
                    c = tuple(c[q] * (1 - k) + tint[q] * k for q in range(3))
            layer.data[j * n + i].color = (c[0], c[1], c[2], 1.0)
    me.materials.append(ctx.mat("Ground", "vertex", (0.3, 0.45, 0.2, 1), scale=8.0 / size))
    obj = bpy.data.objects.new(name, me)
    ctx.collection.objects.link(obj)
    objects = [obj]
    ctx.ground = ground

    if water > 0:
        wm = bpy.data.meshes.new(name + "_Water")
        s2, z = size / 2, water * height
        wm.from_pydata([(-s2, -s2, z), (s2, -s2, z), (s2, s2, z), (-s2, s2, z)], [], [(0, 1, 2, 3)])
        wm.materials.append(ctx.mat("Water", "water", spec.color("water_color", "#1f5f85"), scale=3.0 / size))
        wobj = bpy.data.objects.new(name + "_Water", wm)
        wobj.parent = obj
        ctx.collection.objects.link(wobj)
        objects.append(wobj)

    # ---- scatter --------------------------------------------------------------
    rng = Rng(seed * 7919 + 13)

    def spots(count, max_slope, lo, hi, margin=0.06, zone=None):
        out, tries = [], 0
        limit = count * 40 / max(layout.area[zone], 0.01) if zone else count * 40
        while len(out) < count and tries < limit:
            tries += 1
            u, v = rng.uniform(margin, 1 - margin), rng.uniform(margin, 1 - margin)
            if layout is not None:
                kind = layout.at(u, v)
                if (zone and kind != zone) or (not zone and kind in BLOCKED):
                    continue
            t = h01(u, v)
            if not (max(lo, water + 0.02) <= t <= hi):
                continue
            e = 1.0 / res
            slope = math.hypot(h01(min(u + e, 1), v) - h01(max(u - e, 0), v),
                               h01(u, min(v + e, 1)) - h01(u, max(v - e, 0))) * height / (2 * cell)
            if slope > max_slope:
                continue
            out.append(((u - 0.5) * size, (v - 0.5) * size, t * height))
        if len(out) < count:
            warn("map '%s': only found room for %d of %d scattered items" % (name, len(out), count), spec.line)
        return out

    def scatter(label, count, make_mesh, variants, max_slope, lo, hi, scale_range, zone=None):
        if count <= 0:
            return
        protos = []
        for k in range(min(variants, count)):
            mb = MeshBuilder()
            make_mesh(mb, k)
            protos.append(mb.to_mesh("%s_%s%d" % (name, label, k + 1)))
        margin = 0.01 if zone else 0.06
        for idx, (x, y, z) in enumerate(spots(count, max_slope, lo, hi, margin, zone)):
            o = bpy.data.objects.new("%s_%s_%03d" % (name, label, idx + 1), protos[idx % len(protos)])
            k = rng.uniform(*scale_range)
            o.location = (x, y, z - 0.05)
            o.scale = (k, k, k)
            o.rotation_euler.z = rng.uniform(0, math.tau)
            o.parent = obj
            ctx.collection.objects.link(o)
            objects.append(o)

    tree_kind = spec.choice("tree_type", tree_tpl.NAMES, "palm" if type_name in ("island", "desert") else
                            ("pine" if type_name == "mountains" else "oak"))
    def zone_count(key, zone):
        """(count, zone): a painted zone sets the default count from its area."""
        if layout is None or not layout.area[zone]:
            return spec.integer(key, 0, 0, 5000), None
        dens = spec.num(key + "_density", DENSITY[zone], 0, 100)     # per 100 m2
        auto = int(round(layout.area[zone] * size * size * dens / 100.0))
        return spec.integer(key, min(auto, 5000), 0, 5000), zone

    n_trees, tree_zone = zone_count("trees", "forest")
    if n_trees:
        bark = ctx.mat("Bark", "wood", (0.11, 0.06, 0.03, 1))
        leaf = ctx.mat("Leaves", "foliage", spec.color("foliage", "#2d5a3a" if tree_kind in ("pine", "fir") else "#447a2e"))
        th = spec.num("tree_height", max(2.0, size * 0.07), 0.2, 200)
        scatter("Tree", n_trees, lambda mb, k: tree_tpl.make_tree(mb, tree_kind, th, seed + k * 31, bark, leaf, bark),
                4, 0.6, 0.0, 0.68, (0.7, 1.25), tree_zone)
    n_rocks, rock_zone = zone_count("rocks", "rock")
    if n_rocks:
        stone = ctx.mat("Rock", "stone", (0.23, 0.22, 0.21, 1), blocks=False)

        class _M:                                       # minimal stand-in for prop.Mats
            pass
        m = _M()
        m.stone = stone

        def rock(mb, k):
            rs = Spec("prop", "%s_rock%d" % (name, k), spec.line)
            rs.props["seed"] = (str(seed + k * 17), spec.line)
            prop_tpl.PROPS["rock"][0](mb, max(0.6, size * 0.025), m, rs)
        scatter("Rock", n_rocks, rock, 4, 1.5, 0.0, 1.0, (0.5, 1.8), rock_zone)
    if layout is not None:                              # walls and bridge decks, one strip per centre line
        px = size / layout.w
        for kind, label in (("wall", "Walls"), ("bridge", "Bridge")):
            lines = layout.centrelines((kind,))
            if not lines:
                continue
            mb = MeshBuilder(smooth_faces=False)
            if kind == "wall":
                mi = mb.m(ctx.mat("Wall", "stone", spec.color("wall_color", "#6b655c")))
                wh = spec.num("wall_height", WALL_H, 0.1, 50)
                half = spec.num("wall_thickness", px, 0.05, 50) / 2
                for pts, wid, closed in lines:
                    wp = _resample([((u - 0.5) * size, (v - 0.5) * size) for u, v in pts], px, closed,
                                   wid * size / 2)
                    zc = [ground(x, y) for x, y in wp]
                    lo = []
                    for i, (x, y) in enumerate(wp):         # base under the lower side, sunk 0.3 m
                        a, b = wp[max(i - 1, 0)], wp[min(i + 1, len(wp) - 1)]
                        L = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
                        ox, oy = -(b[1] - a[1]) / L * half, (b[0] - a[0]) / L * half
                        lo.append(min(zc[i], ground(x + ox, y + oy), ground(x - ox, y - oy)) - 0.3)
                    _strip(mb, wp, half, lo, [z + wh for z in zc], mi, closed)
            else:
                mi = mb.m(ctx.mat("Planks", "wood", (0.25, 0.15, 0.08, 1)))
                top = (water + 0.03) * height + 0.05     # level with the banks
                for pts, wid, closed in lines:
                    ww = max(wid * size, px)
                    wp = _resample([((u - 0.5) * size, (v - 0.5) * size) for u, v in pts], px, closed, ww / 2)
                    _strip(mb, wp, ww / 2, [top - DECK_T] * len(wp), [top] * len(wp), mi, closed)
            o = bpy.data.objects.new("%s_%s" % (name, label), mb.to_mesh("%s_%s" % (name, label)))
            o.parent = obj
            ctx.collection.objects.link(o)
            objects.append(o)
    if blobs:
        if spec.has("houses"):
            warn("map '%s': 'houses' ignored, the layout places one house per painted house area" % name,
                 spec.line_of("houses"))
        places = []
        segs = [(a, b) for pts, _, closed in way_lines
                for a, b in zip(pts, pts[1:] + (pts[:1] if closed else []))]
        reach = (FACE_R * size / max(layout.w, layout.h)) ** 2
        for u, v, _ in blobs[:500]:
            face, best = None, reach
            hx, hy = (u - 0.5) * size, (v - 0.5) * size
            for (au, av), (bu, bv) in segs:             # nearest centre-line point, in metres
                ax, ay = (au - 0.5) * size, (av - 0.5) * size
                dx, dy = (bu - au) * size, (bv - av) * size
                L2 = dx * dx + dy * dy or 1e-12
                t = min(max(((hx - ax) * dx + (hy - ay) * dy) / L2, 0.0), 1.0)
                nx, ny = ax + dx * t - hx, ay + dy * t - hy
                d2 = nx * nx + ny * ny
                if d2 < best:
                    best = d2
                    L, nl = math.sqrt(L2), math.sqrt(d2) or 1.0
                    mx, my = -dy / L, dx / L            # segment normal, turned toward the way
                    if mx * nx + my * ny < 0:
                        mx, my = -mx, -my
                    if (mx * nx + my * ny) / nl < 0.5:  # past a line's end: face the point itself
                        mx, my = nx / nl, ny / nl
                    face = math.atan2(mx, -my)          # front (-Y) square to the way
            places.append(((u - 0.5) * size, (v - 0.5) * size, h01(u, v) * height, face))
    else:
        n_houses = spec.integer("houses", 0, 0, 500)
        places = [p + (None,) for p in spots(n_houses, 0.28, 0.0, 0.5, margin=0.15)] if n_houses else []
    if places:
        saved = ctx.collection, ctx.name
        for idx, (x, y, z, face) in enumerate(places):
            hs_spec = Spec("structure", "%s_House%d" % (name, idx + 1), spec.line)
            hs_spec.props = {"lowpoly": ("true", spec.line),
                             "roof_color": (("#7b3327", "#5a4a3a", "#3f5a6a")[idx % 3], spec.line)}
            ctx.name = hs_spec.name
            ent = house_tpl.build(hs_spec, ctx, ("house", "cottage", "cabin")[idx % 3])
            ent.root.location = (x, y, z - 0.15)
            spin = rng.uniform(0, math.tau)
            ent.root.rotation_euler.z = spin if face is None else face
            ent.root.parent = obj
            objects.extend(ent.objects)
        ctx.collection, ctx.name = saved
    return Entity(name, obj, objects)
