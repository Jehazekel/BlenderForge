# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack
Local web app (not built yet). A small local server drives Blender, and the user can switch between headless runs (`blender --background`) and a live GUI Blender window (head mode, via `tools/live_view.py` / Blender MCP). Framework undecided.

## Users
Layered, two audiences in one interface:
- **Creators / game devs**: want a rigged, animated model from a short text spec, then an export. They do not care about internals.
- **The maintainer**: builds and tunes creatures; needs anatomy numbers, gates, animation checks and build logs.
Simple by default; maintainer detail is one step away, never in the creator's way.

## Product Purpose
BlenderForge builds rigged 3D characters, animals, structures, maps and props in Blender from a plain text (.md) spec. The GUI wraps that loop: manage projects, write or generate the spec, build, look at the model and its animations, check it, export it.

## Positioning
Deterministic: no AI, no network, no GPU at build time. The same spec always gives the same file, byte for byte. Proportions come from cited anatomy profiles, not guesses.

## Operating Context
- A project is one spec file (`.md`) plus its outputs (`.blend`, preview `.png`, `.glb`/`.fbx`/`.stl`).
- New project: pick a template (humanoid, tetrapod, bird, fish, snake, house, tower, bridge, terrain, tree, prop, vehicle, or an example such as knight, wolf, village); the spec is generated, then edited either through a form or as raw markdown, kept in sync.
- Build modes: `--check` (validate only, ~1 s), build + render preview, export. Renders 1-10 s.
- Views: front, side, face, sheet (six angles); focus on a bone; frame/animation scrub.
- Checks: anatomy line (errors, warnings, key sizes), mirror symmetry, skin weights, animation checks (IK reach, lowest bone, sharpest bend), regression sweep of 18 scenes (~50 s).
- Edit mode: `--base scene.blend` adds or replaces entities in an existing file.

## Capabilities and Constraints
- Builder is `build.py` run by Blender 5.2; the GUI never changes how models are built.
- Options: export glb/fbx/stl, engine eevee/workbench/cycles, samples, resolution, frame, low-poly, fps.
- Faces -Y, stands on z = 0, left is +X.
- Undecided: framework, how projects are stored on disk beyond spec + out folder.

## Evidence on Hand
- Real example specs in `examples/` (base male, base female, village plan).
- Real check output, e.g. Knight: "0 errors, 0 warnings; 1.80 m, 7.7 heads tall, hips 0.95 m, shoulders 1.47 m, arm span 2.03 m".
- No user counts, testimonials or benchmarks exist; do not invent them.

## Product Principles
1. The spec is the source of truth; every GUI control writes to it.
2. The model is the result; give it the most room.
3. Numbers before pictures: checks run first, renders when shape matters.
4. Simple first, detail on request.
5. Same input, same output, visibly.
