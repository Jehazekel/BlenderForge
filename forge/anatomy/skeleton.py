"""Landmark and constraint solver for tetrapods.

Input: a resolved anatomical profile (trunk units) and a target body length.
Output: a Skeleton - joint landmarks in metres, trunk cross-section stations,
limb paths and the measures that validation checks.

Constraints solved here rather than typed in by hand:
  * every limb chain must reach the ground, so the shoulder and hip heights
    follow from bone lengths and standing joint angles;
  * the shoulder and hip joints are one trunk length apart, so the back slope
    follows from those two heights;
  * top line, belly line, neck, head and tail hang off those joints;
  * limb thickness follows trunk cross-section (allometric scaling);
  * the whole animal is scaled so nose-to-rump equals the requested size.

The character faces -Y, stands on z = 0, left is +X. No bpy here.
"""

import math

from mathutils import Vector

FORE_JOINTS = ["shoulder", "elbow", "carpus", "fore_fetlock", "fore_coffin", "fore_tip"]
HIND_JOINTS = ["hip", "stifle", "hock", "hind_fetlock", "hind_coffin", "hind_tip"]


def V(x=0.0, y=0.0, z=0.0):
    return Vector((x, y, z))


def _smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def seg_dir(angle, out, side=1):
    """Unit direction of a limb segment. angle: degrees from straight down,
    positive = far end forward. out: degrees of sideways splay."""
    a, o = math.radians(angle), math.radians(out)
    return V(side * math.sin(o), -math.sin(a) * math.cos(o), -math.cos(a) * math.cos(o))


class Skeleton:
    def __init__(self):
        self.profile = None
        self.scale = 1.0            # metres per trunk unit
        self.lm = {}                # landmark name -> Vector (metres)
        self.limbs = {}             # ("f"|"h", "L"|"R") -> dict(names, joints, toe, radius)
        self.stations = []          # trunk rings: dict(name, y, hw, top, bot)
        self.tail = []              # [(point, radius)] base -> tip
        self.m = {}                 # measures in trunk units, for validation
        self.holes = {}             # "f"/"h" -> index of the middle ring of the leg opening

    def joint(self, name, side="L"):
        return self.lm["%s.%s" % (name, side)]


def fit_stature(profile, size):
    """Scale both limb chains so the withers stand at the profile's published
    shoulder height / head-body length ratio. Returns the factor applied, or
    None when the profile has no stature data."""
    target = (profile.get("stature") or {}).get("ratio")
    if not target:
        return None
    lb = profile["limb"]
    f0, h0 = lb["fore_scale"], lb["hind_scale"]

    def ratio(m):
        lb["fore_scale"], lb["hind_scale"] = f0 * m, h0 * m
        return solve(profile, size).lm["withers"].z / size

    lo, hi = 0.5, 3.0
    for _ in range(30):
        mid = (lo + hi) / 2.0
        if ratio(mid) < target:
            lo = mid
        else:
            hi = mid
    m = (lo + hi) / 2.0
    lb["fore_scale"], lb["hind_scale"] = f0 * m, h0 * m
    return m


def solve(profile, size):
    P = profile
    tr, nk, hd, lb, tl = P["trunk"], P["neck"], P["head"], P["limb"], P["tail"]
    sk = Skeleton()
    sk.profile = P
    sprawl = P.get("posture") == "sprawl"

    # ---- limbs: chains hang from the joint, their drop sets the joint height ----
    def chain(segs, scale):
        pts = [V()]
        for name, length, angle, out in segs:
            pts.append(pts[-1] + seg_dir(angle, out) * length * scale)
        return pts

    fore = chain(P["fore"], lb["fore_scale"])
    hind = chain(P["hind"], lb["hind_scale"])
    foot_h = lb["foot_h"]
    hf = foot_h - fore[-1].z        # shoulder joint height
    hh = foot_h - hind[-1].z        # hip joint height

    # ---- trunk: joints one unit apart, slope follows from the two heights -------
    dz = hf - hh
    dy = math.sqrt(max(1.0 - dz * dz, 0.04))
    ys, yh = -dy / 2.0, dy / 2.0
    slope = math.degrees(math.atan2(dz, dy))
    cd, cw = tr["chest_depth"], tr["chest_width"]
    ld = cd * (1.0 - 0.55 * tr["tuck"])                 # loin depth
    withers = hf + tr["shoulder_at"] * cd
    croup = hh + tr["hip_at"] * ld
    sternum = withers - cd
    loin = croup - ld
    xf = cw / 2.0 * tr["joint_x"]
    xh = cw / 2.0 * tr["hip_width"] * tr["joint_x"]

    # limb thickness from trunk cross-section (allometry), unless overridden
    lr = 0.22 * math.sqrt(cd * cw) * lb["thick"]
    mass = lb["upper_mass"]
    if sprawl:
        df = dh = max(0.05, min(0.12, lr * 1.5))
        yf_c, yh_c = ys, yh
    else:
        dh = max(0.07, min(0.17, lr * 2.0 * mass ** 0.5))
        df = max(0.06, min(0.15, lr * 1.7 * mass ** 0.5))
        yf_c, yh_c = ys + 0.06, yh - 0.04
    y1, y2 = yh_c - dh, yf_c + df                        # inner edges of the leg openings
    if y1 - y2 < 0.10:                                   # very short trunk: squeeze the openings
        mid = (y1 + y2) / 2.0
        y1, y2 = mid + 0.05, mid - 0.05
        dh, df = yh_c - y1, y2 - yf_c

    def top(y):
        t = max(0.0, min(1.0, (yh - y) / (yh - ys)))
        return croup + (withers - croup) * t

    def bot(y):
        return loin + (sternum - loin) * _smooth((y1 - y) / max(y1 - y2, 1e-6))

    hump = tr["hump"] * cd
    hip_w = tr["hip_width"]
    table = [   # name, y, width factor, top (1 = top line), bottom (-1 = belly line), extra top
        ("rump", yh + tr["rump"], 0.46 * hip_w, 0.70, -0.10, 0.0),
        ("hind_back", yh_c + dh, 0.86 * hip_w, 1.00, -0.80, 0.0),
        ("hind_mid", yh_c, 0.97 * hip_w, 1.00, -1.00, 0.0),
        ("hind_front", y1, 0.94 * (hip_w + 1) / 2, 1.00, -1.00, 0.0),
        ("belly", (y1 + y2) / 2.0, 0.93, 1.00, -1.00, hump * 0.4),
        ("fore_back", y2, 0.98, 1.00, -1.00, hump),
        ("fore_mid", yf_c, 1.00, 1.00, -1.00, hump),
        ("fore_front", yf_c - df, 0.92, 1.00, -0.95, hump * 0.5),
        ("chest_front", yf_c - df - tr["forechest"], 0.60, 0.86, -0.35, 0.0),
    ]
    stations = []
    for name, y, wf, tn, bn, extra in table:
        zc, half = (top(y) + bot(y)) / 2.0, (top(y) - bot(y)) / 2.0
        stations.append(dict(name=name, y=y, hw=cw / 2.0 * wf, top=zc + tn * half + extra, bot=zc + bn * half))
    sk.holes = {"h": 2, "f": 6}

    # ---- neck and head -------------------------------------------------------------
    n_a, h_a = math.radians(nk["angle"]), math.radians(hd["angle"])
    front_y = stations[-1]["y"]
    neck0 = V(0, front_y + 0.02, withers - nk["set"] * cd)
    neck1 = neck0 + V(0, -math.cos(n_a), math.sin(n_a)) * nk["length"]
    f = V(0, -math.cos(h_a), math.sin(h_a))
    u = V(0, math.sin(h_a), math.cos(h_a))
    nose = neck1 + f * (hd["skull"] + hd["muzzle"]) - u * hd["depth"] * 0.30
    rump_y = stations[0]["y"]

    # ---- tail ------------------------------------------------------------------------
    tail = []
    if tl["length"] > 0.01:
        n_t = 2 if tl["length"] < 0.2 else 6
        p = V(0, rump_y + 0.01, croup - 0.30 * ld)
        style = tl.get("style", "plain")
        for k in range(n_t + 1):
            uu = k / n_t
            if style == "bushy":
                bulge = (0.45 + 0.75 * math.sin(math.pi * min(1.0, uu * 0.85 + 0.10)))
                bulge *= 1.0 - 0.75 * max(0.0, uu - 0.75) / 0.25
            elif style == "taper":
                bulge = 1.0 - 0.88 * uu
            elif style == "hair":
                bulge = 1.0 - 0.35 * uu
            else:
                bulge = 1.0 - 0.5 * uu
            r = tl["radius"] * max(0.14, bulge)
            tail.append((p.copy(), r))
            ang = math.radians(min(89.0, tl["angle"] + tl["curl"] * 60.0 * uu))
            step = V(0, math.cos(ang), -math.sin(ang)) * tl["length"] / n_t
            p = p + step
            p.z = max(p.z, r * 1.1)                     # tails rest on the ground, not through it

    # ---- scale everything so nose-to-rump is the requested size --------------------
    length = rump_y - nose.y
    k = size / max(length, 1e-6)
    sk.scale = k
    lm = sk.lm
    for name, p in (("nose", nose), ("neck_base", neck0), ("poll", neck1),
                    ("withers", V(0, ys, withers + hump)), ("croup", V(0, yh, croup)),
                    ("sternum", V(0, yf_c, sternum)), ("loin", V(0, y1, loin)),
                    ("rump", V(0, rump_y, croup - 0.30 * ld))):
        lm[name] = p * k
    for pair, pts, names, x, y, h in (("f", fore, FORE_JOINTS, xf, ys, hf), ("h", hind, HIND_JOINTS, xh, yh, hh)):
        segs = P["fore" if pair == "f" else "hind"]
        for side, sg in (("L", 1.0), ("R", -1.0)):
            origin = V(sg * x, y, h)
            joints = [(origin + V(sg * q.x, q.y, q.z)) * k for q in pts]
            for jn, q in zip(names, joints):
                lm["%s.%s" % (jn, side)] = q
            ankle = joints[-1]
            toe = V(ankle.x, ankle.y - lb["foot_len"] * k, 0.0)
            lm["%s_toe.%s" % ("fore" if pair == "f" else "hind", side)] = toe
            sk.limbs[(pair, side)] = dict(names=[s[0] for s in segs], joints=joints, toe=toe)
    sk.stations = [dict(name=s["name"], y=s["y"] * k, hw=s["hw"] * k, top=s["top"] * k, bot=s["bot"] * k)
                   for s in stations]
    sk.tail = [(p * k, r * k) for p, r in tail]
    sk.lr = lr * k
    sk.neck = dict(p0=neck0 * k, p1=neck1 * k, angle=n_a, thick=nk["thick"])
    sk.head = dict(f=f, u=u, angle=h_a, skull=hd["skull"] * k, muzzle=hd["muzzle"] * k,
                   width=hd["width"] * k, muzzle_width=hd["muzzle_width"] * k, depth=hd["depth"] * k)
    sk.cd, sk.cw = cd * k, cw * k

    # ---- measures in trunk units -------------------------------------------------------
    def seg_len(segs, i, scale):
        return segs[i][1] * scale if i < len(segs) else 0.0

    trunk_mass = sum(s["hw"] * (s["top"] - s["bot"]) for s in stations)
    com = sum(s["hw"] * (s["top"] - s["bot"]) * s["y"] for s in stations)
    head_mass = (hd["skull"] + hd["muzzle"]) * hd["width"] * hd["depth"] * 1.2
    neck_mass = nk["length"] * cd * cw * 0.25 * nk["thick"]
    com += head_mass * (neck1.y - (hd["skull"] + hd["muzzle"]) * 0.4) + neck_mass * (neck0.y + neck1.y) / 2
    com /= (trunk_mass + head_mass + neck_mass)
    sk.m = dict(
        back_slope=slope, shoulder_height=hf, hip_height=hh, withers=withers + hump, croup=croup,
        head_to_trunk=hd["skull"] + hd["muzzle"], neck_to_trunk=nk["length"], chest_depth=cd,
        width_to_depth=cw / cd, fore_to_hind_height=hf / max(hh, 1e-6),
        upper_to_lower_fore=seg_len(P["fore"], 0, 1) / max(seg_len(P["fore"], 1, 1), 1e-6),
        upper_to_lower_hind=seg_len(P["hind"], 0, 1) / max(seg_len(P["hind"], 1, 1), 1e-6),
        leg_to_trunk=sternum, limb_radius_to_depth=lr / cd, tail_to_trunk=tl["length"],
        com_y=com, fore_foot_y=ys + fore[-1].y, hind_foot_y=yh + hind[-1].y,
        fore_foot_drop=hf + fore[-1].z - foot_h, hind_foot_drop=hh + hind[-1].z - foot_h,
        belly_clearance=min(sternum, loin), length=length,
    )
    return sk
