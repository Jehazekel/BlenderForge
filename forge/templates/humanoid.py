"""Humanoid character: one connected quad cage, biped rig, face keys, outfits.

Proportions are data, as for the animals: `anatomy/data/humans.json` holds the
profile, `anatomy.biped.solve` turns it into joint landmarks, and this file
builds geometry and bones on those landmarks. A new body type is a new JSON
entry. The character faces -Y, stands on z = 0 and is modelled in the rest pose the
profile asks for (`arm.rest_angle`: an A-pose by default).
"""

import math

from mathutils import Matrix, Vector

from .. import creature, parts
from ..anatomy import biped, profiles, validate
from ..face import Head
from ..meshkit import MeshBuilder, Palette, V, X, Y, Z, add_bevel, sec_dir, sec_x, sec_z
from ..rigging import Rig

NAMES = profiles.names("biped")

# multipliers: chest, waist, hip, depth, limb, neck
BUILDS = {
    "slim": (0.90, 0.88, 0.92, 0.88, 0.84, 0.92),
    "average": (1.0, 1.0, 1.0, 1.0, 1.0, 1.0),
    "athletic": (1.10, 0.96, 1.0, 1.04, 1.12, 1.08),
    "muscular": (1.24, 1.04, 1.04, 1.14, 1.32, 1.28),
    "heavy": (1.16, 1.42, 1.28, 1.38, 1.22, 1.22),
}
OUTFITS = ("casual", "armor", "robe", "tunic", "none")
HAIR = ("short", "long", "bald", "none")


def apply_friendly(P, spec):
    """The simple keys (build, head_size, leg_length...) as edits to the profile."""
    cw, ww, hpw, dp, lm, nk = BUILDS[spec.choice("build", BUILDS, "average")]
    b = P["breadth"]
    b["shoulder"] *= cw
    b["chest"] *= cw
    b["waist"] *= ww
    b["hip"] *= hpw
    for key in P["depth"]:
        P["depth"][key] *= dp
    for key in P["girth"]:
        P["girth"][key] *= nk if key == "neck" else lm
    k = spec.num("head_size", 1.0, 0.5, 2.5)
    for key in ("height", "width", "depth"):
        P["head"][key] *= k
    limb = spec.num("limb_length", 1.0, 0.5, 1.8)
    k = spec.num("arm_length", 1.0, 0.5, 1.8) * limb
    P["arm"]["upper"] *= k
    P["arm"]["fore"] *= k
    k = spec.num("leg_length", 1.0, 0.5, 1.8) * limb
    P["leg"]["thigh"] *= k
    P["leg"]["shank"] *= k
    return lm


def build(spec, ctx, type_name):
    P = profiles.get(type_name)
    for key, value in P.get("defaults", {}).items():
        spec.set_default(key, value)
    name = spec.name
    H = spec.num("height", 1.8, 0.3, 20)
    lm = apply_friendly(P, spec)
    overrides = profiles.apply_overrides(P, spec)
    sk = biped.solve(P, H)
    L = sk.lm
    outfit = spec.choice("outfit", OUTFITS, "casual")
    accessories = spec.items("accessories") + spec.items("accessory")
    hair = spec.choice("hair", HAIR, "short")
    deform = {"deform": True}

    # ---- materials -------------------------------------------------------
    skin_c = spec.color("skin", "#c68642")
    metal_c = spec.color("outfit_color", "#aab2bd" if outfit == "armor" else "#3b6ea5")
    pants_c = spec.color("pants_color", "#3a3f4b" if outfit != "robe" else "#3b2a55")
    if outfit == "robe" and not spec.has("outfit_color"):
        metal_c = spec.color("robe_color", "#4a3570")
    pal = Palette()
    M = {}
    M["skin"] = ctx.mat("Skin", "skin", skin_c)
    top_kind = "metal" if outfit == "armor" else "cloth"
    M["top"] = ctx.mat("Top", top_kind, metal_c, scale=2.0, **deform) if outfit != "none" else M["skin"]
    if outfit == "armor":
        M["bottom"] = ctx.mat("Mail", "metal", tuple(c * 0.45 for c in metal_c[:3]), roughness=0.55, **deform)
        M["trim"] = ctx.mat("Leather", "leather", spec.color("trim_color", "#5a3a22"), **deform)
    else:
        M["bottom"] = ctx.mat("Bottom", "cloth", pants_c, scale=2.0, **deform)
        M["trim"] = ctx.mat("Belt", "leather", spec.color("trim_color", "#4a2f1c"), **deform)
    M["shoes"] = ctx.mat("Shoes", "leather", spec.color("shoes", "#2a211b"), **deform)
    M["hair"] = ctx.mat("Hair", "fur", spec.color("hair_color", "#2b1d14"), scale=2.0, **deform)
    M["white"] = ctx.mat("EyeWhite", "plain", (0.9, 0.9, 0.88, 1), roughness=0.25)
    M["iris"] = ctx.mat("Iris", "plain", spec.color("eyes", "#4a3020"), roughness=0.2)
    M["pupil"] = ctx.mat("Pupil", "plain", (0.01, 0.01, 0.01, 1), roughness=0.15)
    M["mouth"] = ctx.mat("Mouth", "plain", (0.10, 0.02, 0.02, 1), roughness=0.5)
    M["teeth"] = ctx.mat("Teeth", "plain", (0.86, 0.84, 0.78, 1), roughness=0.3)
    lt = P["face"]["lip_tint"]                      # lips: the skin colour, darker and redder
    lip_c = spec.color("lips", "#a8605a") if spec.has("lips") else tuple(
        c * k + a for c, (k, a) in zip(skin_c[:3], lt)) + (1.0,)
    M["lips"] = ctx.mat("Lips", "skin", lip_c)
    sleeve = {"casual": ("top", "skin", "skin"), "tunic": ("top", "top", "skin"),
              "armor": ("top", "top", "trim"), "robe": ("top", "top", "skin"),
              "none": ("skin", "skin", "skin")}[outfit]
    boot = "top" if outfit == "armor" else ("shoes" if outfit == "tunic" else "bottom")
    if outfit == "none":
        boot = "skin"
        M["shoes"] = M["skin"]

    # ---- proportions -----------------------------------------------------
    # every length below comes from the solved landmarks or the profile
    U = sk.scale                                    # metres per stature unit
    br, dpt, gi, sp = P["breadth"], P["depth"], P["girth"], P["shape"]
    z_cr, zn, sh_z = L["crotch"].z, L["chin"].z, L["shoulder.L"].z
    hh = L["crown"].z - zn
    chest_w, waist_w, hip_w = L["shoulder.L"].x, br["waist"] / 2 * U, sk.hip_w
    chest_d, waist_d, hip_d = (dpt[k] / 2 * U for k in ("chest", "waist", "hip"))
    neck_r = gi["neck"] * U
    arm_gap = sp["arm_gap"] * U                     # half height of the arm opening
    top = sh_z + arm_gap
    sway = {k: v * U for k, v in sp["sway"].items()}    # how far each section sits behind the bone line
    torso = [   # (height, half width, half depth, y)
        (z_cr, hip_w * sp["crotch"][0], hip_d * sp["crotch"][1], sway["crotch"]),
        (L["pelvis"].z, hip_w, hip_d, sway["pelvis"]), (L["waist"].z, waist_w, waist_d, sway["waist"]),
        (L["chest"].z, max(br["chest"] / 2 * U, chest_w * sp["chest_min"]), chest_d, sway["chest"]),
        (sh_z - arm_gap, chest_w, chest_d, 0.0),
        (top, chest_w * sp["shoulder_cap"][0], chest_d * sp["shoulder_cap"][1], 0.0),
        (top + (zn - top) * sp["neck_base"][0], neck_r * sp["neck_base"][1], neck_r * sp["neck_base"][2], sway["neck"]),
        (zn, neck_r, neck_r, sway["neck"]),
    ]
    tz = [t[0] for t in torso]
    hw, hd, hc = P["head"]["width"] / 2 * U, P["head"]["depth"] / 2 * U, P["head"]["forward"] * U

    body = MeshBuilder(pal)
    extras = MeshBuilder(pal)
    mi = {k: pal.index(v) for k, v in M.items()}

    # ---- torso and neck: one loft of 8-vertex rings; the head cage sits on it
    rings = []
    seg_mats = ["bottom", "bottom", "top", "top", "top", "top", "skin"]
    for k, (_, rx, ry, y) in enumerate(torso):
        r = body.ring(V(0, y, tz[k]), X * rx, Y * ry, 8, power=sp["square"] if k < 6 else 1.0)
        if rings:
            skip = (7, 0, 3, 4) if k == 5 else ()       # arm holes
            body.bridge(rings[-1], r, mi[seg_mats[k - 1]], skip)
        rings.append(r)
    head = Head(P, U, zn, hh, hc)
    head.build(body, rings[-1], mi["skin"], mi["lips"])
    crotch = body.vert(V(0, sway["crotch"], z_cr - sp["crotch_drop"] * U))

    # ---- legs: lofted from the two halves of the pelvis floor ------------
    r0 = rings[0]
    z_kn, z_an = L["knee.L"].z, L["ankle.L"].z
    jl = P["joint_loop"]                            # support-loop offset, fraction of the segment
    th, kn, ca, an_r = (gi[k] * U for k in ("thigh", "knee", "calf", "ankle"))
    lx = L["hip.L"].x
    foot_y, foot_l, foot_w = sk.foot_y, P["leg"]["foot_len"] * U * 0.487, P["leg"]["foot_w"] / 2 * U * 1.1
    z_in = min(0.028 * U, z_an * 0.72)              # instep
    for sg, loop in ((1, [r0[6], r0[7], r0[0], r0[1], r0[2], crotch]),
                     (-1, [r0[2], r0[3], r0[4], r0[5], r0[6], crotch])):
        x = sg * lx
        d_t, d_s = jl * (z_cr - z_kn), jl * (z_kn - z_an)       # support loops either side of the knee
        f_t, f_s = jl * 2.0, jl / 0.32
        secs = [
            sec_z((x, 0, z_cr - 0.035 * U), th, th * 1.05),
            sec_z((x, -0.004 * U, (z_cr + z_kn) / 2), th * 0.86, th * 0.9),
            sec_z((x, (-0.012 + 0.008 * f_t) * U, z_kn + d_t), kn + (th * 0.86 - kn) * f_t, kn + (th * 0.9 - kn) * f_t),
            sec_z((x, -0.012 * U, z_kn), kn, kn),
            sec_z((x, (-0.012 + 0.016 * f_s) * U, z_kn - d_s), kn + (ca - kn) * f_s, kn + (ca * 1.08 - kn) * f_s),
            sec_z((x, 0.004 * U, z_kn - (z_kn - z_an) * 0.32), ca, ca * 1.08),
            sec_z((x, 0.004 * U, z_an), an_r, an_r),
            sec_z((x * 1.02, foot_y, z_in), foot_w * (0.8 + 0.2 * lm), foot_l),
            sec_z((x * 1.02, foot_y, 0.0), foot_w * 0.94 * (0.8 + 0.2 * lm), foot_l * 0.95),
        ]
        body.loft(secs, start=loop, cap_end=True,
                  mats=([mi["bottom"]] + [mi["skin"]] * 8) if outfit == "none" else
                  ([mi["bottom"]] * 5 + [mi[boot], mi[boot], mi["shoes"], mi["shoes"]]))

    # ---- arms: lofted out of the holes left between the top torso rings --
    lo, hi = rings[4], rings[5]
    arm_z = sh_z
    x0 = chest_w
    rest = math.radians(P["arm"].get("rest_angle", 0.0))

    def arm_rest(sg):
        """T-pose -> rest pose: swing an arm down about its shoulder joint (an A-pose)."""
        pivot = Matrix.Translation((sg * x0 * 0.92, 0, arm_z))
        return pivot @ Matrix.Rotation(sg * rest, 4, "Y") @ pivot.inverted()

    upper, fore, hand = (P["arm"][k] * U for k in ("upper", "fore", "hand"))
    hp = P["hand"]
    palm, pw, pt = hand * hp["palm"], hp["palm_w"] * U, hp["palm_t"] * U
    ua, el, wr = (gi[k] * U for k in ("upper_arm", "elbow", "wrist"))
    for sg, loop in ((1, [lo[7], lo[0], lo[1], hi[1], hi[0], hi[7]]),
                     (-1, [lo[3], lo[4], lo[5], hi[5], hi[4], hi[3]])):
        with body.part(xform=arm_rest(sg)):
            def ax(d, y=0.0, z=0.0):
                return (sg * (x0 + d), y, arm_z + z)
            secs = [
                sec_x(ax(0.018 * U), ua * 1.25, ua * 1.3),
                sec_x(ax(upper * 0.5), ua, ua),
                sec_x(ax(upper * (1 - jl), 0.008 * U * (1 - 2 * jl)), el + (ua - el) * 2 * jl, el + (ua - el) * 2 * jl),
                sec_x(ax(upper, 0.008 * U), el, el),
                sec_x(ax(upper + fore * jl, (0.008 - 0.004 * jl / 0.4) * U), el * (1 + 0.02 * jl / 0.4), el),
                sec_x(ax(upper + fore * 0.4, 0.004 * U), el * 1.02, el),
                sec_x(ax(upper + fore), wr, wr * 0.85),
                sec_x(ax(upper + fore + palm * 0.5), pw, pt),
                sec_x(ax(upper + fore + palm), pw, pt * 0.9),
            ]
            body.loft(secs, start=loop, cap_end=True,
                      mats=[mi[sleeve[0]]] * 4 + [mi[sleeve[1]]] * 3 + [mi[sleeve[2]]] * 2)
            # fingers and thumb: separate shells that take auto weights from their own bones
            hm = mi[sleeve[2]]
            fr = pw * hp["finger_r"]
            fz = min(fr, pt * 0.85)
            for i, rel in enumerate(hp["fingers"]):                 # index first, on the thumb (-Y) side
                fy = pw * (-0.75 + 0.5 * i)
                fl = (hand - palm) * rel
                body.loft([sec_x(ax(upper + fore + palm - fr * 0.5, fy), fr, fz),
                           sec_x(ax(upper + fore + palm + fl * 0.5, fy), fr, fz),
                           sec_x(ax(upper + fore + palm + fl * 0.94, fy), fr * 0.85, fz * 0.85)], n=6, mat=hm)
            t_a = math.radians(hp["thumb_out"])
            t_d = V(sg * math.cos(t_a), -math.sin(t_a), 0)
            t_0 = V(*ax(upper + fore + palm * hp["thumb_at"], -pw * 0.8))
            t_l = (hand - palm) * hp["thumb"]
            body.loft([sec_dir(t_0 + t_d * t_l * k, t_d, fr * r, fz * r) for k, r in ((0.0, 1.2), (0.5, 1.15), (0.95, 1.0))],
                      n=6, mat=hm)

    # ---- robe / tunic skirts are separate shells that still get auto weights
    if outfit in ("robe", "tunic"):
        bottom_z = 0.07 * U if outfit == "robe" else z_cr - 0.10 * U
        flare = 1.55 if outfit == "robe" else 1.22
        secs = [sec_z((0, 0, tz[2]), waist_w * 1.06, waist_d * 1.08),
                sec_z((0, 0, tz[1]), hip_w * 1.12, hip_d * 1.14),
                sec_z((0, 0, (tz[0] + bottom_z) / 2), hip_w * (1 + flare) / 2, hip_d * (1 + flare) / 1.8),
                sec_z((0, 0, bottom_z), hip_w * flare, hip_d * flare * 1.1)]
        body.loft(secs, n=8, mat=mi["top"], cap_start=False, cap_end=False)

    # ---- face: eyes, brows, ears, mouth interior and the shape keys -------
    face = creature.new_face()
    head.features(extras, face, mi)
    head.keys(face)

    # ---- hair -------------------------------------------------------------
    helmet = "helmet" in accessories
    hp_ = P["hair"]
    if hair in ("short", "long") and not helmet:
        with extras.part(bone="head"):
            rings_h = head.shell(extras, mi["hair"], hp_["scale"], hp_[hair], hp_["front"], hp_["side"])
            if hair == "long":
                for j in range(1, 8):               # the back of the rim hangs to the shoulders
                    rings_h[0][j].co.z = zn - hh * hp_["long_drop"]
                    rings_h[0][j].co.y += hd * 0.12

    # ---- armour plates (rigid) ---------------------------------------------
    if outfit == "armor":
        for sg in (1, -1):
            with extras.part(bone="upper_arm.%s" % ("L" if sg > 0 else "R"), xform=arm_rest(sg)):
                extras.sphere((sg * (x0 + 0.012 * U), 0, arm_z + ua * 0.45),
                              (ua * 1.75, ua * 1.6, ua * 1.25), mi["top"], n=8, m=4)
            with extras.part(bone="shin.%s" % ("L" if sg > 0 else "R")):
                extras.sphere((sg * lx, -0.022 * U - kn * 0.55, z_kn), (kn * 0.95, kn * 0.6, kn * 1.2),
                              mi["top"], n=6, m=3)
    if outfit in ("armor", "tunic", "robe"):
        with extras.part(bone="hips"):
            zb = tz[1] + (tz[2] - tz[1]) * 0.75
            k = 1.10
            extras.loft([sec_z((0, 0, zb - 0.014 * U), waist_w * k * 1.03, waist_d * k * 1.05),
                         sec_z((0, 0, zb + 0.014 * U), waist_w * k, waist_d * k)],
                        n=8, mat=mi["trim"], power=0.85)
            extras.box((0, -waist_d * k * 0.98, zb), (0.03 * U, 0.012 * U, 0.034 * U), mi["shoes"])

    # ---- rig ----------------------------------------------------------------
    rig = Rig(name, "biped")
    rig.bone("root", (0, 0, 0), (0, 0.12 * U, 0), deform=False)
    rig.bone("hips", (0, 0, tz[1]), (0, 0, tz[2]), "root")
    rig.bone("spine", (0, 0, tz[2]), (0, 0, tz[3]), "hips", True)
    rig.bone("chest", (0, 0, tz[3]), (0, 0, tz[5]), "spine", True)
    rig.bone("neck", (0, 0, tz[5]), (0, hc, zn + hh * 0.06), "chest", True)
    rig.bone("head", (0, hc, zn + hh * 0.06), (0, hc, zn + hh), "neck", True)
    for s, sg in (("L", 1), ("R", -1)):             # eyeballs only: no skin follows these
        ec = head.eye_centre(sg)
        rig.bone("eye." + s, ec, ec - Y * hh * 0.10, "head")
    rig.rigid_only = ("eye.L", "eye.R")
    anchors = {}
    for s, sg in (("L", 1), ("R", -1)):
        sh = V(sg * x0 * 0.92, 0, arm_z)
        tm = arm_rest(sg)
        elb, wri, tip = (L["%s.%s" % (j, s)].copy() for j in ("elbow", "wrist", "fingertip"))
        knuckle = wri + (tip - wri) * hp["palm"]
        th0 = wri + (tip - wri) * hp["palm"] * hp["thumb_at"] + V(0, -pw * 0.8, 0)
        th1 = th0 + V(sg * math.cos(t_a), -math.sin(t_a), 0) * (hand - palm) * hp["thumb"]
        anchors["hand." + s] = (tm, (wri + tip) / 2)
        anchors["forearm." + s] = (tm, (elb + wri) / 2)
        elb, wri, tip, knuckle, th0, th1 = (tm @ q for q in (elb, wri, tip, knuckle, th0, th1))
        rig.bone("shoulder." + s, (sg * 0.02 * U, 0, tz[5] - 0.02 * U), sh, "chest")
        rig.bone("upper_arm." + s, sh, elb, "shoulder." + s, True)
        rig.bone("forearm." + s, elb, wri, "upper_arm." + s, True)
        rig.bone("hand." + s, wri, knuckle, "forearm." + s, True)
        rig.bone("fingers." + s, knuckle, tip, "hand." + s, True)
        rig.bone("thumb." + s, th0, th1, "hand." + s)
        rig.bone("hand_ik." + s, wri, knuckle, "root", deform=False)
        rig.ik("forearm." + s, "hand_ik." + s, 2, influence=0.0)
        hip, knee, ank = (L["%s.%s" % (j, s)].copy() for j in ("hip", "knee", "ankle"))
        toe = V(L["toe." + s].x, L["toe." + s].y * 0.92, 0.012 * U)
        rig.bone("thigh." + s, hip, knee, "hips")
        rig.bone("shin." + s, knee, ank, "thigh." + s, True)
        rig.bone("foot." + s, ank, toe, "shin." + s, True)
        rig.bone("foot_ik." + s, ank, toe, "root", deform=False)
        rig.ik("shin." + s, "foot_ik." + s, 2)
        rig.copy_rotation("foot." + s, "foot_ik." + s)
    rig.meta = {"height": H, "leg": L["hip.L"].z - z_an, "thigh": L["hip.L"].z - z_kn, "arm_rest": rest}

    # ---- accessories: separate objects parented to bones ---------------------
    acc_objs = []
    metal = None

    def acc_mat(label, kind, color, **kw):
        return ctx.mat(label, kind, spec.color(label.lower() + "_color", color), **kw)

    for acc in accessories:
        ab = MeshBuilder()
        bone, sharp, bevel = "head", 40, 0.0
        if acc == "helmet":
            metal = metal or acc_mat("Helmet", "metal", "#b4bcc6")
            head.shell(ab, metal, 1.16, 0.22, 0.72, 0.36)
            ab.box((0, hc - hd * 1.13, zn + hh * 0.45), (hw * 0.16, hd * 0.10, hh * 0.34), metal)
            crest = [V(0, hc - hd * 0.9, zn + hh * 0.98), V(0, hc - hd * 0.3, zn + hh * 1.22),
                     V(0, hc + hd * 0.8, zn + hh * 1.12), V(0, hc + hd * 1.1, zn + hh * 0.7),
                     V(0, hc + hd * 0.6, zn + hh * 0.95)]
            ab.extrude([p - X * hw * 0.07 for p in crest], X * hw * 0.14,
                       acc_mat("Plume", "cloth", "#a3242b"))
            sharp = 60
        elif acc == "hat":
            cloth = acc_mat("Hat", "cloth", "#4a3570")
            ab.lathe([(hw * 2.3, 0), (hw * 1.15, hh * 0.05), (hw * 0.95, hh * 0.3),
                      (hw * 0.5, hh * 0.8), (hw * 0.12, hh * 1.25)], n=12, mat=cloth,
                     center=(0, hc, zn + hh * 0.80), cap_start=True, cap_end=True)
            sharp = 50
        elif acc == "crown":
            gold = acc_mat("Crown", "metal", "#d4a637", roughness=0.2)
            ab.lathe([(hw * 0.86, 0), (hw * 0.92, hh * 0.16)], n=12, mat=gold,
                     center=(0, hc, zn + hh * 0.86))
            for k in range(6):
                a = math.tau * k / 6
                ab.cylinder(V(math.cos(a) * hw * 0.9, hc + math.sin(a) * hw * 0.9, zn + hh * 1.0),
                            V(math.cos(a) * hw * 0.94, hc + math.sin(a) * hw * 0.94, zn + hh * 1.16),
                            hh * 0.05, hh * 0.008, n=4, mat=gold)
        elif acc in ("sword", "axe", "staff"):
            bone = "hand.R"
            tm, p = anchors[bone]
            p = p + V(0, -0.02 * U, 0)
            steel = acc_mat("Blade", "metal", "#cfd6de", roughness=0.18)
            wood = acc_mat("Grip", "wood", "#5a3a22")
            with ab.part(xform=tm @ Matrix.Translation(p) @ Matrix.Rotation(math.pi / 2, 4, "X")):
                if acc == "sword":
                    parts.sword(ab, 0.52 * H, steel, acc_mat("Hilt", "metal", "#c9a03a"), wood)
                elif acc == "axe":
                    parts.axe(ab, 0.45 * H, steel, wood)
                else:
                    with ab.part(xform=Matrix.Translation((0, 0, -0.45 * H))):
                        parts.staff(ab, 0.95 * H, wood, acc_mat("Gem", "emissive", "#58c8ff"))
            bevel = 0.0
        elif acc == "shield":
            bone = "forearm.L"
            tm, p = anchors[bone]
            p = p + V(0, 0, el + 0.012 * U)
            with ab.part(xform=tm @ Matrix.Translation(p) @ Matrix.Rotation(-math.pi / 2, 4, "X")):
                parts.shield(ab, 0.17 * H, acc_mat("Shield", "wood", "#7a2e2e"),
                             acc_mat("ShieldRim", "metal", "#b4bcc6"), style="heater")
        elif acc == "cape":
            bone = "chest"
            cloth = acc_mat("Cape", "cloth", "#8c1f28")
            y = chest_d + 0.012 * U
            pts = [V(-chest_w * 0.95, y, tz[5]), V(chest_w * 0.95, y, tz[5]),
                   V(chest_w * 1.35, y + 0.10 * U, z_kn), V(-chest_w * 1.35, y + 0.10 * U, z_kn)]
            ab.extrude(pts, Y * 0.012 * U, cloth)
        elif acc == "backpack":
            bone = "chest"
            ab.box((0, chest_d + 0.05 * U, (tz[2] + tz[5]) / 2),
                   (chest_w * 1.5, 0.09 * U, (tz[5] - tz[2]) * 0.9), acc_mat("Pack", "leather", "#6b4a2f"))
            bevel = 0.012 * U
        else:
            from ..log import warn
            warn("unknown accessory '%s' (options: helmet, hat, crown, sword, axe, staff, shield, "
                 "cape, backpack)" % acc, spec.line_of("accessories"))
            continue
        obj = ab.to_object("%s_%s" % (name, acc.title()), ctx.collection, sharp_angle=sharp)
        if bevel and not ctx.spec_lowpoly(spec):
            add_bevel(obj, bevel)
        acc_objs.append((obj, bone))

    issues = validate.check_biped(sk, overrides) + validate.check_cage(body, extras) + validate.check_rig(rig)
    entity = creature.finalize(ctx, spec, name, body, extras, rig, face, "head", acc_objs, preserve_volume=True,
                              smooth_weights=P["shape"]["weight_smooth"])
    validate.report(name, P, sk, issues, entity, spec, ctx)
    # box the `face` camera views frame (head plus a margin), in armature space
    entity.regions = {"face": ((-hw * 1.12, hc - hd * 1.12, zn - hh * 0.10), (hw * 1.12, hc + hd * 1.12, zn + hh * 1.08))}
    return entity
