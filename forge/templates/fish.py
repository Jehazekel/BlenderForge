"""Fish: laterally flattened loft, fins as thin shells, spine chain. Faces -Y."""

import math

from .. import creature
from ..meshkit import MeshBuilder, Palette, V, X, Y, Z, sec_x, sec_y
from ..rigging import Rig

from ..anatomy import profiles, validate

NAMES = profiles.names("fish")
KEYS = ("body_height", "body_width", "peduncle", "tail_fin", "dorsal")


def build(spec, ctx, type_name):
    P = profiles.get(type_name)
    profiles.apply_overrides(P, spec)
    hk, wk, tk, dk, col_d = P["body_height"], P["body_width"], P["tail_fin"], P["dorsal"], P["color"]
    pk = P["peduncle"]                                 # tail-root depth relative to the default taper
    name = spec.name
    S = spec.num("size", 0.6, 0.03, 40)
    col = spec.color("scales", col_d)
    for key in ("color", "fur"):
        if spec.has(key):
            col = spec.color(key, col_d)
    fin_c = spec.color("fin_color", tuple(min(1.0, c * 1.25 + 0.03) for c in col[:3]) + (1,))
    depth = spec.num("depth", 0.0)                     # swim height above z = 0

    pal = Palette()
    skin = ctx.mat("Scales", "scales", col, scale=1.4, deform=True)
    finm = ctx.mat("Fins", "scales", fin_c, scale=1.4, deform=True)
    dark = ctx.mat("Dark", "plain", (0.02, 0.02, 0.02, 1), roughness=0.2)
    white = ctx.mat("EyeWhite", "plain", (0.92, 0.92, 0.9, 1), roughness=0.2)
    inner = ctx.mat("Mouth", "plain", (0.2, 0.05, 0.05, 1))
    ms, mfin, md, mw, mm = (pal.index(m) for m in (skin, finm, dark, white, inner))
    body = MeshBuilder(pal)
    extras = MeshBuilder(pal)

    rz, rx = 0.17 * S * hk, 0.075 * S * wk
    zc = max(rz * 1.6, depth)
    # stations from nose (-Y) to tail root (+Y): (y, width, height)
    st = [(-0.50, 0.30, 0.28), (-0.40, 0.72, 0.66), (-0.25, 0.95, 0.92), (-0.05, 1.0, 1.0),
          (0.15, 0.82, 0.86), (0.30, 0.52, 0.55 * (1 + pk) / 2), (0.40, 0.26, min(0.30 * pk, 0.8))]
    secs = [sec_y(V(0, y * S, zc), rx * w, rz * h) for y, w, h in reversed(st)]
    rings = body.loft(secs, n=8, mat=ms, cap_start=True, cap_end=False)
    nose = V(0, -0.535 * S, zc - rz * 0.05)
    body.cap(rings[-1], ms, c=nose)

    # tail fin: thin vertical fan
    th = 0.24 * S * tk
    y0 = 0.39 * S
    body.loft([sec_y(V(0, y0, zc), rx * 0.14, rz * 0.26),
               sec_y(V(0, y0 + 0.09 * S * tk, zc), rx * 0.10, th * 0.75),
               sec_y(V(0, y0 + 0.17 * S * tk, zc), rx * 0.05, th)], n=6, mat=mfin)
    # dorsal and belly fins
    for zs, hgt, ys in ((1, 0.16 * S * dk, -0.05), (-1, 0.07 * S, 0.12)):
        base = zc + zs * rz * 0.90
        pts = [V(0, (ys - 0.10) * S, base), V(0, (ys + 0.02) * S, base + zs * hgt),
               V(0, (ys + 0.14) * S, base + zs * hgt * 0.35), V(0, (ys + 0.13) * S, base)]
        body.extrude([p - X * rx * 0.07 for p in pts], X * rx * 0.14, mfin)
    # pectoral fins
    fins = {}
    for s, sg in (("L", 1), ("R", -1)):
        root = V(sg * rx * 0.85, -0.24 * S, zc - rz * 0.35)
        tip = root + V(sg * 0.13 * S, 0.07 * S, -0.05 * S)
        fsecs = [sec_x(root, 0.03 * S, 0.008 * S), sec_x((root + tip) / 2 + V(0, 0.01 * S, 0), 0.05 * S, 0.006 * S),
                 sec_x(tip, 0.02 * S, 0.004 * S)]
        body.loft(fsecs, n=6, mat=mfin)
        fins[s] = (root, tip)

    # face
    face = creature.new_face()
    er = rz * 0.17
    for sg in (1, -1):
        creature.add_eye(extras, face, V(sg * rx * 0.78, -0.36 * S, zc + rz * 0.22), er,
                         V(sg, -0.25, 0.05), mw, md, ms, bone="spine1")
    mz = zc - rz * 0.12
    pts = [(V(rx * 0.62, -0.445 * S, mz), -1.0), (V(rx * 0.36, -0.505 * S, mz), -0.5),
           (V(0, -0.528 * S, mz), 0.0), (V(-rx * 0.36, -0.505 * S, mz), 0.5),
           (V(-rx * 0.62, -0.445 * S, mz), 1.0)]
    creature.add_mouth(extras, face, pts, mm, rz * 0.05, bone="spine1")
    face["mouth_w"] = rz * 0.28
    for i in (5, 6, 7):
        face["jaw"].append((rings[-1][i].index, V(0, 0, -rz * 0.16)))

    # rig: spine chain from head to tail
    rig = Rig(name, "fish")
    rig.bone("root", (0, 0, 0), (0, 0.2 * S, 0), deform=False)
    ys = [-0.50, -0.22, -0.02, 0.16, 0.30, 0.40, 0.40 + 0.17 * tk]
    spine = []
    parent = "root"
    for k in range(len(ys) - 1):
        bn = "spine%d" % (k + 1)
        rig.bone(bn, V(0, ys[k] * S, zc), V(0, ys[k + 1] * S, zc), parent, connect=k > 0)
        spine.append(bn)
        parent = bn
    for s in ("L", "R"):
        rig.bone("fin." + s, fins[s][0], fins[s][1], "spine2")
    rig.meta = {"size": S, "spine": spine}
    entity = creature.finalize(ctx, spec, name, body, extras, rig, face, "spine1")
    validate.report_params(name, P, KEYS, entity, spec)
    return entity
