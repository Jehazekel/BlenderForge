"""Landmark solver for upright bipeds (humans), the counterpart of skeleton.py.

Input: a resolved profile in stature units and a target height in metres.
Output: a Skeleton with joint landmarks in metres and the measures that
validation checks.

Solved rather than typed in:
  * the leg chain must reach the ground, so hip height is ankle + shank + thigh;
  * shoulder, chin and crown stack on the hip by trunk, neck and head length;
  * the whole figure is scaled so the crown is at the requested height, which
    means a longer leg or bigger head changes proportions, never the height;
  * hip joints are kept far enough apart for the thighs not to merge.

Faces -Y, stands on z = 0, left is +X, T-pose. No bpy here.
"""

from .skeleton import Skeleton, V


def solve(profile, height):
    P = profile
    lg, tr, nk, hd, ar, br, gi = (P[s] for s in ("leg", "trunk", "neck", "head", "arm", "breadth", "girth"))
    sk = Skeleton()
    sk.profile = P

    hip = lg["ankle_h"] + lg["shank"] + lg["thigh"]
    sh = hip + tr["length"]                             # acromion: the top of the shoulder
    sj = sh - tr.get("shoulder_drop", 0.0)              # centre of the shoulder joint, below it
    chin = sh + nk["length"]
    top = chin + hd["height"]
    k = height / top
    sk.scale = k

    hx = max(br["hip"] / 2.0 * br["hip_joint"], gi["thigh"] * 1.04)
    sx = br["shoulder"] / 2.0 * br["shoulder_joint"]
    foot_c = 0.004 - 0.29 * lg["foot_len"]              # the ankle sits over the rear third of the foot
    arm = ar["upper"] + ar["fore"] + ar["hand"]

    lm = sk.lm
    for name, z in (("crotch", hip - tr["crotch"]), ("pelvis", hip), ("waist", hip + tr["length"] * tr["waist_at"]),
                    ("chest", hip + tr["length"] * tr["chest_at"]), ("neck_base", sh), ("chin", chin),
                    ("eyes", chin + hd["height"] * hd["eye_at"]), ("crown", top)):
        lm[name] = V(0, 0, z) * k
    for side, sg in (("L", 1.0), ("R", -1.0)):
        for name, p in (
            ("hip", V(sg * hx, 0, hip)),
            ("knee", V(sg * hx, -lg["knee_fwd"], lg["ankle_h"] + lg["shank"])),
            ("ankle", V(sg * hx, 0.004, lg["ankle_h"])),
            ("heel", V(sg * hx * 1.02, foot_c + lg["foot_len"] / 2.0, 0)),
            ("toe", V(sg * hx * 1.02, foot_c - lg["foot_len"] / 2.0, 0)),
            ("shoulder", V(sg * sx, 0, sj)),
            ("elbow", V(sg * (sx + ar["upper"]), 0.010, sj)),
            ("wrist", V(sg * (sx + ar["upper"] + ar["fore"]), 0.002, sj)),
            ("fingertip", V(sg * (sx + arm), 0, sj)),
        ):
            lm["%s.%s" % (name, side)] = p * k

    sk.hip_w = max(br["hip"] / 2.0, gi["thigh"] * 1.75) * k     # hips wide enough for the thighs
    sk.foot_y = foot_c * k
    sk.m = dict(
        head_to_stature=hd["height"] / top, neck_to_stature=nk["length"] / top, leg_to_stature=hip / top,
        trunk_to_stature=tr["length"] / top, thigh_to_shank=lg["thigh"] / max(lg["shank"], 1e-6),
        upper_to_forearm=ar["upper"] / max(ar["fore"], 1e-6), arm_span=2.0 * (sx + arm) / top,
        fingertip_height=(sj - arm) / top, shoulder_to_hip=br["shoulder"] / max(br["hip"], 1e-6),
        shoulder_width=br["shoulder"] / top, foot_to_stature=lg["foot_len"] / top,
        heads_tall=top / max(hd["height"], 1e-6), length=top,
    )
    fc = P.get("face")
    if fc:                                              # face canons, checked like the body ratios
        at = {r[0]: r for r in fc["rows"]}
        sk.m.update(
            eye_height=at["eye"][1], eye_spacing=fc["columns"][2] * at["eye"][2],
            mouth_to_eye_spacing=at["mouth"][2] / at["eye"][2],
            mid_face=(at["brow"][1] - at["nose_base"][1]) / max(at["hairline"][1], 1e-6),
            lower_face=at["nose_base"][1] / max(at["hairline"][1], 1e-6),
            head_width_to_depth=hd["width"] / max(hd["depth"], 1e-6),
        )
    sk.summary = "%.2f m, %.1f heads tall, hips %.2f m, shoulders %.2f m, arm span %.2f m" % (
        height, sk.m["heads_tall"], hip * k, sh * k, sk.m["arm_span"] * height)
    return sk
