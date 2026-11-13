"""Maps: a height-field terrain from seeded fractal noise or from an image,
coloured by height and slope, with water and scattered trees, rocks and houses.

An image given as the input file (or `heightmap: file.png`) drives the height
from its brightness; `colors: image` also paints the terrain with its pixels.
"""

import math
import os

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
    water = spec.num("water", water_d, 0, 1)            # fraction of the height range
    palette = PALETTES.get(type_name, PALETTES["default"])
    image = None
    path = spec.get("heightmap")
    if path:
        if not os.path.isabs(path):
            path = os.path.join(ctx.base_dir, path)
        if not os.path.isfile(path):
            raise ForgeError("heightmap image not found: %s" % path, spec.line_of("heightmap"))
        image = HeightImage(path, spec.line_of("heightmap"))
    use_image_colors = image is not None and spec.choice("colors", ("height", "image"), "height") == "image"

    def h01(u, v):
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

    def spots(count, max_slope, lo, hi, margin=0.06):
        out, tries = [], 0
        while len(out) < count and tries < count * 40:
            tries += 1
            u, v = rng.uniform(margin, 1 - margin), rng.uniform(margin, 1 - margin)
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

    def scatter(label, count, make_mesh, variants, max_slope, lo, hi, scale_range):
        if count <= 0:
            return
        protos = []
        for k in range(min(variants, count)):
            mb = MeshBuilder()
            make_mesh(mb, k)
            protos.append(mb.to_mesh("%s_%s%d" % (name, label, k + 1)))
        for idx, (x, y, z) in enumerate(spots(count, max_slope, lo, hi)):
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
    n_trees = spec.integer("trees", 0, 0, 5000)
    if n_trees:
        bark = ctx.mat("Bark", "wood", (0.11, 0.06, 0.03, 1))
        leaf = ctx.mat("Leaves", "foliage", spec.color("foliage", "#2d5a3a" if tree_kind in ("pine", "fir") else "#447a2e"))
        th = spec.num("tree_height", max(2.0, size * 0.07), 0.2, 200)
        scatter("Tree", n_trees, lambda mb, k: tree_tpl.make_tree(mb, tree_kind, th, seed + k * 31, bark, leaf, bark),
                4, 0.6, 0.0, 0.68, (0.7, 1.25))
    n_rocks = spec.integer("rocks", 0, 0, 5000)
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
        scatter("Rock", n_rocks, rock, 4, 1.5, 0.0, 1.0, (0.5, 1.8))
    n_houses = spec.integer("houses", 0, 0, 500)
    if n_houses:
        saved = ctx.collection, ctx.name
        for idx, (x, y, z) in enumerate(spots(n_houses, 0.28, 0.0, 0.5, margin=0.15)):
            hs_spec = Spec("structure", "%s_House%d" % (name, idx + 1), spec.line)
            hs_spec.props = {"lowpoly": ("true", spec.line),
                             "roof_color": (("#7b3327", "#5a4a3a", "#3f5a6a")[idx % 3], spec.line)}
            ctx.name = hs_spec.name
            ent = house_tpl.build(hs_spec, ctx, ("house", "cottage", "cabin")[idx % 3])
            ent.root.location = (x, y, z - 0.15)
            ent.root.rotation_euler.z = rng.uniform(0, math.tau)
            ent.root.parent = obj
            objects.extend(ent.objects)
        ctx.collection, ctx.name = saved
    return Entity(name, obj, objects)
