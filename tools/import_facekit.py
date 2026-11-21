"""One-time converter: ICT-FaceKit OBJs -> forge/assets/face/ict_face.blend.

    $BL --background --python tools/import_facekit.py -- [third_party/ICT-FaceKit] [out.blend]

Reads FaceXModel/generic_neutral_mesh.obj and every expression OBJ (same topology)
with a plain-text parser (no numpy/openmesh), converts to Blender axes and metres
(OBJ is Y-up, faces +Z, centimetres; Blender faces -Y, Z-up), drops the eye overlay
sub-meshes that need Unreal-style shading, and saves one mesh object `ICTFace` with
a shape key per expression (ARKit names, _L/_R = the face's own left/right, which
is +X here as in the rest of the project). The build only ever reads the saved
.blend, so the project needs neither the download nor network access.
ICT-FaceKit is MIT licensed (c) 2020 USC Institute for Creative Technologies; the
LICENSE is copied next to the asset and into the .blend as a text block.
"""
import math
import os
import shutil
import sys

import bpy
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DROP = {"M_LacrimalFluid", "M_EyeBlend", "M_EyeOcclusion"}     # overlay shells
# eyeball turn added to FaceKit's eyeLook shapes, which only move the lids (ARKit
# full weight ~ the extreme of comfortable gaze; approximation)
EYE_TURN = {"Up": ("X", -25.0), "Down": ("X", 30.0), "In": ("Z", 30.0), "Out": ("Z", 30.0)}
COLORS = {                                   # placeholder shading; skin is recoloured at build
    "M_Face": (0.78, 0.6, 0.5), "M_BackHead": (0.78, 0.6, 0.5),
    "M_GumsTongue": (0.62, 0.25, 0.27), "M_Teeth": (0.88, 0.85, 0.78),
    "M_ScleraLeft": (0.9, 0.88, 0.85), "M_ScleraRight": (0.9, 0.88, 0.85),
    "M_IrisLeft": (0.18, 0.11, 0.06), "M_IrisRight": (0.18, 0.11, 0.06),
    "M_EyeLashes": (0.03, 0.02, 0.02),
}


def _vec(line):
    _, x, y, z = line.split()[:4]
    return (float(x) * 0.01, -float(z) * 0.01, float(y) * 0.01)


def read_positions(path):
    with open(path, encoding="utf-8") as fh:
        return [_vec(l) for l in fh if l.startswith("v ")]


def read_neutral(path):
    verts, uvs, faces, mats, mat = [], [], [], [], None
    with open(path, encoding="utf-8") as fh:
        for l in fh:
            if l.startswith("v "):
                verts.append(_vec(l))
            elif l.startswith("vt "):
                p = l.split()
                uvs.append((float(p[1]), float(p[2])))
            elif l.startswith("usemtl"):
                mat = l.split()[1]
            elif l.startswith("f ") and mat not in DROP:
                corners = [c.split("/") for c in l.split()[1:]]
                faces.append([(int(c[0]) - 1, int(c[1]) - 1 if len(c) > 1 and c[1] else -1) for c in corners])
                mats.append(mat)
    return verts, uvs, faces, mats


def sphere_center(pts):
    """Least-squares sphere fit (normal equations, Gaussian elimination)."""
    rows = [(2 * p.x, 2 * p.y, 2 * p.z, 1.0, p.dot(p)) for p in pts]
    a = [[sum(r[i] * r[j] for r in rows) for j in range(4)] + [sum(r[i] * r[4] for r in rows)] for i in range(4)]
    for c in range(4):
        piv = max(range(c, 4), key=lambda r: abs(a[r][c]))
        a[c], a[piv] = a[piv], a[c]
        for r in range(4):
            if r != c:
                f = a[r][c] / a[c][c]
                a[r] = [x - f * y for x, y in zip(a[r], a[c])]
    return Vector([a[i][4] / a[i][i] for i in range(3)])


def turn_eyes(ob, names):
    """Rotate each eyeball (sclera + iris) inside its eyeLook shapes."""
    me, kb = ob.data, ob.data.shape_keys.key_blocks
    for side, sx in (("Left", 1.0), ("Right", -1.0)):
        ball = {v for p in me.polygons if me.materials[p.material_index].name in
                ("FK_Sclera" + side, "FK_Iris" + side) for v in p.vertices}
        sclera = [me.vertices[v].co.copy() for p in me.polygons
                  if me.materials[p.material_index].name == "FK_Sclera" + side for v in p.vertices]
        c = sphere_center(sclera)
        for d, (axis, deg) in EYE_TURN.items():
            n = "eyeLook%s_%s" % (d, side[0])
            if n not in kb:
                continue
            if axis == "Z":            # in = toward the nose: -X for the left eye
                deg *= (-sx if d == "In" else sx)
            m = Matrix.Translation(c) @ Matrix.Rotation(math.radians(deg), 4, axis) @ Matrix.Translation(-c)
            for v in ball:
                kb[n].data[v].co = m @ kb["Basis"].data[v].co
        names.append("eye %s centre %s" % (side, tuple(round(x, 4) for x in c)))


def main(src, out):
    fx = os.path.join(src, "FaceXModel")
    verts, uvs, faces, mats = read_neutral(os.path.join(fx, "generic_neutral_mesh.obj"))
    used = sorted({v for f in faces for v, _ in f})
    remap = {v: i for i, v in enumerate(used)}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    me = bpy.data.meshes.new("ICTFace")
    me.from_pydata([verts[v] for v in used], [], [[remap[v] for v, _ in f] for f in faces])
    names = list(dict.fromkeys(mats))
    for n in names:
        m = bpy.data.materials.new(n.replace("M_", "FK_"))
        m.use_nodes = True
        bsdf = next(nd for nd in m.node_tree.nodes if nd.type == "BSDF_PRINCIPLED")
        bsdf.inputs["Base Color"].default_value = COLORS.get(n, (0.5, 0.5, 0.5)) + (1.0,)
        bsdf.inputs["Roughness"].default_value = 0.25 if "Sclera" in n or "Iris" in n or "Teeth" in n else 0.55
        m.diffuse_color = COLORS.get(n, (0.5, 0.5, 0.5)) + (1.0,)
        me.materials.append(m)
    idx = {n: i for i, n in enumerate(names)}
    me.polygons.foreach_set("material_index", [idx[m] for m in mats])
    uv = me.uv_layers.new(name="UVMap")
    flat = [c for f in faces for _, t in f for c in (uvs[t] if t >= 0 else (0.0, 0.0))]
    uv.data.foreach_set("uv", flat)
    me.shade_smooth()

    ob = bpy.data.objects.new("ICTFace", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.shape_key_add(name="Basis", from_mix=False)
    exprs = sorted(f[:-4] for f in os.listdir(fx)
                   if f.endswith(".obj") and not f.startswith(("identity", "generic_neutral")))
    for name in exprs:
        pos = read_positions(os.path.join(fx, name + ".obj"))
        if len(pos) != len(verts):
            print("FACEKIT skip %s: %d verts, neutral has %d" % (name, len(pos), len(verts)))
            continue
        kb = ob.shape_key_add(name=name, from_mix=False)
        kb.data.foreach_set("co", [c for v in used for c in pos[v]])
        kb.slider_max = 1.0
    me.shape_keys.use_relative = True
    notes = []
    turn_eyes(ob, notes)
    print("FACEKIT", "; ".join(notes))

    lic = os.path.join(src, "LICENSE")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.isfile(lic):
        shutil.copyfile(lic, os.path.join(os.path.dirname(out), "ICT-FaceKit-LICENSE.txt"))
        t = bpy.data.texts.new("ICT-FaceKit-LICENSE.txt")
        with open(lic, encoding="utf-8") as fh:
            t.write(fh.read())
        t.use_fake_user = True
    ob["source"] = "ICT-FaceKit (MIT, USC ICT), generic_neutral_mesh + %d expressions" % (len(me.shape_keys.key_blocks) - 1)
    bpy.ops.wm.save_as_mainfile(filepath=out, compress=True)
    print("FACEKIT %s: %d verts, %d faces, %d shape keys, %.1f MB"
          % (out, len(me.vertices), len(me.polygons), len(me.shape_keys.key_blocks) - 1,
             os.path.getsize(out) / 2 ** 20))


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    main(os.path.abspath(argv[0] if argv else os.path.join(ROOT, "third_party", "ICT-FaceKit")),
         os.path.abspath(argv[1] if len(argv) > 1 else os.path.join(ROOT, "forge", "assets", "face", "ict_face.blend")))
