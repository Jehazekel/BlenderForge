"""Procedural Principled materials: flat colours plus noise-based surfaces.

Every material stores its recipe in custom properties so `# edit:` sections can
recolour it later by rebuilding the node tree.
"""

import warnings

import bpy

KINDS = ("plain", "skin", "cloth", "stone", "brick", "wood", "fur", "metal", "foliage",
         "water", "glass", "emissive", "ground", "vertex", "scales", "roof", "leather")


def _tree(mat):
    if mat.node_tree is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    return nt


def _set(node, name, value):
    sock = node.inputs.get(name)
    if sock is not None:
        try:
            sock.default_value = value
        except (TypeError, ValueError):
            pass


def _shade(color, k):
    return (min(1.0, color[0] * k), min(1.0, color[1] * k), min(1.0, color[2] * k), 1.0)


def _out(node, *names):
    for n in names:
        if n in node.outputs:
            return node.outputs[n]
    return node.outputs[0]


def _noise_color(nt, bsdf, coords, color, scale, stretch=(1, 1, 1), dark=0.6, light=1.15,
                 detail=5.0, bump=0.3, rough_var=0.0, roughness=0.7):
    """Noise -> two-tone colour ramp -> base colour, plus a matching bump."""
    nodes, links = nt.nodes, nt.links
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (scale * stretch[0], scale * stretch[1], scale * stretch[2])
    links.new(coords, mapping.inputs["Vector"])
    noise = nodes.new("ShaderNodeTexNoise")
    _set(noise, "Scale", 1.0)
    _set(noise, "Detail", detail)
    _set(noise, "Roughness", 0.6)
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    fac = _out(noise, "Factor", "Fac")
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.3
    ramp.color_ramp.elements[0].color = _shade(color, dark)
    ramp.color_ramp.elements[1].position = 0.7
    ramp.color_ramp.elements[1].color = _shade(color, light)
    links.new(fac, ramp.inputs[0])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    if bump > 0:
        bn = nodes.new("ShaderNodeBump")
        _set(bn, "Strength", bump)
        _set(bn, "Distance", 0.05)
        links.new(fac, bn.inputs["Height"])
        links.new(bn.outputs["Normal"], bsdf.inputs["Normal"])
    if rough_var > 0:
        mr = nodes.new("ShaderNodeMapRange")
        _set(mr, "To Min", max(0.0, roughness - rough_var))
        _set(mr, "To Max", min(1.0, roughness + rough_var))
        links.new(fac, mr.inputs[0])
        links.new(mr.outputs[0], bsdf.inputs["Roughness"])
    return fac


def _block_coords(nt, coords, cylindrical, radius):
    """2D wall coordinates: (x + y, z) for boxes, (angle * radius, z) for towers."""
    nodes, links = nt.nodes, nt.links
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(coords, sep.inputs[0])
    op = nodes.new("ShaderNodeMath")
    if cylindrical:
        op.operation = "ARCTAN2"
        links.new(sep.outputs[1], op.inputs[0])
        links.new(sep.outputs[0], op.inputs[1])
        mul = nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = radius
        links.new(op.outputs[0], mul.inputs[0])
        u = mul.outputs[0]
    else:
        op.operation = "ADD"
        links.new(sep.outputs[0], op.inputs[0])
        links.new(sep.outputs[1], op.inputs[1])
        u = op.outputs[0]
    comb = nodes.new("ShaderNodeCombineXYZ")
    links.new(u, comb.inputs[0])
    links.new(sep.outputs[2], comb.inputs[1])
    return comb.outputs[0]


def _blocks(nt, bsdf, coords, color, opts, brick):
    nodes, links = nt.nodes, nt.links
    vec = _block_coords(nt, coords, opts.get("cylindrical", False), opts.get("radius", 1.0))
    try:
        tex = nodes.new("ShaderNodeTexBrick")
    except RuntimeError:
        _noise_color(nt, bsdf, coords, color, 3.0)
        return
    links.new(vec, tex.inputs["Vector"])
    size = opts.get("block", 0.25 if brick else 0.55)
    _set(tex, "Scale", 1.0)
    _set(tex, "Brick Width", size * (2.2 if brick else 1.8))
    _set(tex, "Row Height", size)
    _set(tex, "Mortar Size", size * 0.06)
    _set(tex, "Mortar Smooth", 0.2)
    _set(tex, "Color1", _shade(color, 0.82))
    _set(tex, "Color2", _shade(color, 1.12))
    _set(tex, "Mortar", _shade(color, 0.45) if not brick else (0.55, 0.53, 0.5, 1.0))
    # break up the flat block colours with a little noise
    noise = nodes.new("ShaderNodeTexNoise")
    _set(noise, "Scale", 6.0)
    _set(noise, "Detail", 4.0)
    links.new(coords, noise.inputs["Vector"])
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 0.35
    links.new(_out(tex, "Color"), mix.inputs[6])
    links.new(_out(noise, "Color"), mix.inputs[7])
    links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    bump = nodes.new("ShaderNodeBump")
    _set(bump, "Strength", 0.5)
    _set(bump, "Distance", 0.03)
    links.new(_out(tex, "Factor", "Fac"), bump.inputs["Height"])
    bump.invert = True
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])


def apply(mat, kind, color, opts=None):
    """(Re)build the node tree of `mat` for a surface kind and colour."""
    opts = dict(opts or {})
    color = tuple(color[:3]) + (1.0,)
    nt = _tree(mat)
    nodes, links = nt.nodes, nt.links
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs[0], out.inputs["Surface"])
    _set(bsdf, "Base Color", color)
    tc = nodes.new("ShaderNodeTexCoord")
    # Generated coordinates stay glued to deforming (rigged) meshes.
    coords = tc.outputs["Generated" if opts.get("deform") else "Object"]
    k = opts.get("scale", 1.0)
    rough, metal = 0.6, 0.0

    if kind == "skin":
        rough = 0.55
        _set(bsdf, "Subsurface Weight", 0.08)
        _set(bsdf, "Subsurface Radius", (0.8, 0.3, 0.2))
        _set(bsdf, "Subsurface Scale", 0.02)
    elif kind == "cloth":
        rough = 0.85
        _noise_color(nt, bsdf, coords, color, 60.0 * k, dark=0.88, light=1.06, bump=0.08)
        _set(bsdf, "Sheen Weight", 0.08)
    elif kind == "leather":
        rough = 0.6
        _noise_color(nt, bsdf, coords, color, 30.0 * k, dark=0.75, light=1.1, bump=0.15)
    elif kind == "stone":
        rough = 0.9
        if opts.get("blocks", True):
            _blocks(nt, bsdf, coords, color, opts, brick=False)
        else:
            _noise_color(nt, bsdf, coords, color, 2.5 * k, dark=0.55, light=1.15, bump=0.5)
    elif kind == "brick":
        rough = 0.85
        _blocks(nt, bsdf, coords, color, opts, brick=True)
    elif kind == "wood":
        rough = 0.65
        axis = opts.get("grain", "z")
        stretch = {"x": (0.08, 1, 1), "y": (1, 0.08, 1), "z": (1, 1, 0.08)}[axis]
        _noise_color(nt, bsdf, coords, color, 14.0 * k, stretch, dark=0.6, light=1.15,
                     detail=6.0, bump=0.2)
    elif kind == "fur":
        rough = 0.95
        _noise_color(nt, bsdf, coords, color, 45.0 * k, (1, 0.35, 1), dark=0.6, light=1.05,
                     detail=8.0, bump=0.35)
        _set(bsdf, "Sheen Weight", 0.12)
        _set(bsdf, "Sheen Roughness", 0.6)
    elif kind == "scales":
        rough, metal = 0.3, 0.25
        _noise_color(nt, bsdf, coords, color, 28.0 * k, dark=0.7, light=1.2, bump=0.25)
    elif kind == "metal":
        rough, metal = opts.get("roughness", 0.32), 1.0
        _noise_color(nt, bsdf, coords, color, 9.0 * k, dark=0.82, light=1.08, bump=0.04,
                     rough_var=0.12, roughness=rough)
    elif kind == "foliage":
        rough = 0.8
        _noise_color(nt, bsdf, coords, color, 3.0 * k, dark=0.6, light=1.25, bump=0.0)
    elif kind == "ground":
        rough = 0.95
        _noise_color(nt, bsdf, coords, color, 1.2 * k, dark=0.7, light=1.2, bump=0.3)
    elif kind == "roof":
        rough = 0.75
        _noise_color(nt, bsdf, coords, color, 5.0 * k, (1, 1, 6), dark=0.7, light=1.12, bump=0.35)
    elif kind == "water":
        rough = 0.06
        _set(bsdf, "Alpha", 0.82)
        _set(bsdf, "Specular IOR Level", 0.8)
        _noise_color(nt, bsdf, coords, color, 0.8 * k, dark=0.85, light=1.1, detail=1.5, bump=0.12)
    elif kind == "glass":
        rough, metal = 0.08, 0.35
    elif kind == "emissive":
        _set(bsdf, "Emission Color", color)
        _set(bsdf, "Emission Strength", opts.get("strength", 4.0))
    elif kind == "vertex":
        rough = 0.92
        vc = nodes.new("ShaderNodeVertexColor")
        vc.layer_name = opts.get("layer", "Col")
        noise = nodes.new("ShaderNodeTexNoise")
        _set(noise, "Scale", 2.0 * k)
        _set(noise, "Detail", 6.0)
        links.new(coords, noise.inputs["Vector"])
        ramp = nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].color = (0.72, 0.72, 0.72, 1)
        ramp.color_ramp.elements[1].color = (1.15, 1.15, 1.15, 1)
        links.new(_out(noise, "Factor", "Fac"), ramp.inputs[0])
        mix = nodes.new("ShaderNodeMix")
        mix.data_type = "RGBA"
        mix.blend_type = "MULTIPLY"
        mix.inputs[0].default_value = 1.0
        links.new(vc.outputs["Color"], mix.inputs[6])
        links.new(ramp.outputs["Color"], mix.inputs[7])
        links.new(mix.outputs[2], bsdf.inputs["Base Color"])

    if not bsdf.inputs["Roughness"].is_linked:
        _set(bsdf, "Roughness", opts.get("roughness", rough))
    _set(bsdf, "Metallic", metal)

    # Viewport / Workbench / exporters without node support use these.
    mat.diffuse_color = color
    mat.roughness = rough
    mat.metallic = metal * 0.45         # full metal reads as black in Workbench
    mat["forge_kind"] = kind
    mat["forge_color"] = list(color)
    for key, value in opts.items():
        if isinstance(value, (int, float, str, bool)):
            mat["forge_opt_" + key] = value
    return mat


def make(name, kind="plain", color=(0.8, 0.8, 0.8, 1.0), **opts):
    if kind not in KINDS:
        kind = "plain"
    mat = bpy.data.materials.new(name)
    return apply(mat, kind, color, opts)


def recolor(mat, color):
    """Rebuild a forge material with a new base colour."""
    kind = mat.get("forge_kind", "plain")
    opts = {k[len("forge_opt_"):]: mat[k] for k in mat.keys() if k.startswith("forge_opt_")}
    apply(mat, kind, color, opts)
