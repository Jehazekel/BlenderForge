"""Bird: lofted body, beak, three-bone wings, tail fan and legs. Faces -Y."""

import math

from .. import creature
from ..meshkit import MeshBuilder, Palette, V, X, Y, Z, sec_dir, sec_x, sec_y, sec_z
from ..rigging import Rig

from ..anatomy import profiles, validate

NAMES = profiles.names("bird")
KEYS = ("wingspan", "neck", "leg", "beak", "tail", "girth")


def build(spec, ctx, type_name):
    P = profiles.get(type_name)
    profiles.apply_overrides(P, spec)
    span_k, neck_k, leg_k, beak_k, girth = (P[k] for k in ("wingspan", "neck", "leg", "beak", "girth"))
    col_d, beak_d = P["color"], P["beak_color"]
    name = spec.name
    S = spec.num("size", 0.5, 0.05, 20)                # beak-to-tail length
    span = spec.num("wingspan", span_k * S, 0.05, 60)
    girth *= {"slim": 0.85, "average": 1.0, "heavy": 1.25, "muscular": 1.1}[
        spec.choice("build", ("slim", "average", "heavy", "muscular"), "average")]
    col = spec.color("feathers", col_d)
    if spec.has("color"):
        col = spec.color("color", col_d)
    if spec.has("fur"):
        col = spec.color("fur", col_d)
    wing_c = spec.color("wing_color", tuple(c * 0.6 for c in col[:3]) + (1,))
    tail_len = {"long": 0.42, "short": 0.2, "none": 0.0}[spec.choice("tail", ("long", "short", "none"), "short")] * S * P["tail"]

    pal = Palette()
    feat = ctx.mat("Feathers", "fur", col, scale=1.6, deform=True)
    wingm = ctx.mat("Wings", "fur", wing_c, scale=1.6, deform=True)
    beakm = ctx.mat("Beak", "plain", spec.color("beak_color", beak_d), roughness=0.35)
    dark = ctx.mat("Dark", "plain", (0.02, 0.02, 0.02, 1), roughness=0.2)
    white = ctx.mat("EyeShine", "plain", (0.95, 0.95, 0.95, 1))
    mf, mw, mb_, md, mwh = (pal.index(m) for m in (feat, wingm, beakm, dark, white))
    body = MeshBuilder(pal)
    extras = MeshBuilder(pal)

    leg = 0.22 * S * leg_k
    r = 0.15 * S * girth
    zc = leg + r * 0.9
    L = 0.5 * S
    pitch = math.radians(50)
    n_len = 0.12 * S * neck_k
    hr = 0.085 * S
    neck0 = V(0, -L * 0.42, zc + r * 0.45)
    neck1 = neck0 + V(0, -math.cos(pitch), math.sin(pitch)) * n_len
    head_c = neck1 + V(0, -hr * 0.3, hr * 0.5)
    secs = [
        (V(0, L * 0.55, zc + r * 0.25), r * 0.22, r * 0.18, 0.2),
        (V(0, L * 0.38, zc + r * 0.10), r * 0.62, r * 0.55, 0.1),
        (V(0, L * 0.10, zc), r * 0.95, r * 0.92, 0.0),
        (V(0, -L * 0.20, zc), r * 1.0, r * 1.0, 0.0),
        (V(0, -L * 0.42, zc + r * 0.2), r * 0.74, r * 0.80, 0.25),
        ((neck0 + neck1) / 2, r * 0.42, r * 0.44, pitch),
        (neck1, hr * 0.80, hr * 0.80, pitch * 0.8),
        (head_c, hr, hr * 0.98, 0.25),
        (head_c + V(0, -hr * 0.72, -hr * 0.05), hr * 0.62, hr * 0.62, 0.0),
    ]
    rings = body.loft([sec_y(c, a, b, p) for c, a, b, p in secs], n=8, mat=mf,
                      cap_start=True, cap_end=False)
    body.cap(rings[-1], mf, c=head_c + V(0, -hr * 0.98, -hr * 0.08))

    # wings: flat lofts along X
    half = span / 2.0
    chord = 0.34 * S
    wy, wz = -L * 0.12, zc + r * 0.55
    wing_pts = {}
    for s, sg in (("L", 1), ("R", -1)):
        stations = [(0.55 * r, 0.75, 0.10), (half * 0.38, 1.0, 0.085), (half * 0.70, 0.82, 0.06),
                    (half * 0.92, 0.48, 0.04), (half, 0.16, 0.02)]
        wsecs = [sec_x((sg * x, wy + chord * (1 - c) * 0.35 + (x / half) ** 2 * chord * 0.25, wz),
                       chord * c * 0.5, chord * t) for x, c, t in stations]
        body.loft(wsecs, n=6, mat=mw)
        wing_pts[s] = [V(sg * x, wy, wz) for x in (0.4 * r, half * 0.38, half * 0.70, half)]

    # tail fan
    if tail_len > 0:
        t0 = V(0, L * 0.50, zc + r * 0.25)
        tsecs = [sec_y(t0, r * 0.30, r * 0.07, 0.1),
                 sec_y(t0 + V(0, tail_len * 0.5, tail_len * 0.04), r * 0.62, r * 0.05, 0.05),
                 sec_y(t0 + V(0, tail_len, tail_len * 0.06), r * 0.85, r * 0.03, 0.0)]
        body.loft(tsecs, n=6, mat=mw)

    # legs
    lr = 0.022 * S
    leg_pts = {}
    for s, sg in (("L", 1), ("R", -1)):
        x = sg * r * 0.42
        hip = V(x, L * 0.02, zc - r * 0.55)
        knee = V(x, L * 0.06, leg * 0.5)
        ank = V(x, L * 0.02, 0.02 * S)
        toe = V(x, -0.11 * S, 0.008 * S)
        body.loft([sec_z(hip, lr * 2.4, lr * 2.4), sec_z(knee, lr * 1.1, lr * 1.1), sec_z(ank, lr, lr)],
                  n=4, mat=mb_)
        body.loft([sec_y(ank + V(0, 0.03 * S, 0), lr * 1.3, lr * 0.8), sec_y((ank + toe) / 2, lr * 2.2, lr * 0.7),
                   sec_y(toe, lr * 2.6, lr * 0.5)], n=4, mat=mb_)
        leg_pts[s] = (hip, knee, ank, toe)

    # face
    face = creature.new_face()
    er = hr * 0.20
    for sg in (1, -1):
        creature.add_eye(extras, face, head_c + V(sg * hr * 0.72, -hr * 0.42, hr * 0.22), er,
                         V(sg, -0.55, 0.1), mwh, md, mf, pupil=False)
    b_len = 0.11 * S * beak_k
    b0 = head_c + V(0, -hr * 0.80, -hr * 0.10)
    with extras.part(bone="head"):
        ring = extras.ring(b0, X * hr * 0.40, Z * hr * 0.34, 4, phase=math.pi / 4)
        mid = extras.ring(b0 + V(0, -b_len * 0.5, -hr * 0.03), X * hr * 0.26, Z * hr * 0.22, 4, phase=math.pi / 4)
        extras.bridge(ring, mid, mb_)
        tip = extras.cap(mid, mb_, c=b0 + V(0, -b_len, -hr * 0.12))
        extras.face(ring, mb_)
    # beak: lower half opens, corners lift for Smile
    for v in mid + [tip]:
        if v.co.z < b0.z - hr * 0.02 or v is tip:
            face["jaw_x"].append((v.index, V(0, 0, -b_len * (0.5 if v is not tip else 0.25))))
    low = [v for v in ring if v.co.z < b0.z]
    face["mouth"] = [(v.index, 1.0, -1) for v in low]
    face["mouth_w"] = hr * 0.25

    # rig
    rig = Rig(name, "bird")
    rig.bone("root", (0, 0, 0), (0, 0.2 * S, 0), deform=False)
    bc = V(0, L * 0.25, zc)
    rig.bone("body", bc, V(0, -L * 0.30, zc + r * 0.1), "root")
    rig.bone("neck", V(0, -L * 0.30, zc + r * 0.1), neck1, "body", True)
    rig.bone("head", neck1, head_c + V(0, -hr * 0.9, 0), "neck", True)
    tail_names = []
    if tail_len > 0:
        t0 = V(0, L * 0.50, zc + r * 0.25)
        rig.bone("tail1", bc, t0, "body")
        rig.bone("tail2", t0, t0 + V(0, tail_len, tail_len * 0.06), "tail1", True)
        tail_names = ["tail2"]
    wings = {}
    for s, sg in (("L", 1), ("R", -1)):
        wings[s] = []
        parent = "body"
        for k in range(3):
            bn = "wing%d.%s" % (k + 1, s)
            rig.bone(bn, wing_pts[s][k], wing_pts[s][k + 1], parent, connect=k > 0)
            wings[s].append(bn)
            parent = bn
        hip, knee, ank, toe = leg_pts[s]
        rig.bone("thigh." + s, hip + V(0, 0, r * 0.2), knee, "body")
        rig.bone("shin." + s, knee, ank, "thigh." + s, True)
        rig.bone("foot." + s, ank, toe, "shin." + s, True)
    rig.meta = {"size": S, "wings": wings, "tail": tail_names}
    entity = creature.finalize(ctx, spec, name, body, extras, rig, face, "head")
    P["wingspan"] = span / S
    validate.report_params(name, P, KEYS, entity, spec)
    return entity

