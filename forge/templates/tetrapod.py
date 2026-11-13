"""Four-limbed animals (mammals, reptiles, amphibians) from a solved skeleton.

This file is geometry only. Every position it uses comes from
`anatomy.skeleton.solve`, which in turn reads an anatomical profile from
`forge/anatomy/data/*.json`. A new species or breed is a new JSON entry.
"""

import math

from .. import creature
from ..anatomy import profiles, reference, skeleton, validate
from ..meshkit import MeshBuilder, Palette, V, X, Y, Z, sec_y
from ..rigging import Rig

NAMES = profiles.names("tetrapod")
TAILS = ("long", "short", "bushy", "none")
EARS = ("pointed", "round", "floppy", "none")
BUILDS = {"slim": 0.85, "average": 1.0, "muscular": 1.15, "heavy": 1.35}
N = 12                      # ring size: bottom is index 9
LOW = (7, 8, 9, 10, 11)     # ring vertices below the midline
SLOTS = ("fur", "belly", "hair", "dark", "white", "mouth", "hoof", "horn")


def _transport(points, radii, last_down=0):
    """Ring sections along a path with a twist-free (parallel transport) frame.

    The final `last_down` sections are forced horizontal so feet sit flat.
    """
    n = len(points)
    secs, u = [], None
    for i, p in enumerate(points):
        if i >= n - last_down:
            t = V(0, 0, -1)
        else:
            t = (points[min(i + 1, n - 1)] - points[max(i - 1, 0)])
            t = t.normalized() if t.length > 1e-9 else V(0, 0, -1)
        if u is None:
            u = Y.cross(t)
            if u.length < 0.2:
                u = X.cross(t)
        else:
            u = u - t * u.dot(t)
            if u.length < 1e-4:
                u = Y.cross(t) if abs(t.y) < 0.9 else X.cross(t)
        u.normalize()
        v = t.cross(u)
        r1, r2 = radii[i]
        secs.append((p, u * r1, v * r2))
    return secs


def apply_friendly(P, spec):
    """The simple keys (leg_length, build, tail...) as edits to the profile."""
    g = BUILDS[spec.choice("build", BUILDS, "average")] * spec.num("girth", 1.0, 0.4, 2.5)
    g = 1.0 + (g - 1.0) * 0.8
    P["trunk"]["chest_depth"] *= g
    P["trunk"]["chest_width"] *= g
    k = spec.num("leg_length", 1.0, 0.3, 3.0)
    P["limb"]["fore_scale"] *= k
    P["limb"]["hind_scale"] *= k
    P["neck"]["length"] *= spec.num("neck_length", 1.0, 0.2, 3.0)
    k = spec.num("head_size", 1.0, 0.5, 2.5)
    for key in ("skull", "muzzle", "width", "muzzle_width", "depth"):
        P["head"][key] *= k
    P["head"]["muzzle"] *= spec.num("snout_length", 1.0, 0.2, 3.0)
    if spec.has("tail"):
        t = spec.choice("tail", TAILS, "long")
        tl = P["tail"]
        if t == "none":
            tl["length"] = 0.0
        elif t == "short":
            tl["length"] = min(tl["length"], 0.12) or 0.12
        elif t == "bushy":
            tl.update(style="bushy", radius=max(tl["radius"], 0.085), length=max(tl["length"], 0.5))
        else:
            tl["length"] = max(tl["length"], 0.55)
            if tl.get("style") == "bushy":
                tl["style"] = "plain"
                tl["radius"] = 0.035
    if spec.has("ears"):
        P["ears"]["type"] = spec.choice("ears", EARS, P["ears"]["type"])
        if P["ears"]["size"] <= 0:
            P["ears"]["size"] = 0.10
    P["surface"] = spec.choice("material", ("fur", "skin", "scales"), P["surface"])


def make(sk, slot):
    """Pure geometry: skeleton -> (body builder, extras builder, rig, face).

    `slot` maps material slot names to palette indices, so this also runs
    without Blender materials (used when fitting to a reference silhouette).
    """
    P = sk.profile
    k = sk.scale
    feats = P["features"]
    sprawl = P.get("posture") == "sprawl"
    mammal = P.get("class") == "mammal"
    body, extras = MeshBuilder(slot["_palette"]), MeshBuilder(slot["_palette"])
    mf, mbel, mhair, md, mw, mm, mhoof = (slot[s] for s in SLOTS[:7])

    # ---- one loft: tail tip -> rump -> chest -> neck -> head -> nose ------------
    secs = []
    tail_pts = [p for p, _ in sk.tail]
    for i in range(len(sk.tail) - 1, -1, -1):            # tip first
        p, r = sk.tail[i]
        a, c = tail_pts[max(i - 1, 0)], tail_pts[min(i + 1, len(tail_pts) - 1)]
        d = a - c if (a - c).length > 1e-9 else V(0, -1, 0)
        secs.append((p, r, r, math.atan2(d.z, -d.y)))
    n_tail = len(secs)
    for s in sk.stations:
        secs.append((V(0, s["y"], (s["top"] + s["bot"]) / 2), s["hw"], (s["top"] - s["bot"]) / 2, 0.0))

    nk, hd = sk.neck, sk.head
    neck0, neck1, n_p, h_p, nt = nk["p0"], nk["p1"], nk["angle"], hd["angle"], nk["thick"]
    f, u = hd["f"], hd["u"]
    hs = hd["skull"] / 1.26                               # head unit
    sn = hd["muzzle"]
    skf = hd["width"] / (1.6 * hs)                        # skull width factor
    sw = hd["muzzle_width"] / (0.84 * hs)                 # muzzle width factor
    dk = hd["depth"] / (1.52 * hs)                        # depth factor
    rx, rz = sk.cw / 2, sk.cd / 2
    taper = P["head"]["muzzle_taper"]                 # muzzle tip width / base width
    tap_h = 0.62 + (taper - 0.67) * 0.6
    head = []
    if (neck1 - neck0).length > 0.08 * k:
        head += [
            (neck0 + (neck1 - neck0) * 0.30, rx * 0.66 * nt, rz * 0.74 * nt, n_p),
            (neck0 + (neck1 - neck0) * 0.68, (rx * 0.30 + hs * 0.34 * skf) * nt, (rz * 0.32 + hs * 0.36 * dk) * nt, n_p),
        ]
    head += [
        (neck1 - f * hs * 0.18, hs * 0.62 * skf * min(nt, 1.3), hs * 0.68 * dk, (n_p + h_p) / 2),
        (neck1 + f * hs * 0.42 + u * hs * 0.06 * dk, hs * 0.80 * skf, hs * 0.76 * dk, h_p),
        (neck1 + f * hs * 0.98 - u * hs * 0.02 * dk, hs * 0.68 * skf, hs * 0.64 * dk, h_p),
        (neck1 + f * hs * 1.26 - u * hs * 0.20 * dk, hs * 0.42 * sw, hs * 0.40 * dk, h_p),
        (neck1 + f * (hs * 1.26 + sn * 0.55) - u * hs * 0.25 * dk, hs * 0.42 * sw * (1 + taper) / 2,
         hs * 0.40 * dk * (1 + tap_h) / 2, h_p),
        (neck1 + f * (hs * 1.26 + sn) - u * hs * 0.28 * dk, hs * 0.42 * sw * taper, hs * 0.40 * dk * tap_h, h_p),
    ]
    secs += head
    tail_mat = mhair if P["tail"].get("style") == "hair" else mf
    rings = body.loft([sec_y(c, a, b, p) for c, a, b, p in secs], n=N,
                      mats=[tail_mat] * max(n_tail, 1) + [mf], cap_start=False, cap_end=False)
    body.cap(rings[0], tail_mat if n_tail else mf)
    nose_tip = head[-1][0] + f * hs * 0.10
    body.cap(rings[-1], mf, c=nose_tip)
    R = rings[n_tail:]
    H = rings[-len(head):]

    if mbel != mf:                                        # lighter underside
        under = {v.index for ring in R for i, v in enumerate(ring) if i in LOW}
        for face in body.bm.faces:
            if all(v.index in under for v in face.verts):
                face.material_index = mbel

    # ---- legs leave through two flank quads and follow the joint landmarks -------
    def open_flank(ra, rb, rc, i):
        j = (i + 1) % N
        for a, b in ((ra, rb), (rb, rc)):
            quad = (a[i], a[j], b[j], b[i])
            for face in list(a[i].link_faces):
                if all(v in face.verts for v in quad):
                    body.bm.faces.remove(face)
        return [ra[i], ra[j], rb[j], rc[j], rc[i], rb[i]]

    lr = sk.lr
    mass = P["limb"]["upper_mass"]
    foot_len = P["limb"]["foot_len"] * k
    foot_h = P["limb"]["foot_h"] * k
    for pair in ("h", "f"):
        ki = sk.holes[pair]
        ra, rb, rc = R[ki - 1], R[ki], R[ki + 1]
        for side, sg, i in (("L", 1, 11 if sprawl else 10), ("R", -1, 6 if sprawl else 7)):
            loop = open_flank(ra, rb, rc, i)
            limb = sk.limbs[(pair, side)]
            J = limb["joints"]
            c0 = sum((v.co for v in loop), V()) / len(loop)
            if sprawl:
                pts = [c0 + (J[1] - J[0]).normalized() * lr * 0.4] + J[1:]
                rad = [(1.15, 1.15)] + [(0.85 - 0.25 * q / max(len(J) - 2, 1),) * 2 for q in range(len(J) - 1)]
            else:
                p0 = V(J[0].x * 0.35 + c0.x * 0.65, c0.y, c0.z - lr * 0.3)
                pts = [p0, p0 + (J[1] - p0) * 0.45] + J[1:]
                up = (1.45 * mass, 2.3 * mass) if pair == "h" else (1.30 * mass, 1.9 * mass)
                kn = (0.95, 1.20) if pair == "h" else (0.85, 0.98)
                rad = [up, (up[0] * 0.92, up[1] * 0.85), kn]
                for q in range(2, len(J)):
                    w = 0.62 - 0.12 * min(1.0, (q - 2) / max(len(J) - 3, 1))
                    rad.append((w, w * (1.12 if q == 2 else 1.04)))
            ankle = J[-1]
            if feats["hooves"]:
                pw, pl, shift = lr * 0.62, lr * 0.74, lr * 0.15
            else:
                pw = lr * 0.68
                pl = max(lr * 0.98, foot_len * 0.55)
                shift = pl - lr * 0.5
            zp = min(foot_h * 0.65, ankle.z * 0.7)
            pts += [V(ankle.x, ankle.y - shift, zp), V(ankle.x, ankle.y - shift, 0.0)]
            radii = [(lr * a, lr * b) for a, b in rad] + [(pw, pl), (pw * 1.06 if feats["hooves"] else pw * 0.94,
                                                                     pl * 1.08 if feats["hooves"] else pl * 0.94)]
            mats = [mf] * (len(pts) - 2) + [mhoof, mhoof]
            body.loft(_transport(pts, radii, last_down=2), start=loop, cap_end=True, mats=mats)

    # a folded limb (frog) can put a joint ring partly under the ground: it rests on it
    for v in body.bm.verts:
        if v.co.z < 0.0:
            v.co.z = 0.0

    # ---- face ------------------------------------------------------------------
    face = creature.new_face(up=u)
    hp = P["head"]
    er = hp["eye_size"] * k
    half_w, half_d = hd["width"] / 2, hd["depth"] / 2
    for sg in (1, -1):
        eye = neck1 + f * hd["skull"] * hp["eye_at"] + u * half_d * hp["eye_up"] * 1.3 + X * sg * half_w * hp["eye_out"] * 1.25
        look = V(sg * 0.6, 0, 0) + f + u * (0.5 if hp["eye_up"] > 0.7 else 0.0)
        creature.add_eye(extras, face, eye, er, look, mw, md, mf, pupil=False, up=u)
        etype = P["ears"]["type"]
        if etype != "none" and P["ears"]["size"] > 0:
            s = "L" if sg > 0 else "R"
            base = neck1 + f * hs * 0.22 + u * half_d * 0.80 + X * sg * half_w * 0.58
            out = V(sg, 0, 0) if etype != "floppy" else V(sg, 0, 0) * 0.9 - u * 0.1
            creature.add_ear(extras, etype, base, out, u + V(sg * 0.28, 0, 0) - f * 0.1,
                             P["ears"]["size"] * k * 1.6, mf, mf, "ear." + s)
    if mammal:
        with extras.part(bone="head"):
            extras.sphere(nose_tip + u * hs * 0.10 * dk - f * hs * 0.02,
                          (hs * 0.15 * sw, hs * 0.11, hs * 0.11 * dk), md, n=6, m=3)
    (mid_c, mid_w, mid_h, _), (tip_c, tip_w, tip_h, _) = head[-2], head[-1]
    low = 0.52
    pts = [(mid_c + X * mid_w * 0.99 - u * mid_h * low, -1.0),
           (tip_c + X * tip_w * 1.00 - u * tip_h * low, -0.6),
           (tip_c + X * tip_w * 0.64 + f * hs * 0.085 - u * tip_h * low, -0.3),
           (tip_c + f * hs * 0.125 - u * tip_h * low, 0.0),
           (tip_c - X * tip_w * 0.64 + f * hs * 0.085 - u * tip_h * low, 0.3),
           (tip_c - X * tip_w * 1.00 - u * tip_h * low, 0.6),
           (mid_c - X * mid_w * 0.99 - u * mid_h * low, 1.0)]
    creature.add_mouth(extras, face, pts, mm, hs * 0.035, up=u)
    face["mouth_w"] = hs * 0.30
    for ring, amount in ((H[-1], 1.0), (H[-2], 0.55)):
        for i in LOW:
            face["jaw"].append((ring[i].index, -u * hs * 0.30 * dk * amount))

    # ---- species features ----------------------------------------------------------
    S = sk.m["length"] * k
    if feats["mane"] == "horse":
        nu = V(0, math.sin(n_p), math.cos(n_p))
        a0 = neck0 + nu * rz * 0.50 + V(0, 0.06 * S, 0)
        a1 = neck1 + u * hs * 0.62
        with extras.part(bone="neck"):
            prof = [a0 - nu * 0.03 * S, a1 - u * 0.03 * S, a1 + f * hs * 0.55 + u * 0.01 * S,
                    a1 + u * 0.075 * S, (a0 + a1) / 2 + nu * 0.085 * S, a0 + nu * 0.045 * S]
            extras.extrude([p - X * 0.016 * S for p in prof], X * 0.032 * S, mhair)
    elif feats["mane"] == "lion":
        with extras.part(bone="neck"):
            extras.sphere(neck1 + f * hs * 0.05 - u * hs * 0.15, (hs * 1.30, hs * 1.05, hs * 1.42), mhair, n=8, m=5)
    if feats["horns"]:
        mh = slot["horn"]
        for sg in (1, -1):
            base = neck1 + f * hs * 0.30 + u * half_d * 0.85 + X * sg * half_w * 0.45
            with extras.part(bone="head"):
                if feats["horns"] == "cow":
                    mid = base + (X * sg * 0.75 + u * 0.25) * hs * 0.55
                    extras.cylinder(base, mid, hs * 0.13, hs * 0.10, n=6, mat=mh, hint=Y)
                    extras.cylinder(mid, mid + (X * sg * 0.2 + u * 0.9 + f * 0.3) * hs * 0.55, hs * 0.10, hs * 0.02, n=6, mat=mh, hint=Y)
                else:
                    beam = [base, base + (X * sg * 0.35 + u * 0.9 - f * 0.2) * hs * 1.1,
                            base + (X * sg * 0.75 + u * 1.9 + f * 0.1) * hs * 1.1]
                    mid = (beam[1] + beam[2]) / 2
                    for p0, p1, r0, r1 in ((beam[0], beam[1], 0.09, 0.07), (beam[1], beam[2], 0.07, 0.02),
                                           (beam[1], beam[1] + (f * 0.8 + u * 0.5) * hs * 0.8, 0.06, 0.015),
                                           (mid, mid + (f * 0.5 + u * 0.8 + X * sg * 0.3) * hs * 0.7, 0.05, 0.015)):
                        extras.cylinder(p0, p1, hs * r0, hs * r1, n=6, mat=mh, hint=X)

    # ---- rig: bones sit on the solved joints -----------------------------------------
    lm = sk.lm
    rig = Rig(P.get("_entity", "Animal"), "quadruped")
    rig.bone("root", (0, 0, 0), (0, 0.15 * S, 0), deform=False)
    hip = V(0, lm["hip.L"].y, lm["croup"].z - sk.cd * 0.30)
    chest_p = V(0, lm["shoulder.L"].y, lm["withers"].z - sk.cd * 0.35)
    mid = (hip + chest_p) / 2 - V(0, 0, sk.cd * 0.03)
    rig.bone("hips", hip, hip + (mid - hip) * 0.45, "root")
    rig.bone("spine1", hip + (mid - hip) * 0.45, mid, "hips", True)
    rig.bone("spine2", mid, chest_p, "spine1", True)
    rig.bone("neck", chest_p, neck1 - f * hs * 0.1, "spine2")
    rig.bone("head", neck1 - f * hs * 0.1, neck1 + f * (hs * 1.26 + sn), "neck", True)
    tail_names = []
    if len(tail_pts) > 1:
        tail_names = rig.chain("tail", [hip + V(0, 0.06 * S, 0)] + tail_pts[1:], "hips")
    for s, sg in (("L", 1), ("R", -1)):
        if P["ears"]["type"] != "none" and P["ears"]["size"] > 0:
            base = neck1 + f * hs * 0.22 + u * half_d * 0.80 + X * sg * half_w * 0.58
            rig.bone("ear." + s, base, base + (u + V(sg * 0.2, 0, 0)) * hs * 0.6, "head")
        for pair, parent in (("h", "hips"), ("f", "spine2")):
            limb = sk.limbs[(pair, s)]
            J = limb["joints"]
            prev = parent
            for q, seg in enumerate(limb["names"]):
                bn = "%s_%s.%s" % (pair, seg, s)
                rig.bone(bn, J[q], J[q + 1], prev, connect=q > 0)
                prev = bn
            toe = V(limb["toe"].x, limb["toe"].y, 0.012 * S)
            rig.bone("%s_foot.%s" % (pair, s), J[-1], toe, prev, True)
            rig.bone("%s_ik.%s" % (pair, s), J[-1], toe, "root", deform=False)
            rig.ik(prev, "%s_ik.%s" % (pair, s), len(limb["names"]))
            rig.copy_rotation("%s_foot.%s" % (pair, s), "%s_ik.%s" % (pair, s))
    rig.meta = {"size": S, "leg_f": max(lm["shoulder.L"].z - foot_h, 0.02 * S),
                "leg_h": max(lm["hip.L"].z - foot_h, 0.02 * S),
                "torso": (chest_p - hip).length, "tail": tail_names,
                # how far the neck may pitch down in a run before a low head meets the ground
                "neck_dip": min(1.0, lm["nose"].z * 0.8 / max(0.35 * (lm["nose"] - chest_p).length, 1e-6)),
                "tail_floor": min([r for _, r in sk.tail] or [0.0]),
                "foot_f": (sk.limbs[("f", "L")]["toe"] - sk.limbs[("f", "L")]["joints"][-1]).length,
                "foot_h": (sk.limbs[("h", "L")]["toe"] - sk.limbs[("h", "L")]["joints"][-1]).length}
    return body, extras, rig, face


class _Index(dict):
    """Material slots as plain indices, for geometry built without Blender materials."""

    def __init__(self):
        super().__init__({s: i for i, s in enumerate(SLOTS)})
        self["_palette"] = Palette()


def silhouette_geometry(profile, size):
    """Body cage for a profile, with no Blender data created (reference fitting)."""
    sk = skeleton.solve(profile, size)
    body, extras, _, _ = make(sk, _Index())
    return sk, body, extras


def build(spec, ctx, type_name):
    name = spec.name
    P = profiles.get(type_name)
    P["_entity"] = name
    S = spec.num("size", P.get("size", 1.2), 0.05, 40)   # measured head-body length when known
    leg_fit = skeleton.fit_stature(P, S)        # before the user's own leg_length and overrides
    apply_friendly(P, spec)
    overrides = profiles.apply_overrides(P, spec)

    # reference images: measure, optionally fit the profile, always report
    refs = reference.from_spec(spec, ctx.base_dir)
    fit_notes = []
    if refs and spec.flag("reference_fit", True):
        fit_notes = reference.fit(P, S, refs, silhouette_geometry)
    sk = skeleton.solve(P, S)

    fur_c = spec.color("fur", P["color"])
    if spec.has("color"):
        fur_c = spec.color("color", P["color"])
    feats = P["features"]
    belly_c = None
    if feats.get("belly_color"):
        belly_c = spec.color("belly", feats["belly_color"])
    elif feats.get("belly"):
        belly_c = tuple(c + (1.0 - c) * feats["belly"] for c in fur_c[:3]) + (1.0,)
    if spec.has("belly"):
        belly_c = spec.color("belly", "#d8d0c0")
    dark_k = 0.35 if feats["mane"] == "horse" else 0.55
    mane_c = spec.color("mane_color", tuple(c * dark_k for c in fur_c[:3]) + (1,))
    surf = P["surface"]
    pal = Palette()
    fur = ctx.mat("Fur" if surf == "fur" else "Skin", surf, fur_c, scale=2.2, deform=True)
    mats = {
        "fur": fur,
        "belly": ctx.mat("Belly", surf, belly_c, scale=2.2, deform=True) if belly_c else fur,
        "hair": ctx.mat("Mane", "fur", mane_c, scale=2.2, deform=True)
        if feats["mane"] or P["tail"].get("style") == "hair" else fur,
        "dark": ctx.mat("Dark", "plain", (0.02, 0.02, 0.02, 1), roughness=0.25),
        "white": ctx.mat("EyeShine", "plain", (0.95, 0.95, 0.95, 1), roughness=0.2),
        "mouth": ctx.mat("Mouth", "plain", (0.18, 0.04, 0.05, 1), roughness=0.5),
        "hoof": ctx.mat("Hoof", "plain", (0.03, 0.025, 0.02, 1), roughness=0.4) if feats["hooves"] else fur,
        "horn": ctx.mat("Horn", "plain", spec.color("horn_color", "#d8cdb4"), roughness=0.45) if feats["horns"] else fur,
    }
    slot = {s: pal.index(mats[s]) for s in SLOTS}
    slot["_palette"] = pal
    body, extras, rig, face = make(sk, slot)
    rig.name = name

    issues = validate.check_skeleton(sk, overrides)
    issues += validate.check_cage(body, extras)
    issues += validate.check_rig(rig)
    if refs:
        issues += reference.compare(refs, body, extras, fit_notes)
    entity = creature.finalize(ctx, spec, name, body, extras, rig, face, "head")
    if leg_fit:
        issues.append(("info", "stature", "legs scaled x%.2f to shoulder height %.2f of head-body length (%s)"
                       % (leg_fit, P["stature"]["ratio"], P["stature"]["source"])))
    validate.report(name, P, sk, issues, entity, spec, ctx)
    if refs and spec.flag("reference_show", True):
        entity.objects += reference.add_empties(refs, entity, ctx)
    return entity
