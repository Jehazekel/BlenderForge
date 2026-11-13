"""Round tower: tapered wall, string courses, spiral of windows, corbelled top
with battlements and / or a roof."""

import math

from mathutils import Vector

from .. import parts, static
from ..meshkit import TAU, MeshBuilder, V, Z

NAMES = ["tower", "castle_tower", "watchtower", "lighthouse", "wizard_tower", "silo"]
ROOFS = ("cone", "flat", "dome", "battlement", "none")
DEFAULT_ROOF = {"tower": "cone", "castle_tower": "battlement", "watchtower": "battlement",
                "lighthouse": "dome", "wizard_tower": "cone", "silo": "dome"}


def build(spec, ctx, type_name):
    floors = spec.integer("floors", 4, 1, 60)
    R = spec.num("radius", 3.0, 0.3, 100)
    fh = spec.num("floor_height", 3.0, 1.0, 20)
    roof = spec.choice("roof", ROOFS, DEFAULT_ROOF[type_name])
    n_win = spec.integer("windows", max(0, (floors - 1) * 2), 0, 400)
    low = ctx.spec_lowpoly(spec)
    seg = spec.integer("segments", 12 if low else 32, 6, 96)
    battlements = spec.flag("battlements", roof in ("battlement", "flat") or type_name == "castle_tower")
    taper = spec.num("taper", 0.06 if type_name != "lighthouse" else 0.3, 0, 0.8)
    Hh = floors * fh
    k = min(1.5, max(0.5, fh / 3.0))                   # detail scale

    wall, wall_kind = static.wall_material(ctx, spec, "stone", cylindrical=True, radius=R,
                                           block=0.45 * k)
    trim_c = tuple(min(1.0, c * 1.25) for c in list(wall["forge_color"])[:3]) + (1,)
    trim = ctx.mat("Trim", "stone", spec.color("trim_color", trim_c), blocks=False)
    roof_m = ctx.mat("Roof", "roof", spec.color("roof_color", "#7a2f2a" if roof == "cone" else "#5a6470"))
    wood = ctx.mat("Door", "wood", spec.color("door_color", "#5b3a22"))
    glass = ctx.mat("Glass", "glass", spec.color("glass_color", "#1c2a3a"))
    metal = ctx.mat("Iron", "metal", (0.12, 0.12, 0.13, 1), roughness=0.5)
    mb = MeshBuilder()

    def rad(z):
        return R * (1.0 - taper * max(0.0, min(1.0, z / Hh)))

    # wall with a flared plinth
    prof = [(R * 1.05, 0.0), (R * 1.05, 0.45 * k), (R * 1.0, 0.75 * k)]
    steps = max(2, floors)
    prof += [(rad(Hh * i / steps), Hh * i / steps) for i in range(1, steps + 1) if Hh * i / steps > 0.8 * k]
    mb.lathe(prof, n=seg, mat=wall, cap_start=True)
    # string course at every floor
    for f in range(1, floors):
        z, r = f * fh, rad(f * fh)
        mb.lathe([(r, z - 0.10 * k), (r + 0.09 * k, z - 0.07 * k), (r + 0.09 * k, z + 0.07 * k), (r, z + 0.10 * k)],
                 n=seg, mat=trim)

    # corbelled top
    rt = rad(Hh)
    out = rt + 0.38 * k
    mb.lathe([(rt, Hh - 0.7 * k), (out, Hh - 0.15 * k), (out, Hh + 0.02)], n=seg, mat=trim)
    top_z = Hh
    if battlements:
        ph = 0.95 * k
        mb.lathe([(out, Hh), (out, Hh + ph), (out - 0.32 * k, Hh + ph), (out - 0.32 * k, Hh + 0.05)],
                 n=seg, mat=wall)
        mb.lathe([(out - 0.3 * k, Hh + 0.05), (0.01, Hh + 0.05)], n=seg, mat=trim)
        parts.ring_battlements(mb, (0, 0, Hh + ph), out, wall, merlon=0.62 * k, height=0.62 * k,
                               thick=0.32 * k)
        top_z = Hh + 0.05
    else:
        mb.lathe([(out, Hh + 0.02), (0.01, Hh + 0.02)], n=seg, mat=trim)

    if roof == "cone":
        rr = (out - 0.45 * k) if battlements else out + 0.45 * k
        if battlements:                                # inner drum carries the roof
            mb.lathe([(rr * 0.92, top_z), (rr * 0.92, top_z + 1.6 * k)], n=seg, mat=wall)
            top_z += 1.6 * k
            rr += 0.25 * k
        h = spec.num("roof_height", rr * 1.7, 0.2, 200)
        parts.cone_roof(mb, (0, 0, top_z), rr, h, seg, roof_m)
        mb.sphere((0, 0, top_z + h), 0.14 * k, metal, n=8, m=3)
        peak = top_z + h
    elif roof == "dome":
        rr = (out - 0.5 * k) if battlements else out * 0.96
        if type_name == "lighthouse":                  # lantern room under the dome
            mb.lathe([(rr * 0.75, top_z), (rr * 0.75, top_z + 1.8 * k)], n=seg,
                     mat=ctx.mat("Lamp", "emissive", (1.0, 0.85, 0.45, 1), strength=6.0))
            for j in range(8):
                a = TAU * j / 8
                mb.cylinder(V(math.cos(a) * rr * 0.78, math.sin(a) * rr * 0.78, top_z),
                            V(math.cos(a) * rr * 0.78, math.sin(a) * rr * 0.78, top_z + 1.8 * k),
                            0.05 * k, n=4, mat=metal)
            top_z += 1.8 * k
            rr *= 0.9
        parts.dome_roof(mb, (0, 0, top_z), rr, seg, roof_m)
        peak = top_z + rr * 0.85
    else:
        peak = top_z + (1.5 * k if battlements else 0.0)
    if spec.flag("flag", type_name == "castle_tower" and roof != "none"):
        parts.flag(mb, (0, 0, peak), 2.6 * k, metal,
                   ctx.mat("Flag", "cloth", spec.color("flag_color", "#b3262d")))

    # door, then windows climbing in a spiral so every one is visible somewhere
    door_a = -math.pi / 2
    if spec.flag("door", True):
        dw = 1.15 * k
        r = R * 1.05 - (R * 1.05 - math.sqrt(max((R * 1.05) ** 2 - (dw * 0.6) ** 2, 0.0)))
        p = V(math.cos(door_a) * r, math.sin(door_a) * r, 0.0)
        parts.door(mb, p, V(math.cos(door_a), math.sin(door_a), 0),
                   1.15 * k, 2.3 * k, trim, wood, metal, arched=True)
    upper = max(1, floors - 1)
    w, h = 0.62 * k, 1.35 * k
    for i in range(n_win):
        f = (i % upper) + (1 if floors > 1 else 0)
        ring_i = i // upper
        per_ring = max(1, math.ceil(n_win / upper))
        a = door_a + TAU * (ring_i + 0.5 * (f % 2)) / per_ring + (0.0 if floors > 1 else math.pi / per_ring)
        z = f * fh + fh * 0.52
        r = rad(z)
        sag = r - math.sqrt(max(r * r - (w * 0.62) ** 2, 0.0))
        n = V(math.cos(a), math.sin(a), 0)
        parts.window(mb, n * (r - sag + 0.01) + Z * z, n, w, h, trim, glass, arched=True)

    return static.finish(ctx, spec, mb, bevel=0.0, sharp=40)
