"""Run every numeric gate for one input file and print one line per gate.

    $BL --background --python tools/gates.py -- out/t_char.md [--sweep] [--rebase]

Steps (each a separate headless Blender run):
  check    build.py --check: 0 warnings, no error
  anatomy  every `anatomy:` line has 0 errors and 0 warnings
  build    full build saved to out/<stem>.blend (what tools/live_view.py shows)
  anim     tools/check_anims.py: ik_miss == 0, lowest >= 0
  rig/face/uv/deform  tools/check_character.py (characters only)
  sweep    (--sweep) --check on every out/t_*.md and examples/*; fails if any
           scene has more warnings or errors than out/sweep_baseline.json.
           --rebase rewrites the baseline from this run.

Last line: `GATES: <n> fail` and exit code 0 (all pass) or 1. Runs on Blender's
own Python; standard library only.
"""
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
BASELINE = os.path.join(OUT, "sweep_baseline.json")
JOBS = 4

try:
    import bpy
    BL = bpy.app.binary_path
except ImportError:                                  # plain Python: pass the exe in BLENDER
    BL = os.environ.get("BLENDER", "blender")

FAILS = []


def gate(name, ok, text):
    print("GATE %-8s %-4s %s" % (name, "ok" if ok else "FAIL", text))
    if not ok:
        FAILS.append(name)


def blender(args):
    return subprocess.Popen([BL, "--background"] + args, cwd=ROOT,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")


def run(args):
    p = blender(args)
    out, _ = p.communicate()
    return p.returncode, out


def forge_lines(out):
    return [l[len("[forge] "):] for l in out.splitlines() if l.startswith("[forge] ")]


def build_check(src, dst):
    """--check one file -> (exit code, warnings, anatomy errors, anatomy warnings, error text)."""
    code, out = run(["--python", "build.py", "--", src, dst, "--check"])
    lines = forge_lines(out)
    warn = err_a = warn_a = 0
    error = ""
    for l in lines:
        m = re.match(r"check: \d+ entit\w+, (\d+) warning", l)
        if m:
            warn = int(m.group(1))
        m = re.match(r"anatomy: .*?: (?:(\d+) errors?, )?(\d+) warnings?", l)
        if m:
            err_a += int(m.group(1) or 0)
            warn_a += int(m.group(2))
        if l.startswith("error") or "internal error" in l:
            error = l
    if "Traceback" in out and not error:
        error = "traceback"
    return code, warn, err_a, warn_a, error, lines


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    files = [a for a in argv if not a.startswith("--")]
    if len(files) != 1:
        print(__doc__)
        return 2
    src = os.path.abspath(files[0])
    stem = os.path.splitext(os.path.basename(src))[0]
    blend = os.path.join(OUT, stem + ".blend")

    code, warn, err_a, warn_a, error, lines = build_check(src, blend)
    gate("check", code == 0 and not error and warn == 0,
         error or "%d warning%s" % (warn, "" if warn == 1 else "s"))
    for l in lines:
        if ": warning: " in l or l.startswith("error"):
            print("     " + l.split(": warning: ", 1)[-1])
    anat = [l for l in lines if l.startswith("anatomy:") and " source: " not in l]
    template = dict(re.findall(r"anatomy: (\S+) \((\w+)", " ".join(anat)))   # name -> template
    gate("anatomy", err_a == 0 and warn_a == 0,
         "%d entit%s, %d errors, %d warnings" % (len(anat), "y" if len(anat) == 1 else "ies", err_a, warn_a))
    if code or error:
        return finish(argv)

    code, out = run(["--python", "build.py", "--", src, blend])
    gate("build", code == 0 and "Traceback" not in out, os.path.relpath(blend, ROOT))
    if code:
        return finish(argv)

    code, out = run([blend, "--python", "tools/check_anims.py"])
    bad = []
    n = 0
    for l in out.splitlines():
        m = re.match(r"ANIM (\S+)\s+(\S+)\s+ik_miss=([\d.]+) lowest=(-?[\d.]+)", l)
        if m:
            n += 1
            if float(m.group(3)) > 0.0005 or float(m.group(4)) < -0.0005:
                bad.append("%s %s ik_miss=%s lowest=%s" % m.groups())
    gate("anim", not bad, "; ".join(bad) or "%d action%s" % (n, "" if n == 1 else "s"))

    code, out = run([blend, "--python", "tools/check_character.py"])
    for l in out.splitlines():
        if not l.startswith("CHAR "):
            continue
        body = l[5:].strip()
        m = re.search(r"max_influences=(\d+) unweighted=(\d+) idle_bones=(\S+)", body)
        if m:
            gate("rig", int(m.group(1)) <= 4 and m.group(2) == "0" and m.group(3) == "none", body)
        m = re.search(r"face: (\d+) keys", body)
        if m:      # humans get the 7-key facial rig, animals the base 4
            need = 7 if template.get(body.split()[0]) == "humanoid" else 4
            gate("face", int(m.group(1)) >= need, body)
        if " uv: " in " " + body:
            gate("uv", "gate=ok" in body, body)
        if " deform " in body:
            gate("deform", "gate=ok" in body, body)

    if "--sweep" in argv:
        sweep("--rebase" in argv)
    return finish(argv)


def sweep(rebase):
    scenes = sorted(glob.glob(os.path.join(OUT, "t_*.md")))
    scenes += sorted(f for f in glob.glob(os.path.join(ROOT, "examples", "*"))
                     if f.endswith((".md", ".txt")))
    tmp = os.path.join(OUT, "_sweep")
    os.makedirs(tmp, exist_ok=True)
    now = {}
    for i in range(0, len(scenes), JOBS):
        batch = scenes[i:i + JOBS]
        procs = [(s, blender(["--python", "build.py", "--", s,
                              os.path.join(tmp, os.path.splitext(os.path.basename(s))[0] + ".blend"),
                              "--check"])) for s in batch]
        for s, p in procs:
            out, _ = p.communicate()
            warn = sum(int(m) for m in re.findall(r"check: \d+ entit\w+, (\d+) warning", out))
            errs = sum(int(m) for m in re.findall(r"anatomy: .*?: (\d+) errors?,", out))
            failed = int(p.returncode != 0 or "Traceback" in out)
            now[os.path.relpath(s, ROOT).replace("\\", "/")] = [failed, errs, warn]
    if rebase or not os.path.isfile(BASELINE):
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(now, fh, indent=1, sort_keys=True)
        gate("sweep", True, "%d scenes, baseline written" % len(now))
        return
    with open(BASELINE, encoding="utf-8") as fh:
        base = json.load(fh)
    worse = ["%s %s->%s" % (k, base.get(k), v) for k, v in sorted(now.items())
             if any(a > b for a, b in zip(v, base.get(k, [0, 0, 0])))]
    gate("sweep", not worse, "; ".join(worse) or "%d scenes, nothing worse than baseline" % len(now))


def finish(argv):
    print("GATES: %d fail%s" % (len(FAILS), (" (" + ", ".join(FAILS) + ")") if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    if code:
        sys.exit(code)
