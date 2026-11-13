"""Houses and box buildings: walls, floors of windows, door, roof, chimney.

`house`, `cottage`, `cabin` and `barn` default to pitched roofs; `building`,
`shop`, `apartment` and `keep` default to flat roofs with a parapet.
"""

from .. import parts, static
from ..meshkit import MeshBuilder, V

# type: (width, depth, floors, floor height, roof, wall, windows per floor on the front)
PRESETS = {
    "house": (8.0, 6.0, 1, 2.8, "gable", "plaster", 2),
    "cottage": (6.0, 5.0, 1, 2.5, "gable", "stone", 2),
    "cabin": (6.0, 5.0, 1, 2.6, "gable", "wood", 2),
    "barn": (9.0, 12.0, 1, 4.5, "gable", "wood", 0),
    "building": (10.0, 8.0, 3, 3.2, "flat", "brick", 4),
    "shop": (8.0, 7.0, 2, 3.2, "flat", "brick", 3),
    "apartment": (14.0, 10.0, 6, 3.0, "flat", "concrete", 6),
    "keep": (10.0, 10.0, 3, 4.0, "battlement", "stone", 2),
}
NAMES = list(PRESETS)
ROOFS = ("gable", "hip", "flat", "battlement")


def build(spec, ctx, type_name):
    w_d, d_d, f_d, fh_d, roof_d, wall_d, win_d = PRESETS[type_name]
    W = spec.num("width", w_d, 1.5, 300)
    D = spec.num("depth", d_d, 1.5, 300)
    floors = spec.integer("floors", f_d, 1, 80)
    fh = spec.num("floor_height", fh_d, 1.8, 20)
    roof = spec.choice("roof", ROOFS, roof_d)
    n_win = spec.integer("windows", win_d, 0, 60)
    H = floors * fh
    base_h = 0.35

    wall, wall_kind = static.wall_material(ctx, spec, wall_d)
    trim = ctx.mat("Trim", "wood" if wall_kind in ("wood", "plaster") else "stone",
                   spec.color("trim_color", "#4a3526" if wall_kind in ("wood", "plaster") else "#b9b4a8"),
                   blocks=False)
    stone = ctx.mat("Base", "stone", (0.25, 0.24, 0.23, 1), blocks=False)
    roof_m = ctx.mat("Roof", "roof", spec.color("roof_color", "#7b3327" if roof in ("gable", "hip") else "#4d5057"))
    wood = ctx.mat("Door", "wood", spec.color("door_color", "#5b3a22"))
    glass = ctx.mat("Glass", "glass", spec.color("glass_color", "#22364a"))
    metal = ctx.mat("Iron", "metal", (0.15, 0.15, 0.16, 1), roughness=0.5)
    mb = MeshBuilder()

    mb.box((0, 0, base_h / 2), (W + 0.3, D + 0.3, base_h), stone)
    mb.box((0, 0, base_h + H / 2), (W, D, H), wall)
    z0 = base_h
    post = 0.22
    for sx in (-1, 1):                                  # corner posts / pilasters
        for sy in (-1, 1):
            mb.box((sx * (W / 2 - post / 4), sy * (D / 2 - post / 4), z0 + H / 2), (post, post, H), trim)
    for f in range(1, floors + 1):                      # floor bands
        z = z0 + f * fh
        mb.box((0, 0, z - 0.09), (W + 0.12, D + 0.12, 0.18), trim)

    # openings: front is -Y
    ww = min(1.1, W / max(n_win * 2.0, 2.0) * 0.9)
    wh = min(fh * 0.5, 1.5)
    door_w, door_h = min(1.1, W * 0.25), min(2.1, fh * 0.8)
    if type_name == "barn":
        door_w, door_h = min(3.2, W * 0.45), min(3.4, fh * 0.8)
    has_door = spec.flag("door", True)
    if has_door:
        parts.door(mb, V(0, -D / 2 - 0.005, z0), V(0, -1, 0), door_w, door_h, trim, wood, metal,
                   arched=spec.flag("arched", wall_kind == "stone"))
    arched = spec.flag("arched", False)
    for f in range(floors):
        zc = z0 + f * fh + fh * 0.55
        for side, length, axis, normal in (("front", W, "x", V(0, -1, 0)), ("back", W, "x", V(0, 1, 0)),
                                           ("left", D, "y", V(1, 0, 0)), ("right", D, "y", V(-1, 0, 0))):
            count = n_win if axis == "x" else max(0, int(round(n_win * D / W)))
            for i in range(count):
                t = (i + 0.5) / count * length - length / 2
                t *= 0.88
                if side == "front" and f == 0 and has_door and abs(t) < door_w * 0.5 + ww * 0.75:
                    continue
                if axis == "x":
                    p = V(t, normal.y * (D / 2 + 0.005), zc)
                else:
                    p = V(normal.x * (W / 2 + 0.005), t, zc)
                parts.window(mb, p, normal, ww, wh, trim, glass, arched=arched)

    top = z0 + H
    if roof == "gable":
        axis = "x" if W >= D else "y"
        rh = spec.num("roof_height", min(W, D) * 0.42, 0.2, 100)
        parts.gable_roof(mb, W, D, top, rh, roof_m, wall, overhang=0.4, axis=axis)
    elif roof == "hip":
        rh = spec.num("roof_height", min(W, D) * 0.40, 0.2, 100)
        if W >= D:
            parts.hip_roof(mb, W, D, top, rh, roof_m)
        else:
            from mathutils import Matrix
            import math
            with mb.part(xform=Matrix.Rotation(math.pi / 2, 4, "Z")):
                parts.hip_roof(mb, D, W, top, rh, roof_m)
    else:
        rh = 0.0
        mb.box((0, 0, top + 0.06), (W + 0.25, D + 0.25, 0.12), trim)
        ph = 0.7
        for sx in (-1, 1):
            mb.box((sx * (W / 2 - 0.1), 0, top + 0.12 + ph / 2), (0.24, D + 0.04, ph), wall)
        for sy in (-1, 1):
            mb.box((0, sy * (D / 2 - 0.1), top + 0.12 + ph / 2), (W + 0.04, 0.24, ph), wall)
        if roof == "battlement":
            parts.box_battlements(mb, W + 0.04, D + 0.04, top + 0.12 + ph, wall, merlon=0.7, height=0.7,
                                  thick=0.24)
        else:
            mb.box((W * 0.22, D * 0.18, top + 0.12 + 0.6), (min(2.2, W * 0.25), min(2.0, D * 0.25), 1.2), wall)
    if spec.flag("chimney", roof in ("gable", "hip") and type_name != "barn"):
        cx, cy = (W * 0.28, 0.0) if W >= D else (0.0, D * 0.28)
        ch = rh * 0.75 + 1.0
        mb.box((cx, cy, top + ch / 2), (0.7, 0.7, ch), stone)
        mb.box((cx, cy, top + ch + 0.06), (0.9, 0.9, 0.14), stone)
    return static.finish(ctx, spec, mb, bevel=0.02)
