"""Character gates as numbers: a few CHAR lines per rigged character.

    blender --background scene.blend --python tools/check_character.py 2>&1 | grep CHAR

rig     bone counts, most bones on one vertex, vertices whose weights do not sum
        to 1, deform bones that move nothing
face    shape keys present (expressions and visemes)
deform  per action, worst case over the cycle, measured on the cage
        (edges shorter than 1.2 % of the figure are skipped):
        stretch  longest edge / its rest length, and the bone it follows
        squash   shortest edge / its rest length, and the bone it follows
        volume   lowest and highest mesh volume / rest volume
A clean limb bend stays near stretch 1.5, squash 0.5 and volume 0.95-1.05.
Read `forge/WORKFLOW.md` for the limits each stage has to meet.
"""
import bmesh
import bpy

STEP = 3            # sample every third frame
DETAIL = "--detail" in __import__("sys").argv      # also print the worst edge of each action

sc = bpy.context.scene


def volume(mesh):
    bm = bmesh.new()
    bm.from_mesh(mesh)
    v = abs(bm.calc_volume(signed=True))
    bm.free()
    return v


for arm in sorted((o for o in bpy.data.objects if o.type == "ARMATURE"), key=lambda o: o.name):
    skins = [o for o in arm.children if o.type == "MESH" and any(m.type == "ARMATURE" for m in o.modifiers)]
    if not skins:
        continue
    obj = skins[0]
    me = obj.data
    name = arm.name.replace("_Rig", "")
    names = {g.index: g.name for g in obj.vertex_groups}
    deform = [b.name for b in arm.data.bones if b.use_deform]
    used, owner, most, loose = set(), [], 0, 0
    for v in me.vertices:
        ws = sorted(((g.weight, names[g.group]) for g in v.groups if names[g.group] in deform), reverse=True)
        most = max(most, len(ws))
        loose += abs(sum(w for w, _ in ws) - 1.0) > 0.01
        used.update(n for w, n in ws if w > 0.05)
        owner.append(ws[0][1] if ws else "-")
    idle = sorted(set(deform) - used)
    print("CHAR %-8s rig: bones=%d deform=%d max_influences=%d unweighted=%d idle_bones=%s"
          % (name, len(arm.data.bones), len(deform), most, loose, ",".join(idle) or "none"))
    keys = [k.name for k in me.shape_keys.key_blocks[1:]] if me.shape_keys else []
    print("CHAR %-8s face: %d keys %s" % (name, len(keys), ",".join(keys)))

    # UVs (forge/WORKFLOW.md stage 4): every face mapped, inside the 0-1 square
    uv = me.uv_layers.active
    if uv:
        flat, out, area = 0, 0, 0.0
        for p in me.polygons:
            pts = [uv.data[i].uv for i in p.loop_indices]
            a = abs(sum(pts[i].x * pts[(i + 1) % len(pts)].y - pts[(i + 1) % len(pts)].x * pts[i].y
                        for i in range(len(pts)))) / 2
            area += a
            flat += a < 1e-9
            out += any(not (-1e-4 <= c <= 1.0001) for q in pts for c in q)
        print("CHAR %-8s uv: map=%s faces=%d unmapped=%d outside=%d fill=%.2f gate=%s"
              % (name, uv.name, len(me.polygons), flat, out, area,
                 "ok" if not flat and not out and area <= 1.0 else "FAIL"))
    else:
        print("CHAR %-8s uv: none gate=FAIL" % name)

    ad = arm.animation_data
    if not ad or not ad.nla_tracks:
        continue
    hidden = [m for m in obj.modifiers if m.type == "SUBSURF" and m.show_viewport]
    for m in hidden:
        m.show_viewport = False
    kad = me.shape_keys.animation_data if me.shape_keys else None
    kmute = [(t, t.mute) for t in kad.nla_tracks] if kad else []
    for t, _ in kmute:
        t.mute = True
    edges = [(e.vertices[0], e.vertices[1]) for e in me.edges]
    rest = [(me.vertices[a].co - me.vertices[b].co).length for a, b in edges]
    vol0 = volume(me) or 1.0
    short = 0.012 * (max(arm.dimensions) or 1.0)     # tiny edges exaggerate every ratio
    state = [(t, t.mute) for t in ad.nla_tracks]
    for tr in ad.nla_tracks:
        for t2 in ad.nla_tracks:
            t2.mute = t2 != tr
        act = tr.strips[0].action
        hi, lo, hi_at, lo_at, v_lo, v_hi = 1.0, 1.0, "-", "-", 1.0, 1.0
        hi_e = None
        for f in range(int(act.frame_start), int(act.frame_end) + 1, STEP):
            sc.frame_set(f)
            ev = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            m2 = ev.to_mesh()
            co = [v.co.copy() for v in m2.vertices]
            r = volume(m2) / vol0
            ev.to_mesh_clear()
            v_lo, v_hi = min(v_lo, r), max(v_hi, r)
            for (a, b), l0 in zip(edges, rest):
                if l0 < short:
                    continue
                k = (co[a] - co[b]).length / l0
                if k > hi:
                    hi, hi_at, hi_e = k, owner[a], (f, a, b)
                elif k < lo:
                    lo, lo_at = k, owner[a]
        # gate (forge/WORKFLOW.md stage 6): skin on a ball-joint bone may shear further
        ball = hi_at.split(".")[0] in ("upper_arm", "thigh", "shoulder")
        bad = [n for n, ok in (("stretch", round(hi, 2) <= (1.9 if ball else 1.6)),
                               ("squash", round(lo, 2) >= 0.45),
                               ("volume", round(v_lo, 2) >= 0.95 and round(v_hi, 2) <= 1.05)) if not ok]
        print("CHAR %-8s deform %-6s stretch=%.2f@%s squash=%.2f@%s volume=%.2f-%.2f gate=%s"
              % (name, tr.name, hi, hi_at, lo, lo_at, v_lo, v_hi, "FAIL:" + ",".join(bad) if bad else "ok"))
        if DETAIL and hi_e:
            # the worst edge: frame, rest position and weights of both ends
            print("CHAR %-8s   worst %-6s frame=%d rest_len=%.3f" % (name, tr.name, hi_e[0], (me.vertices[hi_e[1]].co - me.vertices[hi_e[2]].co).length))
            for i in hi_e[1:]:
                v = me.vertices[i]
                ws = sorted(((g.weight, names[g.group]) for g in v.groups if g.weight > 0.01), reverse=True)
                print("CHAR %-8s     v%d (%.3f %.3f %.3f) %s" % (name, i, v.co.x, v.co.y, v.co.z, " ".join("%s=%.2f" % (n, w) for w, n in ws)))
    for t, m in state + kmute:
        t.mute = m
    for m in hidden:
        m.show_viewport = True
