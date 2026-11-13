# BlenderForge

Builds rigged, animated 3D characters, animals, structures, maps and props in
Blender from a plain text file. No AI, no GPU, no network: every vertex, bone
and keyframe comes from deterministic Python driving `bpy` and `bmesh`.

```
blender --background --python build.py -- input.md output.blend
```

The same input always produces the same output. Two runs of `examples/village.md`
give byte-identical `.glb` files.

## Quick start

Windows, with the launcher (finds Blender for you):

```
forge examples\knight.md out\knight.blend --render --export glb,fbx
```

Any platform:

```
blender --background --python build.py -- examples/knight.md out/knight.blend --render --export glb
```

Developed and tested on Blender 5.2 LTS. The code avoids APIs that changed
between 4.2 and 5.x (layered actions, Eevee engine name, STL exporter) and has
fallbacks for the older names, but versions before 5.2 are untested.

### Options

| Option | Meaning |
|---|---|
| `--export glb,fbx,stl` | Export next to the `.blend`. `glb`/`fbx` carry the rig, skin weights, shape keys and every animation. `stl` is the static mesh. |
| `--render [file.png]` | Low-sample preview. Defaults to `<output>.png`. |
| `--engine eevee\|workbench\|cycles` | Preview engine. Falls back Eevee, Workbench, Cycles (CPU) if one is unavailable. |
| `--samples N` `--resolution WxH` `--frame N` | Preview quality, size and frame. |
| `--lowpoly` | Game-ready meshes: no subdivision or bevel modifiers, fewer segments. |
| `--fps N` | Animation frame rate (default 24). |
| `--base scene.blend` | Open an existing file and add, replace or edit entities in it. |
| `--list` | Print every template and type name. |
| `--check` | Build and validate only. Nothing is rendered, exported or saved; each creature prints one `anatomy:` line. |

### Preview rendering

The preview is set up for a clean still in a few seconds:

* Camera: 65 mm lens, fitted to the model's vertices so the subject fills the frame.
* Light: warm key sun with soft shadows, cool fill, rim light from behind,
  gradient sky. The floor fades into the horizon colour, so there is no edge.
* Tone mapping: AgX (falls back to Filmic, then Standard).
* Eevee: 16 samples, soft shadows, ray tracing off. About 3 s at 1280x720 on
  the development machine.
* Cycles (CPU): 16 samples with adaptive sampling, short light paths and the
  OpenImageDenoise denoiser. About 10 s at 1280x720; noise-free where the
  undenoised version was grainy.
* Workbench: under 1 s, flat studio shading.
* Subdivision is capped at level 2 for previews and uses the cheapest
  evaluation quality; the build prints how long it and the render took.

Eevee and Workbench need an OpenGL context (any integrated graphics works).
On a machine with none at all, use `--engine cycles`, which is pure CPU.

## Input format

A Markdown or `.txt` file. A heading starts a section; the lines under it are
`key: value` pairs, several per line if you like.

```markdown
# character: Knight
type: humanoid  height: 1.8  build: muscular  skin: #c68642
outfit: armor  accessories: helmet, sword
animation: walk, idle, wave  expression: smile

# animal: Wolf
type: quadruped  size: 1.2  tail: long  ears: pointed  fur: #555555
animation: run, sit

# structure: Tower
type: castle_tower  floors: 4  radius: 3  roof: cone  windows: 8  material: stone
```

* Section kinds: `character`, `animal`, `structure`, `prop`, `vehicle`, `tree`,
  `map`, `settings`, `edit`. In a `.txt` file the `#` is optional.
* Colours are `#rrggbb`, `#rgb` or a name (`red`, `gold`, `navy`...).
* Bullets, blank lines, code fences, `>` quotes and `//` comments are ignored.
  A plain title like `# My scene` starts a notes block where prose is skipped.
* Every entity also accepts `position: x, y[, z]`, `rotation: degrees`,
  `scale: n`, `lowpoly: true` and `subdiv: 0-3`. Without a position, entities
  line up in a row. With a map in the file, they stand on its surface.
* **An image as the input file** (`build.py -- photo.png out.blend`) becomes a
  terrain: brightness is height, pixels are the ground colours.

### Errors and fallbacks

Mistakes that cannot be guessed stop the build with the file and line:

```
scene.md:2: error: 'height' expects a number, got 'tall'
scene.md:6: error: unknown section 'widget' (expected one of: animal, character, ...)
```

Unknown words fall back to something sensible and print a warning:

```
scene.md:2: warning: unknown type 'humanoyd', assuming 'humanoid'
scene.md:2: warning: unknown outfit 'armour', assuming 'armor'
scene.md:4: warning: 'Bob' has no 'moonwalk' animation, using 'idle' (available: idle, jump, run, sit, walk, wave)
scene.md:2: warning: unknown keyword 'hight' for character 'Bob', ignored
```

Blender exits with code 1 on an error and 0 on success.

## Templates

Run `forge --list` for the full list. Every preset name works as a `type:`.

| Template | Types | Main keys |
|---|---|---|
| humanoid | `humanoid` `knight` `villager` `wizard` `child` `giant` | `height` `build` (slim, average, athletic, muscular, heavy) `head_size` `limb_length` `arm_length` `leg_length` `skin` `hair` (short, long, bald) `hair_color` `eyes` `outfit` (casual, armor, robe, tunic, none) `outfit_color` `pants_color` `accessories` (helmet, hat, crown, sword, axe, staff, shield, cape, backpack) |
| quadruped | `quadruped` `wolf` `dog` `fox` `cat` `horse` `deer` `bear` `cow` `pig` `lion` | `size` `build` `leg_length` `neck_length` `head_size` `tail` (long, short, bushy, none) `ears` (pointed, round, floppy, none) `fur` `belly` `mane_color` `horn_color` `material` (fur, skin, scales) |
| bird | `bird` `eagle` `duck` `chicken` `parrot` `owl` | `size` `wingspan` `feathers` `wing_color` `beak_color` `tail` |
| fish | `fish` `goldfish` `shark` `trout` `eel` | `size` `scales` `fin_color` `depth` |
| tower | `tower` `castle_tower` `watchtower` `lighthouse` `wizard_tower` `silo` | `floors` `radius` `floor_height` `roof` (cone, flat, dome, battlement, none) `windows` `battlements` `flag` `taper` `material` `roof_color` |
| house | `house` `cottage` `cabin` `barn` `building` `shop` `apartment` `keep` | `width` `depth` `floors` `floor_height` `roof` (gable, hip, flat, battlement) `windows` `door` `chimney` `material` (stone, brick, wood, plaster, concrete...) `roof_color` |
| bridge | `bridge` `stone_bridge` `wooden_bridge` `footbridge` | `length` `width` `height` `arches` `style` (stone, wood) |
| tree | `oak` `pine` `fir` `palm` `birch` `dead_tree` `bush` | `height` `seed` `foliage` `trunk` |
| vehicle | `car` `truck` `van` `cart` `wagon` | `length` `width` `height` `color` |
| prop | `crate` `barrel` `chest` `rock` `sword` `shield` `staff` `axe` `table` `chair` `fence` `lantern` `signpost` `well` `campfire` | `size` `color` |
| terrain | `terrain` `hills` `mountains` `island` `valley` `plains` `desert` | `size` `resolution` `height` `seed` `water` `heightmap` `colors` (height, image) `trees` `tree_type` `rocks` `houses` |

## Modeling

* Creatures are one connected, all-quad cage built from lofted rings, the same
  layout a box modeller would make by hand: the torso and head are a single
  loft, legs are pulled out of the pelvis floor, arms out of holes left between
  the shoulder rings. A Subdivision modifier sits on top (`subdiv: 0-3`).
  The knight's body is 686 quads, 0 triangles.
* `lowpoly: true` (or `--lowpoly`) drops the modifiers so the cage itself is
  the game mesh.
* Eyes, lids, brows, mouth, hair, ears and armour plates are modular shells
  attached at points the template defines. Accessories are separate objects
  parented to bones, so a helmet or sword can be hidden or swapped.
* Structures and props are hard-surface: boxes, lathes and extruded profiles
  with sharp-edge shading and a small Bevel modifier.
* Materials are procedural Principled BSDF node trees: flat colour plus noise
  for stone blocks, brick, wood grain, fur, metal, foliage, roofing and water.

### Human proportions

Characters use the same data-driven pipeline as the animals. The profile in
`forge/anatomy/data/humans.json` gives segment lengths and breadths as a
fraction of stature; `forge/anatomy/biped.py` solves joint landmarks from it
(hip height from thigh + shin + ankle, shoulders, chin and crown stacked on
top, everything rescaled to `height:`); `humanoid.py` builds the mesh and the
bones on those landmarks. Each build is checked against plausible human
ranges and prints a line such as

```
anatomy: Knight (knight, human): 0 errors, 0 warnings; 1.80 m, 7.7 heads tall, hips 0.95 m, shoulders 1.47 m, arm span 2.03 m
```

* `knight`, `villager`, `wizard`, `child` and `giant` are JSON entries that
  inherit from `humanoid`. A new body type is one more entry.
* Any profile value can be set from the input with a dotted key:
  `leg.thigh: 0.26`, `arm.fore: 0.15`, `breadth.shoulder: 0.28`,
  `head.height: 0.14`. `validate: strict` turns warnings into a build error,
  `validate: off` silences them, `landmarks: true` adds landmark empties.
* Adult lengths follow the Drillis & Contini (1966) table as reproduced in
  Winter's biomechanics text. They were entered from memory of that table and
  are flagged `"verified": false` until someone checks them against the print.
  Depths, limb thickness and the child and giant presets are approximations.

### Animal species

Each quadruped type is a row of proportions in `forge/templates/quadruped.py`
(chest depth, belly tuck, neck and head angles, snout length and width, leg
thickness) plus features: a lighter underside (wolf, fox, deer, cat), mane and
hair tail (horse), mane ruff (lion), antlers (deer), horns (cow), hooves
(horse, deer, cow, pig). Bodies are 12-sided rings; each leg leaves through
two flank quads, so left and right legs are separate with a chest between
them. A new species is one more row in `PRESETS`.

## Rigging

* Biped, quadruped, bird (three-bone wings), fish (spine chain) and vehicle
  (one bone per wheel) armatures, with tail chains and ear bones.
* Skinning uses `parent_set(type='ARMATURE_AUTO')`. Rigid parts (eyes, hair,
  armour) are appended afterwards and bound 100% to one bone, so loose shells
  never upset the bone-heat solver. Any vertex the solver misses is weighted to
  its nearest bones, and that is reported.
* IK on legs (biped and quadruped) with foot targets parented to the root, so
  feet stay planted while the hips move. Arms have IK targets too
  (`hand_ik.L/R`) with influence 0; raise it to pose a hand by its target.
* Shape keys on every creature: `Smile`, `Frown`, `Blink`, `MouthOpen`.
  `expression:` sets them (smile, frown, blink, open_mouth, grin, angry, sad,
  surprised, sleepy).

## Animation

Each cycle is a pure function of phase: sine-based gaits with offsets between
limbs, sampled every frame.

| Rig | Animations |
|---|---|
| biped | walk, run, idle, wave, jump, sit |
| quadruped | walk, run, idle, sit, jump, tail_sway |
| bird | fly, idle, walk |
| fish | swim, idle |
| vehicle | drive, idle |

* Every animation is its own Action (`Knight_walk`, `Wolf_sit`...) on its own
  NLA track. The first one listed plays; the rest are muted. In Blender's NLA
  editor, click the star on a track to preview it alone.
* Animated creatures also get a looping `blink` on the shape keys.
* Per entity: `speed: 1.5`, `loop: false`, `cycle_frames: 40`.
  Global, in a `# settings` section: `fps`, `frame_start`.

## Settings section

```markdown
# settings
fps: 30  seed: 7  lowpoly: false  subdiv: 2
render: preview.png  engine: eevee  samples: 16  resolution: 1600x900  frame: 12
export: glb, fbx
```

Command-line options override these.

## Editing an existing file

`--base` opens a `.blend` instead of starting empty, so a text file can change
a scene the way an assistant would through Blender MCP, but repeatably:

```markdown
# edit: Tower
color.Roof: #2f5d8a   color.Flag: #e0c040   rotate: 45

# prop: Barrel
type: barrel  position: 4, -2
```

```
forge examples\edit_tower.md out\tower2.blend --base out\tower.blend --render
```

`edit` keys: `move`, `position`, `rotate`, `scale`, `hide`, `delete`, `rename`,
`color` (all materials) and `color.<MaterialSuffix>`. A new entity with the
same name as an existing one replaces it.

## Examples

| File | Shows |
|---|---|
| `examples/knight.md` | Armoured humanoid, accessories, three animations, smile |
| `examples/wolf.md` | Quadruped with run and sit |
| `examples/tower.md` | Castle tower with cone roof and windows |
| `examples/village.md` | A full scene on a terrain map, with settings |
| `examples/menagerie.md` | One of each rig with all its animations |
| `examples/island.txt` | `.txt` input and an image heightmap |
| `examples/island_heightmap.png` | Use directly as the input file |
| `examples/edit_tower.md` | Editing a built file with `--base` |

## Adding a template

One file in `forge/templates/` is one template. It is discovered automatically.

```python
# forge/templates/pillar.py
from .. import static
from ..meshkit import MeshBuilder

NAMES = ["pillar", "column"]          # accepted by `type:`

def build(spec, ctx, type_name):
    h = spec.num("height", 4.0, 0.5, 50)
    r = spec.num("radius", 0.4, 0.05, 10)
    stone = ctx.mat("Stone", "stone", spec.color("color", "#b9b4a8"), blocks=False)
    mb = MeshBuilder()
    mb.lathe([(r * 1.4, 0), (r * 1.4, 0.2), (r, 0.35), (r * 0.9, h - 0.35),
              (r * 1.3, h - 0.2), (r * 1.3, h)], n=20, mat=stone,
             cap_start=True, cap_end=True)
    return static.finish(ctx, spec, mb, bevel=0.01)
```

Keys you read through `spec` are validated and tracked, so unknown keywords
are reported without a schema. For a rigged template, build a `Rig`, fill
`rig.meta` and return `creature.finalize(...)`; see `fish.py` for the shortest
complete one. New animations are plain functions added to `LIBRARY` in
`forge/anims.py`.

## Layout

```
build.py            entry point and command line
forge.bat           Windows launcher
forge/
  parser.py         Markdown / text / image input, typed access, line numbers
  core.py           build context, entity record, template registry
  meshkit.py        bmesh kit: rings, lofts, caps, lathes, extrusions, seeded noise
  materials.py      procedural Principled materials
  rigging.py        armatures, auto weights, rigid merge, shape keys
  anims.py          animation library, Action / NLA handling
  creature.py       eyes, mouths, ears, face keys, creature pipeline
  parts.py          windows, doors, roofs, battlements, weapons
  static.py         shared finishing for structures and props
  scene.py          layout, edits, preview camera and lights, render, export
  templates/        one file per template
examples/
```

## Limits

* It builds what its templates cover. A new creature or building style means
  writing a template; there is no free-form "make me a dragon".
* The look is stylised and clean rather than sculpted. Faces are simple
  shapes; there are no fingers, toes or cloth simulation.
* Meshes have no UV maps. The procedural materials do not need them, but
  exporters only carry the base colour, roughness and metallic values, not the
  noise patterns. Terrain colours are vertex colours and do export.
* Applying modifiers on export would drop shape keys, so creatures export as
  their unsubdivided cage (smooth shaded) with the keys intact. A glTF export
  applies bevels only when nothing in the file has shape keys; FBX and STL
  apply them on every mesh that has none.
* FBX and glTF sample the IK result into plain bone keyframes, which is what
  game engines want; the IK targets themselves are exported as extra bones.
* Automatic weights are good, not hand-painted. Robes and tunic skirts in
  particular stretch on wide strides.
