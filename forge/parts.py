"""Modular hard-surface parts: windows, doors, roofs, battlements, weapons.

Wall parts are modelled in a local frame (X right, Y outward, Z up) and placed
with `mb.part(xform=basis(point, normal))`.
"""

import math

from mathutils import Matrix, Vector

from .meshkit import TAU, V, X, Y, Z, basis, sec_z


def _arc_frame(mb, w, top, depth, t, mat, steps=6):
    """Half-round frame of small blocks above a window or door."""
    r = w / 2.0
    for k in range(steps):
        a = math.pi * (k + 0.5) / steps
        c = V(math.cos(a) * r, depth / 2.0, top + math.sin(a) * r)
        m = Matrix.Translation(c) @ Matrix.Rotation(a - math.pi / 2, 4, "Y").inverted()
        with mb.part(xform=m):
            mb.box((0, 0, 0), (math.pi * r / steps * 1.12, depth, t), mat)


def _arc_panel(mb, w, top, y, mat, steps=6):
    """Half-disc pane filling the arch."""
    r = w / 2.0
    pts = [V(math.cos(math.pi * k / steps) * r, y, top + math.sin(math.pi * k / steps) * r)
           for k in range(steps + 1)]
    mb.face([mb.vert(p) for p in pts], mat)


def window(mb, point, normal, w, h, frame_mat, glass_mat, arched=False, sill=True, bars=True):
    """Framed window centred on `point`. No hole is cut; the pane sits on the wall."""
    t = max(0.05, w * 0.11)
    d = t * 0.9
    with mb.part(xform=basis(point, normal)):
        body_h = h - (w / 2.0 if arched else 0.0)
        z0 = -h / 2.0
        top = z0 + body_h
        mb.box((0, 0.012, z0 + body_h / 2.0), (w, 0.024, body_h), glass_mat)
        mb.box((-w / 2 - t / 2, d / 2, z0 + body_h / 2), (t, d, body_h), frame_mat)
        mb.box((w / 2 + t / 2, d / 2, z0 + body_h / 2), (t, d, body_h), frame_mat)
        if arched:
            _arc_panel(mb, w, top, 0.024, glass_mat)
            _arc_frame(mb, w + t, top, d, t, frame_mat)
        else:
            mb.box((0, d / 2, top + t / 2), (w + 2 * t, d, t), frame_mat)
        if sill:
            mb.box((0, d * 0.8, z0 - t / 2), (w + 3 * t, d * 1.6, t), frame_mat)
        else:
            mb.box((0, d / 2, z0 - t / 2), (w + 2 * t, d, t), frame_mat)
        if bars:
            mb.box((0, 0.03, z0 + body_h / 2), (t * 0.4, 0.03, body_h), frame_mat)
            mb.box((0, 0.03, z0 + body_h * 0.55), (w, 0.03, t * 0.4), frame_mat)


def door(mb, point, normal, w, h, frame_mat, door_mat, metal_mat=None, arched=False, step=True):
    """Door whose bottom centre is `point`."""
    t = max(0.07, w * 0.12)
    d = t
    with mb.part(xform=basis(point, normal)):
        body_h = h - (w / 2.0 if arched else 0.0)
        mb.box((0, 0.02, body_h / 2), (w, 0.04, body_h), door_mat)
        for k in (-1, 0, 1):                         # plank grooves read as a real door
            mb.box((k * w / 3.2, 0.045, body_h / 2), (w / 3.6, 0.02, body_h * 0.94), door_mat)
        mb.box((-w / 2 - t / 2, d / 2, body_h / 2), (t, d, body_h), frame_mat)
        mb.box((w / 2 + t / 2, d / 2, body_h / 2), (t, d, body_h), frame_mat)
        if arched:
            _arc_panel(mb, w, body_h, 0.04, door_mat)
            _arc_frame(mb, w + t, body_h, d, t, frame_mat)
        else:
            mb.box((0, d / 2, body_h + t / 2), (w + 2 * t, d, t), frame_mat)
        if metal_mat is not None:
            mb.sphere((w * 0.32, 0.09, body_h * 0.5), w * 0.045, metal_mat, n=6, m=3)
            for z in (body_h * 0.2, body_h * 0.8):
                mb.box((-w * 0.2, 0.06, z), (w * 0.55, 0.025, 0.05), metal_mat)
        if step:
            mb.box((0, 0.25, -0.06), (w + 4 * t, 0.5, 0.14), frame_mat)


def gable_roof(mb, w, d, z, height, roof_mat, wall_mat, overhang=0.35, thick=0.14, axis="x"):
    """Pitched roof over a w (X) by d (Y) box, ridge along `axis`, plus gable walls."""
    turn = Matrix.Identity(4) if axis == "x" else Matrix.Rotation(math.pi / 2, 4, "Z")
    if axis != "x":
        w, d = d, w
    with mb.part(xform=turn):
        hw, hd = w / 2.0, d / 2.0
        slope = math.atan2(height, hd)
        eave = hd + overhang
        drop = overhang * math.tan(slope)
        ty = thick / math.sin(slope) if slope > 0.2 else thick
        prof = [V(0, -eave, z - drop), V(0, 0, z + height), V(0, eave, z - drop),
                V(0, eave, z - drop + thick), V(0, 0, z + height + ty * math.sin(slope) + thick * 0.4),
                V(0, -eave, z - drop + thick)]
        mb.extrude([p + X * (-hw - overhang) for p in prof], X * (w + 2 * overhang), roof_mat)
        tri = [V(0, -hd, z), V(0, hd, z), V(0, 0, z + height)]
        mb.extrude([p + X * (-hw) for p in tri], X * 0.02, wall_mat)
        mb.extrude([p + X * (hw - 0.02) for p in tri], X * 0.02, wall_mat)
        # ridge cap
        mb.box((0, 0, z + height + thick * 0.9), (w + 2 * overhang + 0.06, 0.18, 0.12), roof_mat)


def hip_roof(mb, w, d, z, height, roof_mat, overhang=0.35):
    hw, hd = w / 2.0 + overhang, d / 2.0 + overhang
    ridge = max(0.0, hw - hd)
    b = [mb.vert(p) for p in (V(-hw, -hd, z), V(hw, -hd, z), V(hw, hd, z), V(-hw, hd, z))]
    lo = [mb.vert(p - Z * 0.12) for p in (V(-hw, -hd, z), V(hw, -hd, z), V(hw, hd, z), V(-hw, hd, z))]
    r0, r1 = mb.vert(V(-ridge, 0, z + height)), mb.vert(V(ridge, 0, z + height))
    mb.face([b[0], b[1], r1, r0], roof_mat)
    mb.face([b[2], b[3], r0, r1], roof_mat)
    mb.face([b[1], b[2], r1], roof_mat)
    mb.face([b[3], b[0], r0], roof_mat)
    for i in range(4):
        mb.face([lo[i], lo[(i + 1) % 4], b[(i + 1) % 4], b[i]], roof_mat)
    mb.face(lo, roof_mat)


def cone_roof(mb, center, radius, height, n, mat, flare=0.12):
    c = Vector(center)
    lo = mb.ring(c - Z * 0.1, X * radius, Y * radius, n)
    mid = mb.ring(c + Z * height * 0.12, X * radius * (0.9 - flare), Y * radius * (0.9 - flare), n)
    mb.bridge(lo, mid, mat)
    mb.fan(mid, c + Z * height, mat)
    mb.cap(lo, mat)


def dome_roof(mb, center, radius, n, mat, squash=0.85):
    c = Vector(center)
    secs = [sec_z(c + Z * radius * squash * math.sin(a), radius * math.cos(a), radius * math.cos(a))
            for a in (0.0, 0.35, 0.7, 1.05, 1.35)]
    mb.loft(secs, n=n, mat=mat, cap_start=True, cap_end=True,
            end_tip=c + Z * radius * squash)


def ring_battlements(mb, center, radius, mat, merlon=0.6, height=0.6, thick=0.3):
    count = max(6, int(round(TAU * radius / (merlon * 2.0))))
    for k in range(count):
        a = TAU * k / count
        m = Matrix.Translation(Vector(center)) @ Matrix.Rotation(a, 4, "Z")
        with mb.part(xform=m):
            mb.box((radius - thick / 2, 0, height / 2), (thick, merlon, height), mat)


def box_battlements(mb, w, d, z, mat, merlon=0.6, height=0.6, thick=0.3):
    for axis, length, off in (("x", w, d / 2), ("y", d, w / 2)):
        count = max(2, int(round(length / (merlon * 2.0))))
        pitch = length / count
        for sign in (-1, 1):
            for k in range(count + 1):
                t = -length / 2 + k * pitch
                if axis == "x":
                    mb.box((t, sign * (off - thick / 2), z + height / 2), (merlon, thick, height), mat)
                elif 0 < k < count:
                    mb.box((sign * (off - thick / 2), t, z + height / 2), (thick, merlon, height), mat)


def flag(mb, base, height, pole_mat, cloth_mat):
    b = Vector(base)
    mb.cylinder(b, b + Z * height, height * 0.018, n=6, mat=pole_mat)
    mb.sphere(b + Z * height, height * 0.04, pole_mat, n=6, m=3)
    w, h = height * 0.5, height * 0.3
    pts = [b + V(0, 0, height * 0.95), b + V(w * 0.5, 0.03, height * 0.95 - h * 0.1),
           b + V(w, -0.02, height * 0.95 - h * 0.5), b + V(w * 0.5, 0.03, height * 0.95 - h * 0.9),
           b + V(0, 0, height * 0.95 - h)]
    mb.extrude(pts, Y * 0.015, cloth_mat)


# -- weapons and gear (modelled upright at the grip, +Z is the business end) ---

def sword(mb, length, blade_mat, hilt_mat, grip_mat):
    g = length * 0.16
    w = length * 0.075
    mb.cylinder(V(0, 0, -g * 0.55), V(0, 0, g * 0.5), length * 0.018, n=8, mat=grip_mat)
    mb.sphere(V(0, 0, -g * 0.7), length * 0.034, hilt_mat, n=8, m=3)
    mb.box((0, 0, g * 0.55), (length * 0.26, length * 0.036, length * 0.03), hilt_mat)
    z0, z1, z2 = g * 0.62, length * 0.86, length
    t = length * 0.011
    lo = [mb.vert(p) for p in (V(-w / 2, 0, z0), V(0, -t, z0), V(w / 2, 0, z0), V(0, t, z0))]
    hi = [mb.vert(p) for p in (V(-w * 0.42, 0, z1), V(0, -t, z1), V(w * 0.42, 0, z1), V(0, t, z1))]
    mb.bridge(lo, hi, blade_mat)
    mb.fan(hi, V(0, 0, z2), blade_mat)
    mb.face(lo, blade_mat)


def shield(mb, radius, face_mat, rim_mat, style="round"):
    """Faces -Y. Round or heater (kite) outline."""
    n = 16
    if style == "round":
        outline = [V(math.cos(TAU * k / n) * radius, 0, math.sin(TAU * k / n) * radius) for k in range(n)]
    else:
        outline = [V(-radius * 0.8, 0, radius), V(radius * 0.8, 0, radius), V(radius * 0.8, 0, 0.1 * radius),
                   V(radius * 0.45, 0, -radius * 0.7), V(0, 0, -radius * 1.15),
                   V(-radius * 0.45, 0, -radius * 0.7), V(-radius * 0.8, 0, 0.1 * radius)]
    t = radius * 0.1
    bulge = radius * 0.16
    back = [mb.vert(p + Y * t) for p in outline]
    front = [mb.vert(p) for p in outline]
    inner = [mb.vert(p * 0.82 - Y * bulge * 0.4) for p in outline]
    mb.bridge(back, front, rim_mat)
    mb.bridge(front, inner, rim_mat)
    mb.fan(inner, V(0, -bulge, 0), face_mat)
    mb.face(back, rim_mat)
    mb.sphere(V(0, -bulge, 0), radius * 0.16, rim_mat, n=8, m=3)


def staff(mb, length, wood_mat, gem_mat):
    mb.cylinder(V(0, 0, 0), V(0, 0, length), length * 0.014, length * 0.011, n=8, mat=wood_mat)
    mb.sphere(V(0, 0, length + length * 0.035), length * 0.04, gem_mat, n=8, m=4)
    for k in range(3):
        a = TAU * k / 3
        p = V(math.cos(a), math.sin(a), 0) * length * 0.03
        mb.cylinder(p + Z * (length * 0.97), p * 1.3 + Z * (length * 1.06), length * 0.007, n=4, mat=wood_mat)


def axe(mb, length, blade_mat, wood_mat):
    mb.cylinder(V(0, 0, -length * 0.15), V(0, 0, length * 0.85), length * 0.02, n=8, mat=wood_mat)
    z = length * 0.72
    r = length * 0.2
    prof = [V(0.01, 0, z - r * 0.25), V(r * 0.8, 0, z - r * 0.7), V(r, 0, z),
            V(r * 0.8, 0, z + r * 0.7), V(0.01, 0, z + r * 0.25)]
    mb.extrude([p - Y * length * 0.012 for p in prof], Y * length * 0.024, blade_mat)
    mb.box((0, 0, z), (length * 0.06, length * 0.05, r * 0.6), blade_mat)
