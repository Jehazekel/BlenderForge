# BlenderForge

Builds rigged 3D characters, animals, structures and maps in Blender from a text file. Deterministic Python on `bpy`/`bmesh`; no network, no AI at build time.

## Commands
Blender: `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe` (call it `$BL`). Runs take 1-10 s.
- Check only (no render, save or export): `$BL --background --python build.py -- in.md out/x.blend --check`
- Build + preview: add `--render --resolution 640x360` instead of `--check`
- Templates: `$BL --background --python build.py -- --list`
- Animations: build a `.blend`, then `$BL --background x.blend --python tools/check_anims.py 2>&1 | grep ANIM` (one line per action: IK reach, lowest bone, sharpest bend).
- Characters: `tools/check_character.py` (same way, `grep CHAR`): rig, shape keys, stretch/squash/volume per action; add `-- --detail` for the worst edge (frame, position, weights). Views: `--view sheet` (six angles, one image) or `face`, `side`, ...; `--focus NAME`.
- Character work follows the nine stages and gates in `forge/WORKFLOW.md`; test file `out/t_char.md`.

## Keeping sessions cheap
- Verify with `--check` first. Each creature prints one `anatomy:` line (errors, warnings, key sizes); that is the test result.
- Pipe build output through `grep "forge\]\|Traceback"`; Blender's own log is noise. For a regression sweep keep only `grep "check:\|warning:\|Traceback"` (one line per scene).
- Check animations with `tools/check_anims.py` numbers before rendering a frame.
- Look at a render only when shape matters, at 640x360, one image per change.
- Do not read `out/`, `*.anatomy.json` or `forge/anatomy/data/measured.json` whole; grep for the entity or key.
- Read `PROGRESS.md` for status instead of re-exploring; update it when a piece of work lands.

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
