# BlenderForge progress

Last updated: 2026-11-12. Tested on Blender 5.2.2 LTS at
`C:\Program Files\Blender Foundation\Blender 5.2\blender.exe`.

## Status in one paragraph

The base tool is complete and documented in `README.md`. The animal shape pass
and the preview render tuning are finished. The anatomy system (profile
database, landmark solver, validation, reference images) is partly built: the
core runs and a 15-animal test scene builds, but several pieces are untested
or missing. Sixteen profiles now take values from open datasets (AVONET,
FishShapes, PanTHERIA) with source, units, specimen IDs and licence recorded;
the limb and trunk proportions of the tetrapods are still approximations.
Snakes, fingers, joint support loops and the animation re-check landed on
2026-11-12 (see "Characters and animals pass"). Every test scene and example
passes `--check` with 0 warnings. The README has not been updated since the
anatomy work started. A character workflow pass (nine stages, new head and
face, A-pose rig, view sheet) is in progress: see "Character workflow pass".

## Finished and verified

### Base tool
- Headless build: `blender --background --python build.py -- input.md output.blend`,
  plus `forge.bat` launcher.
- Markdown, `.txt` and image input; errors with line numbers; typo fallbacks.
- Templates: humanoid, bird, fish, tower, house/building, bridge, tree,
  vehicle, prop, terrain map.
- Auto rigging, IK legs, four face shape keys, NLA animation actions.
- Exports to `.glb`, `.fbx`, `.stl`; preview render with Eevee, Workbench or
  Cycles (CPU).
- `--base` editing of an existing `.blend`.
- Repeatable: two builds gave byte-identical `.glb` files.

### Animal shapes and rendering
- 12-sided bodies, separate legs, species features (mane, antlers, horns,
  hooves, lighter belly).
- Preview: 65 mm lens, three-light rig, gradient sky, fading floor, AgX.
- Timings at 1280x720: Eevee about 3 s, Cycles about 10 s, Workbench under 1 s.

### Anatomy system (new)
- `forge/anatomy/data/*.json`: profile database with inheritance.
  - `classes.json`: tetrapod defaults, per-class plausibility ranges, joint rules.
  - `mammals.json`: canid (wolf, dog, greyhound, dachshund, fox), felid (cat,
    lion), bear, horse, deer, cow, pig.
  - `reptiles_amphibians.json`: lizard, iguana, crocodile, salamander, frog,
    plus serpent profiles.
  - `birds_fish.json`: bird and fish profiles (not yet read by their templates).
- `forge/anatomy/profiles.py`: loader, inheritance, dotted-key overrides
  (`hind.tibia: 0.4`, `trunk.chest_depth: 0.5`).
- `forge/anatomy/skeleton.py`: solver. Joint heights come from bone lengths and
  standing angles; back slope, top line, belly line, limb thickness and overall
  scale follow from those.
- `forge/templates/tetrapod.py`: geometry and rig built only from solved
  landmarks. Replaces the deleted `quadruped.py`.
- `forge/anatomy/validate.py`: proportion ranges, joint direction, ground
  contact, balance, mesh and rig symmetry. Results are printed and stored on
  the armature as custom properties. `validate: strict` turns warnings into a
  build error; `landmarks: true` adds landmark empties.
- A 15-animal test scene builds. The checks caught and I fixed: asymmetric eye
  highlights, asymmetric antlers, a frog with joints below the ground.

### Measured data (2026-11-12, from `references/3D animal.txt`)
- `tools/import_measurements.py AVONET.csv FishShapes.csv PanTHERIA.txt`
  writes `forge/anatomy/data/measured.json`. Only the rows for the 16 mapped
  profiles are kept (raw values, units, USNM specimen numbers, citation,
  licence). The full datasets are not stored in the project.
- `profiles.get()` lays measured values over the exact profile last; breeds
  and relatives do not inherit them. `profile["source"]` carries attribution.
- Birds (eagle, duck, chicken, parrot, owl, heron): leg, beak, tail, wingspan
  from AVONET, size-corrected by cube root of mass against the all-bird median.
- Fish (goldfish, trout, eel): body height, width and new `peduncle` value
  from FishShapes specimens. Goldfish uses crucian carp as a proxy.
- Mammals (wolf, fox, cat, lion, bear, deer, pig): default `size` is the
  PanTHERIA head-body length. Cat uses wildcat as a proxy.
- `bird.py` and `fish.py` read `birds_fish.json` (old item 4), accept dotted
  overrides and run `validate.report_params`. `type: heron` now builds.
- `build.py` writes `<output>.anatomy.json` with measures, issues and source
  (old item 5). The armature also gets an `anatomy_source` property.
- Test scene `out/t_measured.md` builds 15 animals with 0 warnings;
  `menagerie`, `wolf` and `t_zoo` rebuild with the same warnings as before.

### Characters on the anatomy pipeline (2026-11-12)
- `forge/anatomy/data/humans.json` + `forge/anatomy/biped.py`: human profile in
  stature units and its landmark solver. `humanoid.py` reads only landmarks;
  the hand-typed proportions and the `PRESETS` dict are gone.
- `validate.check_biped` and a `human` limits block in `classes.json`.
- Hand-entered sources: a profile's `cite` block (inherited, unlike
  `_measured`). The Drillis & Contini numbers are marked `"verified": false`:
  two web searches did not turn up the printed table. Check against Winter
  2009 fig. 4.1 and flip the flag.
- `build.py --check`: build and validate without render, export or save.
- Console source line shortened; full citation stays in `.anatomy.json`.
- `CLAUDE.md` and `.claudeignore` added to keep assistant sessions cheap.
- Verified: `out/t_people.md` (6 body types) 0 warnings, `examples/knight.md`
  builds, renders mid-walk and exports glb; animal test scene unchanged.
- Not done: reference-image fitting for humans (`reference.py` measures are
  animal-specific).

### Characters and animals pass (2026-11-12)
- Snake: `forge/templates/snake.py` reads the `serpent` profiles (`snake`,
  `python`, `eel_snake`). Rest pose is straight (so it mirrors exactly); the
  S-curve is a travelling wave on a 24-bone spine. `animation: slither, idle`.
  A snake with no animation is left posed in the curve, but exports (glb, fbx)
  carry the straight rest pose unless an animation is listed.
- Crocodile: lower limb segments lengthened (upper/lower now about 1.4,
  approximation) and its `leg_to_trunk` limit lowered; 0 warnings.
- Frog: mesh no longer dips below the ground (tetrapod cage is clamped at
  z = 0). Frog and crocodile eyes moved onto the head surface.
- Animations re-checked on the tetrapod rig with `tools/check_anims.py`
  (wolf, horse, cat, crocodile, frog: walk, run, sit, jump, idle). Fixed:
  tails going under the ground in sit / run (`Animator.keep_above`), long feet
  dipping in the swing, crocodile head dipping in a run. IK chains of 2 to 4
  bones reach their targets in walk, run and sit; no merge fallback needed.
- Humans: four fingers and a thumb per hand (`hand` block in `humans.json`,
  approximation), `fingers.L/R` and `thumb.L/R` bones, support loops either
  side of knees and elbows (`joint_loop`). The hand bone now ends at the
  knuckles.
- Verified: 12 scenes / examples `--check` 0 warnings; `out/t_anim.md` built
  twice gives byte-identical `.glb`. Test scenes: `out/t_snake.md`,
  `out/t_anim.md`, `out/t_hands.md`.
- Still open here: the frog's body reads as a lizard (hind legs do not look
  folded) - needs a shape pass; in a jump, legs leave their IK targets by up
  to 6 % of body size at full extension; fingers have one bone per hand (no
  per-finger or grip pose, so a held sword passes through an open hand).

### Character workflow pass (2026-11-12, in progress)
- `forge/WORKFLOW.md`: nine stages, each with a numeric or one-image gate,
  plus the cheap-check table. Read it before character work.
- Views: `--view front|side|back|three_quarter|face|face_side|face_three_quarter|sheet`
  and `--focus NAME` (also `view:` / `focus:` in `# settings`). `sheet` tiles
  six views into one image (`scene.render_sheet`). Characters set
  `entity.regions["face"]` for the face views.
- `tools/check_character.py`: rig counts, shape keys, per-action stretch,
  squash and volume on the cage. `check_anims.py` now ignores IK at
  influence 0 (hand IK used to show a false 0.4 miss).
- Head: `forge/face.py` replaces the 8-sided head and stuck-on nose. 16-column
  skull with nose, lips, chin, brow ridge and eye sockets modelled as relief;
  real mouth slit with cavity and teeth; iris, pupil, upper and lower lids on
  `eye.L/R` bones; ears and brows placed from face rows. All numbers in the
  `face` and `hair` blocks of `humans.json` (approximation, drawing canons).
- Face keys: Smile, Frown, Blink, MouthOpen (jaw hinge), BrowUp, Pucker, Wide;
  new expressions `surprised`, `brow_up`, `oo`, `ee`; `animation: talk`
  (placeholder viseme loop + head nods).
- Face ratios validated: `eye_height`, `eye_spacing`, `mouth_to_eye_spacing`,
  `mid_face`, `lower_face`, `head_width_to_depth` (limits in `classes.json`).
- Body: torso `shape` block (sway: buttocks back, chest forward, neck back),
  `trunk.shoulder_drop`, narrower head; `woman` and `man` profiles; lip colour
  derived from skin; `outfit: none` shows bare legs.
- Deformation: A-pose rest (`arm.rest_angle` 40), collar bone takes part of
  the arm drop, `rigging.smooth_weights` (2 passes), dual-quaternion skinning
  in Blender. Walk shoulder stretch 1.86 -> 1.52; IK misses 0.
- Verified: every test scene and example `--check` 0 warnings (child got its
  own `fingertip_height` range, since the lower shoulder joint moved it).
- Second session (2026-11-12): `check_character.py -- --detail` prints the
  worst edge of each action (frame, rest position, weights of both ends).
  `weight_smooth` 2 -> 3; the collar bone takes `COLLAR_SWING` (0.3) of the arm
  swing in `anims._arms_down`. Stretch now: walk 1.47, run 1.84, wave 1.68,
  jump 1.90, idle/sit 1.46, talk 1.40. Sweep of all 15 scenes: 0 warnings
  (`edit_tower` only warns when built without its base file). glb and
  anatomy.json byte-identical across two builds.
- Stretch gate (<= 1.6) findings, so nobody repeats the experiments:
  - Worst edges: run = groin (crotch vertex to top inner-thigh ring, 4 cm edge)
    at 69 deg hip flexion; jump = shoulder cap top to first arm ring at 78 deg;
    wave = outer elbow at 80 deg.
  - Tried and removed: per-joint extra smoothing, folding midline weights to
    the hips, pulling groin skin onto the hips (made it worse, up to 3.1).
    More global smoothing (4 passes) only reaches run 1.81, jump 1.84, wave 1.64.
  - Cause is shear: a point 15 cm from the hip joint moves ~18 cm at 69 deg, and
    an extra edge loop halves both the edge and the offset, so the ratio stays.
    Only a blend 4+ edges wide or a smaller joint angle lowers it.
  - Decision needed: keep 1.6 for hinge poses up to ~60 deg and allow ~1.9 at
    ball joints beyond that, or tone down run stride / jump arm swing.
- Face render looked at (`out/t_face.md`, grin, three-quarter): Smile and
  MouthOpen work. Problems seen: lips read as a flat coloured rectangle with no
  lip volume; eyes are small and bulge with no visible white or socket shading;
  brows are thin floating lines; the ear is a flap hidden at the hairline; nose
  has little tip or nostril definition.
- Face pass (same day, third sitting): the eyelid sphere kept its middle band,
  so skin covered the whole eyeball; `face.eye` now deletes the band between
  the equator ring and the +30 deg ring and maps the lid rings from there, so
  whites, iris and both lids show. Lip corner quads are split on the diagonal
  to the mouth corner, so the lips taper instead of ending square. Ear moved
  out (`ear_out` 0.08, `ear_thick` 0.18), brows thicker (`brow_thick` 0.60).
  `eye_depth` 0.66 buried the eye (the cage has no eye opening), back at 0.71.
  Checked: t_char, t_people, t_pose, knight, village 0 warnings.
- Fourth sitting (2026-11-12, paused mid-step): Pucker (`expression: oo`,
  `view: face`) rendered and reads right. Blink half-closed: the key was fine
  (32 verts, 1.25 cm travel), but the iris and pupil (front at 1.12 r) poked
  through the lid's flat facets. `face.eye` now uses 12 lid columns and a
  radius of 1.13 r / (cos(pi/12) cos(15 deg)), so the facets clear 1.13 r.
  That was not enough (looked at in the fifth sitting).
- Fifth sitting (2026-11-12): Blink confirmed closed (`out/t_blink.md`, `view: face`).
  Cause of the remaining poke-through: shut, the upper lid's 2 segments spanned
  124 deg (62 deg facets, sagging to 1.00 r). The lid sphere now has 11 rings
  (15 deg apart, 5 upper segments) and its radius is solved from the shut
  segment span (about 1.19 r, a little less puffy than before). Open eye
  still shows white, iris and both lids.
  Nose: new `nose_ala` row (0.322) between `nose_base` and `nose_tip` gives a
  rounded tip, a steep underside and wings; `nostril` [across, radius] in the
  `face` block places two dark ovals on the underside (`face.features`).
  Looked at front and three-quarter: reads as a nose. Sweep of all 17 scenes:
  0 warnings (`edit_tower` warns only without its base file).
- Sixth sitting (2026-11-12): three open items closed.
  - Nose: a row may now place its own columns (`face.row_columns`, read in
    `Head.__init__`, used by `co`/`surface`/`build` for the front half only).
    `nose_base`/`nose_ala`/`nose_tip` put the wing column at 0.20/0.24/0.19
    instead of the shared 0.17, so the wings flare and the nostrils (placed
    between midline and wing) move apart with them.
  - Eye socket without cutting the cage: eye row relief
    `[0.04, -0.14, -0.20, -0.10]` and `eye_depth` 0.64 changed together. The
    eyeball centre sits just behind the socket skin, the brow (0.93) and cheek
    (0.83) stand proud of the lid front (0.79). Moving `eye_depth` alone is what
    buried the eye before; the inner column (-0.14, the canthus) must be deep
    too or the nose side covers the inner half of the eye. Looked at: front
    open, three-quarter shut (`t_blink`). Shut eye still reads as a small dome
    (lid sphere 1.19 r), but inside the socket.
  - Squash gate: `joint_loop` 0.12 -> 0.16 (support loops further from elbow
    and knee, so the edges across the joint are longer). All 7 actions of
    `t_char` now `gate=ok`: walk 1.47/0.63, run 1.84/0.52, idle 1.40/0.59,
    wave 1.53/0.55, jump 1.90/0.61, sit 1.43/0.60, talk 1.40/0.79
    (stretch/squash). 0.20 is too far: run stretch 2.12 at shin.L.
  - Sweep of all 18 scenes 0 warnings (`edit_tower` as before); IK misses 0.
  - `t_people` re-rendered (all six, knight included): builds and reads fine
    at scene scale. Neck "seam": not a mesh seam. Torso and neck share one
    material and one loft; the line is the concave bend at the `neck_base`
    ring (about 45 deg between shoulder slope and neck column). Reasoned from
    the ring numbers, not confirmed in a close-up. Softening it needs one more
    ring between `shoulder_cap` and `neck_base`.
  - Stage 4, UVs: `meshkit.unwrap` (Blender smart project, 66 deg, margin
    0.02) runs in `creature.finalize` after skinning and before shape keys,
    so every creature (people and animals) gets one `UVMap`.
    `check_character.py` prints a `uv:` line (unmapped, outside 0-1, fill,
    gate). Adult: 1326 faces, 0 unmapped, 0 outside, fill 0.23; Wolf fill
    0.28. glb carries TEXCOORD_0 and is byte-identical across two builds.
    Sweep of all 18 scenes 0 warnings. Build time of `t_char` 0.3 -> 1.4 s
    (not checked how much of that is the unwrap).
- Open, next steps in order:
  1. UV quality: fill is low (0.23) and islands are cut by angle, not along
     chosen seams, and are not mirrored left/right. Good enough for baking,
     poor for hand painting. Still open in stage 4: export drops the subdivision.
  2. Face polish, optional: nose shape hardly reads from the front under flat
     light (fine at three-quarter); eyes are small.
  3. Optional: extra neck ring to soften the neck base bend (see above).
  4. Stages 5 and 9 of WORKFLOW.md not started (textures/hair, final render).
- Backup of `forge/` from before this pass was in the session scratchpad
  only; it is not kept.

## Written but never run

- `forge/anatomy/reference.py`: silhouette masks from `reference_side`,
  `reference_front`, `reference_top` images, measuring, profile fitting,
  model-versus-reference comparison, image empties. No test image exists yet.

## Not done

1. Done (see Characters and animals pass).
2. Done.
3. Done.
4. Done (see Measured data).
5. Done (see Measured data).
6. A tool to make test reference silhouettes (orthographic black-on-white
   render of a model with changed proportions), then a fit test: build a
   default dog against a long-legged reference and check the leg ratio is
   recovered.
7. Rebuild every example in `examples/` and re-check exports and
   repeatability.
8. README: add the anatomy section (profiles, overrides, validation,
   reference images, new species and breeds) and update the template table
   (`quadruped` row is now `tetrapod`).
9. Visual tuning still open: cow has no patches, lion mane is a simple ball,
   frog body shape.

10. Leg length: partly done. `forge/anatomy/data/stature.json` holds shoulder
    height / head-body length for wolf, fox, lion, bear and deer, and
    `skeleton.fit_stature` scales both limb chains to match before the user's
    `leg_length` and overrides (wolf x1.20, fox x1.54, lion x1.33, bear x0.92,
    deer x1.05). These are SECONDARY sources (field-guide ranges), not
    specimens. Still open: the fit scales every bone equally, so segment
    ratios are unchanged; lion looks leggy; pig, cat, horse, cow, dog have no
    stature data (wild boar figures made the pig stilted, so it was removed).
    Proper fix is limb bone lengths from specimens (oVert / MorphoSource).
    Test scene: `out/t_legs.md`.
11. No measured data yet for horse, cow (no head-body length in PanTHERIA),
    dog breeds, shark (not a teleost), reptiles and amphibians. Bird neck and
    girth and fish fins are not in the datasets and stay artistic.

## Known caveats

- AVONET was read from a GitHub copy of the BirdLife sheet
  (txm676/GlobalFDPDLoss) because Figshare refused automated download.
- FishShapes licence is CC0 in its README and paper but CC BY-NC 4.0 on the
  Zenodo record page. Check before commercial use.
- Bird values are relative to the median bird, not absolute ratios to body
  length (AVONET has no body length).

- Profile numbers not listed in `measured.json` are approximations from
  general anatomy. The Vandruff
  PDF that was supplied as a source is a course syllabus with no proportion
  data, and the other reference links were not opened.
- Reference fitting only works on plain silhouettes (flat background or alpha
  channel). It has no image recognition.
- Creatures export as the unsubdivided cage, because applying modifiers drops
  shape keys. No UV maps.

## How to pick up

Test scene used during the anatomy work (recreate under `out/`):

```
# animal: Wolf
type: wolf  size: 1.2
# animal: Croc
type: crocodile  size: 2.4
# animal: Frog
type: frog  size: 0.35
```

```
forge out\t_zoo.md out\t_zoo.blend --render
```

Suggested order: items 10, 6, 11, the frog shape pass, and the README last.
Item 7 is half done: every example passes `--check`, exports were only
re-checked for `out/t_anim.md`.
