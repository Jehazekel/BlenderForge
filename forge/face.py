"""Human head: a 16-column skull cage with the face modelled into it.

Every number comes from the profile's `head` and `face` blocks
(`anatomy/data/humans.json`). A row is one horizontal ring of the head; a
column is one vertical line of the face (midline, nose wing, pupil, cheek).
Nose, lips, brow ridge and eye sockets are `relief` on those rows, so they are
part of the skin mesh and deform with it. The mouth is a real slit: the lower
lip has its own edge, and the jaw key opens it over a dark cavity and teeth.

Ring order: vertex 0 is the left side (+X), 4 the back (+Y), 8 the right
side, 12 the front midline (-Y), so vertex 2i lines up with vertex i of the
8-vertex neck ring.
"""

import math

import bmesh

from mathutils import Matrix, Vector

from . import creature
from .meshkit import V, X, Y, Z

N = 16
FRONT_MID = 12


class Head:
    def __init__(self, P, U, zn, hh, hc):
        self.F = F = P["face"]
        self.hw = P["head"]["width"] / 2 * U
        self.hd = P["head"]["depth"] / 2 * U
        self.hh, self.zn, self.hc = hh, zn, hc
        self.cols, self.pw = F["columns"], F["power"]
        self.rows = [dict(zip(("name", "at", "w", "f", "b", "relief"), r)) for r in F["rows"]]
        self.row = {r["name"]: k for k, r in enumerate(self.rows)}
        for r in self.rows:         # a row may place its own columns (the nose wings flare)
            r["cols"] = F.get("row_columns", {}).get(r["name"], self.cols)
        self.rings = []
        self.low = {}               # lower-lip edge: ring index -> vertex

    # -- shape --------------------------------------------------------------
    @staticmethod
    def col(j):
        """(side, column, x sign): side is -1 front, +1 back, 0 for the two side verts."""
        j %= N
        if j in (0, 8):
            return 0, len_cols, (1 if j == 0 else -1)
        if j < 8:
            return 1, abs(j - 4), (1 if j < 4 else (-1 if j > 4 else 0))
        return -1, abs(j - FRONT_MID), (1 if j > FRONT_MID else (-1 if j < FRONT_MID else 0))

    def shape(self, t):
        """(width, front, back) factors at height t, interpolated between rows."""
        rows = self.rows
        if t <= rows[0]["at"]:
            r = rows[0]
            return r["w"], r["f"], r["b"]
        for a, b in zip(rows, rows[1:]):
            if t <= b["at"]:
                k = (t - a["at"]) / max(b["at"] - a["at"], 1e-9)
                return tuple(a[q] + (b[q] - a[q]) * k for q in ("w", "f", "b"))
        r = rows[-1]
        return r["w"], r["f"], r["b"]

    def co(self, t, j, scale=1.0, relief=0.0, shape=None, cols=None):
        w, f, b = shape or self.shape(t)
        side, c, sx = self.col(j)
        xf = 1.0 if side == 0 else (cols if cols and side < 0 else self.cols)[c]
        k = (1.0 - xf ** self.pw) ** (1.0 / self.pw)
        y = 0.0 if side == 0 else (b * self.hd * k if side > 0 else -(f * k + relief) * self.hd)
        return V(sx * w * self.hw * xf * scale, self.hc + y * scale, self.zn + self.hh * t)

    def z(self, name):
        return self.zn + self.hh * self.rows[self.row[name]]["at"]

    def surface(self, name, c):
        """Front skin point of a row at face column c (left side)."""
        r = self.rows[self.row[name]]
        return self.co(r["at"], FRONT_MID + c, relief=r["relief"][c], shape=(r["w"], r["f"], r["b"]),
                       cols=r["cols"])

    # -- skin ---------------------------------------------------------------
    def build(self, mb, neck, skin, lips):
        for r in self.rows:
            ring = []
            for j in range(N):
                side, c, _ = self.col(j)
                ring.append(mb.vert(self.co(r["at"], j, relief=r["relief"][c] if side < 0 else 0.0,
                                            shape=(r["w"], r["f"], r["b"]), cols=r["cols"])))
            self.rings.append(ring)
        b = self.rings[0]
        for i in range(8):                  # 8 -> 16 under the jaw, mirrored left to right
            i1, j = (i + 1) % 8, 2 * i
            if i in (0, 1, 4, 5):
                mb.face([neck[i], b[j + 1], b[j]], skin)
                mb.face([neck[i], neck[i1], b[(j + 2) % N], b[j + 1]], skin)
            else:
                mb.face([neck[i], neck[i1], b[j + 1], b[j]], skin)
                mb.face([neck[i1], b[(j + 2) % N], b[j + 1]], skin)
        m = self.row["mouth"]
        gap = Z * self.hh * self.F["lip_gap"]
        for j in (FRONT_MID - 1, FRONT_MID, FRONT_MID + 1):
            self.low[j] = mb.vert(self.rings[m][j].co - gap)
        lip_cols = range(FRONT_MID - 2, FRONT_MID + 2)
        for k in range(len(self.rings) - 1):
            lo, hi = self.rings[k], self.rings[k + 1]
            if k + 1 == m:                  # lower lip ends on its own edge: the mouth slit
                hi = [self.low.get(j, v) for j, v in enumerate(hi)]
            for j in range(N):
                j1 = (j + 1) % N
                lip = k in (m - 1, m) and j in lip_cols
                if lip and j in (lip_cols[0], lip_cols[-1]):
                    # corner quads split on the diagonal to the mouth corner, so the
                    # lips taper to a point instead of ending as a rectangle
                    q = [lo[j], lo[j1], hi[j1], hi[j]]
                    slit = hi if k == m - 1 else lo     # the row the mouth corner is on
                    i = q.index(slit[j if j == lip_cols[0] else j1])
                    q = q[i:] + q[:i]                   # corner first, winding kept
                    first_lip = q[1] in (slit[j], slit[j1])
                    mb.face([q[0], q[1], q[2]], lips if first_lip else skin)
                    mb.face([q[0], q[2], q[3]], skin if first_lip else lips)
                    continue
                mb.face([lo[j], lo[j1], hi[j1], hi[j]], lips if lip else skin)
        mb.cap(self.rings[-1], skin, c=V(0, self.hc, self.zn + self.hh))

    def shell(self, mb, mat, scale, back_t, front_t, side_t=None, top_t=1.0):
        """Cap that follows the skull (hair, helmet). Each part of the rim stops at its own height."""
        side_t = front_t - 0.30 if side_t is None else side_t
        ts = [r["at"] for r in self.rows if r["at"] > min(back_t, front_t, side_t)]
        rings = []
        for k, t in enumerate(ts):
            ring = []
            for j in range(N):
                side, c, _ = self.col(j)
                lim = back_t if side > 0 else (side_t if side == 0 or c == len_cols - 1 else front_t)
                ring.append(mb.vert(self.co(max(t, lim + 0.004 * k), j, scale)))
            if rings:
                mb.bridge(rings[-1], ring, mat)
            rings.append(ring)
        mb.cap(rings[-1], mat, c=V(0, self.hc, self.zn + self.hh * (top_t + (scale - 1.0) * 0.9)))
        return rings

    # -- eyes, ears, brows, mouth interior ----------------------------------
    def eye_centre(self, sg=1):
        F = self.F
        p = self.surface("eye", 2)
        return V(sg * p.x, self.hc - self.hd * F["eye_depth"], p.z)

    def features(self, mb, face, mats):
        """Loose parts, skinned rigidly: eyeballs on the eye bones, the rest on the head."""
        F, hh, hd, hw, hc = self.F, self.hh, self.hd, self.hw, self.hc
        er = hh * F["eye_r"]
        keys_x = face.setdefault("keys_x", {})
        for s, sg in (("L", 1), ("R", -1)):
            c = self.eye_centre(sg)
            eye(mb, face, c, er, mats["white"], mats["iris"], mats["pupil"], mats["skin"],
                "eye." + s, "head", F["lid_open"])
            bz = self.z("brow") + hh * F["brow_up"]
            n0 = len(face["brows"])
            p = self.surface("brow", 2)
            creature.add_brow(mb, face, (sg * p.x, p.y + er * 0.25, bz),
                              (hw * F["brow_len"], er * 0.9, er * F["brow_thick"]), mats["hair"], sg)
            for i, _ in face["brows"][n0:]:
                keys_x.setdefault("BrowUp", {})[i] = Z * hh * F["brow_raise"]
            ez = (self.z("brow") + self.z("nose_base")) / 2
            eh = (self.z("brow") - self.z("nose_base")) / 2
            w = self.shape(F["ear_at"])[0] * hw
            with mb.part(bone="head"):
                mb.sphere((sg * (w + eh * F["ear_out"]), hc + hd * F["ear_back"], ez),
                          (eh * F["ear_thick"], eh * F["ear_depth"], eh), mats["skin"], n=6, m=3)
        # nostrils: dark ovals sunk into the underside of the nose, between the midline
        # and the wing
        if "nostril" in F and "nose_ala" in self.row:
            at, nr = F["nostril"][0], hh * F["nostril"][1]
            lo = self.surface("nose_base", 0).lerp(self.surface("nose_base", 1), at)
            hi = self.surface("nose_ala", 0).lerp(self.surface("nose_ala", 1), at)
            p = lo.lerp(hi, 0.5)
            with mb.part(bone="head"):
                for sg in (1, -1):
                    mb.sphere((sg * p.x, p.y, p.z), (nr * 0.8, nr * 1.4, nr * 0.7), mats["mouth"], n=6, m=3)
        # mouth: dark cavity, upper teeth on the skull, lower teeth on the jaw key
        mz = self.z("mouth")
        mw = self.surface("mouth", 2).x
        front = self.surface("mouth", 0).y
        with mb.part(bone="head"):
            mb.box((0, front + hd * 0.26, mz - hh * 0.035), (mw * 1.5, hd * 0.30, hh * 0.13), mats["mouth"])
            mb.box((0, front + hd * 0.17, mz + hh * 0.016), (mw * 0.95, hd * 0.04, hh * 0.034), mats["teeth"])
            n0 = mb.count
            mb.box((0, front + hd * 0.19, mz - hh * 0.034), (mw * 0.85, hd * 0.04, hh * 0.030), mats["teeth"])
        mb.bm.verts.ensure_lookup_table()
        for i in range(n0, mb.count):
            face["jaw_x"].append((i, self._jaw(mb.bm.verts[i].co, 1.0)))

    # -- shape keys ---------------------------------------------------------
    def _jaw(self, p, weight):
        """Offset of a point when the jaw swings open about the hinge in front of the ear."""
        F = self.F
        hinge = V(0, self.hc + self.hd * F["jaw_hinge"][0], self.zn + self.hh * F["jaw_hinge"][1])
        rot = Matrix.Rotation(math.radians(F["jaw_open"]) * weight, 3, "X")
        return hinge + rot @ (Vector(p) - hinge) - Vector(p)

    def keys(self, face):
        """Expression and viseme offsets for the skin (body-mesh vertex indices)."""
        F, hh, hd = self.F, self.hh, self.hd
        K = face.setdefault("keys", {})
        m = self.row["mouth"]
        fall = F["jaw_falloff"]             # jaw weight by face column, then the side vertex
        mw = self.surface("mouth", 2).x

        def add(key, v, d):
            K.setdefault(key, {})[v.index] = K.get(key, {}).get(v.index, Vector()) + d

        def pair(k, c):
            """(vertex, x sign) of row k at face column c, both sides."""
            return [(self.rings[k][FRONT_MID + c], 1)] + ([(self.rings[k][FRONT_MID - c], -1)] if c else [])

        # jaw: everything below the mouth line, fading towards the ears
        for k in range(m + 1):
            for j in range(N):
                side, c, _ = self.col(j)
                if side > 0:
                    continue
                wgt = fall[min(c, len(fall) - 1)]
                if k == m:
                    if j in self.low:
                        v, wgt = self.low[j], 1.0
                    else:
                        v, wgt = self.rings[k][j], wgt * F["jaw_corner"]
                else:
                    v = self.rings[k][j]
                face["jaw"].append((v.index, self._jaw(v.co, wgt)))
        # mouth corners and cheeks
        up, out, back = Z * hh, X * mw, Y * hd
        for v, sg in pair(m, 2):
            add("Smile", v, up * 0.030 + out * (0.20 * sg) + back * 0.05)
            add("Frown", v, up * -0.024 + out * (0.04 * sg))
            add("Wide", v, out * (0.22 * sg) + back * 0.05)
            add("Pucker", v, out * (-0.38 * sg) + back * -0.06)
        for name in ("nose_base", "nose_tip"):
            for c in (2, 3):
                for v, sg in pair(self.row[name], c):
                    add("Smile", v, up * 0.012 + back * -0.03)
        for k, lift in ((m + 1, 0.004), (m - 1, 0.006)):
            for c in (0, 1):
                for v, sg in pair(k, c):
                    add("Pucker", v, back * -0.08 + out * (-0.10 * sg * c))
                    add("Smile", v, up * lift)
        lows = [(self.low[FRONT_MID], 0)] + [(self.low[FRONT_MID + sg], sg) for sg in (1, -1)]
        for v, sg in lows:
            add("Pucker", v, back * -0.07 + up * -0.010 + out * (-0.10 * sg))
            add("Wide", v, up * -0.014)
            add("Smile", v, up * (-0.004 if sg == 0 else 0.004))
        for c in (0, 1):
            for v, sg in pair(m, c):
                add("Pucker", v, back * -0.07 + up * 0.006 + out * (-0.10 * sg * c))
        # brows: the ridge follows the brow blocks
        for c in (1, 2, 3):
            for v, sg in pair(self.row["brow"], c):
                add("BrowUp", v, up * F["brow_raise"] * 0.5)
                if c == 1:
                    add("Frown", v, up * -0.012)


len_cols = 4        # face columns between the midline and the side vertex


def eye(mb, face, c, r, white, iris, pupil, lid_mat, bone, lid_bone, lid_open):
    """Eyeball with iris and pupil on its own bone, and two lids that Blink closes."""
    c = Vector(c)
    with mb.part(bone=bone):
        mb.sphere(c, r, white, n=8, m=5)
        mb.sphere(c - Y * r * 0.58, r * 0.52, iris, n=8, m=3)
        mb.sphere(c - Y * r * 0.93, r * 0.19, pupil, n=6, m=2)
    start = mb.count
    cols = 12
    rings = 11                              # lid sphere rings, 15 deg apart: equator ring, then +15 deg
    edge = math.pi / (rings + 1)
    up_at, dn_at = (math.radians(a) for a in lid_open)
    # the pupil reaches 1.12 r; the shut lid's flat facets (not just its vertices) must
    # clear it, or the closed lid shows the iris through it. Shut, the upper lid's
    # segments stretch from dn_at to the pole, so that is the facet size that counts.
    span = (math.pi / 2 - dn_at + 0.07) / round((math.pi / 2 - edge) / edge)
    big = r * 1.13 / (math.cos(math.pi / cols) * math.cos(span / 2))
    with mb.part(bone=lid_bone):
        mb.sphere(c, big, lid_mat, n=cols, m=rings)
    mb.bm.verts.ensure_lookup_table()
    # the band between those two rings is the eye opening: without removing it the
    # lid covers the whole eyeball
    band = [f for f in mb.bm.faces if all(v.index >= start for v in f.verts)
            and min(v.co.z for v in f.verts) > c.z - big * 0.01
            and max(v.co.z for v in f.verts) < c.z + big * (math.sin(edge) + 0.01)]
    bmesh.ops.delete(mb.bm, geom=band, context="FACES_ONLY")
    mb.bm.verts.ensure_lookup_table()
    for i in range(start, mb.count):
        v = mb.bm.verts[i]
        rel = v.co - c
        lat = math.asin(max(-1.0, min(1.0, rel.z / big)))
        flat = Vector((rel.x, rel.y, 0.0))
        d = flat.normalized() if flat.length > 1e-6 else Vector()

        def at(a):
            return c + (d * math.cos(a) + Z * math.sin(a)) * big

        if lat > edge / 2:                     # upper lid: gathered above the eye, slides down to close
            u = max(0.0, (lat - edge) / (math.pi / 2 - edge))
            rest = up_at + u * (math.pi / 2 - up_at)
            shut = dn_at - 0.07 + u * (math.pi / 2 - dn_at + 0.07)
        else:                               # lower lid stays put
            u = min(1.0, (lat + math.pi / 2) / (math.pi / 2))
            rest = shut = -math.pi / 2 + u * (math.pi / 2 + dn_at)
        v.co = at(rest)
        face["lids"].append((i, at(shut) - v.co))
