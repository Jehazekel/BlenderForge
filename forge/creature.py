"""Shared pieces for rigged creatures: eyes, mouths, ears, face shape keys and
the final skin -> merge -> shape keys -> animate pipeline."""

import math

from mathutils import Vector

from . import anims, rigging
from .core import Entity
from .log import warn
from .meshkit import X, Y, Z, add_subsurf, sec_dir, unwrap

EXPRESSIONS = {
    "smile": {"Smile": 1.0}, "happy": {"Smile": 1.0}, "grin": {"Smile": 1.0, "MouthOpen": 0.35},
    "frown": {"Frown": 1.0}, "sad": {"Frown": 0.8}, "angry": {"Frown": 1.0, "MouthOpen": 0.15},
    "blink": {"Blink": 1.0}, "sleep": {"Blink": 1.0}, "sleepy": {"Blink": 0.6},
    "open_mouth": {"MouthOpen": 1.0}, "open": {"MouthOpen": 1.0}, "mouth_open": {"MouthOpen": 1.0},
    "shout": {"MouthOpen": 1.0, "Frown": 0.5},
    "surprised": {"MouthOpen": 0.6, "BrowUp": 1.0}, "brow_up": {"BrowUp": 1.0},
    "oo": {"Pucker": 1.0, "MouthOpen": 0.25}, "ee": {"Wide": 1.0, "MouthOpen": 0.2},
    "neutral": {}, "none": {},
}


def new_face(up=Z):
    return {"mouth": [], "mouth_w": 0.1, "lids": [], "brows": [], "brow_h": 0.01,
            "jaw": [], "jaw_x": [], "up": Vector(up)}


def add_eye(mb, face, c, r, fwd, white, dark, lid_mat, bone="head", pupil=True, up=Z):
    """Eyeball, pupil and an upper lid that the Blink key pulls down."""
    c, fwd, up = Vector(c), Vector(fwd).normalized(), Vector(up)
    with mb.part(bone=bone):
        mb.sphere(c, r, white if pupil else dark, n=8, m=5)
        if pupil:
            mb.sphere(c + fwd * r * 0.55, r * 0.5, dark, n=8, m=3)
        else:
            mb.sphere(c + fwd * r * 0.62 + up * r * 0.38,
                      r * 0.22, white, n=4, m=2)
        start = mb.count
        big = r * 1.17
        mb.sphere(c, big, lid_mat, n=8, m=5)
    mb.bm.verts.ensure_lookup_table()
    for i in range(start, mb.count):
        v = mb.bm.verts[i]
        full = v.co.copy()
        rel = full - c
        h = rel.dot(up)
        flat = rel - up * h
        lat = math.asin(max(-1.0, min(1.0, h / big)))
        # Resting lid: the whole dome is gathered into a cap over the top of
        # the eyeball. Blink slides it back down to the full dome.
        lat2 = math.radians(38) + (lat + math.pi / 2) / math.pi * math.radians(52)
        ldir = flat.normalized() if flat.length > 1e-6 else Vector()
        v.co = c + (ldir * math.cos(lat2) + up * math.sin(lat2)) * big
        face["lids"].append((i, full - v.co))


def add_mouth(mb, face, points, mat, thickness, bone="head", up=Z):
    """A dark lip strip. `points` is [(position, xn)] with xn from -1 to 1."""
    up = Vector(up)
    with mb.part(bone=bone):
        top, bot = [], []
        for pos, xn in points:
            taper = 1.0 - 0.75 * abs(xn) ** 2
            t = mb.vert(Vector(pos) + up * thickness * 0.5 * taper)
            b = mb.vert(Vector(pos) - up * thickness * 0.5 * taper)
            face["mouth"].append((t.index, xn, 1))
            face["mouth"].append((b.index, xn, -1))
            top.append(t)
            bot.append(b)
        for i in range(len(points) - 1):
            mb.face([bot[i], bot[i + 1], top[i + 1], top[i]], mat)
    face["mouth_w"] = (Vector(points[0][0]) - Vector(points[-1][0])).length / 2.0


def add_brow(mb, face, c, size, mat, side, bone="head"):
    """Small brow block; the vertices nearest the nose drop for Frown."""
    with mb.part(bone=bone):
        verts = mb.box(c, size, mat)
    for v in verts:
        inner = 1.0 if (v.co.x - c[0]) * side < 0 else 0.0
        face["brows"].append((v.index, inner))
    face["brow_h"] = size[2]


def add_ear(mb, kind, base, out, up, size, mat, inner_mat, bone):
    """Ear shell at an attachment point. kind: pointed, round, floppy."""
    base, out, up = Vector(base), Vector(out).normalized(), Vector(up).normalized()
    side = up.cross(out).normalized()
    with mb.part(bone=bone):
        if kind == "round":
            c = base + up * size * 0.12
            secs = [sec_dir(c + out * size * d, out, size * w, size * w, hint=up)
                    for d, w in ((-0.12, 0.3), (0.0, 0.52), (0.1, 0.3))]
            mb.loft(secs, n=8, mat=mat)
        elif kind == "floppy":
            pts = [base, base + out * size * 0.35 + up * size * 0.15,
                   base + out * size * 0.55 - up * size * 0.45, base + out * size * 0.5 - up * size * 1.0]
            wid = [0.30, 0.36, 0.32, 0.14]
            secs = []
            for i, p in enumerate(pts):
                t = pts[min(i + 1, 3)] - pts[max(i - 1, 0)]
                secs.append(sec_dir(p, t, size * wid[i], size * 0.09, hint=out))
            mb.loft(secs, n=6, mat=mat)
        else:       # pointed
            tip = base + up * size + out * size * 0.15
            secs = [(base - up * size * 0.1, side * size * 0.36, out * size * 0.20),
                    (base + up * size * 0.45 + out * size * 0.05, side * size * 0.25, out * size * 0.12)]
            rings = mb.loft(secs, n=6, mat=mat, cap_end=False)
            mb.cap(rings[-1], mat, c=tip)


def face_shape_keys(face, offset):
    """Smile, Frown, Blink and MouthOpen as per-vertex offsets.

    Indices from the extras builder are shifted by `offset`; jaw entries index
    the body mesh directly.
    """
    up = face["up"]
    w = face["mouth_w"]
    bh = face["brow_h"]
    keys = {"Smile": {}, "Frown": {}, "Blink": {}, "MouthOpen": {}}
    for i, xn, row in face["mouth"]:
        g = offset + i
        x2 = xn * xn
        keys["Smile"][g] = up * (w * (0.42 * x2 - 0.10))
        keys["Frown"][g] = up * (w * (-0.36 * x2 + 0.07))
        opening = (1.0 - x2)
        keys["MouthOpen"][g] = up * (w * (0.12 if row > 0 else -0.60) * opening)
    for i, delta in face["lids"]:
        keys["Blink"][offset + i] = delta
    for i, inner in face["brows"]:
        g = offset + i
        keys["Frown"][g] = up * (-bh * 1.3 * inner + bh * 0.3 * (1 - inner))
        keys["Smile"][g] = up * (bh * 0.5)
    for i, delta in face["jaw"]:
        keys["MouthOpen"][i] = keys["MouthOpen"].get(i, Vector()) + delta
    for i, delta in face["jaw_x"]:          # jaw vertices that live in the extras builder
        keys["MouthOpen"][offset + i] = keys["MouthOpen"].get(offset + i, Vector()) + delta
    for names, shift in ((face.get("keys", {}), 0), (face.get("keys_x", {}), offset)):
        for name in sorted(names):          # extra keys (visemes, brows): body, then extras indices
            dst = keys.setdefault(name, {})
            for i, delta in names[name].items():
                dst[shift + i] = dst.get(shift + i, Vector()) + delta
    return {k: v for k, v in keys.items() if v}


def finalize(ctx, spec, name, body, extras, rig, face, default_bone, accessories=(),
             auto=True, preserve_volume=False, smooth_weights=0):
    """Turn builders + rig into a skinned, shape-keyed, animated entity."""
    lowpoly = ctx.spec_lowpoly(spec)
    levels = 0 if lowpoly else spec.integer("subdiv", ctx.subdiv, 0, 3)
    arm = rig.build(ctx.collection)
    obj = body.to_object(name, ctx.collection)
    if auto:
        loose = [arm.data.bones[n] for n in getattr(rig, "rigid_only", ())]
        for b in loose:                     # bones that only carry rigid parts take no skin weights
            b.use_deform = False
        rigging.skin_auto(obj, arm, preserve_volume)
        for b in loose:
            b.use_deform = True
        rigging.smooth_weights(obj, smooth_weights)
        offset = rigging.merge_rigid(obj, arm, extras, default_bone)
        rigging.clean_weights(obj)
    else:
        rigging.skin_rigid(obj, arm, body.rigid, default_bone)
        offset = len(obj.data.vertices)
    unwrap(obj)
    if face is not None:
        rigging.add_shape_keys(obj, face_shape_keys(face, offset))
    add_subsurf(obj, levels)
    objects = [arm, obj]
    for acc_obj, bone in accessories:
        rigging.parent_to_bone(acc_obj, arm, bone)
        objects.append(acc_obj)

    anims.animate(arm, rig, spec, ctx)

    keys = obj.data.shape_keys
    for raw in spec.items("expression"):
        combo = EXPRESSIONS.get(raw)
        if combo is None:
            warn("unknown expression '%s' (options: %s)" % (raw, ", ".join(sorted(EXPRESSIONS))),
                 spec.line_of("expression"))
            continue
        for key, value in combo.items():
            if keys is not None and key in keys.key_blocks:
                keys.key_blocks[key].value = value
    if face is not None and spec.flag("blink", True) and "blink" not in spec.items("expression"):
        if spec.items("animation") or spec.items("animations"):
            anims.blink_action(obj, name, ctx.fps, ctx.frame_start)
    if face is not None and "talk" in spec.items("animation") + spec.items("animations"):
        anims.talk_action(obj, name, ctx.fps, ctx.frame_start)
    return Entity(name, arm, objects, armature=arm, static=False)
