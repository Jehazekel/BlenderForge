"""Build context, entity record and the template registry."""

import difflib
import importlib
import pkgutil

import bpy
from mathutils import Vector

from . import materials
from .log import warn

# kind -> template type used when `type:` is missing or unknown
DEFAULT_TYPE = {
    "character": "humanoid", "animal": "quadruped", "structure": "building",
    "prop": "crate", "vehicle": "car", "tree": "oak", "map": "terrain",
}


class Entity:
    """What a template returns: the object to move plus everything it made."""

    def __init__(self, name, root, objects, armature=None, static=True):
        self.name = name
        self.root = root
        self.objects = list(objects)
        self.armature = armature
        self.static = static

    def bounds(self):
        bpy.context.view_layer.update()
        lo = Vector((1e9, 1e9, 1e9))
        hi = Vector((-1e9, -1e9, -1e9))
        for obj in self.objects:
            if obj.type != "MESH":
                continue
            for corner in obj.bound_box:
                p = obj.matrix_world @ Vector(corner)
                for i in range(3):
                    lo[i] = min(lo[i], p[i])
                    hi[i] = max(hi[i], p[i])
        if lo.x > hi.x:
            return Vector(), Vector()
        return lo, hi


class Context:
    def __init__(self, scene, settings):
        self.scene = scene
        self.settings = settings
        self.fps = settings["fps"]
        self.lowpoly = settings["lowpoly"]
        self.subdiv = settings["subdiv"]
        self.seed = settings["seed"]
        self.frame_start = settings["frame_start"]
        self.collection = None
        self.name = ""
        self.ground = None          # height function set by a map
        self.base_dir = "."

    def begin(self, name):
        self.name = name
        old = bpy.data.collections.get(name)
        if old is not None:         # --base file: replace an entity of the same name
            remove_collection(old)
        col = bpy.data.collections.new(name)
        self.scene.collection.children.link(col)
        self.collection = col
        return col

    def mat(self, label, kind="plain", color=(0.8, 0.8, 0.8, 1.0), **opts):
        return materials.make("%s_%s" % (self.name, label), kind, color, **opts)

    def spec_lowpoly(self, spec):
        return spec.flag("lowpoly", self.lowpoly)


def remove_collection(col):
    for obj in list(col.all_objects):
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            try:
                getattr(bpy.data, {"Mesh": "meshes", "Armature": "armatures"}[type(data).__name__]).remove(data)
            except (KeyError, RuntimeError):
                pass
    for child in list(col.children_recursive):
        bpy.data.collections.remove(child)
    bpy.data.collections.remove(col)


# -- registry -----------------------------------------------------------------

_templates = {}     # type name -> module
_loaded = False


def load_templates():
    """Import every module in forge/templates. One file = one template."""
    global _loaded
    if _loaded:
        return _templates
    from . import templates as pkg
    for mod_info in pkgutil.iter_modules(pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        mod = importlib.import_module("%s.%s" % (pkg.__name__, mod_info.name))
        if not hasattr(mod, "build") or not hasattr(mod, "NAMES"):
            continue
        for name in mod.NAMES:
            _templates[name] = mod
    _loaded = True
    return _templates


def resolve(spec):
    """Pick the template for a spec. Returns (module, type name)."""
    templates = load_templates()
    fallback = DEFAULT_TYPE.get(spec.kind, "crate")
    raw = spec.get("type")
    if raw is None:
        # "# animal: Wolf" with no type: try the name itself, then the default.
        guess = spec.name.lower().replace(" ", "_")
        t = guess if guess in templates else fallback
        return templates[t], t
    t = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if t in templates:
        return templates[t], t
    near = difflib.get_close_matches(t, list(templates), n=1, cutoff=0.72)
    if near:
        warn("unknown type '%s', assuming '%s'" % (raw, near[0]), spec.line_of("type"))
        return templates[near[0]], near[0]
    warn("unknown type '%s' for %s '%s', using '%s' (known: %s)"
         % (raw, spec.kind, spec.name, fallback, ", ".join(sorted(templates))), spec.line_of("type"))
    return templates[fallback], fallback
