---
name: fix-loop
description: Unattended build-check-look-fix loop for one BlenderForge input file. Runs the numeric gates, looks at the model in the live Blender from the angles that matter, fixes issues in forge/, and stops at a cap. Use when the user says "fix loop", "/fix-loop", or asks to fix a model's issues automatically.
---

# Fix loop

Argument: one input file (default `out/t_char.md`) and optionally the problem to focus on.
Work without asking the user. Stop only when done, at a cap, or when a stop rule below fires.
`$BL` = `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`. `<stem>` = input file name without extension.

## 0. Set up (once)
1. Checkpoint: `git stash create` (prints a commit id; empty output means the tree is clean, use `git rev-parse HEAD`). Note it as `start`. Never commit, push, stash-apply or reset; the user commits.
2. Log file: append to `out/fixloop/<stem>.md` (create it). One block per round.
3. Live or headless: call `get_addon_status`.
   - If it fails, start the viewer in the background: `"$BL" out/<stem>.blend --python tools/live_view.py` (after step 1 of the first round has built the file), wait a few seconds and retry once.
   - Still failing: headless mode. Use `--render --view <angle> --resolution 640x360` images instead of `look` and say so in the log.

## 1. Round
1. Numbers: `"$BL" --background --python tools/gates.py -- <input> --sweep 2>&1 | grep "GATE\|^     \|Traceback"`.
   The first round with no `out/sweep_baseline.json` writes one; never pass `--rebase` yourself.
2. If any gate fails, fix that first (section 2) without looking at images. Order: check, anatomy, build, rig, anim, deform, face, uv, sweep.
3. When every gate passes, look:
   - Confirm the viewer shows this build: `out/<stem>.blend.live` must equal the file's `st_mtime_ns`. Retry for up to ~10 s.
   - `get_scene_info` for the character names. Call `look` with `mode: "angles"`, `target: ["<Name>"]` (whole body) or `["F_<Name>_<bone>"]` with `distance` (zoom on head, hand, foot), `max_size` 512 and the 2-3 views from the "Views by problem" table in `forge/WORKFLOW.md` for the current stage or focus. A failed call right after a build is normal: retry once.
   - Before fixing anything seen in an image, confirm it with a number (a short headless script in the scratchpad on `out/<stem>.blend`). Images give false positives: in the first trial the eyes looked turned sideways but measured straight ahead.
   - Judge only against that stage's gate text in `forge/WORKFLOW.md`. Name each problem in one line (what, where, which view).
   - Nothing wrong: the gate passes; move to the next stage or problem. Nothing left: stop (section 4).
4. Fix one problem (section 2), then go back to step 1. A fix counts only when every gate still passes and the sweep reports nothing worse.

## 2. Fixing rules
- Before editing, record a round checkpoint with `git stash create` (or HEAD when the tree is clean).
- Data before code: change the profile in `forge/anatomy/data/*.json` before `forge/templates/*.py`, `face.py`, `creature.py`.
- Never change a value that comes from `measured.json` or carries a `cite`. Add an override with `_about` saying "approximation (visual fix-loop)" instead.
- No proportion numbers in templates. Keep left/right mirrored, no randomness, standard library plus bpy only.
- Smallest change that fixes the problem. One problem per round.
- If the round made things worse (a gate that passed now fails, or the sweep got worse), undo it: `git checkout <round checkpoint> -- forge/` (for a clean tree use `git checkout HEAD -- <files you changed>`). Log it as reverted.

## 3. Caps
- At most 3 rounds per problem. After the third, log it as "needs review" and move on.
- At most 12 rounds per run.
- A problem that needs a judgement only a person can make (likeness, style, "looks right") goes straight to "needs review".

## 4. Finish
1. Run the gates once more with `--sweep`.
2. Log block: rounds used, fixed, reverted, needs review, final gate line.
3. Add a short entry to `PROGRESS.md` under the relevant pass (what changed, what still needs review).
4. Report to the user: what was fixed (files), what needs review, the `start` checkpoint for undoing everything (`git checkout <start> -- forge/`), and that nothing was committed.

## Log block format (out/fixloop/<stem>.md)
```
## Round <n> - <gate or problem>
seen: <one line, view(s)>
change: <file: what>
result: <GATES line> | reverted | needs review
```
