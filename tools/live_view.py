"""Live viewer: reload a .blend in the Blender GUI each time a build rewrites it.

Builds stay headless (build.py); this window only shows the result.

    $BL out/x.blend --python tools/live_view.py
    $BL --python tools/live_view.py -- out/x.blend     (file may not exist yet)

The current layout and viewport angle are kept across reloads (load_ui=False).
For zooming, every bone gets a focus point `F_<character>_<bone>` (see _view_only).
After each load it writes <file>.live holding the loaded file's mtime_ns, so a
script can tell when the window shows the latest build. The window is view-only:
a reload discards anything changed by hand.
"""
import os
import sys

import bpy

POLL = 0.5  # seconds


def _target():
    argv = sys.argv
    if "--" in argv and argv.index("--") + 1 < len(argv):
        return os.path.abspath(argv[argv.index("--") + 1])
    if bpy.data.filepath:
        return bpy.data.filepath
    print("[live] usage: blender out/x.blend --python tools/live_view.py")
    return None


TARGET = _target()
_state = {"loaded": None, "seen": None}


def _mtime():
    try:
        return os.stat(TARGET).st_mtime_ns
    except OSError:
        return None


def _view_only():
    """Viewer-side additions (never saved; a reload rebuilds them).

    - Rigs hidden (bones poke through eyes and skin), so shape can be judged.
    - A focus point `F_<character>_<bone>` at the middle of every bone, following the
      animation, so `look` can zoom anywhere: target=["F_Adult_head"], distance=0.5.
    """
    from mathutils import Matrix
    rigs = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    for rig in rigs:
        rig.hide_set(True)      # still deforms the mesh; only the bone display goes
        who = rig.name[:-len("_Rig")] if rig.name.endswith("_Rig") else rig.name
        for pb in rig.pose.bones:
            name = "F_%s_%s" % (who, pb.name)
            if name in bpy.data.objects:
                continue
            e = bpy.data.objects.new(name, None)
            e.empty_display_type = "PLAIN_AXES"
            e.empty_display_size = 0.005
            e.hide_render = e.hide_select = True
            bpy.context.scene.collection.objects.link(e)
            e.parent, e.parent_type, e.parent_bone = rig, "BONE", pb.name
            e.matrix_world = rig.matrix_world @ pb.matrix @ Matrix.Translation((0, pb.length / 2, 0))


def _mark(mtime):
    _view_only()
    _state["loaded"] = mtime
    with open(TARGET + ".live", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("%d\n" % mtime)


def _poll():
    m = _mtime()
    if m is None or m == _state["loaded"]:
        _state["seen"] = None
        return POLL
    if m != _state["seen"]:      # changed since last poll: wait until it settles
        _state["seen"] = m
        return POLL
    try:
        bpy.ops.wm.open_mainfile(filepath=TARGET, load_ui=False)
    except RuntimeError as exc:
        print("[live] reload failed: %s" % str(exc).strip().splitlines()[-1])
        return POLL
    _mark(m)
    print("[live] reloaded %s" % os.path.basename(TARGET))
    return POLL


if TARGET and not bpy.app.background:
    if bpy.data.filepath and os.path.normcase(bpy.data.filepath) == os.path.normcase(TARGET):
        m = _mtime()
        if m is not None:
            _mark(m)
    if not bpy.app.timers.is_registered(_poll):
        bpy.app.timers.register(_poll, first_interval=POLL, persistent=True)
    print("[live] watching %s" % TARGET)
