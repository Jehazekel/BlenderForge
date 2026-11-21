"""Reference-image alignment: measure silhouettes, fit a profile, compare.

Works on plain silhouettes: one animal on a flat background (or with an alpha
channel), seen from the side, front or top. There is no image recognition
here. The image is thresholded into a mask and a few robust proportions are
read off it; the model's own cage is rasterised from the same direction and
measured the same way, so the two sets of numbers are directly comparable.

    reference_side: wolf_side.png      reference_front: wolf_front.png
    reference_top: wolf_top.png        reference_fit: true
    reference_facing: left             (side view: which way the nose points)
"""

import math
import os

from ..log import ForgeError, info, warn

VIEWS = ("side", "front", "top")
RES = 200                   # raster size along the longest side
TOLERANCE = 0.08            # relative difference reported as a mismatch
NAMES = {"leg": "leg length", "depth": "body depth", "rise": "head and neck height",
         "aspect": "height to length", "width": "body width"}


class Ref:
    def __init__(self, view, path, mask):
        self.view, self.path, self.mask = view, path, mask
        self.m = measure(mask, view)
        self.flipped = False


# ---- masks ----------------------------------------------------------------------------

def load_mask(path, line=None, res=RES):
    """Image -> rows of booleans (top row first). Foreground = not background."""
    import bpy
    try:
        img = bpy.data.images.load(path, check_existing=False)
    except RuntimeError:
        raise ForgeError("cannot load reference image '%s'" % path, line)
    w, h = img.size
    if w < 4 or h < 4:
        raise ForgeError("reference image '%s' is empty or unreadable" % path, line)
    if max(w, h) > res:
        s = res / float(max(w, h))
        img.scale(max(4, int(w * s)), max(4, int(h * s)))
        w, h = img.size
    px = list(img.pixels[:])
    ch = img.channels
    bpy.data.images.remove(img)

    def at(x, y):
        i = (y * w + x) * ch
        return px[i:i + ch]

    alphas = [px[i + 3] for i in range(0, len(px), ch)] if ch == 4 else []
    use_alpha = bool(alphas) and min(alphas) < 0.5 < max(alphas)
    corners = [at(0, 0), at(w - 1, 0), at(0, h - 1), at(w - 1, h - 1)]
    bg = [sorted(c[k] for c in corners)[1] for k in range(min(ch, 3))]
    rows = []
    for y in range(h - 1, -1, -1):              # Blender stores the bottom row first
        row = []
        for x in range(w):
            p = at(x, y)
            if use_alpha:
                row.append(p[3] > 0.5)
            else:
                row.append(sum(abs(p[k] - bg[k]) for k in range(len(bg))) > 0.30)
        rows.append(row)
    if not any(any(r) for r in rows):
        raise ForgeError("reference image '%s' has no visible silhouette against its background" % path, line)
    return rows


def _crop(mask):
    ys = [y for y, row in enumerate(mask) if any(row)]
    xs = [x for row in mask for x, v in enumerate(row) if v]
    y0, y1, x0, x1 = min(ys), max(ys), min(xs), max(xs)
    return [row[x0:x1 + 1] for row in mask[y0:y1 + 1]]


def _longest_run(row):
    best = cur = 0
    for v in row:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best


def measure(mask, view):
    """Proportions of a silhouette, all relative to its own length or height."""
    m = _crop(mask)
    h, w = len(m), len(m[0])
    if view == "side":
        runs = [_longest_run(r) for r in m]
        peak = max(range(h), key=lambda y: runs[y])
        lim = 0.55 * runs[peak]
        top = peak
        while top > 0 and runs[top - 1] >= lim:
            top -= 1
        bot = peak
        while bot < h - 1 and runs[bot + 1] >= lim:
            bot += 1
        return {"aspect": h / w, "depth": (bot - top + 1) / w, "leg": (h - 1 - bot) / w, "rise": top / w}
    if view == "front":
        return {"aspect": h / w, "width": max(_longest_run(r) for r in m) / h}
    return {"aspect": h / w, "width": w / h}      # top view: width over length


def rasterize(builders, view):
    """Fill the cage's faces into a mask, seen from the side (nose left), front or top."""
    tris = []
    lo = [1e9, 1e9]
    hi = [-1e9, -1e9]
    for mb in builders:
        if mb is None:
            continue
        for face in mb.bm.faces:
            pts = []
            for v in face.verts:
                c = v.co
                p = (c.y, c.z) if view == "side" else ((c.x, c.z) if view == "front" else (c.x, -c.y))
                pts.append(p)
                for k in (0, 1):
                    lo[k], hi[k] = min(lo[k], p[k]), max(hi[k], p[k])
            for i in range(1, len(pts) - 1):
                tris.append((pts[0], pts[i], pts[i + 1]))
    span = max(hi[0] - lo[0], hi[1] - lo[1], 1e-9)
    s = (RES - 1) / span
    w, h = int((hi[0] - lo[0]) * s) + 2, int((hi[1] - lo[1]) * s) + 2
    mask = [[False] * w for _ in range(h)]
    for a, b, c in tris:
        ax, ay = (a[0] - lo[0]) * s, (hi[1] - a[1]) * s
        bx, by = (b[0] - lo[0]) * s, (hi[1] - b[1]) * s
        cx, cy = (c[0] - lo[0]) * s, (hi[1] - c[1]) * s
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        for y in range(max(0, int(min(ay, by, cy))), min(h - 1, int(max(ay, by, cy)) + 1) + 1):
            row = mask[y]
            for x in range(max(0, int(min(ax, bx, cx))), min(w - 1, int(max(ax, bx, cx)) + 1) + 1):
                l1 = ((by - cy) * (x - cx) + (cx - bx) * (y - cy)) / den
                l2 = ((cy - ay) * (x - cx) + (ax - cx) * (y - cy)) / den
                if l1 >= -0.02 and l2 >= -0.02 and l1 + l2 <= 1.02:
                    row[x] = True
    return mask


# ---- input ----------------------------------------------------------------------------------

def from_spec(spec, base_dir):
    refs = []
    facing = spec.choice("reference_facing", ("auto", "left", "right"), "auto")
    for view in VIEWS:
        key = "reference_" + view
        path = spec.get(key)
        if not path:
            continue
        if not os.path.isabs(path):
            path = os.path.join(base_dir, path)
        if not os.path.isfile(path):
            raise ForgeError("reference image not found: %s" % path, spec.line_of(key))
        mask = load_mask(path, spec.line_of(key))
        flipped = False
        if view == "side":
            c = _crop(mask)
            top_x = sum(x for x, v in enumerate(c[0]) if v) / max(1, sum(c[0]))
            if facing == "right" or (facing == "auto" and top_x > len(c[0]) / 2):
                mask = [list(reversed(r)) for r in mask]     # models face left, so flip the picture
                flipped = True
        ref = Ref(view, path, mask)
        ref.flipped = flipped
        refs.append(ref)
        info("reference %s view: %s%s -> %s" % (view, os.path.basename(path), " (mirrored)" if flipped else "",
                                               ", ".join("%s %.3f" % (NAMES.get(k, k), v) for k, v in ref.m.items())))
    return refs


# ---- fitting ----------------------------------------------------------------------------------

def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def fit(profile, size, refs, geometry):
    """Nudge the profile until the model's silhouette proportions match the references.

    Only whole-limb scale, chest depth and width and neck length are changed,
    each within sane bounds, so the result is still the same species.
    """
    start = dict(legs=profile["limb"]["fore_scale"], depth=profile["trunk"]["chest_depth"],
                 width=profile["trunk"]["chest_width"], neck=profile["neck"]["length"])
    for _ in range(8):
        _, body, extras = geometry(profile, size)
        worst = 0.0
        for ref in refs:
            model = measure(rasterize((body, extras), ref.view), ref.view)
            for key, target in ref.m.items():
                if model.get(key, 0) < 1e-6 or target < 1e-6:
                    continue
                r = target / model[key]
                worst = max(worst, abs(r - 1.0))
                r = _clamp(r, 0.6, 1.6) ** 0.8
                if ref.view == "side" and key == "leg":
                    for k in ("fore_scale", "hind_scale"):
                        profile["limb"][k] = _clamp(profile["limb"][k] * r, 0.15, 4.0)
                elif ref.view == "side" and key == "depth":
                    profile["trunk"]["chest_depth"] = _clamp(profile["trunk"]["chest_depth"] * r, 0.08, 0.9)
                elif ref.view == "side" and key == "rise":
                    profile["neck"]["length"] = _clamp(profile["neck"]["length"] * r ** 0.7, 0.02, 1.5)
                elif key == "width":
                    profile["trunk"]["chest_width"] = _clamp(profile["trunk"]["chest_width"] * r, 0.06, 1.2)
        if worst < 0.02:
            break
    end = dict(legs=profile["limb"]["fore_scale"], depth=profile["trunk"]["chest_depth"],
               width=profile["trunk"]["chest_width"], neck=profile["neck"]["length"])
    notes = ["%s %.2f -> %.2f" % (k, start[k], end[k]) for k in start if abs(end[k] - start[k]) > 0.005 * max(start[k], 1e-6)]
    if notes:
        info("reference fit adjusted: " + ", ".join(notes))
    return notes


def compare(refs, body, extras, fit_notes=()):
    """Issues for every proportion that still differs from a reference."""
    out = []
    for ref in refs:
        model = measure(rasterize((body, extras), ref.view), ref.view)
        for key, target in ref.m.items():
            got = model.get(key)
            if got is None or target < 1e-6:
                continue
            diff = (got - target) / target
            text = "%s view %s: model %.3f, reference %.3f (%+.0f%%)" % (ref.view, NAMES.get(key, key), got, target, diff * 100)
            if abs(diff) > TOLERANCE and target > 0.03:
                out.append(("warning", "reference.%s.%s" % (ref.view, key), text))
            else:
                out.append(("info", "reference.%s.%s" % (ref.view, key), text))
    return out


def add_empties(refs, entity, ctx):
    """Place each picture behind the model as an image empty for eyeballing."""
    import bpy
    from mathutils import Vector
    lo, hi = entity.bounds()
    col = bpy.data.collections.get("References") or bpy.data.collections.new("References")
    if col.name not in ctx.scene.collection.children:
        ctx.scene.collection.children.link(col)
    for ref in refs:
        try:
            img = bpy.data.images.load(ref.path, check_existing=True)
        except RuntimeError:
            continue
        e = bpy.data.objects.new("%s_ref_%s" % (entity.name, ref.view), None)
        e.empty_display_type = "IMAGE"
        e.data = img
        e.color[3] = 0.5
        e.use_empty_image_alpha = True
        rows = [y for y, r in enumerate(ref.mask) if any(r)]
        cols = [x for r in ref.mask for x, v in enumerate(r) if v]
        mw, mh = len(ref.mask[0]), len(ref.mask)
        fw = (max(cols) - min(cols) + 1) / mw            # silhouette width as a fraction of the picture
        cx = ((max(cols) + min(cols)) / 2 + 0.5) / mw - 0.5
        cy = 0.5 - ((max(rows) + min(rows)) / 2 + 0.5) / mh
        if ref.flipped:
            cx = -cx
        aspect = mh / mw
        mid = (lo + hi) / 2
        if ref.view == "side":
            width = (hi.y - lo.y) / fw
            e.rotation_euler = (math.radians(90), 0, math.radians(90))
            e.scale = (-1 if ref.flipped else 1, 1, 1)
            e.location = Vector((lo.x - (hi.x - lo.x), mid.y - cx * width, mid.z - cy * width * aspect))
        elif ref.view == "front":
            width = (hi.x - lo.x) / fw
            if getattr(ref, "biped", False):                # A-pose model: match heights, not widths
                width = (hi.z - lo.z) / ((max(rows) - min(rows) + 1) / mh) / aspect
            e.rotation_euler = (math.radians(90), 0, 0)
            e.location = Vector((mid.x - cx * width, hi.y + (hi.y - lo.y) * 0.3, mid.z - cy * width * aspect))
        else:
            width = (hi.x - lo.x) / fw
            e.location = Vector((mid.x - cx * width, mid.y + cy * width * aspect, -0.01))
        e.empty_display_size = width if aspect <= 1 else width * aspect
        e.parent = entity.root
        col.objects.link(e)
    return []


# ---- humans (front view, compared with the solved skeleton) -------------------------------------
#
# The human rest pose is an A-pose and a photo can be in any pose, so only measures that do not
# depend on the arms are always used: crown to the narrowest row under the head (jaw or neck), and crotch height.
# Arm span needs `reference_pose: tpose`; hip width needs `tpose` or `apose` (arms clear of the hips).
# The model side is read off the skeleton rather than a raster of the mesh, so fitting is instant.

BIPED_RES = 600           # a head is about 1/8 of the height, so it needs more pixels than an animal
BIPED_NAMES = {"neck": "crown to jaw/neck", "crotch": "crotch height", "span": "arm span", "hip": "hip width"}
BIPED_GROUPS = {          # measure -> (profile values it scales, user keys that lock it)
    "crotch": ((("leg", "thigh"), ("leg", "shank")), ("leg_length", "limb_length", "leg.")),
    "neck": ((("head", "height"), ("head", "width"), ("head", "depth")), ("head_size", "head.")),
    "span": ((("arm", "upper"), ("arm", "fore"), ("arm", "hand")), ("arm_length", "limb_length", "arm.")),
    "hip": ((("breadth", "hip"),), ("breadth.hip", "build")),
}


def measure_biped(mask, pose):
    """Front silhouette of a standing person -> proportions of its own height."""
    m = _crop(mask)
    h, w = len(m), len(m[0])
    runs = [[x for x, v in enumerate(r) if v] for r in m]
    cx = round(sum(runs[0]) / max(1, len(runs[0])))            # body centre: middle of the crown
    out = {}
    y = h - 1                                                 # crotch: lowest row filled at the centre
    while y > 0 and not m[y][cx]:
        y -= 1
    if y < h - 1:
        out["crotch"] = (h - 1 - y) / h
    top = max(1, int(h * 0.30))                               # neck: narrowest centre run below the head
    widths = []
    for yy in range(int(h * 0.05), top):
        r = m[yy]
        if not r[cx]:
            continue
        a = b = cx
        while a > 0 and r[a - 1]:
            a -= 1
        while b < w - 1 and r[b + 1]:
            b += 1
        widths.append((b - a + 1, yy))
    head = best = None                                      # widest head row, then narrowest before the shoulders
    for wd, yy in widths:
        if best is None and (head is None or wd >= head):
            head = wd
        elif best is None and wd < 0.8 * head:
            best = (wd, yy)
        elif best is not None:
            if wd < best[0]:
                best = (wd, yy)
            elif wd > 1.5 * best[0]:
                break
    if best is not None:
        out["neck"] = (best[1] + 0.5) / h
    if pose == "tpose":
        out["span"] = w / h
    if pose in ("tpose", "apose") and "crotch" in out:
        yy = max(0, int(h - 1 - (out["crotch"] + 0.04) * h))
        r = m[yy]
        if r[cx]:
            a = b = cx
            while a > 0 and r[a - 1]:
                a -= 1
            while b < w - 1 and r[b + 1]:
                b += 1
            out["hip"] = (b - a + 1) / h
    return out


def model_biped(profile, sk):
    """The same proportions read off a solved skeleton (stature units).

    The mesh's visible crotch, narrowest neck and hip outline sit a little off the landmarks;
    profile['reference'] holds those offsets, calibrated on the default humanoid mesh.
    """
    c = profile.get("reference", {})
    m = sk.m
    return {"crotch": sk.lm["crotch"].z / sk.scale / m["length"] * c.get("crotch", 1.0),
            "neck": m["head_to_stature"] * c.get("narrow_at", 1.0),
            "span": m["arm_span"], "hip": 2 * sk.hip_w / sk.scale / m["length"] * c.get("hip", 1.0)}


def biped_refs(spec, base_dir):
    """Front reference for a human; side and top are not used for humans yet."""
    for view in ("side", "top"):
        if spec.get("reference_" + view):
            warn("reference_%s is not used for humans yet (front view only)" % view, spec.line_of("reference_" + view))
    path = spec.get("reference_front")
    if not path:
        return []
    if not os.path.isabs(path):
        path = os.path.join(base_dir, path)
    if not os.path.isfile(path):
        raise ForgeError("reference image not found: %s" % path, spec.line_of("reference_front"))
    pose = spec.choice("reference_pose", ("any", "apose", "tpose"), "any")
    ref = Ref("front", path, load_mask(path, spec.line_of("reference_front"), BIPED_RES))
    ref.m = measure_biped(ref.mask, pose)
    ref.biped = True
    if not ref.m:
        raise ForgeError("reference image '%s': no head, neck or legs found in the silhouette" % path,
                         spec.line_of("reference_front"))
    info("reference front view: %s (pose %s) -> %s" % (os.path.basename(path), pose,
         ", ".join("%s %.3f" % (BIPED_NAMES[k], v) for k, v in sorted(ref.m.items()))))
    return [ref]


def fit_biped(profile, height, refs, solve, spec):
    """Scale whole segment groups until the skeleton matches the reference; user-set groups are left alone."""
    ref = refs[0]
    locked = [k for k in ref.m if any(spec.has(u) if not u.endswith(".") else
                                      any(p.startswith(u) for p in spec.props) for u in BIPED_GROUPS[k][1])]
    keys = [k for k in sorted(ref.m) if k not in locked]
    start = {k: profile[s][f] for k in keys for s, f in BIPED_GROUPS[k][0][:1]}
    for _ in range(12):
        model = model_biped(profile, solve(profile, height))
        worst = 0.0
        for k in keys:
            r = ref.m[k] / max(model[k], 1e-6)
            worst = max(worst, abs(r - 1))
            for s, f in BIPED_GROUPS[k][0]:
                first = BIPED_GROUPS[k][0][0]
                base = start[k] if (s, f) == first else None
                v = profile[s][f] * _clamp(r, 0.8, 1.25) ** 0.8
                if base is not None:
                    v = _clamp(v, base * 0.75, base * 1.33)
                    r_eff = v / profile[s][f]
                    profile[s][f] = v
                else:
                    profile[s][f] *= r_eff
        if worst < 0.01:
            break
    notes = ["%s x%.2f" % (BIPED_NAMES[k], profile[BIPED_GROUPS[k][0][0][0]][BIPED_GROUPS[k][0][0][1]] / start[k])
             for k in keys if abs(profile[BIPED_GROUPS[k][0][0][0]][BIPED_GROUPS[k][0][0][1]] / start[k] - 1) > 0.005]
    notes += ["%s kept (set in the input)" % BIPED_NAMES[k] for k in locked]
    if notes:
        info("reference fit adjusted: " + ", ".join(notes))
    return notes


def compare_biped(refs, profile, sk):
    out = []
    model = model_biped(profile, sk)
    for key, target in sorted(refs[0].m.items()):
        got = model[key]
        diff = (got - target) / target
        text = "front view %s: model %.3f, reference %.3f (%+.0f%%)" % (BIPED_NAMES[key], got, target, diff * 100)
        out.append(("warning" if abs(diff) > TOLERANCE else "info", "reference.front.%s" % key, text))
    return out
