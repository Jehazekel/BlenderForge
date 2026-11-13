"""Scene orchestration: build every section, lay entities out, light, render,
export and save."""

import math
import os
import warnings

import bpy
from mathutils import Vector

from . import core, materials
from .log import ForgeError, info, warn
from .parser import parse_color

DEFAULTS = {
    "fps": 24, "frame_start": 1, "lowpoly": False, "subdiv": 2, "seed": 1,
    "export": [], "render": None, "engine": "eevee", "samples": 16,
    "resolution": (1280, 720), "ground": True, "frame": None, "base": None,
    "view": "three_quarter", "focus": None,
}
# camera direction (from the subject towards the camera) and the region it frames
VIEWS = {
    "three_quarter": ((-0.60, -1.0, 0.30), "body"), "front": ((0.0, -1.0, 0.04), "body"),
    "side": ((-1.0, 0.0, 0.04), "body"), "back": ((0.0, 1.0, 0.04), "body"),
    "face": ((0.0, -1.0, 0.0), "face"), "face_side": ((-1.0, 0.0, 0.0), "face"),
    "face_three_quarter": ((-0.62, -1.0, 0.08), "face"),
}
# `view: sheet` tiles these into one image (3 x 2), so one small render shows every angle
SHEET = ("front", "side", "three_quarter", "face", "face_side", "face_three_quarter")
ENGINES = {"eevee": ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"), "workbench": ("BLENDER_WORKBENCH",),
           "cycles": ("CYCLES",)}


def read_settings(specs, overrides):
    """Merge `# settings` sections and command-line options over the defaults."""
    s = dict(DEFAULTS)
    for spec in specs:
        if spec.kind != "settings":
            continue
        s["fps"] = spec.integer("fps", s["fps"], 1, 240)
        s["frame_start"] = spec.integer("frame_start", s["frame_start"], 0, 100000)
        s["lowpoly"] = spec.flag("lowpoly", s["lowpoly"])
        s["subdiv"] = spec.integer("subdiv", s["subdiv"], 0, 3)
        s["seed"] = spec.integer("seed", s["seed"])
        s["samples"] = spec.integer("samples", s["samples"], 1, 4096)
        s["ground"] = spec.flag("ground", s["ground"])
        s["engine"] = spec.choice("engine", ENGINES, s["engine"])
        if spec.has("export"):
            s["export"] = spec.items("export")
        if spec.has("render"):
            text = spec.get("render").strip()
            s["render"] = None if text.lower() in ("false", "no", "off") else text
        if spec.has("resolution"):
            text = spec.get("resolution").lower().replace("x", " ")
            try:
                w, h = [int(float(p)) for p in text.replace(",", " ").split()[:2]]
                s["resolution"] = (max(16, w), max(16, h))
            except ValueError:
                raise ForgeError("'resolution' expects e.g. 1280x720", spec.line_of("resolution"))
        if spec.has("frame"):
            s["frame"] = spec.integer("frame", 1)
        s["view"] = spec.choice("view", tuple(VIEWS) + ("sheet",), s["view"])
        if spec.has("focus"):
            s["focus"] = spec.get("focus").strip()
        spec.warn_unused()
    for key, value in overrides.items():
        if value is not None:
            s[key] = value
    return s


def reset_scene(base=None):
    if base:
        if not os.path.isfile(base):
            raise ForgeError("--base file not found: %s" % base)
        bpy.ops.wm.open_mainfile(filepath=base)
        old = bpy.data.collections.get("Preview")
        if old is not None:
            core.remove_collection(old)
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    return scene


# -- edits to existing objects ---------------------------------------------------

def apply_edit(spec):
    """`# edit: Name` changes an object or collection that already exists."""
    name = spec.name
    col = bpy.data.collections.get(name)
    obj = bpy.data.objects.get(name)
    if col is not None:
        members = list(col.all_objects)
        roots = [o for o in members if o.parent is None or o.parent not in members]
    elif obj is not None:
        members, roots = [obj] + list(obj.children_recursive), [obj]
    else:
        warn("edit target '%s' not found (known: %s)"
             % (name, ", ".join(sorted(c.name for c in bpy.data.collections)) or "none"), spec.line)
        for key in spec.props:
            spec.used.add(key)
        return
    if spec.flag("delete", False):
        if col is not None:
            core.remove_collection(col)
        else:
            for o in members:
                bpy.data.objects.remove(o, do_unlink=True)
        info("edit: deleted '%s'" % name)
        return
    move = spec.vec("move")
    pos = spec.vec("position")
    rot = spec.get("rotate")
    scale = spec.vec("scale")
    for r in roots:
        if pos is not None:
            r.location = pos
        if move is not None:
            r.location = Vector(r.location) + Vector(move)
        if rot is not None:
            r.rotation_euler.z += math.radians(spec.num("rotate", 0))
        if scale is not None:
            r.scale = [a * b for a, b in zip(r.scale, scale)]
    if spec.has("hide"):
        hide = spec.flag("hide", True)
        for o in members:
            o.hide_viewport = o.hide_render = hide
    mats = {}
    for o in members:
        if o.type == "MESH":
            for m in o.data.materials:
                if m is not None:
                    mats[m.name] = m
    for key in list(spec.props):
        if key == "color" or key.startswith("color."):
            col_val = parse_color(spec.get(key))
            if col_val is None:
                warn("'%s' is not a colour" % spec.props[key][0], spec.line_of(key))
                continue
            want = key[6:].lower() if "." in key else None
            hits = [m for n, m in mats.items() if want is None or n.lower().endswith(want)]
            if not hits:
                warn("no material matching '%s' on '%s' (have: %s)"
                     % (want, name, ", ".join(sorted(mats))), spec.line_of(key))
            for m in hits:
                materials.recolor(m, col_val)
    new_name = spec.get("rename")
    if new_name:
        (col or obj).name = new_name
    info("edit: updated '%s'" % name)


# -- building ---------------------------------------------------------------------

def build_all(specs, settings, base_dir):
    scene = reset_scene(settings["base"])
    scene.render.fps = settings["fps"]
    ctx = core.Context(scene, settings)
    ctx.base_dir = base_dir
    core.load_templates()
    entities = []
    order = sorted((s for s in specs if s.kind not in ("settings", "edit")),
                   key=lambda s: 0 if s.kind == "map" else 1)       # terrain first
    for spec in order:
        module, type_name = core.resolve(spec)
        ctx.begin(spec.name)
        info("building %s '%s' (%s)" % (spec.kind, spec.name, type_name))
        position = spec.vec("position")
        n_pos = spec.given_count("position") if position else 0
        rotation = spec.num("rotation", 0.0)
        scale = spec.num("scale", 1.0, 0.01, 1000)
        entity = module.build(spec, ctx, type_name)
        entity.kind = spec.kind
        entity.position, entity.n_pos = position, n_pos
        if rotation:
            entity.root.rotation_euler.z = math.radians(rotation)
        if scale != 1.0:
            entity.root.scale = (scale, scale, scale)
        spec.warn_unused()
        entities.append(entity)
    layout(entities, ctx)
    for spec in specs:
        if spec.kind == "edit":
            apply_edit(spec)
            spec.warn_unused()
    end = settings["frame_start"]
    for action in bpy.data.actions:
        end = max(end, int(action.frame_range[1]))
    scene.frame_start = settings["frame_start"]
    scene.frame_end = max(end, settings["frame_start"] + 1)
    return scene, ctx, entities


def layout(entities, ctx):
    """Explicit `position:` wins; everything else lines up along X."""
    row = [e for e in entities if e.position is None and e.kind != "map"]
    cursor = 0.0
    spans = []
    for e in row:
        lo, hi = e.bounds()
        width = max(hi.x - lo.x, 0.2)
        e.root.location.x += cursor - lo.x
        spans.append(e)
        cursor += width + max(0.6, width * 0.35)
    shift = (cursor - (max(0.6, 0) if row else 0)) / 2.0 if row else 0.0
    for e in row:
        e.root.location.x -= shift
        if ctx.ground:
            e.root.location.z = ctx.ground(e.root.location.x, e.root.location.y)
    for e in entities:
        if e.position is None:
            continue
        x, y, z = e.position
        if e.n_pos < 3 and ctx.ground and e.kind != "map":
            z = ctx.ground(x, y)
        e.root.location = (x, y, z)


def scene_bounds(entities):
    lo = Vector((1e9, 1e9, 1e9))
    hi = Vector((-1e9, -1e9, -1e9))
    for e in entities:
        a, b = e.bounds()
        if (b - a).length == 0:
            continue
        for i in range(3):
            lo[i], hi[i] = min(lo[i], a[i]), max(hi[i], b[i])
    if lo.x > hi.x:
        return Vector((-1, -1, 0)), Vector((1, 1, 2))
    return lo, hi


# -- preview: camera, lights, ground ------------------------------------------------

def content_objects(scene):
    """Everything in the scene except the preview rig (camera, lights, ground)."""
    skip = set()
    for label in ("Preview", "References"):
        col = bpy.data.collections.get(label)
        if col is not None:
            skip.update(col.all_objects)
    return [o for o in scene.collection.all_objects if o not in skip]


def setup_preview(scene, entities, settings):
    bpy.context.view_layer.update()
    lo, hi = scene_bounds(entities)
    col = bpy.data.collections.new("Preview")
    scene.collection.children.link(col)
    center = (lo + hi) / 2
    radius = max((hi - lo).length / 2, 0.5)
    has_map = any(e.kind == "map" for e in entities) or any(
        o.type == "MESH" and "Col" in o.data.color_attributes for o in content_objects(scene))

    cam_data = bpy.data.cameras.new("PreviewCamera")
    cam_data.lens = 65              # longer lens: less distortion on characters
    cam = bpy.data.objects.new("PreviewCamera", cam_data)
    col.objects.link(cam)
    scene.camera = cam
    view = settings["view"] if settings["view"] in VIEWS else "three_quarter"
    if has_map and view == "three_quarter":
        aim_camera(scene, entities, settings, None, direction=(-0.60, -1.0, 0.72))
    else:
        aim_camera(scene, entities, settings, view)
    corners = _corners(scene, entities, None, "body")
    if corners:
        lo = Vector([min(c[i] for c in corners) for i in range(3)])
        hi = Vector([max(c[i] for c in corners) for i in range(3)])
        center = (lo + hi) / 2
        radius = max((hi - lo).length / 2, 0.5)

    # three-point sun rig: warm key with soft shadows, cool fill, rim from behind
    for label, energy, euler, color, soft, shadow in (
            ("KeySun", 2.5, (math.radians(50), 0, math.radians(-38)), (1.0, 0.95, 0.88), 9.0, True),
            ("FillSun", 0.7, (math.radians(62), 0, math.radians(65)), (0.72, 0.84, 1.0), 30.0, False),
            ("RimSun", 1.1, (math.radians(68), 0, math.radians(168)), (1.0, 0.97, 0.92), 6.0, False)):
        light = bpy.data.lights.new(label, "SUN")
        light.energy = energy
        light.color = color
        for attr, value in (("angle", math.radians(soft)), ("use_shadow", shadow)):
            try:
                setattr(light, attr, value)
            except Exception:
                pass
        lo_obj = bpy.data.objects.new(label, light)
        lo_obj.rotation_euler = euler
        col.objects.link(lo_obj)

    horizon = (0.80, 0.86, 0.93)
    zenith = (0.30, 0.50, 0.82)
    sky_strength = 0.65
    world = bpy.data.worlds.new("PreviewWorld")
    scene.world = world
    world.color = horizon
    _sky(world, horizon, zenith, sky_strength)

    if settings["ground"] and not has_map:
        me = bpy.data.meshes.new("PreviewGround")
        r = radius * 60
        me.from_pydata([(-r, -r, 0), (r, -r, 0), (r, r, 0), (-r, r, 0)], [], [(0, 1, 2, 3)])
        ground = bpy.data.objects.new("PreviewGround", me)
        ground.location = (center.x, center.y, min(lo.z, 0.0) - 0.002)
        me.materials.append(_ground_material((0.24, 0.26, 0.26), horizon, sky_strength,
                                             radius * 2.5, radius * 22))
        col.objects.link(ground)
    return cam


def _corners(scene, entities, focus, region):
    """World-space points the camera has to keep in frame."""
    ents = [e for e in entities if e.name.lower() == focus.lower()] if focus else []
    if focus and not ents:
        warn("focus: no entity named '%s'" % focus)
    if region != "body":
        for e in ents or entities:
            box = getattr(e, "regions", {}).get(region)
            if box:
                lo, hi = box
                m = e.root.matrix_world
                return [m @ Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
                        for z in (lo[2], hi[2])]
    objs = [o for e in ents for o in e.objects] if ents else content_objects(scene)
    corners = []
    for o in objs:
        if o.type != "MESH":
            continue
        verts = o.data.vertices
        step = max(1, len(verts) // 600)
        corners += [o.matrix_world @ verts[i].co for i in range(0, len(verts), step)]
    return corners


def aim_camera(scene, entities, settings, view, direction=None, aspect=None):
    """Point the preview camera along a named view and back off until the
    subject (the `focus` entity, or everything) just fits the frame."""
    cam = scene.camera
    cam_data = cam.data
    vec, region = VIEWS[view] if view else (direction, "body")
    direction = Vector(direction or vec).normalized()
    if aspect is None:
        aspect = settings["resolution"][0] / settings["resolution"][1]
    bpy.context.view_layer.update()
    corners = _corners(scene, entities, settings.get("focus"), region)
    if not corners:
        corners = list(scene_bounds(entities))
    lo = Vector([min(c[i] for c in corners) for i in range(3)])
    hi = Vector([max(c[i] for c in corners) for i in range(3)])
    center = (lo + hi) / 2
    radius = max((hi - lo).length / 2, 0.05)
    quat = (-direction).to_track_quat("-Z", "Y")
    right, up = quat @ Vector((1, 0, 0)), quat @ Vector((0, 1, 0))
    tan_h = 18.0 / cam_data.lens * (1.0 if aspect >= 1 else aspect)
    tan_v = tan_h / aspect
    # centre the view on what the camera actually sees, then back off until it fits
    xs = [c.dot(right) for c in corners]
    ys = [c.dot(up) for c in corners]
    center = center + right * ((min(xs) + max(xs)) / 2 - center.dot(right)) \
        + up * ((min(ys) + max(ys)) / 2 - center.dot(up))
    dist = 0.1
    for c in corners:
        p = c - center
        depth = p.dot(direction)        # > 0 means nearer the camera
        dist = max(dist, abs(p.dot(right)) / tan_h + depth, abs(p.dot(up)) / tan_v + depth)
    dist *= 1.07
    cam.location = center + direction * dist
    cam.rotation_euler = quat.to_euler()
    cam_data.clip_start = max(0.01, dist * 0.01)
    cam_data.clip_end = dist * 6 + radius * 10 + 200


def render_sheet(scene, entities, path, settings):
    """Six views (body and face: front, side, three-quarter) tiled into one image."""
    from array import array
    W, H = settings["resolution"]
    cw, ch = W // 3, H // 2
    cell = dict(settings, resolution=(cw, ch))
    if not cell.get("focus"):
        first = next((e for e in entities if getattr(e, "regions", None)), None)
        cell["focus"] = first.name if first else None
    big = array("f", [0.0]) * (cw * 3 * ch * 2 * 4)
    for k, view in enumerate(SHEET):
        aim_camera(scene, entities, cell, view, aspect=cw / ch)
        tmp = "%s.cell%d.png" % (path, k)
        if not render_preview(scene, tmp, cell, quiet=True):
            return None
        img = bpy.data.images.load(tmp)
        buf = array("f", [0.0]) * (cw * ch * 4)
        img.pixels.foreach_get(buf)
        bpy.data.images.remove(img)
        os.remove(tmp)
        cx, cy = k % 3, 1 - k // 3              # image rows run bottom to top
        for y in range(ch):
            d = ((cy * ch + y) * cw * 3 + cx * cw) * 4
            big[d:d + cw * 4] = buf[y * cw * 4:(y + 1) * cw * 4]
    out = bpy.data.images.new("ForgeSheet", cw * 3, ch * 2, alpha=True)
    out.pixels.foreach_set(big)
    out.filepath_raw = path
    out.file_format = "PNG"
    out.save()
    bpy.data.images.remove(out)
    info("rendered sheet (%s) -> %s" % (", ".join(SHEET), path))
    return True


def _sky(world, horizon, zenith, strength):
    """Vertical gradient background: bright horizon, deeper blue overhead."""
    if world.node_tree is None:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            world.use_nodes = True
    nt = world.node_tree
    if nt is None:
        return
    try:
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputWorld")
        bg = nt.nodes.new("ShaderNodeBackground")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        ramp = nt.nodes.new("ShaderNodeValToRGB")
        ramp.color_ramp.elements[0].position = 0.0
        ramp.color_ramp.elements[0].color = tuple(horizon) + (1,)
        ramp.color_ramp.elements[1].position = 0.55
        ramp.color_ramp.elements[1].color = tuple(zenith) + (1,)
        nt.links.new(tc.outputs["Generated"], sep.inputs[0])
        nt.links.new(sep.outputs[2], ramp.inputs[0])
        nt.links.new(ramp.outputs[0], bg.inputs[0])
        bg.inputs[1].default_value = strength
        nt.links.new(bg.outputs[0], out.inputs[0])
    except Exception:
        for node in nt.nodes:
            if node.type == "BACKGROUND":
                node.inputs[0].default_value = tuple(horizon) + (1,)
                node.inputs[1].default_value = strength


def _ground_material(color, horizon, strength, near, far):
    """Matte floor that dissolves into the horizon colour, so there is no hard edge."""
    mat = materials.make("PreviewGround", "plain", tuple(color) + (1,), roughness=0.95)
    try:
        nt = mat.node_tree
        out = next(n for n in nt.nodes if n.type == "OUTPUT_MATERIAL")
        bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
        tc = next(n for n in nt.nodes if n.type == "TEX_COORD")
        length = nt.nodes.new("ShaderNodeVectorMath")
        length.operation = "LENGTH"
        fade = nt.nodes.new("ShaderNodeMapRange")
        fade.inputs["From Min"].default_value = near
        fade.inputs["From Max"].default_value = far
        try:
            fade.interpolation_type = "SMOOTHSTEP"
        except Exception:
            pass
        sky = nt.nodes.new("ShaderNodeEmission")
        sky.inputs[0].default_value = tuple(horizon) + (1,)
        sky.inputs[1].default_value = strength
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(tc.outputs["Object"], length.inputs[0])
        nt.links.new(length.outputs["Value"], fade.inputs[0])
        nt.links.new(fade.outputs[0], mix.inputs[0])
        nt.links.new(bsdf.outputs[0], mix.inputs[1])
        nt.links.new(sky.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    except Exception:
        pass
    return mat


def _color_management(scene):
    """Filmic-style tone mapping keeps highlights from clipping to white."""
    vs = scene.view_settings
    for transform, looks in (("AgX", ("AgX - Medium High Contrast", "Medium High Contrast")),
                             ("Filmic", ("Medium High Contrast",)), ("Standard", ())):
        try:
            vs.view_transform = transform
        except TypeError:
            continue
        for look in looks:
            try:
                vs.look = look
                break
            except TypeError:
                continue
        return transform
    return None


def _tune(target, **values):
    """Set whichever of these properties this Blender version has."""
    ok = True
    for key, value in values.items():
        try:
            setattr(target, key, value)
        except (AttributeError, TypeError, ValueError):
            ok = False
    return ok


def _set_engine(scene, name):
    for ident in ENGINES[name]:
        try:
            scene.render.engine = ident
            return True
        except TypeError:
            continue
    return False


def render_preview(scene, path, settings, quiet=False):
    """Low-sample still. Falls back Eevee -> Workbench -> Cycles (CPU)."""
    scene.render.resolution_x, scene.render.resolution_y = settings["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = path
    _color_management(scene)
    # never subdivide past what a preview can show
    _tune(scene.render, use_simplify=True, simplify_subdivision_render=max(2, settings["subdiv"]),
          threads_mode="AUTO")
    order = [settings["engine"]] + [e for e in ("eevee", "workbench", "cycles") if e != settings["engine"]]
    for engine in order:
        if not _set_engine(scene, engine):
            continue
        samples = settings["samples"]
        if engine == "eevee":
            _tune(scene.eevee, taa_render_samples=samples, use_shadows=True, shadow_ray_count=2,
                  shadow_step_count=6, use_raytracing=False, use_overscan=False)
        elif engine == "cycles":
            # Few samples + adaptive sampling + denoiser: clean stills in seconds on a CPU.
            c = scene.cycles
            _tune(c, device="CPU", samples=samples, use_adaptive_sampling=True, adaptive_threshold=0.05,
                  adaptive_min_samples=4, max_bounces=4, diffuse_bounces=2, glossy_bounces=2,
                  transmission_bounces=2, transparent_max_bounces=4, caustics_reflective=False,
                  caustics_refractive=False, sample_clamp_indirect=4.0, use_denoising=True)
            if not _tune(c, denoiser="OPENIMAGEDENOISE"):
                _tune(c, use_denoising=False)
            _tune(c, denoising_input_passes="RGB_ALBEDO_NORMAL", denoising_prefilter="FAST")
        else:
            sh = scene.display.shading
            sh.light = "STUDIO"
            sh.color_type = "MATERIAL"
            sh.show_shadows = True
            sh.show_cavity = True
        if os.path.exists(path):
            os.remove(path)
        try:
            bpy.ops.render.render(write_still=True)
        except Exception as exc:        # no GL context, missing engine, ...
            warn("%s render failed (%s)" % (engine, str(exc).strip().splitlines()[-1]))
            continue
        if os.path.exists(path):
            if not quiet:
                info("rendered preview with %s -> %s" % (engine, path))
            return engine
        warn("%s produced no image, trying the next engine" % engine)
    warn("could not render a preview on this machine")
    return None


# -- export ---------------------------------------------------------------------------

def _select(entities):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    objs = [o for o in content_objects(bpy.context.scene) if o.name in bpy.context.view_layer.objects]
    for o in objs:
        o.select_set(True)
    if objs:
        bpy.context.view_layer.objects.active = objs[0]
    return objs


def export(entities, out_base, formats):
    done = []
    for fmt in formats:
        fmt = fmt.lower().lstrip(".")
        path = "%s.%s" % (out_base, fmt)
        objs = _select(entities)
        try:
            if fmt in ("glb", "gltf"):
                # Applying modifiers would silently drop shape keys, so only do
                # it when nothing in the export has any.
                apply = not any(o.type == "MESH" and o.data.shape_keys for o in objs)
                bpy.ops.export_scene.gltf(
                    filepath=path, export_format="GLB" if fmt == "glb" else "GLTF_SEPARATE",
                    use_selection=True, export_animations=True, export_animation_mode="ACTIONS",
                    export_skins=True, export_morph=True, export_yup=True, export_apply=apply)
            elif fmt == "fbx":
                bpy.ops.export_scene.fbx(
                    filepath=path, use_selection=True, object_types={"ARMATURE", "MESH", "EMPTY"},
                    add_leaf_bones=False, bake_anim=True, bake_anim_use_nla_strips=True,
                    bake_anim_use_all_actions=False, use_mesh_modifiers=True, mesh_smooth_type="FACE")
            elif fmt == "stl":
                for o in objs:
                    if o.type != "MESH":
                        o.select_set(False)
                if hasattr(bpy.ops.wm, "stl_export"):
                    bpy.ops.wm.stl_export(filepath=path, export_selected_objects=True, apply_modifiers=True)
                else:
                    bpy.ops.export_mesh.stl(filepath=path, use_selection=True, use_mesh_modifiers=True)
            else:
                warn("unknown export format '%s' (use glb, gltf, fbx or stl)" % fmt)
                continue
        except Exception as exc:
            warn("%s export failed: %s" % (fmt, str(exc).strip().splitlines()[-1]))
            continue
        if os.path.exists(path):
            info("exported %s" % path)
            done.append(path)
    return done


def save(path):
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False, compress=True)
    info("saved %s" % path)
