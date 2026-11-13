# Character workflow

Nine stages. Finish one to its gate before starting the next. Each gate is a
number or one image, so a session can check it cheaply.

Test file: `out/t_char.md` (one unclothed adult, every animation, `view: sheet`).
`$BL` = `C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`.

## Cheap checks, in cost order

| Cost | Command | Output |
|---|---|---|
| ~1 s | `$BL --background --python build.py -- in.md out/x.blend --check` | one `anatomy:` line per character (body and face ratios against `classes.json` limits) |
| ~2 s | `$BL --background x.blend --python tools/check_anims.py 2>&1 \| grep ANIM` | IK reach, lowest bone, sharpest bend per action |
| ~5 s | `$BL --background x.blend --python tools/check_character.py 2>&1 \| grep CHAR` | rig counts, shape keys, per-action stretch / squash / volume |
| ~6 s + image | `--render --view sheet --resolution 960x540 --frame 1` | front, side, 3/4 of body and face in one image |

Look at an image only when the numbers pass and shape is the question.
`--view face_three_quarter` (or `face`, `face_side`, `front`, `side`, `back`)
renders one angle; `--focus NAME` frames one character in a crowd.

## Stages

### 1. Reference and measurements
- Input: stature, build, and (later) front and side reference photos.
- Data: `forge/anatomy/data/humans.json` (profile, `cite`, `_about`).
- Gate: `--check` 0 warnings; every number either cited or marked approximation.
- Open: photo fitting for humans (`reference.py` measures are animal-only);
  Drillis & Contini table not yet verified against the print.

### 2. Body base mesh and anatomy
- Code: `anatomy/biped.py` (landmarks), `templates/humanoid.py` (cage).
- Data: `breadth`, `depth`, `girth`, `shape` (torso sections, sway, arm gap).
- Gate: body ratios inside limits; sheet front/side reads as a person
  (buttocks behind, chest forward, neck behind the jaw).

### 3. Head and face
- Code: `forge/face.py` (`Head`: 16-column skull cage with nose, lips, chin,
  brow ridge and eye sockets as relief on the rows).
- Data: `face` block (rows, columns, eye, brow, ear, jaw), `hair` block.
- Gate: face ratios inside limits (`eye_height`, `eye_spacing`,
  `mouth_to_eye_spacing`, `mid_face`, `lower_face`, `head_width_to_depth`);
  face row of the sheet shows a nose, closed lips, eyes in sockets.

### 4. Topology and UVs
- Gate: quads only on the skin; support loops at knees and elbows
  (`joint_loop`); mirror check passes (`check_cage`).
- UVs: `meshkit.unwrap` (smart project) gives every creature one `UVMap`.
  Gate: `check_character.py` `uv:` line ends in `gate=ok` (no unmapped
  faces, nothing outside 0-1).
- Open: islands are cut by angle, not on chosen seams, and are not mirrored;
  export drops the subdivision.

### 5. Skin, eyes, hair, clothing
- Code: `materials.py` (`skin` has subsurface), outfits in `humanoid.py`.
- Gate: one 3/4 render in Eevee; Cycles only for a final look.
- Open: textures, hair cards or curves, cloth simulation.

### 6. Skeleton and body rig
- Rest pose is an A-pose (`arm.rest_angle`, 40 deg), which halves the
  shoulder bend of a T-pose. Collar bone takes a share of the arm drop.
- Weights: bone heat, then `shape.weight_smooth` passes; dual-quaternion
  (preserve volume) in Blender. Eye bones carry only the eyeballs.
- Gate (`check_character.py`): `unweighted=0`, `idle_bones=none`,
  `max_influences<=4`; per action stretch <= 1.6 (<= 1.9 where the worst
  edge follows a ball-joint bone: upper_arm, thigh, shoulder), squash >= 0.45,
  volume 0.95-1.05. `check_anims.py`: `ik_miss=0.000`, `lowest>=0`. Each `deform` line ends in
  `gate=ok` or `gate=FAIL:<what>`.

### 7. Facial rig
- Shape keys: Smile, Frown, Blink, MouthOpen (jaw hinge), BrowUp, Pucker, Wide.
- Expressions: `expression: smile, surprised, oo, ee, ...` (`creature.EXPRESSIONS`).
- Gate: `face: 7 keys`; a `face` view with `expression: grin` shows an open
  mouth with teeth and no skin through the teeth.

### 8. Animation
- `animation: walk, run, idle, wave, jump, sit, talk`. `talk` adds a looping
  viseme track (placeholder, not lip sync) and small head nods.
- Gate: same numbers as stage 6 for every action.

### 9. Render and compositing
- Preview: Eevee, 16 samples. Final: `--engine cycles --samples 128`.
- Open: compositing, cameras per shot.

## Token rules
- `--check` first; numbers before images; one image per change, 640x360 or a
  960x540 sheet.
- Grep build output: `grep "forge\]\|Traceback"`; sweeps: `grep "check:\|warning:\|Traceback"`.
- Edit data (JSON) before code; a new body type is a new profile entry.
- Do not read `out/`, `*.anatomy.json` or `measured.json` whole.
