"""Rigged base mesh from `base samples/` (a Rigify rig made in Blender), animated
with the clip library in forge/rigify_anims.py.

    # character: Hero
    type: base_sample   body: male
    animation: @idle, @locomotion, walk, punching   (or: all)

Keys: file (a .blend; default the low-poly male/female basemesh), body (male |
female), height (metres; default keeps the sample's own size), color, speed,
face (ict = the bundled ICT-FaceKit head with ARKit shape keys, default when the
asset exists | none = the sample's own head), say (line for the lip-sync clips).
Rigging comes from the Rigify add-on: the rig is appended as generated, with its
`rig_ui.py` panel (IK/FK switch and snapping in the N-panel when the file is
opened in Blender). Arms are switched to FK and legs stay IK so clips key FK arm
rotations and IK foot targets. Every clip is an Action on its own NLA track and
is marked as an asset tagged with its reference category, so the Asset Browser
and the Action editor list them.
"""
import os

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

from .. import face_anims, rigify_anims
from ..core import Entity
from ..log import info, warn

NAMES = ["base_sample", "basemesh", "base_mesh"]
DEFAULT_FILE = os.path.join("base samples", "humans", "Rigged Low poly Male and Female Basemesh for Animation.blend")
BODIES = {"male": ("Male", "rig_male"), "female": ("Female", "rig")}
DEFAULT_ANIMS = ("idle", "walk", "run", "jump", "wave", "talk")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FACE_FILE = os.path.join(ROOT, "forge", "assets", "face", "ict_face.blend")
HEAD = "DEF-spine.006"
FK_NECK = 0.25        # FaceKit units below its crown where the neck is cut (above the shoulder flare)
FK_SKULL = 0.18       # crown to just under the jaw: the part measured against the body's head


def _find(path, ctx):
    for base in (ctx.base_dir, ROOT, os.getcwd()):
        p = os.path.join(base, path)
        if os.path.isfile(p):
            return p
    return None


def _append(path, mesh_name, rig_name):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        missing = [n for n in (mesh_name, rig_name) if n not in src.objects]
        if missing:
            raise RuntimeError("%s has no object(s) %s (objects: %s)"
                               % (os.path.basename(path), ", ".join(missing), ", ".join(src.objects)))
        dst.objects = [mesh_name, rig_name]
        dst.texts = [t for t in src.texts if t.startswith("rig_ui")]
    return dst.objects[0], dst.objects[1], list(dst.texts)


def _body_points(mesh):
    """World points of the evaluated body, each with its head-bone weight."""
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    g = mesh.vertex_groups.get(HEAD)
    gi = g.index if g else -1
    return [(ev.matrix_world @ v.co, max((e.weight for e in v.groups if e.group == gi), default=0.0))
            for v in ev.data.vertices]


def _extent(pts, cx):
    return max(abs(p.x - cx) for p in pts), min(p.y for p in pts), max(p.y for p in pts)


def _attach_face(rig, mesh, name, ctx):
    """Swap the sample's head for the bundled ICT-FaceKit head: the body head is
    hidden by a Mask modifier, the FaceKit head is fitted to its width, depth and
    crown, its neck is cut above the shoulder flare and tapered into the body's
    neck, and it is skinned to the neck/head bones. Expressions, gaze and lip-sync
    are its ARKit shape keys (forge/face_anims.py)."""
    with bpy.data.libraries.load(FACE_FILE, link=False) as (src, dst):
        dst.objects = ["ICTFace"]
        dst.texts = [t for t in src.texts if "LICENSE" in t]
    head = dst.objects[0]
    ctx.collection.objects.link(head)
    head.name = name + "_Head"
    me = head.data

    body = _body_points(mesh)
    cx = mesh.matrix_world.translation.x       # the body mirrors about its own origin
    top_b = max(p.z for p, _ in body)
    hw_b, y0_b, y1_b = _extent([p for p, w in body if w > 0.5], cx)
    skin = {i for i, m in enumerate(me.materials) if m.name.startswith(("FK_Face", "FK_BackHead"))}
    skin_v = {v for p in me.polygons if p.material_index in skin for v in p.vertices}
    top_f = max(me.vertices[v].co.z for v in skin_v)
    hw_f, y0_f, y1_f = _extent([me.vertices[v].co for v in skin_v if me.vertices[v].co.z > top_f - FK_SKULL], 0.0)
    s = 0.5 * (hw_b / hw_f + (y1_b - y0_b) / (y1_f - y0_f))
    off = Vector((cx, 0.5 * (y0_b + y1_b) - s * 0.5 * (y0_f + y1_f), top_b - s * top_f))
    me.transform(Matrix.Translation(off) @ Matrix.Scale(s, 4), shape_keys=True)

    # cut the neck, then taper its last stretch into the body's neck
    cut = top_b - s * FK_NECK
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < cut], context="VERTS")
    bm.to_mesh(me)
    bm.free()
    kb = me.shape_keys.key_blocks
    ring = [v.co for v in me.vertices if abs(v.co.z - cut) < 0.01 * s]
    hw_nf, yn0, yn1 = _extent(ring, cx)
    near = [p for p, _ in body if abs(p.z - cut) < 0.012 and abs(p.x - cx) < 1.6 * hw_nf]
    if near:
        hw_nb, b0, b1 = _extent(near, cx)
        k = (hw_nb + 0.003) / hw_nf
        yc_f, yc_b = 0.5 * (yn0 + yn1), 0.5 * (b0 + b1)
        span = 0.08 * s
        for v in me.vertices:
            u = 1.0 - (v.co.z - cut) / span
            if u <= 0.0:
                continue
            u = u * u * (3 - 2 * u) if u < 1.0 else 1.0
            f = 1.0 + (k - 1.0) * u
            new = Vector((cx + (v.co.x - cx) * f, yc_f + (v.co.y - yc_f) * f + u * (yc_b - yc_f), v.co.z))
            d = new - v.co
            for key in kb:
                key.data[v.index].co += d
            v.co = new

    # then snap the last few cm onto the body's neck surface (sideways only), 2 mm proud
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    tmp = ev.to_mesh()
    tree = BVHTree.FromPolygons([ev.matrix_world @ v.co for v in tmp.vertices], [p.vertices[:] for p in tmp.polygons])
    ev.to_mesh_clear()
    span = 0.035 * s
    for v in me.vertices:
        u = 1.0 - (v.co.z - cut) / span
        if u <= 0.0:
            continue
        u = u * u * (3 - 2 * u) if u < 1.0 else 1.0
        loc, nrm, _, _ = tree.find_nearest(v.co)
        if loc is None:
            continue
        d = (loc + nrm * 0.002 - v.co) * u
        d.z = 0.0
        for key in kb:
            key.data[v.index].co += d
        v.co += d

    # skin: the head bone above its root; below, the body's own weights from the
    # nearest body vertex (so both necks bend alike), blended over 3 cm
    bones = rig.data.bones
    top_neck = (rig.matrix_world @ bones[HEAD].head_local).z
    ev = mesh.evaluated_get(bpy.context.evaluated_depsgraph_get())
    tmp = ev.to_mesh()
    names = {g.index: g.name for g in mesh.vertex_groups}
    kd = KDTree(len(tmp.vertices))
    for v in tmp.vertices:
        kd.insert(ev.matrix_world @ v.co, v.index)
    kd.balance()
    near_w = {}
    blend = 0.03
    for v in me.vertices:
        u = max(0.0, min(1.0, (top_neck - v.co.z) / blend))       # 1 = fully body weights
        w = {HEAD: 1.0 - u}
        if u > 0.0:
            _, i, _ = kd.find(v.co)
            src = [(names[e.group], e.weight) for e in tmp.vertices[i].groups
                   if e.group in names and names[e.group].startswith("DEF-") and e.weight > 1e-3]
            tot = sum(x for _, x in src) or 1.0
            for n, x in src:
                w[n] = w.get(n, 0.0) + u * x / tot
        for n, x in w.items():
            if x > 1e-4:
                near_w.setdefault(n, []).append((v.index, x))
    ev.to_mesh_clear()
    for n, items in sorted(near_w.items()):
        g = head.vertex_groups.new(name=n)
        by_w = {}
        for i, x in items:
            by_w.setdefault(round(x, 4), []).append(i)
        for x, idx in sorted(by_w.items()):
            g.add(idx, x, "REPLACE")
    mw = head.matrix_world.copy()
    head.parent = rig
    head.matrix_world = mw
    head.modifiers.new("Armature", "ARMATURE").object = rig

    mask = mesh.modifiers.new("HideHead", "MASK")
    mask.vertex_group, mask.threshold, mask.invert_vertex_group = HEAD, 0.5, True
    mirror = next((i for i, m in enumerate(mesh.modifiers) if m.type == "MIRROR"), -1)
    try:
        mesh.modifiers.move(len(mesh.modifiers) - 1, mirror + 1)
    except Exception:
        with bpy.context.temp_override(object=mesh):
            bpy.ops.object.modifier_move_to_index(modifier=mask.name, index=mirror + 1)

    col = next((n.inputs["Base Color"].default_value[:] for sl in mesh.material_slots if sl.material
                and sl.material.use_nodes for n in sl.material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    for m in me.materials:
        if col and m.name.startswith(("FK_Face", "FK_BackHead")):
            next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED").inputs["Base Color"].default_value = col
            m.diffuse_color = col
    info("base_sample: ICT-FaceKit head fitted (scale %.3f, neck cut at %.3f m, %d shape keys)"
         % (s, cut, len(kb) - 1))
    return head


def build(spec, ctx, type_name):
    rel = spec.get("file") or DEFAULT_FILE
    path = _find(rel, ctx)
    if path is None:
        raise RuntimeError("base sample file not found: %s" % rel)
    body = spec.choice("body", BODIES, "male")
    mesh, rig, texts = _append(path, *BODIES[body])
    for obj in (rig, mesh):
        ctx.collection.objects.link(obj)
    rig.name = spec.name + "_Rig"
    mesh.name = spec.name
    rig.location = (0.0, 0.0, 0.0)          # the sample sits off-centre beside its partner
    rig.show_in_front = True
    for t in texts:                         # Rigify panel registers when the file opens
        t.use_module = True

    # the sample is saved mid-pose (male: torso dropped 0.36 m, fingers in
    # a fist; female: feet IK raised 0.35 m):
    # clear it before measuring
    for pb in rig.pose.bones:
        if not pb.name.startswith(("ORG-", "MCH-", "DEF-")):
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pb.rotation_euler = (0.0, 0.0, 0.0)
            pb.scale = (1.0, 1.0, 1.0)

    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh.evaluated_get(deps)
    zs = [(ev.matrix_world @ v.co).z for v in ev.data.vertices]
    height = (max(zs) - min(zs)) if zs else 0.0
    native = height                         # rig units: clip offsets scale with it
    if zs:                                  # stand on z = 0 (the sample sits ~1 cm below)
        rig.location.z = -min(zs)
    head = None
    if spec.choice("face", {"ict": 1, "none": 0}, "ict" if os.path.isfile(FACE_FILE) else "none") == "ict":
        head = _attach_face(rig, mesh, spec.name, ctx)
    want = spec.num("height", 0.0, 0.0, 10.0)
    if want and height > 1e-6:
        rig.scale = (want / height,) * 3
        rig.location.z *= want / height
        height = want

    if not mesh.material_slots or all(s.material is None for s in mesh.material_slots):
        mesh.data.materials.clear()
        mesh.data.materials.append(ctx.mat("Skin", "skin", spec.color("color", "#c8a088")))

    # arms FK (clips key rotations), legs IK (feet stay planted)
    for side in ("L", "R"):
        for ctrl, value in (("upper_arm_parent", 1.0), ("thigh_parent", 0.0)):
            pb = rig.pose.bones.get("%s.%s" % (ctrl, side))
            if pb is not None and "IK_FK" in pb.keys():
                pb["IK_FK"] = value

    names = spec.items("animation") + spec.items("animations")
    face_clips = face_anims.resolve(names or DEFAULT_ANIMS) if head else []
    body_names = [n for n in names if rigify_anims._norm(n) not in face_anims.CLIPS
                  or rigify_anims._norm(n) in rigify_anims.CLIPS]
    clips = rigify_anims.resolve(body_names) if names else rigify_anims.resolve(DEFAULT_ANIMS)
    speed = spec.num("speed", 1.0, 0.05, 20)
    hidden = [o for o in (mesh, head) if o is not None]
    mods = [m for o in hidden for m in o.modifiers if m.show_viewport]
    for o in hidden:                        # bake evaluates the rig per frame; skip the meshes
        o.hide_viewport = True
    for m in mods:
        m.show_viewport = False
    try:
        baked = rigify_anims.bake(rig, spec.name, clips, ctx.fps, ctx.frame_start, speed, native)
    finally:
        for o in hidden:
            o.hide_viewport = False
        for m in mods:
            m.show_viewport = True
    if head is not None:
        baked += face_anims.bake(head, spec.name, face_clips, ctx.fps, ctx.frame_start, speed,
                                 spec.get("say") or None)
    for name, action, cat in baked:
        try:
            action.asset_mark()
            action.asset_data.tags.new(cat)
            action.asset_data.description = "%s (%s)" % (name.replace("_", " "), cat)
        except Exception as exc:            # asset API missing: the NLA tracks still hold them
            warn("could not mark action %s as asset: %s" % (action.name, exc))
            break
    cats = sorted({c for _, _, c in baked})
    info("base_sample: %s from %s, %.2f m, %d bones, %d clips (%s)"
         % (body, os.path.basename(path), height, len(rig.data.bones), len(baked), ", ".join(cats)))
    return Entity(spec.name, rig, [rig, mesh] + ([head] if head else []), armature=rig, static=False)
