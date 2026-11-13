"""Snakes: one loft along a straight spine chain. Faces -Y, belly on z = 0.

The rest pose is straight so left and right mirror exactly. The S-curve is a
pose (travelling wave down the spine): `animation: slither` moves it, and a
snake with no animation is left posed in the curve at phase 0.

Every proportion comes from the `serpent` profiles (`body.*`, body-length units).
"""

from .. import anims, creature
from ..anatomy import profiles, validate
from ..meshkit import MeshBuilder, Palette, V, X, Z, sec_y
from ..rigging import Rig

NAMES = profiles.names("serpent")
KEYS = ("radius", "head_length", "head_width", "waves", "amplitude")
N = 12                      # ring size: bottom is index 9
LOW = (7, 8, 9, 10, 11)


def build(spec, ctx, type_name):
    P = profiles.get(type_name)
    profiles.apply_overrides(P, spec)
    B = P["body"]
    name = spec.name
    S = spec.num("size", P.get("size", 1.0), 0.05, 40)          # nose to tail tip
    col = spec.color("scales", P["color"])
    for key in ("color", "fur"):
        if spec.has(key):
            col = spec.color(key, P["color"])
    belly_k = P["features"].get("belly", 0.0)
    belly_c = tuple(c + (1.0 - c) * belly_k for c in col[:3]) + (1.0,)
    if spec.has("belly"):
        belly_c = spec.color("belly", "#d8d0c0")

    pal = Palette()
    skin = ctx.mat("Scales", "scales", col, scale=1.4, deform=True)
    bel = ctx.mat("Belly", "scales", belly_c, scale=1.4, deform=True) if belly_k or spec.has("belly") else skin
    dark = ctx.mat("Dark", "plain", (0.02, 0.02, 0.02, 1), roughness=0.2)
    white = ctx.mat("EyeWhite", "plain", (0.92, 0.92, 0.9, 1), roughness=0.2)
    inner = ctx.mat("Mouth", "plain", (0.2, 0.05, 0.05, 1))
    ms, mb, md, mw, mm = (pal.index(m) for m in (skin, bel, dark, white, inner))
    body, extras = MeshBuilder(pal), MeshBuilder(pal)

    r = B["radius"] * S
    hl = B["head_length"] * S
    hw, hh = B["head_width"], B["head_height"]
    flat = B["flat"]
    y_nose, y_tail = -S / 2.0, S / 2.0
    n_bones, per_bone = int(B["bones"]), int(B["rings_per_bone"])

    # stations nose -> tail: (y, half width, half height)
    st = [(y_nose + hl * t, r * hw * w, r * hh * h) for t, w, h in B["head_stations"]]
    y_neck = y_nose + hl * B["neck_at"]
    st.append((y_neck, r * B["neck"], r * B["neck"] * flat))
    y_body = y_neck + hl * 0.5
    m_rings = n_bones * per_bone
    t0 = B["tail_from"]
    for j in range(m_rings + 1):
        y = y_body + (y_tail - y_body) * j / m_rings
        u = (y - y_nose) / S
        w = 1.0 if u <= t0 else 1.0 - (1.0 - B["tail_tip"]) * (u - t0) / (1.0 - t0)
        st.append((y, r * w, r * w * flat))
    secs = [sec_y(V(0, y, b), a, b) for y, a, b in reversed(st)]     # each ring rests on z = 0
    rings = body.loft(secs, n=N, mat=ms, cap_start=True, cap_end=False)
    n_head = len(B["head_stations"])
    tip_h = st[0][2]
    nose = V(0, y_nose - hl * 0.06, tip_h)
    body.cap(rings[-1], ms, c=nose)
    if mb != ms:
        under = {v.index for ring in rings for i, v in enumerate(ring) if i in LOW}
        for face in body.bm.faces:
            if all(v.index in under for v in face.verts):
                face.material_index = mb

    # face
    face = creature.new_face()
    ey, ew, eh = st[B["eye_station"]]
    for sg in (1, -1):
        creature.add_eye(extras, face, V(sg * ew * 0.80, ey, eh * 1.45), B["eye_size"] * S,
                         V(sg, -0.3, 0.25), mw, md, ms, bone="spine1", pupil=False)
    (y1, w1, h1), (y0, w0, h0) = st[1], st[0]
    mz1, mz0 = h1 * 0.80, h0 * 0.80
    pts = [(V(w1 * 0.98, y1, mz1), -1.0), (V(w0 * 0.98, y0, mz0), -0.5),
           (V(0, y0 - hl * 0.05, mz0), 0.0), (V(-w0 * 0.98, y0, mz0), 0.5),
           (V(-w1 * 0.98, y1, mz1), 1.0)]
    creature.add_mouth(extras, face, pts, mm, h0 * 0.10, bone="spine1")
    face["mouth_w"] = w0 * 0.5
    for ring, amount in ((rings[-1], 1.0), (rings[-2], 0.5)):
        for i in (8, 9, 10):
            face["jaw"].append((ring[i].index, V(0, 0, -h0 * 0.10 * amount)))

    # rig: spine chain head -> tail along the body axis
    rig = Rig(name, "serpent")
    rig.bone("root", (0, 0, 0), (0, 0.1 * S, 0), deform=False)
    zc = r * flat
    spine, parent = [], "root"
    for k in range(n_bones):
        bn = "spine%d" % (k + 1)
        rig.bone(bn, V(0, y_nose + S * k / n_bones, zc), V(0, y_nose + S * (k + 1) / n_bones, zc),
                 parent, connect=k > 0)
        spine.append(bn)
        parent = bn
    rig.meta = {"size": S, "spine": spine, "waves": B["waves"], "amplitude": B["amplitude"]}
    issues = validate.check_cage(body, extras) + validate.check_rig(rig)
    entity = creature.finalize(ctx, spec, name, body, extras, rig, face, "spine1")
    if not (spec.items("animation") or spec.items("animations")):
        anims.pose(entity.armature, rig, anims.serpent_slither, 0.0)
    flat_p = dict(B, name=P["name"], limits=P["limits"], source=P["source"])
    flat_p["class"] = P.get("class")
    validate.report_params(name, flat_p, KEYS, entity, spec, issues)
    return entity
