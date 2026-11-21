# BlenderForge

Builds rigged 3D characters, animals, structures and maps in Blender from a text file. Deterministic Python on `bpy`/`bmesh`; no network, no AI at build time.

## Commands
Blender: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` (call it `$BL`). Runs take 1-10 s.
- Check only (no render, save or export): `$BL --background --python build.py -- in.md out/x.blend --check`
- Build + preview: add `--render --resolution 640x360` instead of `--check`
- Templates: `$BL --background --python build.py -- --list`
- Animations: build a `.blend`, then `$BL --background x.blend --python tools/check_anims.py 2>&1 | grep ANIM` (one line per action: IK reach, lowest bone, sharpest bend).
- Characters: `tools/check_character.py` (same way, `grep CHAR`): rig, shape keys, stretch/squash/volume per action; add `-- --detail` for the worst edge (frame, position, weights). Views: `--view sheet` (six angles, one image) or `face`, `side`, ...; `--focus NAME`.
- All numeric gates at once: `$BL --background --python tools/gates.py -- in.md [--sweep]` (one `GATE` line each, last line `GATES: n fail`; `--sweep` compares 18 scenes with `out/sweep_baseline.json`, ~50 s).
- Character work follows the nine stages and gates in `forge/WORKFLOW.md`; test file `out/t_char.md`.

## Keeping sessions cheap
- Verify with `--check` first. Each creature prints one `anatomy:` line (errors, warnings, key sizes); that is the test result.
- Pipe build output through `grep "forge\]\|Traceback"`; Blender's own log is noise. For a regression sweep keep only `grep "check:\|warning:\|Traceback"` (one line per scene).
- Check animations with `tools/check_anims.py` numbers before rendering a frame.
- Look at a render only when shape matters, at 640x360, one image per change.
- Do not read `out/`, `*.anatomy.json` or `forge/anatomy/data/measured.json` whole; grep for the entity or key.
- Read `PROGRESS.md` for status instead of re-exploring; update it when a piece of work lands.

## Live mode (Blender MCP, optional)
Headless `build.py` stays the only builder and the only result that counts. Live mode adds a GUI window to watch and `look` at.
- Viewer: `$BL out/x.blend --python tools/live_view.py` reloads after each build, keeps your view, writes `out/x.blend.live` (loaded mtime_ns). Minimized works.
- Before `look`, confirm `x.blend.live` matches the file's mtime_ns, so you see the latest build.
- `look` only after the number checks pass. Use `mode: "angles"`, 2-3 views picked from `forge/WORKFLOW.md` "Views by problem", `max_size` <= 512. Always pass `target`: the mesh `<Name>` for the whole body (untargeted framing includes the 144 m `PreviewGround`), or a focus point `F_<Name>_<bone>` plus `distance` to zoom (`F_Adult_head` 0.55, `F_Adult_hand.L` 0.4). The viewer hides rigs and adds these points; they are never saved. Eyes read badly in `solid`; use `material` for faces. The server restarts on each reload, so one failed call right after a build is normal; retry once.
- Allowed: `look`, `get_scene_info`, `get_addon_status`. `execute_blender_code` asks first. Generators and asset imports are denied (`.claude/settings.json`).
- Fixes go into `forge/` (profiles before code) and must pass headless `--check` plus the regression sweep. Never change measured or cited values to fix a look; add an override marked approximation.
- At most 3 look-fix rounds per gate, then log it in `PROGRESS.md` as needing review. Commit once per round.
- Unattended fixing: the `fix-loop` skill (`/fix-loop out/t_char.md`) runs gates, looks, fixes, with caps and a log in `out/fixloop/`.
- No live Blender (`get_addon_status` fails)? Use headless `--render --view ...` instead.

## Architecture
Creatures follow four layers; keep them apart:
1. `forge/anatomy/data/*.json` — profiles (pure data, with `inherits`). New species or body type = new entry, not new code.
2. `forge/anatomy/skeleton.py` (tetrapods), `biped.py` (humans) — profile + size -> landmarks and measures. No `bpy`.
3. `forge/templates/*.py` — geometry and bones placed only on solved landmarks. Human head and face: `forge/face.py`, driven by the `face` block in `humans.json`.
4. `forge/creature.py`, `scene.py` — skinning, shape keys, animation, render, export.

`forge/anatomy/validate.py` checks measures against per-class `limits` in `classes.json`.

## Rules
- No proportion numbers in templates; put them in the profile and record where they came from (`_sources`, `cite`, or say "approximation" in `_about`).
- Faces -Y, stands on z = 0, left is +X. Left/right must mirror exactly; `check_cage` enforces it.
- Same input must give the same output: no `random`, no time, no dict-order dependence.
- Standard library, `bpy`, `bmesh`, `mathutils` only.
