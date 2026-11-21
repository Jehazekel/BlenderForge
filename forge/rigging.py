"""Armature construction, automatic skinning and shape keys."""

import bmesh
import bpy
from mathutils import Matrix, Vector

from .log import info, warn


class Rig:
    """Bone list that becomes an armature. `meta` feeds the animation library."""

    def __init__(self, name, kind):
        self.name = name
        self.kind = kind
        self.bones = []         # dicts in creation order (parents first)
        self.iks = []
        self.copies = []
        self.meta = {}

    def bone(self, name, head, tail, parent=None, connect=False, deform=True):
        head, tail = Vector(head), Vector(tail)
        if (tail - head).length < 1e-4:
            tail = head + Vector((0, 0, 0.01))
        self.bones.append(dict(name=name, head=head, tail=tail, parent=parent,
                               connect=connect, deform=deform))
        return name

    def chain(self, prefix, points, parent=None, deform=True):
        names = []
        for i in range(len(points) - 1):
            n = "%s%d" % (prefix, i + 1)
            self.bone(n, points[i], points[i + 1], parent, connect=i > 0, deform=deform)
            parent = n
            names.append(n)
        return names

    def ik(self, bone, target, chain=2, influence=1.0):
        self.iks.append((bone, target, chain, influence))

    def copy_rotation(self, bone, target):
        self.copies.append((bone, target))

    def has(self, name):
        return any(b["name"] == name for b in self.bones)

    def build(self, collection):
        arm = bpy.data.armatures.new(self.name + "_Rig")
        obj = bpy.data.objects.new(self.name + "_Rig", arm)
        collection.objects.link(obj)
        _activate(obj)
        bpy.ops.object.mode_set(mode="EDIT")
        for b in self.bones:
            eb = arm.edit_bones.new(b["name"])
            eb.head, eb.tail = b["head"], b["tail"]
            eb.use_deform = b["deform"]
            if b["parent"]:
                eb.parent = arm.edit_bones[b["parent"]]
                eb.use_connect = bool(b["connect"]) and (eb.parent.tail - eb.head).length < 1e-4
        bpy.ops.object.mode_set(mode="OBJECT")
        for bone, target, chain, influence in self.iks:
            con = obj.pose.bones[bone].constraints.new("IK")
            con.target = obj
            con.subtarget = target
            con.chain_count = chain
            con.influence = influence
        for bone, target in self.copies:
            con = obj.pose.bones[bone].constraints.new("COPY_ROTATION")
            con.target = obj
            con.subtarget = target
        arm.display_type = "OCTAHEDRAL"
        obj.show_in_front = True
        return obj


def _activate(obj, others=()):
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    for o in others:
        o.select_set(True)
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj


def _segment_distance(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
    return (p - (a + ab * t)).length


def _deform_bones(arm_obj):
    return [(b.name, b.head_local.copy(), b.tail_local.copy())
            for b in arm_obj.data.bones if b.use_deform]


def _nearest_weights(p, bones):
    d = sorted((max(_segment_distance(p, h, t), 1e-5), name) for name, h, t in bones)
    if len(d) == 1 or d[1][0] > d[0][0] * 1.8:
        return [(d[0][1], 1.0)]
    w0, w1 = 1.0 / d[0][0] ** 2, 1.0 / d[1][0] ** 2
    return [(d[0][1], w0 / (w0 + w1)), (d[1][1], w1 / (w0 + w1))]


def skin_auto(mesh_obj, arm_obj, preserve_volume=False):
    """Automatic (bone heat) weights, with a distance-based safety net.

    `preserve_volume` turns on dual-quaternion blending, which stops joints
    collapsing in Blender. Exported files (glb, fbx) always blend linearly."""
    _activate(arm_obj, [mesh_obj])
    try:
        bpy.ops.object.parent_set(type="ARMATURE_AUTO")
    except RuntimeError as exc:
        warn("automatic weights failed (%s); using distance weights" % str(exc).strip())
    if mesh_obj.parent is not arm_obj:
        mesh_obj.parent = arm_obj
    if not any(m.type == "ARMATURE" for m in mesh_obj.modifiers):
        mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
        mod.object = arm_obj
    for mod in mesh_obj.modifiers:
        if mod.type == "ARMATURE":
            mod.use_deform_preserve_volume = preserve_volume

    bones = _deform_bones(arm_obj)
    for name, _, _ in bones:
        if name not in mesh_obj.vertex_groups:
            mesh_obj.vertex_groups.new(name=name)
    deform_idx = {mesh_obj.vertex_groups[name].index for name, _, _ in bones}
    fixed = 0
    for v in mesh_obj.data.vertices:
        total = sum(g.weight for g in v.groups if g.group in deform_idx)
        if total < 1e-4:
            for name, w in _nearest_weights(v.co, bones):
                mesh_obj.vertex_groups[name].add([v.index], w, "REPLACE")
            fixed += 1
    if fixed == len(mesh_obj.data.vertices):
        info("bone heat found no solution for '%s'; used distance weights" % mesh_obj.name)
    elif fixed:
        info("filled %d unweighted vertices on '%s'" % (fixed, mesh_obj.name))


ROOT_FADE = {"h_femur": "up", "f_humerus": "up", "tail1": "back"}
MID_FADE = 2.0   # limb weight reaches 0 this many joint-widths inside the joint (1.0 = at the midline)


def fade_roots(mesh_obj, arm_obj, band_frac=0.6):
    """Keep upper-limb and tail-base weights off the trunk around them.

    Bone heat on short, thick trunks (toy animals) lets `h_femur`/`f_humerus`
    reach the back above the joint and `tail1` reach the rump in front of its base,
    so a leg swing or tail flick tears the rump; they also reach the groin and
    chest web between the legs. A vertex above the limb joint
    (or in front of the tail base, along the bone) keeps that weight scaled by
    max(0, 1 - d / band), band = band_frac * bone length, and a limb weight inside
    the joint fades linearly to 0 at MID_FADE joint-widths in; what is lost goes to the
    bone's parent. Uses only z and the bone axis, so left and right stay mirrored."""
    groups = mesh_obj.vertex_groups
    rules = []
    for b in arm_obj.data.bones:
        kind = ROOT_FADE.get(b.name.split(".")[0])
        if kind and b.name in groups and b.parent and b.parent.name in groups:
            band = max(band_frac * b.length, 1e-4)
            axis = (b.tail_local - b.head_local).normalized()
            rules.append((groups[b.name].index, groups[b.parent.name].index, kind, b.head_local.copy(), axis, band))
    if not rules:
        return
    for v in mesh_obj.data.vertices:
        w = {g.group: g.weight for g in v.groups}
        changed = False
        for gi, pi, kind, head, axis, band in rules:
            if gi not in w:
                continue
            d = v.co.z - head.z if kind == "up" else -(v.co - head).dot(axis)
            f = max(0.0, 1.0 - d / band) if d > 0 else 1.0
            if kind == "up" and abs(head.x) > 1e-4:          # groin / chest web between the legs
                inward = abs(head.x) - v.co.x * (1.0 if head.x > 0 else -1.0)
                if inward > 0:
                    f *= max(0.0, 1.0 - inward / (MID_FADE * abs(head.x)))
            if f >= 1.0:
                continue
            keep = w[gi] * f
            w[pi] = w.get(pi, 0.0) + w[gi] - keep
            w[gi] = keep
            changed = True
        if not changed:
            continue
        total = sum(w.values())
        for gi, x in w.items():
            if x <= 1e-6:
                groups[gi].remove([v.index])
            else:
                groups[gi].add([v.index], x / total, "REPLACE")


def split_sides(mesh_obj, band_frac=0.1):
    """Keep left bones off the right side and right bones off the left.

    Bone heat and smoothing let weights cross the midline when two limbs sit
    close together (short, thick legs), so moving one leg drags the other.
    A vertex at x on the far side keeps a `.L`/`.R` weight scaled by
    max(0, 1 - |x| / band), band = band_frac * mesh half-width, so the midline
    itself stays smooth. Left is +X. Mirrored input gives mirrored output."""
    verts = mesh_obj.data.vertices
    half = max((abs(v.co.x) for v in verts), default=0.0)
    if half < 1e-6:
        return
    band = band_frac * half
    side = {}
    for vg in mesh_obj.vertex_groups:
        if vg.name.endswith(".L"):
            side[vg.index] = 1.0
        elif vg.name.endswith(".R"):
            side[vg.index] = -1.0
    if not side:
        return
    groups = mesh_obj.vertex_groups
    for v in verts:
        own = [(g.group, g.weight) for g in v.groups]
        new = []
        for gi, w in own:
            sg = side.get(gi)
            if sg is not None and v.co.x * sg < 0:
                w *= max(0.0, 1.0 - abs(v.co.x) / band)
            new.append((gi, w))
        total = sum(w for _, w in new)
        if total < 1e-6 or all(abs(a[1] - b[1]) < 1e-9 for a, b in zip(own, new)):
            continue
        for gi, w in new:
            if w <= 1e-6:
                groups[gi].remove([v.index])
            else:
                groups[gi].add([v.index], w / total, "REPLACE")


def smooth_weights(mesh_obj, passes, factor=0.5):
    """Blend each vertex's weights with its neighbours'. Bone heat on a coarse
    cage changes bone too abruptly across a joint; this widens the transition."""
    if passes <= 0:
        return
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    layer = bm.verts.layers.deform.verify()
    for _ in range(passes):
        old = [dict(v[layer].items()) for v in bm.verts]
        for v in bm.verts:
            near = sorted(e.other_vert(v).index for e in v.link_edges)
            if not near:
                continue
            mix = {g: w * (1.0 - factor) for g, w in old[v.index].items()}
            for i in near:
                for g, w in old[i].items():
                    mix[g] = mix.get(g, 0.0) + w * factor / len(near)
            v[layer].clear()
            for g in sorted(mix):
                v[layer][g] = mix[g]
    bm.to_mesh(mesh_obj.data)
    bm.free()


def skin_rigid(mesh_obj, arm_obj, rigid, default_bone):
    """Hard-surface skinning: every vertex follows exactly one bone."""
    mesh_obj.parent = arm_obj
    mod = mesh_obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm_obj
    taken = set()
    for bone, idx in rigid.items():
        vg = mesh_obj.vertex_groups.new(name=bone)
        vg.add(list(idx), 1.0, "REPLACE")
        taken.update(idx)
    rest = [v.index for v in mesh_obj.data.vertices if v.index not in taken]
    if rest:
        vg = mesh_obj.vertex_groups.get(default_bone) or mesh_obj.vertex_groups.new(name=default_bone)
        vg.add(rest, 1.0, "REPLACE")


def merge_rigid(mesh_obj, arm_obj, extras, default_bone):
    """Append a second builder (eyes, hair, armour plates) to a skinned mesh.

    Those parts are added after bone-heat weighting so loose shells can never
    upset the solver; each one is bound 100% to its bone. Returns the index
    offset of the appended vertices.
    """
    offset = len(mesh_obj.data.vertices)
    if extras is None or extras.count == 0:
        return offset
    extra_mesh = extras.to_mesh(mesh_obj.name + "_extras")
    for bone in list(extras.rigid) + [default_bone]:
        if bone not in mesh_obj.vertex_groups:
            mesh_obj.vertex_groups.new(name=bone)
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    bm.from_mesh(extra_mesh)
    bm.verts.ensure_lookup_table()
    layer = bm.verts.layers.deform.verify()
    done = set()
    for bone, idx in extras.rigid.items():
        gi = mesh_obj.vertex_groups[bone].index
        for i in idx:
            v = bm.verts[offset + i]
            v[layer].clear()
            v[layer][gi] = 1.0
            done.add(i)
    gi = mesh_obj.vertex_groups[default_bone].index
    for i in range(extras.count):
        if i not in done:
            bm.verts[offset + i][layer][gi] = 1.0
    bm.to_mesh(mesh_obj.data)
    bm.free()
    bpy.data.meshes.remove(extra_mesh)
    me = mesh_obj.data
    for mat in extras.palette.mats[len(me.materials):]:
        me.materials.append(mat)
    return offset


def clean_weights(mesh_obj, limit=4):
    """Game-ready weights: at most `limit` bones per vertex, summing to 1.

    Bone heat can return weights a hair above 1.0 and more than four
    influences; engines and exporters want neither.
    """
    bm = bmesh.new()
    bm.from_mesh(mesh_obj.data)
    layer = bm.verts.layers.deform.verify()
    for v in bm.verts:
        items = sorted(v[layer].items(), key=lambda kv: (-kv[1], kv[0]))
        keep = [(g, w) for g, w in items[:limit] if w > 1e-4]
        total = sum(w for _, w in keep)
        v[layer].clear()
        for g, w in keep:
            v[layer][g] = w / total
    bm.to_mesh(mesh_obj.data)
    bm.free()


def parent_to_bone(obj, arm_obj, bone_name):
    """Attach an accessory object to a bone, keeping its modelled position."""
    bone = arm_obj.data.bones.get(bone_name)
    if bone is None:
        obj.parent = arm_obj
        return
    obj.parent = arm_obj
    obj.parent_type = "BONE"
    obj.parent_bone = bone_name
    obj.matrix_parent_inverse = (bone.matrix_local @ Matrix.Translation((0, bone.length, 0))).inverted()


def add_shape_keys(obj, deltas):
    """deltas: {key name: {vertex index: Vector offset}}. Adds a Basis first."""
    if not deltas:
        return
    obj.shape_key_add(name="Basis")
    base = [v.co.copy() for v in obj.data.vertices]
    for name, moves in deltas.items():
        sk = obj.shape_key_add(name=name)
        for i, d in moves.items():
            if 0 <= i < len(base):
                sk.data[i].co = base[i] + d
        sk.value = 0.0
