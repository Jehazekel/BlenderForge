"""Automated anatomy checks on a solved skeleton, the mesh cage and the rig.

Each check returns issues as (level, code, message) with level "error",
"warning" or "info". Nothing here needs Blender except `report`, which stores
the result on the armature and can add landmark empties.
"""

import json

from ..log import ForgeError, info, warn
from . import profiles

REPORTS = []        # one dict per validated animal; build.py writes them next to the .blend

LABELS = {
    "back_slope": "back slope (degrees, + = withers higher)",
    "head_to_trunk": "head length / trunk length",
    "neck_to_trunk": "neck length / trunk length",
    "chest_depth": "chest depth / trunk length",
    "width_to_depth": "chest width / chest depth",
    "fore_to_hind_height": "shoulder height / hip height",
    "upper_to_lower_fore": "upper arm / forearm",
    "upper_to_lower_hind": "thigh / shin",
    "leg_to_trunk": "chest clearance / trunk length",
    "limb_radius_to_depth": "limb thickness / chest depth",
    "tail_to_trunk": "tail length / trunk length",
    "head_to_stature": "head height / stature",
    "neck_to_stature": "neck length / stature",
    "leg_to_stature": "hip joint height / stature",
    "thigh_to_shank": "thigh / shin",
    "upper_to_forearm": "upper arm / forearm",
    "arm_span": "arm span / stature",
    "fingertip_height": "fingertip height with arms hanging / stature",
    "shoulder_to_hip": "shoulder breadth / hip breadth",
    "shoulder_width": "shoulder breadth / stature",
    "foot_to_stature": "foot length / stature",
    "eye_height": "eye line / head height", "eye_spacing": "pupil distance / head width",
    "mouth_to_eye_spacing": "mouth width / pupil distance", "mid_face": "brow to nose base / face height",
    "lower_face": "nose base to chin / face height", "head_width_to_depth": "head width / head depth",
}


def _limits(sk, overrides=()):
    P, m = sk.profile, sk.m
    out = []
    note = " (after your overrides: %s)" % ", ".join(overrides) if overrides else ""
    for key, (lo, hi) in P["limits"].items():
        if key not in m:
            continue
        v = m[key]
        if lo <= v <= hi:
            continue
        span = max(hi - lo, 1e-6)
        far = (lo - v if v < lo else v - hi) / span
        level = "error" if far > 0.5 else "warning"
        out.append((level, "proportion." + key, "%s is %.2f, outside the %s range %.2f-%.2f%s"
                    % (LABELS.get(key, key), v, P.get("class", "class"), lo, hi, note)))
    return out


def _mirrored(sk):
    out = []
    for name, p in sk.lm.items():                       # left / right landmarks must mirror
        if name.endswith(".L"):
            q = sk.lm.get(name[:-1] + "R")
            if q is None or abs(p.x + q.x) > 1e-6 or abs(p.y - q.y) > 1e-6 or abs(p.z - q.z) > 1e-6:
                out.append(("error", "symmetry.landmark", "landmark %s has no mirrored partner" % name))
    return out


def check_biped(sk, overrides=()):
    """Human proportions, joint order and direction, ground contact."""
    lm = sk.lm
    out = _limits(sk, overrides)
    order = ("ankle.L", "knee.L", "hip.L", "waist", "chest", "shoulder.L", "chin", "eyes", "crown")
    for a, b in zip(order, order[1:]):
        if lm[b].z - lm[a].z < 1e-6:
            out.append(("error", "joint.order", "%s is not above %s" % (b.split(".")[0], a.split(".")[0])))
    if lm["ankle.L"].z < -1e-6 or lm["crotch"].z <= lm["knee.L"].z:
        out.append(("error", "ground.legs", "the legs are too short for this trunk: the crotch is at or below the knees"))
    if lm["knee.L"].y > min(lm["hip.L"].y, lm["ankle.L"].y) + 1e-6:
        out.append(("error", "joint.knee", "the knee sits behind the hip-ankle line, so the leg would bend backwards"))
    if lm["elbow.L"].y < min(lm["shoulder.L"].y, lm["wrist.L"].y) - 1e-6:
        out.append(("error", "joint.elbow", "the elbow sits in front of the shoulder-wrist line, so the arm would bend backwards"))
    return out + _mirrored(sk)


def check_skeleton(sk, overrides=()):
    """Proportions, joint placement, ground contact and balance."""
    P, m = sk.profile, sk.m
    out = []
    note = " (after your overrides: %s)" % ", ".join(overrides) if overrides else ""

    for key, (lo, hi) in P["limits"].items():
        if key not in m:
            continue
        v = m[key]
        if lo <= v <= hi:
            continue
        span = max(hi - lo, 1e-6)
        far = (lo - v if v < lo else v - hi) / span
        level = "error" if far > 0.5 else "warning"
        out.append((level, "proportion." + key, "%s is %.2f, outside the %s range %.2f-%.2f%s"
                    % (LABELS.get(key, key), v, P.get("class", "class"), lo, hi, note)))

    for pair, drop in (("fore", m["fore_foot_drop"]), ("hind", m["hind_foot_drop"])):
        if abs(drop) > 1e-5:
            out.append(("error", "ground." + pair, "%s feet miss the ground by %.4f trunk lengths" % (pair, drop)))

    rules = profiles.joint_rules(P.get("posture", "erect"))
    for pair, key, joint_names in (("f", "fore", ("elbow", "wrist")), ("h", "hind", ("stifle (knee)", "hock"))):
        J = sk.limbs[(pair, "L")]["joints"]
        for i, want in enumerate(rules.get(key, [])):
            if i + 2 > len(J) - 1 + 1 or i + 1 >= len(J):
                continue
            forward = J[i].y - J[i + 1].y           # > 0: the lower joint sits further forward
            if forward * want < -1e-6:
                out.append(("error", "joint.%s.%d" % (key, i),
                            "%s points the wrong way: it should sit %s the joint above it"
                            % (joint_names[min(i, 1)], "ahead of" if want > 0 else "behind")))
    for (pair, side), limb in sk.limbs.items():
        if side == "L" and any(j.z < -1e-6 for j in limb["joints"]):
            out.append(("error", "joint.underground", "a %s limb joint is below the ground"
                        % ("fore" if pair == "f" else "hind")))

    span = m["hind_foot_y"] - m["fore_foot_y"]
    if span > 1e-6:
        t = (m["com_y"] - m["fore_foot_y"]) / span      # 0 = over the front feet, 1 = over the hind feet
        if t < -0.05 or t > 1.05:
            out.append(("warning", "balance", "centre of mass falls %s the feet (%.0f%% along the base); it would tip over"
                        % ("in front of" if t < 0 else "behind", t * 100)))
    if m["belly_clearance"] < -1e-6:
        out.append(("error", "ground.belly", "the belly is %.2f trunk lengths below the ground; legs are too short for this trunk"
                    % -m["belly_clearance"]))
    if sk.lm["nose"].z < 0:
        out.append(("warning", "ground.nose", "the nose is below the ground; raise the neck or head angle"))

    for name, p in sk.lm.items():                       # left / right landmarks must mirror
        if name.endswith(".L"):
            q = sk.lm.get(name[:-1] + "R")
            if q is None or abs(p.x + q.x) > 1e-6 or abs(p.y - q.y) > 1e-6 or abs(p.z - q.z) > 1e-6:
                out.append(("error", "symmetry.landmark", "landmark %s has no mirrored partner" % name))
    return out


def check_cage(*builders):
    """Mesh checks: left / right symmetry and nothing below the ground."""
    pts = []
    for mb in builders:
        if mb is not None:
            pts += [v.co.copy() for v in mb.bm.verts]
    if not pts:
        return []
    size = max(max(p.y for p in pts) - min(p.y for p in pts), 1e-6)
    tol = size * 2e-4
    q = 1.0 / tol

    def key(x, y, z):
        return (round(x * q), round(y * q), round(z * q))

    cells = set()
    for p in pts:
        kx, ky, kz = key(p.x, p.y, p.z)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    cells.add((kx + dx, ky + dy, kz + dz))
    missing = sum(1 for p in pts if key(-p.x, p.y, p.z) not in cells)
    out = []
    if missing:
        out.append(("error", "symmetry.mesh", "%d of %d vertices have no mirror image across the body's midline"
                    % (missing, len(pts))))
    low = min(p.z for p in pts)
    if low < -size * 2e-3:
        out.append(("warning", "ground.mesh", "the mesh dips %.3f m below the ground" % -low))
    return out


def check_rig(rig):
    """Bone checks: mirrored pairs, usable lengths, IK chains that exist."""
    bones = {b["name"]: b for b in rig.bones}
    out = []
    for name, b in bones.items():
        if (b["tail"] - b["head"]).length < 1e-5:
            out.append(("warning", "rig.length", "bone %s has almost no length" % name))
        if name.endswith(".L"):
            r = bones.get(name[:-1] + "R")
            if r is None:
                out.append(("error", "symmetry.rig", "bone %s has no right-side partner" % name))
                continue
            for a, c in ((b["head"], r["head"]), (b["tail"], r["tail"])):
                if abs(a.x + c.x) > 1e-5 or abs(a.y - c.y) > 1e-5 or abs(a.z - c.z) > 1e-5:
                    out.append(("error", "symmetry.rig", "bones %s and %s are not mirror images" % (name, r["name"])))
                    break
    for bone, target, chain, _ in rig.iks:
        cur, n = bone, 0
        while cur and n < chain:
            cur = bones[cur]["parent"] if cur in bones else None
            n += 1
        if bone not in bones or target not in bones or n < chain:
            out.append(("error", "rig.ik", "IK on %s needs %d bones in its chain" % (bone, chain)))
    return out


def source_note(P):
    """One short line saying where a profile's numbers come from. The full
    citation, licence and raw values go in <output>.anatomy.json."""
    src = P.get("source")
    if not src:
        return "approximations (no measured source)"
    ids = src.get("specimens") or []
    return "%d value group%s %s %s, %s%s%s" % (
        len(src["values"]), "" if len(src["values"]) == 1 else "s",
        "entered from" if "verified" in src else "measured from", src["dataset"], src["taxon"],
        " (%d specimen%s)" % (len(ids), "" if len(ids) == 1 else "s") if ids else "",
        "" if src.get("verified", True) else "; not yet checked against the printed table")


def _source_data(P):
    src = P.get("source")
    if not src:
        return None
    return {"dataset": src["dataset"], "taxon": src["taxon"], "note": src.get("note", ""),
            "specimens": src.get("specimens", []), "raw": src["raw"], "values": src["values"],
            "verified": src.get("verified", True), "citation": src["source"].get("citation"), "license": src["source"].get("license"),
            "units": src["source"].get("units"), "url": src["source"].get("url")}


def report_params(name, P, keys, entity, spec, issues=()):
    """Checks for the simple plans (bird, fish, serpent): each multiplier against its limits."""
    mode = spec.choice("validate", ("on", "strict", "off"), "on")
    issues = list(issues)
    for key in keys:
        lo, hi = P.get("limits", {}).get(key, (None, None))
        if lo is not None and not lo <= P[key] <= hi:
            issues.append(("warning", "proportion." + key,
                           "%s = %.2f is outside the plausible range %.2f to %.2f" % (key, P[key], lo, hi)))
    if mode != "off":
        for _, code, msg in issues:
            warn("anatomy [%s] %s: %s" % (code, name, msg), spec.line)
        info("anatomy: %s (%s, %s): %d warning%s; %s"
             % (name, P["name"], P.get("class", "?"), len(issues), "" if len(issues) == 1 else "s", source_note(P)))
    REPORTS.append({
        "name": name, "profile": P["name"], "class": P.get("class"),
        "measures": {k: round(P[k], 4) for k in keys}, "limits": P.get("limits", {}), "source": _source_data(P),
        "issues": [{"level": l, "code": c, "message": m} for l, c, m in issues],
    })
    arm = entity.armature
    if arm is not None:
        arm["anatomy_profile"] = P["name"]
        arm["anatomy_report"] = json.dumps(REPORTS[-1]["issues"])
        arm["anatomy_source"] = json.dumps(REPORTS[-1]["source"])
    if mode == "strict" and issues:
        raise ForgeError("%s failed anatomy validation (validate: strict)" % name, spec.line)


def report(name, P, sk, issues, entity, spec, ctx):
    """Print the result, keep it with the model, and honour `validate: strict`."""
    mode = spec.choice("validate", ("on", "strict", "off"), "on")
    errors = [i for i in issues if i[0] == "error"]
    warnings = [i for i in issues if i[0] == "warning"]
    notes = [i for i in issues if i[0] == "info"]
    line = spec.line
    if mode != "off":
        for level, code, msg in errors + warnings:
            warn("anatomy [%s] %s: %s" % (code, name, msg), line)
        for _, code, msg in notes:
            info("anatomy [%s] %s: %s" % (code, name, msg))
        summary = getattr(sk, "summary", None) or "withers %.2f m, hips %.2f m, back slope %.1f deg" % (
            sk.lm["withers"].z, sk.lm["croup"].z, sk.m["back_slope"])
        info("anatomy: %s (%s, %s): %d error%s, %d warning%s; %s"
             % (name, P["name"], P.get("class", "?"), len(errors), "" if len(errors) == 1 else "s",
                len(warnings), "" if len(warnings) == 1 else "s", summary))
        info("anatomy: %s source: %s" % (name, source_note(P)))
    data = {
        "name": name, "profile": P["name"], "class": P.get("class"), "scale_m_per_trunk": round(sk.scale, 5),
        "measures": {k: round(v, 4) for k, v in sk.m.items()},
        "limits": P["limits"], "source": _source_data(P), "stature": P.get("stature"),
        "landmarks": {k: [round(c, 4) for c in v] for k, v in sorted(sk.lm.items())},
        "issues": [{"level": l, "code": c, "message": m} for l, c, m in issues],
    }
    REPORTS.append(data)
    arm = entity.armature
    if arm is not None:
        arm["anatomy_profile"] = P["name"]
        arm["anatomy_report"] = json.dumps(data["issues"])
        arm["anatomy_landmarks"] = json.dumps(data["landmarks"])
        arm["anatomy_source"] = json.dumps(data["source"])
    if spec.flag("landmarks", False) and arm is not None:
        import bpy
        for lname, p in sk.lm.items():
            e = bpy.data.objects.new("%s_lm_%s" % (name, lname), None)
            e.empty_display_type = "SPHERE"
            e.empty_display_size = 0.012 * sk.m["length"] * sk.scale
            e.location = p
            e.parent = arm
            e.show_name = True
            ctx.collection.objects.link(e)
            entity.objects.append(e)
    if mode == "strict" and (errors or warnings):
        raise ForgeError("'%s' failed anatomy validation (%d error%s, %d warning%s) and 'validate: strict' is set"
                         % (name, len(errors), "" if len(errors) == 1 else "s",
                            len(warnings), "" if len(warnings) == 1 else "s"), line)
