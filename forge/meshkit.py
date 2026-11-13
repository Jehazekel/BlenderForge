"""Small bmesh modelling kit: rings, lofts, caps, boxes, lathes, extrusions.

Organic templates build one connected quad cage out of lofted rings (the
classic box-modelling layout) and put a subdivision modifier on top.
Hard-surface templates combine boxes, lathes and extruded profiles.
"""

import math
from contextlib import contextmanager

import bmesh
import bpy
from mathutils import Matrix, Vector

TAU = math.tau
X = Vector((1.0, 0.0, 0.0))
Y = Vector((0.0, 1.0, 0.0))
Z = Vector((0.0, 0.0, 1.0))


def V(x=0.0, y=0.0, z=0.0):
    return Vector((x, y, z))


def lerp(a, b, t):
    return a + (b - a) * t


def smooth(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


# -- ring sections: (centre, u, v). A ring vertex is c + u*cos(a) + v*sin(a) --

def sec_z(c, rx, ry):
    """Horizontal ring. Angle 0 is +X, 90 degrees is +Y."""
    return (Vector(c), X * rx, Y * ry)


def sec_y(c, rx, rz, pitch=0.0):
    """Ring across a body that runs along -Y, pitched upward by `pitch`."""
    return (Vector(c), X * rx, V(0.0, math.sin(pitch), math.cos(pitch)) * rz)


def sec_x(c, ry, rz):
    """Ring across a limb that runs along X."""
    return (Vector(c), Y * ry, Z * rz)


def sec_dir(c, tangent, r1, r2=None, hint=Z):
    """Ring perpendicular to an arbitrary direction."""
    t = Vector(tangent).normalized()
    u = Vector(hint).cross(t)
    if u.length < 1e-4:
        u = X.cross(t) if abs(t.x) < 0.9 else Y.cross(t)
    u.normalize()
    v = t.cross(u)
    return (Vector(c), u * r1, v * (r1 if r2 is None else r2))


def path_sections(points, radii, hint=Z):
    """Sections along a polyline, with tangents averaged at the joints."""
    out = []
    n = len(points)
    for i, p in enumerate(points):
        a = Vector(points[max(0, i - 1)])
        b = Vector(points[min(n - 1, i + 1)])
        r = radii[i]
        r1, r2 = (r if isinstance(r, (tuple, list)) else (r, r))
        out.append(sec_dir(p, b - a, r1, r2, hint))
    return out


def basis(origin, normal, up=Z):
    """Matrix whose local +Y points along `normal` and local +Z along `up`."""
    n = Vector(normal).normalized()
    right = Vector(up).cross(n)
    if right.length < 1e-5:
        right = X.copy()
    right.normalize()
    upv = n.cross(right)
    m = Matrix((
        (right.x, n.x, upv.x, origin[0]),
        (right.y, n.y, upv.y, origin[1]),
        (right.z, n.z, upv.z, origin[2]),
        (0.0, 0.0, 0.0, 1.0),
    ))
    return m


def rot_z(angle, origin=(0, 0, 0)):
    return Matrix.Translation(Vector(origin)) @ Matrix.Rotation(angle, 4, "Z")


class Palette:
    """Material slots shared by every builder that ends up in one mesh."""

    def __init__(self):
        self.mats = []

    def index(self, mat):
        if mat is None:
            return 0
        for i, m in enumerate(self.mats):
            if m == mat:
                return i
        self.mats.append(mat)
        return len(self.mats) - 1


class MeshBuilder:
    def __init__(self, palette=None, smooth_faces=True):
        self.bm = bmesh.new()
        self.palette = palette or Palette()
        self.count = 0
        self.groups = {}        # region name -> vertex indices
        self.rigid = {}         # bone name -> vertex indices skinned 100% to it
        self.xform = None
        self.smooth_faces = smooth_faces

    # -- bookkeeping --------------------------------------------------------
    @contextmanager
    def part(self, name=None, bone=None, xform=None, flat=None):
        """Everything created inside the block is tagged / transformed."""
        start = self.count
        old_x, old_s = self.xform, self.smooth_faces
        if xform is not None:
            self.xform = (old_x @ xform) if old_x is not None else xform
        if flat is not None:
            self.smooth_faces = not flat
        try:
            yield
        finally:
            self.xform, self.smooth_faces = old_x, old_s
            idx = list(range(start, self.count))
            if name:
                self.groups.setdefault(name, []).extend(idx)
            if bone:
                self.rigid.setdefault(bone, []).extend(idx)

    def m(self, mat):
        return mat if isinstance(mat, int) else self.palette.index(mat)

    # -- elements -----------------------------------------------------------
    def vert(self, co):
        co = Vector(co)
        if self.xform is not None:
            co = self.xform @ co
        v = self.bm.verts.new(co)
        v.index = self.count
        self.count += 1
        return v

    def face(self, verts, mat=0):
        if len(set(verts)) < 3:
            return None
        try:
            f = self.bm.faces.new(verts)
        except ValueError:
            return None
        f.material_index = self.m(mat)
        f.smooth = self.smooth_faces
        return f

    def ring(self, c, u, v, n=8, phase=0.0, power=1.0):
        out = []
        for i in range(n):
            a = phase + TAU * i / n
            ca, sa = math.cos(a), math.sin(a)
            if power != 1.0:
                ca = math.copysign(abs(ca) ** power, ca)
                sa = math.copysign(abs(sa) ** power, sa)
            out.append(self.vert(c + u * ca + v * sa))
        return out

    def bridge(self, r1, r2, mat=0, skip=()):
        n = len(r1)
        for i in range(n):
            if i in skip:
                continue
            j = (i + 1) % n
            self.face([r1[i], r1[j], r2[j], r2[i]], mat)

    def cap(self, ring, mat=0, c=None):
        """Close a ring with quads around a centre vertex."""
        n = len(ring)
        if n == 4 and c is None:
            self.face(ring, mat)
            return None
        if c is None:
            c = sum((v.co for v in ring), Vector()) / n
            cv = self.bm.verts.new(c)       # already in final space
            cv.index = self.count
            self.count += 1
        else:
            cv = self.vert(c)
        if n % 2 == 0:
            for i in range(0, n, 2):
                self.face([cv, ring[i], ring[(i + 1) % n], ring[(i + 2) % n]], mat)
        else:
            for i in range(n):
                self.face([cv, ring[i], ring[(i + 1) % n]], mat)
        return cv

    def fan(self, ring, apex, mat=0):
        av = self.vert(apex)
        n = len(ring)
        for i in range(n):
            self.face([ring[i], ring[(i + 1) % n], av], mat)
        return av

    def order_loop(self, loop, c, u, v):
        """Sort a hole's boundary by angle; return (ordered verts, ring phase)."""
        c = Vector(c)
        if self.xform is not None:
            c = self.xform @ c
        un, vn = u.normalized(), v.normalized()
        ang = sorted(((math.atan2((p.co - c).dot(vn), (p.co - c).dot(un)), p.index, p)
                      for p in loop), key=lambda t: (t[0], t[1]))
        step = TAU / len(ang)
        sx = sum(math.cos(a - i * step) for i, (a, _, _) in enumerate(ang))
        sy = sum(math.sin(a - i * step) for i, (a, _, _) in enumerate(ang))
        return [p for _, _, p in ang], math.atan2(sy, sx)

    def loft(self, sections, n=8, mat=0, cap_start=True, cap_end=True, start=None,
             mats=None, power=1.0, phase=0.0, start_tip=None, end_tip=None):
        """Bridge a row of ring sections. `start` continues from a hole boundary."""
        rings = []
        prev = None
        if start is not None:
            prev, phase = self.order_loop(start, *sections[0])
            n = len(prev)
            cap_start = False
        for k, (c, u, v) in enumerate(sections):
            r = self.ring(c, u, v, n, phase, power)
            if prev is not None:
                seg = len(rings) - (0 if start is not None else 1)
                mm = mats[min(seg, len(mats) - 1)] if mats else mat
                self.bridge(prev, r, mm)
            rings.append(r)
            prev = r
        if cap_start:
            self.cap(rings[0], mats[0] if mats else mat, start_tip)
        if cap_end:
            self.cap(rings[-1], mats[-1] if mats else mat, end_tip)
        return rings

    # -- primitives ---------------------------------------------------------
    def box(self, center, size, mat=0):
        cx, cy, cz = center
        hx, hy, hz = size[0] / 2.0, size[1] / 2.0, size[2] / 2.0
        v = [self.vert((cx + sx * hx, cy + sy * hy, cz + sz * hz))
             for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
        for q in ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)):
            self.face([v[i] for i in q], mat)
        return v

    def cylinder(self, c0, c1, r0, r1=None, n=16, mat=0, caps=True, hint=Z):
        r1 = r0 if r1 is None else r1
        c0, c1 = Vector(c0), Vector(c1)
        t = c1 - c0
        return self.loft([sec_dir(c0, t, r0, hint=hint), sec_dir(c1, t, r1, hint=hint)],
                         n=n, mat=mat, cap_start=caps, cap_end=caps)

    def sphere(self, c, r, mat=0, n=8, m=5, axis="z"):
        """Quad sphere / ellipsoid: `m` latitude rings plus quad pole caps."""
        c = Vector(c)
        rx, ry, rz = (r, r, r) if isinstance(r, (int, float)) else r
        secs = []
        for k in range(m):
            lat = -math.pi / 2 + math.pi * (k + 1) / (m + 1)
            h, w = math.sin(lat), math.cos(lat)
            if axis == "z":
                secs.append((c + Z * rz * h, X * rx * w, Y * ry * w))
            elif axis == "y":
                secs.append((c + Y * ry * h, X * rx * w, Z * rz * w))
            else:
                secs.append((c + X * rx * h, Y * ry * w, Z * rz * w))
        ax = {"z": Z * rz, "y": Y * ry, "x": X * rx}[axis]
        return self.loft(secs, n=n, mat=mat, start_tip=c - ax, end_tip=c + ax)

    def lathe(self, profile, n=24, mat=0, center=(0, 0, 0), cap_start=False, cap_end=False,
              mats=None):
        """Revolve (radius, z) points around the vertical axis."""
        c = Vector(center)
        secs = [(c + Z * z, X * max(r, 1e-4), Y * max(r, 1e-4)) for r, z in profile]
        return self.loft(secs, n=n, mat=mat, cap_start=cap_start, cap_end=cap_end, mats=mats)

    def extrude(self, points, offset, mat=0, caps=True, cap_mat=None):
        """Sweep a planar polygon along `offset`."""
        offset = Vector(offset)
        a = [self.vert(p) for p in points]
        b = [self.vert(Vector(p) + offset) for p in points]
        n = len(a)
        for i in range(n):
            j = (i + 1) % n
            self.face([a[i], a[j], b[j], b[i]], mat)
        if caps:
            cm = mat if cap_mat is None else cap_mat
            self.face(list(reversed(a)), cm)
            self.face(b, cm)
        return a, b

    def quad(self, p0, p1, p2, p3, mat=0):
        return self.face([self.vert(p) for p in (p0, p1, p2, p3)], mat)

    # -- output -------------------------------------------------------------
    def bounds(self):
        if not self.count:
            return Vector(), Vector()
        xs = [v.co for v in self.bm.verts]
        lo = Vector((min(p.x for p in xs), min(p.y for p in xs), min(p.z for p in xs)))
        hi = Vector((max(p.x for p in xs), max(p.y for p in xs), max(p.z for p in xs)))
        return lo, hi

    def to_mesh(self, name, recalc=True):
        bm = self.bm
        bm.verts.ensure_lookup_table()
        if recalc and bm.faces:
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for mat in self.palette.mats:
            me.materials.append(mat)
        return me

    def to_object(self, name, collection, recalc=True, sharp_angle=None):
        me = self.to_mesh(name, recalc)
        if sharp_angle is not None:
            mark_sharp(me, sharp_angle)
        obj = bpy.data.objects.new(name, me)
        collection.objects.link(obj)
        return obj


def mark_sharp(mesh, degrees=35.0):
    """Smooth shading with hard edges kept sharp (no modifier needed)."""
    try:
        mesh.set_sharp_from_angle(angle=math.radians(degrees))
    except Exception:
        pass


def unwrap(obj, angle=66.0, margin=0.02):
    """One UV map by angle-based projection: islands split at hard turns, packed
    into the 0-1 square without overlap. Run before shape keys are added."""
    me = obj.data
    if not me.polygons:
        return
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    view = bpy.context.view_layer
    for o in view.objects:
        o.select_set(False)
    obj.select_set(True)
    view.objects.active = obj
    try:
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(angle), island_margin=margin)
    finally:
        bpy.ops.object.mode_set(mode="OBJECT")
        obj.select_set(False)


def add_subsurf(obj, levels):
    if levels <= 0:
        return None
    mod = obj.modifiers.new("Subdivision", "SUBSURF")
    mod.levels = min(levels, 2)
    mod.render_levels = levels
    for attr, value in (("quality", 1), ("uv_smooth", "NONE")):     # cheaper evaluation, same surface
        try:
            setattr(mod, attr, value)
        except Exception:
            pass
    return mod


def add_bevel(obj, width, segments=2):
    mod = obj.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(40)
    try:
        mod.harden_normals = True
    except Exception:
        pass
    return mod


# -- deterministic noise (no random module state leaks between runs) ----------

def hash01(*keys):
    """Stable hash of integers -> float in [0, 1)."""
    h = 2166136261
    for k in keys:
        h ^= (int(k) & 0xFFFFFFFF)
        h = (h * 16777619) & 0xFFFFFFFF
        h ^= h >> 13
        h = (h * 0x5BD1E995) & 0xFFFFFFFF
        h ^= h >> 15
    return h / 4294967296.0


def value_noise(x, y, seed=0):
    xi, yi = math.floor(x), math.floor(y)
    fx, fy = x - xi, y - yi
    sx, sy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a = hash01(xi, yi, seed)
    b = hash01(xi + 1, yi, seed)
    c = hash01(xi, yi + 1, seed)
    d = hash01(xi + 1, yi + 1, seed)
    return lerp(lerp(a, b, sx), lerp(c, d, sx), sy)


def fbm(x, y, seed=0, octaves=5, gain=0.5, lacunarity=2.0):
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total += amp * value_noise(x, y, seed + o * 101)
        norm += amp
        amp *= gain
        x *= lacunarity
        y *= lacunarity
    return total / norm


class Rng:
    """Tiny seeded generator so results never depend on Python's hash seed."""

    def __init__(self, seed):
        self.seed = int(seed) & 0xFFFFFFFF
        self.i = 0

    def random(self):
        self.i += 1
        return hash01(self.seed, self.i)

    def uniform(self, a, b):
        return a + (b - a) * self.random()

    def choice(self, seq):
        return seq[int(self.random() * len(seq)) % len(seq)]


def name_seed(text):
    h = 0
    for ch in text:
        h = (h * 131 + ord(ch)) & 0xFFFFFFFF
    return h
