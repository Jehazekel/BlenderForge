"""BlenderForge: deterministic, procedural 3D assets from a text file.

    blender --background --python build.py -- input.md output.blend [options]

Options (after the two positional paths):
    --export glb,fbx,stl     also export next to the .blend
    --render [preview.png]   render a low-sample still (default: <output>.png)
    --engine eevee|workbench|cycles
    --samples N              render samples (default 16)
    --resolution WxH         render size (default 1280x720)
    --frame N                frame to render
    --view NAME              front, side, back, three_quarter, face, face_side,
                             face_three_quarter, or sheet (six views in one image)
    --focus NAME             entity the camera frames (default: everything)
    --lowpoly                game-ready meshes, no subdivision or bevel modifiers
    --fps N                  animation frame rate
    --base existing.blend    open this file and add / replace / edit entities in it
    --list                   print the available templates and exit
    --check                  build and validate only: no preview, render, export or save

Only bpy, bmesh, mathutils and the Python standard library are used.
"""

import os
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

USAGE = "usage: blender --background --python build.py -- input.md output.blend [options]"


def parse_args(argv):
    args = argv[argv.index("--") + 1:] if "--" in argv else []
    opts = {"export": None, "render": None, "engine": None, "samples": None, "resolution": None,
            "frame": None, "lowpoly": None, "fps": None, "base": None, "check": False,
            "view": None, "focus": None}
    paths, do_list, want_render = [], False, False
    i = 0
    while i < len(args):
        a = args[i]
        nxt = args[i + 1] if i + 1 < len(args) else None

        def value():
            if nxt is None or nxt.startswith("--"):
                raise SystemExit("error: %s needs a value\n%s" % (a, USAGE))
            return nxt

        if a == "--export":
            opts["export"] = [f.strip() for f in value().split(",") if f.strip()]
            i += 1
            # PowerShell splits "glb,fbx" into separate arguments; accept those too.
            while i + 1 < len(args) and args[i + 1].lower() in ("glb", "gltf", "fbx", "stl"):
                opts["export"].append(args[i + 1])
                i += 1
        elif a == "--render":
            want_render = True
            if nxt is not None and not nxt.startswith("--") and nxt.lower().endswith(".png"):
                opts["render"] = nxt
                i += 1
        elif a in ("--engine", "--base", "--view", "--focus"):
            opts[a[2:]] = value()
            i += 1
        elif a in ("--samples", "--frame", "--fps"):
            try:
                opts[a[2:]] = int(value())
            except ValueError:
                raise SystemExit("error: %s expects a whole number" % a)
            i += 1
        elif a == "--resolution":
            try:
                w, h = value().lower().split("x")
                opts["resolution"] = (int(w), int(h))
            except ValueError:
                raise SystemExit("error: --resolution expects WxH, e.g. 1280x720")
            i += 1
        elif a == "--lowpoly":
            opts["lowpoly"] = True
        elif a == "--check":
            opts["check"] = True
        elif a == "--list":
            do_list = True
        elif a.startswith("--"):
            raise SystemExit("error: unknown option %s\n%s" % (a, USAGE))
        else:
            paths.append(a)
        i += 1
    return paths, opts, do_list, want_render


def main():
    from forge import core, log, parser, scene

    paths, opts, do_list, want_render = parse_args(sys.argv)
    if do_list:
        names = core.load_templates()
        by_mod = {}
        for n, mod in names.items():
            by_mod.setdefault(mod.__name__.split(".")[-1], []).append(n)
        for mod in sorted(by_mod):
            print("%-10s %s" % (mod, ", ".join(by_mod[mod])))
        return 0
    if len(paths) != 2:
        print(USAGE)
        return 2
    src, out = os.path.abspath(paths[0]), os.path.abspath(paths[1])
    if not out.lower().endswith(".blend"):
        out += ".blend"
    out_base = out[:-len(".blend")]
    log.set_source(os.path.basename(src))
    if opts["engine"] and opts["engine"] not in scene.ENGINES:
        print("error: --engine must be one of %s" % ", ".join(scene.ENGINES))
        return 2
    if opts["view"] and opts["view"] != "sheet" and opts["view"] not in scene.VIEWS:
        print("error: --view must be one of %s, sheet" % ", ".join(scene.VIEWS))
        return 2

    try:
        if not os.path.isfile(src):
            raise log.ForgeError("input file not found: %s" % src)
        specs = parser.parse_file(src)
        settings = scene.read_settings(specs, opts)
        if want_render and not settings["render"]:
            settings["render"] = out_base + ".png"
        elif settings["render"]:
            text = settings["render"]
            if text.lower() in ("true", "yes", "on"):
                settings["render"] = out_base + ".png"
            elif not os.path.isabs(text):
                settings["render"] = os.path.join(os.path.dirname(out), text)
        os.makedirs(os.path.dirname(out), exist_ok=True)

        t0 = time.perf_counter()
        sc, ctx, entities = scene.build_all(specs, settings, os.path.dirname(src))
        log.info("built %d entit%s in %.1f s" % (len(entities), "y" if len(entities) == 1 else "ies",
                                                 time.perf_counter() - t0))
        if opts["check"]:
            n = log.warning_count()
            print("[forge] check: %d entit%s, %d warning%s (nothing saved)"
                  % (len(entities), "y" if len(entities) == 1 else "ies", n, "" if n == 1 else "s"))
            return 0
        scene.setup_preview(sc, entities, settings)
        if settings["frame"] is not None:
            sc.frame_set(settings["frame"])
        else:
            sc.frame_set(sc.frame_start + (sc.frame_end - sc.frame_start) // 4)
        if settings["render"]:
            t0 = time.perf_counter()
            if settings["view"] == "sheet":
                done = scene.render_sheet(sc, entities, settings["render"], settings)
            else:
                done = scene.render_preview(sc, settings["render"], settings)
            if done:
                log.info("render took %.1f s" % (time.perf_counter() - t0))
        if settings["export"]:
            scene.export(entities, out_base, settings["export"])
        sc.frame_set(sc.frame_start)
        scene.save(out)
        from forge.anatomy import validate
        if validate.REPORTS:
            import json
            with open(out_base + ".anatomy.json", "w", encoding="utf-8", newline="\n") as fh:
                json.dump({"animals": validate.REPORTS}, fh, indent=1, sort_keys=True)
            log.info("saved %s" % (out_base + ".anatomy.json"))
    except log.ForgeError as exc:
        print("[forge] " + exc.format())
        return 1
    except Exception:
        traceback.print_exc()
        print("[forge] internal error while building (see traceback above)")
        return 1
    n = log.warning_count()
    print("[forge] done: %d entit%s, %d warning%s"
          % (len(entities), "y" if len(entities) == 1 else "ies", n, "" if n == 1 else "s"))
    return 0


if __name__ == "__main__":
    code = main()
    if code:
        sys.exit(code)
