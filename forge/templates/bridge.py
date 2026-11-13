"""Bridges: stone arches or a wooden trestle. Runs along X, deck at `height`."""

import math

from mathutils import Matrix

from .. import static
from ..meshkit import MeshBuilder, V, X, Y, Z

NAMES = ["bridge", "stone_bridge", "wooden_bridge", "footbridge"]


def _stone(spec, ctx, mb, L, W, H, arches):
    wall, _ = static.wall_material(ctx, spec, "stone", block=0.4)
    trim = ctx.mat("Trim", "stone", spec.color("trim_color", "#a9a59c"), blocks=False)
    road = ctx.mat("Road", "ground", spec.color("road_color", "#6e675c"))
    deck_t = 0.45
    pier_w = max(0.6, L / arches * 0.16)
    span = (L - pier_w * (arches + 1)) / arches
    rise = min(span / 2, H - deck_t - 0.4)
    spring = H - deck_t - 0.25 - rise
    steps = 10
    hw = W / 2
    for i in range(arches + 1):                         # piers with cutwaters
        x = -L / 2 + pier_w / 2 + i * (span + pier_w)
        mb.box((x, 0, (H - deck_t) / 2 - 0.5), (pier_w, W, H - deck_t + 1.0), wall)
        for sy in (-1, 1):
            pts = [V(x - pier_w / 2, sy * hw, -1.0), V(x + pier_w / 2, sy * hw, -1.0),
                   V(x, sy * (hw + pier_w * 0.8), -1.0)]
            mb.extrude(pts, Z * (spring + 1.0), trim)
    for i in range(arches):                             # arch ring + spandrel walls
        x0 = -L / 2 + pier_w + i * (span + pier_w)
        arc = []
        for k in range(steps + 1):
            a = math.pi * k / steps
            arc.append((x0 + span / 2 - math.cos(a) * span / 2, spring + math.sin(a) * rise))
        zt = H - deck_t
        front = [mb.vert((x, -hw, z)) for x, z in arc]
        back = [mb.vert((x, hw, z)) for x, z in arc]
        tf = [mb.vert((x, -hw, zt)) for x, z in arc]
        tb = [mb.vert((x, hw, zt)) for x, z in arc]
        for k in range(steps):
            mb.face([front[k], front[k + 1], back[k + 1], back[k]], trim)     # soffit
            mb.face([front[k], front[k + 1], tf[k + 1], tf[k]], wall)
            mb.face([back[k], back[k + 1], tb[k + 1], tb[k]], wall)
    mb.box((0, 0, H - deck_t / 2), (L + 1.0, W + 0.3, deck_t), trim)
    mb.box((0, 0, H + 0.02), (L + 1.0, W - 0.5, 0.05), road)
    for sy in (-1, 1):                                  # parapets
        mb.box((0, sy * (hw - 0.05), H + 0.45), (L + 1.0, 0.3, 0.9), wall)
        mb.box((0, sy * (hw - 0.05), H + 0.94), (L + 1.1, 0.4, 0.1), trim)
        n = max(2, int(L / 4))
        for k in range(n + 1):
            x = -L / 2 + k * L / n
            mb.box((x, sy * (hw - 0.05), H + 0.6), (0.45, 0.45, 1.2), trim)


def _wood(spec, ctx, mb, L, W, H):
    wood = ctx.mat("Wood", "wood", spec.color("color", "#7a5533"), grain="x")
    dark = ctx.mat("Posts", "wood", spec.color("trim_color", "#4f3521"))
    hw = W / 2
    n_planks = max(4, int(L / 0.32))
    pw = L / n_planks
    for k in range(n_planks):
        x = -L / 2 + (k + 0.5) * pw
        mb.box((x, 0, H - 0.04), (pw * 0.93, W, 0.08), wood)
    for sy in (-1, 1):
        mb.box((0, sy * hw * 0.7, H - 0.2), (L, 0.18, 0.24), dark)
    bays = max(1, int(round(L / 4.0)))
    for k in range(bays + 1):
        x = -L / 2 + k * L / bays
        for sy in (-1, 1):
            mb.box((x, sy * (hw - 0.1), (H + 1.0) / 2 - 0.5), (0.2, 0.2, H + 2.0), dark)
        mb.box((x, 0, H - 0.42), (0.22, W, 0.2), dark)
        if H > 1.2:                                     # cross brace
            ang = math.atan2(H - 0.6, W - 0.2)
            with mb.part(xform=Matrix.Translation((x, 0, (H - 0.6) / 2)) @ Matrix.Rotation(ang, 4, "X")):
                mb.box((0, 0, 0), (0.1, math.hypot(W - 0.2, H - 0.6), 0.14), dark)
    for sy in (-1, 1):
        mb.box((0, sy * (hw - 0.1), H + 0.95), (L, 0.1, 0.12), wood)
        mb.box((0, sy * (hw - 0.1), H + 0.5), (L, 0.07, 0.09), wood)


def build(spec, ctx, type_name):
    L = spec.num("length", 20.0, 2, 1000)
    W = spec.num("width", 4.0, 0.8, 100)
    H = spec.num("height", 4.0 if type_name not in ("wooden_bridge", "footbridge") else 2.0, 0.6, 200)
    style = spec.choice("style", ("stone", "wood"),
                        "wood" if type_name in ("wooden_bridge", "footbridge") else "stone")
    if spec.has("material") and spec.get("material").strip().lower() == "wood":
        style = "wood"
    arches = spec.integer("arches", max(1, int(round(L / 7.0))), 1, 60)
    mb = MeshBuilder()
    if style == "wood":
        spec.used.update(("material", "arches"))
        _wood(spec, ctx, mb, L, W, H)
    else:
        _stone(spec, ctx, mb, L, W, H, arches)
    return static.finish(ctx, spec, mb, bevel=0.02)
