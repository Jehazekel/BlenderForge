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

## Live mode with Blender MCP (2026-11-12)
- Optional GUI layer; headless `build.py` stays the only builder. Rules in `CLAUDE.md` "Live mode".
- `.mcp.json` registers the `blender` server (`uvx blender-mcp`); `.claude/settings.json` allows
  `look`/`get_scene_info`/`get_addon_status`, asks for `execute_blender_code`, denies generators and asset imports.
- `tools/live_view.py`: GUI watcher, reloads on rebuild (keeps the view), writes `<file>.live` stamp.
- `scene.save` writes `x.tmp.blend` then swaps it in, so the viewer never loads a partial file.
- Verified: two rebuilds reloaded the viewer, `look` framed `Adult_Rig` from three angles;
  `look` also works with Blender minimized. Add-on updated (protocol 16 expected); not rechecked
  in a clean session because the server restarts on reload.
- `forge/WORKFLOW.md` has a "Views by problem" table for picking `look` angles.
- `tools/gates.py`: runs check, anatomy, build, anim, rig, face, uv, deform gates in one command;
  `--sweep` checks 18 scenes against `out/sweep_baseline.json` (written 2026-11-12, all clean
  except 1 known warning in `examples/edit_tower.md`). Tested on `t_char` (pass) and a broken wolf (fail).
- `.claude/skills/fix-loop/SKILL.md`: the unattended loop (gates, look by stage, fix in data first,
  revert on regression, 3 rounds per problem, 12 per run, log in `out/fixloop/`). Not yet run end to end.
- Zoom in live mode: `live_view.py` hides rigs and adds focus points `F_<Name>_<bone>` that
  follow the animation; `look` targets one with a `distance`. Tested on head and hand.
- First fix-loop trial on `t_char` (2026-11-12): all gates pass, 2 rounds, no model change.
  Eye gaze looked wrong but measured straight ahead (false positive). Needs review: fingers and
  thumb are separate capsules; the thumb touches the palm (2 mm) but splays, so a gap shows from the side.
- Still missing: numeric shape checks (posture, eye sockets, frog crouch) so fewer gates need `look`.

## Human reference fitting (2026-11-12)
- `reference_front` + `reference_pose` on humanoids: `reference.measure_biped` reads crown to jaw,
  crotch height, hip width (apose/tpose) and arm span (tpose) at 600 px; `fit_biped` scales head,
  leg, hip, arm groups (each within 0.75-1.33x, user-set groups locked) against the solved skeleton,
  no mesh rebuild. Mesh-vs-landmark offsets in `humans.json` `reference` (approximation, calibrated
  on the default mesh: self-match 0%).
- Round trip: silhouette of a human with leg_length 1.12, head_size 0.9 -> fit legs x1.13, head x0.87
  (1 px at 600 px is ~1.7%). Lock and side-view warning tested. Gates + sweep clean.
- Not tested: `tpose` arm span (no T-pose test image; the model's rest pose is an A-pose).
  Not done: side view for humans, real photos.

## Painted layout plans (2026-11-13)
- `layout:` + `legend:` on maps (`forge/templates/terrain.py`, `LayoutMap`).
  Nearest legend colour within sRGB distance 0.30, sampled nearest-pixel at the
  heightmap loader's 256 px; 3x3 share gives soft edges for water carving and tints.
- Painted water: unpainted ground is clamped above the water line, painted water
  is carved 0.04 below it; water defaults to 0.12 when the preset has none.
- Trees/rocks only inside forest/rock areas (default 3 and 0.8 per 100 m2);
  houses one per connected red area (>= 3 px), `houses:` ignored with a warning;
  other scatter avoids water, roads and houses.
- Example `examples/village_plan.md` (5 houses, river, forest, fields, rocks);
  sweep now 19 scenes, all gates ok. Follow-up (2026-11-13): houses turn their
  front to the nearest road/path/bridge pixel (40 px search, random if none);
  ground is smoothed across roads, paths and bridges (2 px average) and levelled
  under each house (pad of the blob radius, smooth falloff to twice that). New kinds:
  `path` (#d2b48c, tinted, smoothed), `wall` (#404040, a stone box per pixel,
  `wall_height` default 1.2 m, `wall_color`), `bridge` (#ff00ff, carved like water,
  plank deck level with the banks). village_plan shows all three; sweep 0 fail.
  Centre lines (2026-11-13): `LayoutMap.centrelines(kinds)` thins road/path/wall/
  bridge areas (Zhang-Suen, map edge repeats so lines run off the map), traces them
  (row-major, m-adjacency, short spurs pruned, chains merged), simplifies
  (Douglas-Peucker 0.75 px) and smooths (Chaikin x2); width = 2 x mean edge distance.
  Walls are one swept strip per line (`wall_thickness`, default 1 px; base on the
  lower side, sunk 0.3 m); bridge decks one strip per line, painted width, ends pushed
  out half a width. Ground under ways blends to a per-pixel target (terrain along the
  nearest centre line, averaged 3 px along it): flat across the width, back to the
  terrain over 2.5 px past the edge (`WAY_BLEND`, `WAY_SMOOTH`). Houses face the
  nearest centre-line point, squared to that segment (point itself past a line's end).
  village_plan gained a diagonal paddock wall; 0 warnings, sweep 0 fail.
  Not done: wall and road junctions just overlap (no mitred joins or end caps on
  roads), bridge decks are flat (no railings, no arch), no lots along roads, houses
  are not pushed off a road they overlap, ways are not their own mesh (only tinted).

## Toy cat and coat markings (2026-11-13)
- `toy_cat` profile (mammals.json): chibi cat (big head, short muzzle and legs, raised tail), approximation from Clover Lane Pet Market `pets/cat.png`. Test file `out/ginger_cat.md` (ginger, cream belly, `lowpoly: yes`).
- Tetrapod `markings` profile block, painted per face by `paint_markings` in `templates/tetrapod.py`: `stripes` {period, width, dark} on back, legs, tail and forehead (body mesh only), `socks` (fraction of withers height), `muzzle` (fraction of head width). Input keys: `stripe_color`, `mark_color`, `markings: no`. New material slots `stripe`, `mark`.
- Sweep: 19 scenes, nothing worse than baseline.
- Deformation pass (same day), all gates pass, sweep nothing worse than baseline:
  - `rigging.split_sides` (called in `creature.finalize` after weight smoothing): a vertex on the far side keeps `.L`/`.R` weights only within a band of 10% of the mesh half-width around the midline. Bone heat and smoothing had let weights cross between close legs.
  - `toy_cat` stance widened (chest_width 0.40, hip_width 1.0) and legs thinned (thick 1.10, fore/hind_scale 0.68); the old thick legs nearly touched.
  - `anims.Animator.bake` keys every bone an action does not move at rest. Before, actions without IK or foot keys (tail_sway, idle) inherited the targets and rolls of the action played before them, in NLA and export. The stock `cat` tail_sway missed by 0.006 because of this.
  - `quad_walk` hip bob capped at 0.03 x leg_h, so short legs never lift the hips above rest (front legs overreached).

- Look pass vs reference (2026-11-13): bigger head (skull 0.46, width 0.68), front-set eyes (eye_out 0.36, eye_at 0.88), thicker legs, finer stripes (period 0.13), shorter socks, more chest white, curled tail tip (curl -1.0; radius 0.09 failed tail_sway squash, 0.07 passes).
- New pointed-ear profile keys (`forge/creature.py` add_ear): `width` (base scale), `facing` (0 sideways .. 1 forward), `inner` (colour; adds an inset inner face, input override `ear_color`). Defaults leave every other animal unchanged; sweep clean.

- Fix loop vs reference, headless (2026-11-13, log out/fixloop/ginger_cat.md): chibi proportions (chest_depth 0.72 with a stylized `limits` override, legs 0.95, head ~1.45x, hip_width 1.25 to stop hind feet crossing in walk); stripe period now measured on the trunk with a separate forehead period (`stripes.head`) and crown-only head stripes; new profile `nose` colour (input `nose_color`). Gates 0 fail, sweep clean. GUI comparison still to do.

- GLB proportion + gait match (2026-11-13, log out/fixloop/ginger_cat.md; scripts out/fixloop/compare_shape.py, compare_anim.py): `toy_cat` matched to Clover Lane `pets/models/Cat_animated.glb` by measurement (fractions of height, forge vs GLB): front feet 0.34/0.30, hind 0.82/0.80, mid width 0.36/0.37, tail top 0.97 at y 1.24 / 0.97 at 1.15, length 1.26/1.30. Changes: neck 0.30 @ 150 deg (leans back, pulls head over front feet), forechest 0.03, chest_width 0.70, head width 1.04, tail 1.25 @ -89 curl 1.3 (rises then hooks back). New profile block `gait` {stride, lift, crouch, period} read by `quad_walk` via `rig.meta["gait"]` (period = walk cycle seconds, walk only). Walk now 1.00 s like the GLB; stride 0.23 H vs GLB 0.44 H (longer overreaches the IK legs: ik_miss > 0, tibia stretch fails), lift 0.058/0.075. GLB has only one action (walk); idle and tail_sway have no counterpart. Gates 0 fail, sweep clean.

### Leg projection fix (2026-11-13)
- Cat hind thigh stuck out sideways 0.12 past the bone. Cause: on a deep-bellied, short-legged body the thigh path started level with the knee, so the leg ring frame in `tetrapod._transport` fell back to a vertical first axis and put the fore-aft radius sideways.
- Fix (tetrapod.py): the ring frame always keeps the first radius sideways; the thigh start is kept at least halfway between hip and knee so the thigh runs down. Widest point 0.197 -> 0.163 m. Gates 0 fail, sweep 19 ok.
- Re-compared with Cat_animated.glb: W/H 0.69 -> 0.57 (GLB 0.59), foot spread 0.42 = GLB. Upper front leg was thicker (0.23 vs 0.18 H): toy_cat `limb.upper_mass` 0.78 -> 0.21. `out/fixloop/view_both.py` opens forge model + GLB side by side in the GUI (same height, both walking).

### Program improvements spotted (not done)
- Eyes: no catchlight/iris option for tetrapods (`pupil=False` path gives flat black beads); the eyelid uses fur and reads as a brow ridge on big eyes.
- Mouth is one wide line across the muzzle; a small "w" cat mouth would need a mouth shape key in the profile.
- Markings: no chest-bib region (only belly + muzzle); stripe width is a fixed fraction, so the head gets the same broad bands as the body; no per-region periods.
- Tail curl only bends near the tip; thick stylized tails fail the squash gate on sway. Tail radius could taper and skinning could get more tail bones for thick tails.
- Profiles cannot set trunk length relative to head, so "short body" means scaling every head value up.
- Reference fitting (`reference_side/front/top`) only takes plain-background silhouettes; a three-quarter or illustrated reference (like the pet market art) cannot be measured.
- Walk stride is limited by IK reach; a cartoon gait like the GLB's (legs swing ~140 deg, stride 0.44 H) needs leg-swing (FK rotation) keys or squash-stretch limbs instead of IK foot targets.
- No tool compares animations to a reference: `out/fixloop/compare_anim.py` (root bob, foot stride/lift, top-moving bones per action) could move into `tools/`.
- `look` loop needs a reference-overlay view (render at the reference camera angle beside the image) to compare without reading two images.

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

## Rabbit (2026-11-13)
- New profile `toy_rabbit` (approximation, from Clover Lane Rabbit.md); input `out/rabbit.md`.
  2.40 m long, 1272 tris, anatomy 0/0, sweep ok. Ear `splay`/`lean` profile keys added
  (defaults unchanged). Run/jump/sit gates fail like toy_cat. Improvement list in
  `out/rabbit_notes.md`; needs review (paddle ears, hop gait, rig rename, palette texture).
- Legs fixed (knee spike and sideways thigh skirt removed, straighter hind leg, slimmer upper
  legs); sit/run deform squash got worse (0.21). See `out/rabbit_notes.md`.
- Deformation: knee 25/-30, slimmer limbs, new `rigging.fade_roots` (limb/tail-base weights
  off the trunk). Squash passes in every clip; stretch 1.61-1.70 and volume 0.91 still fail in
  run/jump/sit (shared quad clips; cat fails too). Sweep ok.

## Tetrapod animation and skinning pass (2026-11-14)
- Shared quad run/jump/sit amplitudes toned down and named (forge/anims.py), run bob capped
  by leg height, `Animator.reach_down` lowers hips so feet reach IK targets (anim gate now
  passes for rabbit, toy cat, wolf). `rigging.fade_roots` (limb/tail-base weights off the
  trunk and midline) behind profile `skin.fade_roots` (off for equid, fox). toy_cat limbs
  slimmed. Sweep ok. Most species improve; volume 0.92-0.94 and seam stretch still fail.
  Details and numbers in `out/rabbit_notes.md`.

## Base sample: Rigify male + reference animation library (2026-11-20)
- New template `base_sample` (`forge/templates/base_sample.py`): appends the mesh and
  Rigify rig from `base samples/Rigged Low poly Male and Female Basemesh for Animation.blend`
  (`body: male|female`, `file:`, `height:`, `color:`, `speed:`). Clears the sample's saved pose
  (torso dropped 0.36 m, finger masters scaled into a fist), recentres the rig, adds a skin material, arms FK /
  legs IK, keeps `rig_ui.py` (Rigify N-panel: IK/FK switch, snapping) as a registered module.
- New `forge/rigify_anims.py`: pose vocabulary (left-side armature-axis degrees, auto-mirrored),
  three generators (idle, gait with IK foot paths, key-pose blends) and 241 clips. `REFERENCE`
  maps every item of `references/character_animations.md` sections 1-17 to a clip. Input:
  clip names, reference names ("crouch walking"), `@category` (`@combat`) or `all`.
  Each clip is an Action on its own NLA track, marked as an asset tagged with its category.
- `anims.Animator` takes an optional `keyset` so generated rigs key only their controls.
- Example: `examples/base_male.md` (`animation: all`): builds in ~7 s, 0 warnings, 241 clips.
- Checks: `check_anims` lowest >= -0.026 for all clips except `dive` (-0.095, water entry).
  The repo's character gates (deform/rig/face/uv) do not apply: the sample uses Mirror + Subsurf
  and its own UVs, so cage/evaluated vertex counts differ. A matched-topology check (cage,
  Subsurf off, posed vs rest): idle 1.75, walk 1.86, 84/241 clips <= 2.0, 177 <= 3.0.
- NEEDS REVIEW (3 tweak rounds done): groin edges (DEF-thigh / spine / pelvis) stretch to
  ~4.3 in deep hip flexion (sprint, crouch_run, rolls, pick_up). Likely needs weight painting
  in the sample, not pose changes. Facial / lip-sync items map to head and hand motion only:
  the male mesh has no face rig, face weights or shape keys.
- Review pass (2026-11-20): 86 looping clips had seams (up to 0.33 on foot roll / torso):
  a bone left unset on some frames was interpolated across instead of returning to rest.
  `Animator(fill=True)` now keys rest there (opt-in; creatures unchanged, sweep ok); all loops
  now match end to start. Height was measured before the saved pose was cleared: the male is
  2.11 m at rest (not 1.71: the sample drops its torso 0.36 m), the female 2.05 m. Clip offsets
  scale with body height (`REF_HEIGHT` 2.115 = the male they were tuned on). Rig lifted so the
  rest mesh stands on z = 0 (was -0.011). Reference names may list several clips
  ("strafing left and right=walk_left,walk_right"); run_right, hook, carry_idle and push_against
  are now reachable from reference names; a name in two categories ("falling") resolves to the
  first, matching its asset category. `gates.py` on this input: sweep ok; the creature anim gate
  (lowest >= -0.0005) flags the rig's own toe tips at -0.001 in rest, not a clip fault.
- Female base (2026-11-20): `examples/base_female.md` -> `out/base_female.blend`, 2.05 m,
  406 bones, 241 clips, 0 warnings, all 86 loops seamless. Her rig rests in a T-pose (male:
  A-pose, arm 22 deg down, 13 deg forward), so the same clip rotations left her arms ~20 deg
  high. `rigify_anims._Scaled.fit_arms` now re-bases the FK arm chain (upper arm, forearm,
  hand) on the male's rest directions (`REF_ARM`, direction only, roll kept); sampled arm
  directions now match the male to 0.01. Her longer arms/fingers planted fingertips 7 cm under
  the floor in crawls/prone: `_lift_hands` raises the torso on frames where a hand bone is
  below z = 0 (coarse pass first; skips `dive`). Also fixed the male's crawl (-0.022 -> 0).
  Build 6 s -> ~12 s per body. Remaining below floor: dive (by design, female -0.149),
  death_run toe -0.027 (both), male death_side/collapse -0.023. Stretch numbers equal the
  male's (mirror/subsurf artifact, gate n/a).
- Face template (2026-11-21): ICT-FaceKit (MIT, USC ICT) as the default head for base samples.
  `tools/import_facekit.py` (one-time, stdlib OBJ parser) turns the downloaded OBJs
  (`third_party/ICT-FaceKit/`, gitignored, 143 MB) into `forge/assets/face/ict_face.blend`
  (6.4 MB: 25,959 verts, 57 ARKit-named shape keys, eye overlay shells dropped, license
  copied beside it and into the .blend). FaceKit's eyeLook shapes only move lids, so the
  importer adds eyeball turns (sphere-fit centres; up 25, down/in/out 30 deg, approximation).
  `base_sample` `face: ict` (default when the asset exists; `none` keeps the sample head):
  body head hidden by a Mask modifier (DEF-spine.006 > 0.5), FaceKit head scaled to the
  body head's width/depth (male 1.166, female 1.072), crown-aligned, neck cut 0.25 FK units
  below the crown, tapered + snapped 2 mm proud of the body neck (gap mean 3 / 1.8 mm,
  max 5.5 / 3.5 mm), weights = head bone above its root, body's own weights below (3 cm
  blend). Body never pokes through in nod/shake/look/run (max 7 mm in head turns).
  `forge/face_anims.py`: 41 clips keyed on ARKit names (sections 9 and 10 plus the facial
  part of 11): expressions, gaze with saccades, deterministic blinks, breathing, lip-sync
  from text (letters -> Oculus visemes -> ARKit, `say:` overrides the line), styles
  whisper/shout. One Action per clip on the shape keys (`<Name>_face_<clip>`, NLA track,
  asset-tagged). 282 clips per body, 0 warnings, 37 face loops seamless, values in 0..1.
  Open: `check_character` only reads the body mesh (reports face: 0 keys); no tongue
  shapes in FaceKit (TH/DD visemes are approximate); identity shapes not imported.
- Consistency pass (2026-11-21): gates + sweep 0 fail (21 scenes). Male/female base: same 282 clips, tracks, assets and frame ranges.
  Fixed: the hand floor guard lifted the torso along its rest Z, which lying clips rotate horizontal (male death_side/collapse fingers 7 cm under the floor); it now maps up through the torso's posed parent frame.
  Default sample path follows the move to `base samples/humans/`. dive is exempt by design.
  Floor guard v2: measures in world space (the rig is raised 1-2 cm so soles sit on z = 0; rig space put the floor 1.1/1.9 cm low), floor = rest height of the lowest foot bone (skin under the bone, 8/11 mm; fingers taken as thick as the sole, approximation), and a second pass lifts the root for IK feet/toes (death_run toe swung 7.8 cm through the floor mid-fall). Result: no bone under -5 mm on either body except dive; builds 41-46 s.
