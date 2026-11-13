"""Vehicles: car, truck and a wooden cart. Rigid rig with one bone per wheel,
so `animation: drive` spins the wheels. Faces -Y."""

import math

from mathutils import Matrix

from .. import creature
from ..meshkit import TAU, MeshBuilder, Palette, V, X, Y, Z, add_bevel, mark_sharp
from ..rigging import Rig

NAMES = ["car", "truck", "cart", "wagon", "van"]


def _wheel(mb, c, r, w, tire, hub, bone, spokes=0, wood=None):
    with mb.part(bone=bone):
        if spokes:
            mb.cylinder(c - X * w / 2, c + X * w / 2, r, n=16, mat=wood, hint=Z)
            mb.cylinder(c - X * w * 0.7, c + X * w * 0.7, r * 0.16, n=8, mat=hub, hint=Z)
            for k in range(spokes):
                a = TAU * k / spokes
                m = Matrix.Translation(c) @ Matrix.Rotation(a, 4, "X")
                with mb.part(xform=m):
                    mb.box((0, 0, r * 0.5), (w * 1.15, r * 0.09, r * 0.95), hub)
        else:
            mb.cylinder(c - X * w / 2, c + X * w / 2, r, n=20, mat=tire, hint=Z)
            mb.cylinder(c - X * w * 0.53, c + X * w * 0.53, r * 0.58, n=12, mat=hub, hint=Z)
            for k in range(5):                          # lug pattern so spin is visible
                a = TAU * k / 5
                p = c + V(0, math.cos(a), math.sin(a)) * r * 0.36
                mb.cylinder(p - X * w * 0.56, p + X * w * 0.56, r * 0.09, n=6, mat=tire, hint=Z)


def build(spec, ctx, type_name):
    name = spec.name
    kind = {"wagon": "cart", "van": "truck"}.get(type_name, type_name)
    dl, dw, dh = {"car": (4.2, 1.8, 1.45), "truck": (6.0, 2.2, 2.6), "cart": (2.6, 1.4, 1.3)}[kind]
    L = spec.num("length", dl, 0.5, 60)
    W = spec.num("width", dw, 0.3, 20)
    H = spec.num("height", dh, 0.3, 20)
    col = spec.color("color", {"car": "#b3261e", "truck": "#2f5d8a", "cart": "#7a5533"}[kind])

    pal = Palette()
    paint = ctx.mat("Paint", "metal" if kind != "cart" else "wood", col, roughness=0.25)
    glass = ctx.mat("Glass", "glass", (0.03, 0.05, 0.08, 1))
    tire = ctx.mat("Tire", "plain", (0.02, 0.02, 0.02, 1), roughness=0.9)
    hub = ctx.mat("Hub", "metal", (0.6, 0.62, 0.65, 1), roughness=0.3)
    dark = ctx.mat("Trim", "plain", (0.05, 0.05, 0.06, 1), roughness=0.6)
    lamp = ctx.mat("Lamp", "emissive", (1.0, 0.93, 0.7, 1), strength=3.0)
    red = ctx.mat("TailLamp", "emissive", (0.9, 0.05, 0.03, 1), strength=2.0)
    wood = ctx.mat("Wood", "wood", (0.19, 0.11, 0.06, 1))
    mb = MeshBuilder(pal)
    hw = W / 2
    rig = Rig(name, "vehicle")
    rig.bone("root", (0, 0, 0), (0, 0.3 * L, 0), deform=False)
    wheels = []

    def add_wheel(label, x, y, r, w, **kw):
        bone = "wheel_" + label
        _wheel(mb, V(x, y, r), r, w, tire, hub, bone, **kw)
        rig.bone(bone, (x, y, r), (x + (0.3 if x > 0 else -0.3) * r, y, r), "root")
        wheels.append(bone)

    if kind == "cart":
        r = H * 0.42
        bed_z = r + 0.05
        mb.box((0, 0, bed_z + 0.05), (W, L, 0.10), paint)
        for sx in (-1, 1):
            mb.box((sx * (hw - 0.04), 0, bed_z + 0.32), (0.08, L, 0.45), paint)
        for sy in (-1, 1):
            mb.box((0, sy * (L / 2 - 0.04), bed_z + 0.32), (W, 0.08, 0.45), paint)
        for sx in (-1, 1):                              # shafts
            mb.cylinder(V(sx * hw * 0.7, -L / 2, bed_z), V(sx * hw * 0.7, -L / 2 - L * 0.7, bed_z - 0.1),
                        0.04, n=6, mat=wood)
        mb.cylinder(V(-hw - 0.1, 0, r), V(hw + 0.1, 0, r), 0.05, n=6, mat=wood, hint=Z)
        add_wheel("L", hw + 0.12, 0, r, 0.09, spokes=8, wood=wood)
        add_wheel("R", -hw - 0.12, 0, r, 0.09, spokes=8, wood=wood)
        body_c = V(0, 0, bed_z)
        turns = 1
    else:
        r = 0.33 * (H / 1.45 if kind == "car" else 1.5)
        gz = r * 0.75                                   # ground clearance line
        if kind == "car":
            prof = [(0.50, gz), (0.50, H * 0.50), (0.46, H * 0.58), (0.30, H * 0.60), (0.17, H),
                    (-0.10, H), (-0.24, H * 0.60), (-0.47, H * 0.53), (-0.50, H * 0.40), (-0.50, gz)]
        else:
            prof = [(0.50, gz), (0.50, H * 0.42), (-0.12, H * 0.42), (-0.12, H * 0.78), (-0.20, H * 0.80),
                    (-0.40, H * 0.78), (-0.47, H * 0.48), (-0.50, H * 0.40), (-0.50, gz)]
        pts = [V(-hw, y * L, z) for y, z in prof]
        mb.extrude(pts, X * W, paint)
        if kind == "truck":                             # cargo box
            mb.box((0, L * 0.19, H * 0.42 + (H * 0.58) / 2), (W * 1.02, L * 0.60, H * 0.58), paint)
        # glass: side windows and screens sit just proud of the body
        if kind == "car":
            side = [(0.27, H * 0.63), (0.16, H * 0.94), (-0.09, H * 0.94), (-0.21, H * 0.63)]
            screens = [((-0.105, H * 0.985), (-0.235, H * 0.625)), ((0.175, H * 0.985), (0.295, H * 0.625))]
        else:
            side = [(-0.14, H * 0.50), (-0.14, H * 0.74), (-0.36, H * 0.74), (-0.43, H * 0.50)]
            screens = [((-0.405, H * 0.775), (-0.472, H * 0.50))]
        for sx in (-1, 1):
            mb.extrude([V(sx * (hw + 0.005), y * L, z) for y, z in side], X * sx * 0.01, glass)
        for (y0, z0), (y1, z1) in screens:
            off = V(0, -0.012 if y1 < y0 else 0.012, 0.012)
            mb.quad(V(-hw * 0.86, y0 * L, z0) + off, V(hw * 0.86, y0 * L, z0) + off,
                    V(hw * 0.86, y1 * L, z1) + off, V(-hw * 0.86, y1 * L, z1) + off, glass)
        # bumpers, grille, lamps
        mb.box((0, -L / 2 - 0.03, gz + 0.10), (W * 1.02, 0.14, 0.20), dark)
        mb.box((0, L / 2 + 0.03, gz + 0.10), (W * 1.02, 0.14, 0.20), dark)
        mb.box((0, -L / 2 - 0.01, H * 0.36), (W * 0.45, 0.04, H * 0.10), dark)
        for sx in (-1, 1):
            mb.box((sx * hw * 0.72, -L / 2 - 0.01, H * 0.40), (W * 0.18, 0.05, H * 0.08), lamp)
            mb.box((sx * hw * 0.72, L / 2 + 0.01, H * (0.40 if kind == "car" else 0.30)),
                   (W * 0.18, 0.05, H * 0.07), red)
        fy, ry = -L * 0.31, L * (0.30 if kind == "car" else 0.32)
        ww = 0.24 * (W / 1.8)
        for label, x, y in (("FL", hw - ww * 0.3, fy), ("FR", -hw + ww * 0.3, fy),
                            ("RL", hw - ww * 0.3, ry), ("RR", -hw + ww * 0.3, ry)):
            add_wheel(label, x, y, r, ww)
        body_c = V(0, 0, H * 0.4)
        turns = 2
    rig.bone("body", body_c, body_c + V(0, -0.3 * L, 0), "root")
    rig.meta = {"size": L / 4.0, "wheels": wheels, "turns": turns}
    entity = creature.finalize(ctx, spec, name, mb, None, rig, None, "body", auto=False)
    mesh_obj = entity.objects[1]
    mark_sharp(mesh_obj.data, 35)
    for m in list(mesh_obj.modifiers):                  # no subdivision on hard surfaces
        if m.type == "SUBSURF":
            mesh_obj.modifiers.remove(m)
    if not ctx.spec_lowpoly(spec) and kind != "cart":
        add_bevel(mesh_obj, 0.035 * (L / 4.2), 3)
    return entity
