---
name: BlenderForge Studio
description: Local, form-first desktop GUI for building rigged Blender models from a text spec.
colors:
  canvas: "#2b2622"
  panel-recessed: "#241f1c"
  stage: "#221e1b"
  canvas-soft: "#383330"
  hairline: "#3f3a36"
  hairline-strong: "#5a534d"
  ink: "#f7f5f0"
  body-strong: "#dad2c1"
  body: "#c9c0ad"
  mute: "#aea69c"
  status-pass: "#a8c69f"
  status-warn: "#e0b36a"
  status-fail: "#e88a72"
typography:
  headline:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "32px"
    fontWeight: 500
    lineHeight: "40px"
    letterSpacing: "-0.8px"
  title:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "18px"
    fontWeight: 500
    lineHeight: "24px"
    letterSpacing: "-0.2px"
  body:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: "20px"
  label:
    fontFamily: "Inter, system-ui, sans-serif"
    fontSize: "13px"
    fontWeight: 500
    lineHeight: "18px"
  mono:
    fontFamily: "DM Mono, ui-monospace, Menlo, monospace"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: "20px"
  mono-small:
    fontFamily: "DM Mono, ui-monospace, Menlo, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: "16px"
rounded:
  control: "3px"
  panel: "4px"
  dot: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  panel: "20px"
  xl: "24px"
  2xl: "32px"
  3xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.canvas}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
    height: "36px"
  button-primary-hover:
    backgroundColor: "{colors.body-strong}"
    textColor: "{colors.canvas}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.body-strong}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
    height: "36px"
  button-ghost-hover:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.ink}"
  button-line:
    backgroundColor: "transparent"
    textColor: "{colors.body-strong}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
    height: "36px"
  button-icon:
    backgroundColor: "transparent"
    textColor: "{colors.mute}"
    rounded: "{rounded.control}"
    size: "36px"
  segmented-track:
    backgroundColor: "{colors.canvas-soft}"
    rounded: "{rounded.panel}"
    padding: "2px"
  segment:
    backgroundColor: "transparent"
    textColor: "{colors.mute}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "6px 12px"
    height: "32px"
  segment-on:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
  input:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "9px 10px"
  chip:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "6px 8px 6px 10px"
  clip:
    backgroundColor: "transparent"
    textColor: "{colors.body}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    padding: "6px 12px"
    height: "32px"
  clip-on:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.canvas}"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.body}"
    rounded: "{rounded.control}"
    padding: "8px 12px"
  nav-item-on:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.ink}"
---

# Design System: BlenderForge Studio

## Overview

**Creative North Star: "The Quiet Workbench"**

A warm charcoal room where the model and the spec are the only things that speak. The chrome is low-contrast, flat and thin: one hairline between panes, one cream button per view, colour reserved for build status. Density is moderate rather than IDE-tight; controls are 32-36px tall with roomy 44px form rows, so a beginner can read the form while a maintainer still finds every check.

The world is Warp-inspired: warm near-black surfaces stepped by a few lightness points instead of shadows, Inter for every interface word, DM Mono only for text the machine reads or writes (spec Markdown, file paths, numbers, frame counters). Real BlenderForge renders are the imagery; nothing decorative competes with them.

The system refuses the dense five-panel IDE. Two working panes at most, the model stage always the larger one.

**Key Characteristics:**
- Warm charcoal tonal layering, no shadows, 1px hairlines separate panes.
- Cream (`ink`) is both the brightest text and the single primary action.
- Status colours (pass, warn, fail) appear only as status, plus warn as the spec-key syntax colour.
- Small radii (3px controls, 4px panels and tracks); no pills except 8px status dots.
- Segmented controls for every exclusive choice; chips for lists of parts.

## Colors

A monochrome warm-charcoal ramp with cream ink, plus three muted status hues.

### Primary
- **Bone Cream** (`ink`): primary button fill, selected animation clip, focus ring, selection highlight, headings and active control text. The only light fill in the interface.

### Neutral
- **Warm Charcoal** (`canvas`): app background, top bar, form pane, and the "on" fill inside a segmented track (it reads as a hole cut into the soft fill).
- **Recessed Panel** (`panel-recessed`): side sheets and code blocks that sit below the canvas (template detail aside, Markdown editor, command preview).
- **Stage** (`stage`): the model viewport and thumbnail wells; the darkest surface, so renders carry the light.
- **Soft Fill** (`canvas-soft`): inputs, chips, segmented tracks, hover fill for ghost and icon buttons, active settings nav item.
- **Hairline** (`hairline`): every pane divider, row rule, input border and tile outline.
- **Strong Hairline** (`hairline-strong`): input hover border and dashed "add" outlines; never a pane divider.
- **Body Strong** (`body-strong`): links, ghost button text, spec code text, primary-button hover fill.
- **Body** (`body`): running text, list rows, status line, unselected clips.
- **Mute** (`mute`): field labels, hints, column headers, unselected segments, icon buttons at rest, mono metadata.

### Tertiary (status)
- **Sage Pass** (`status-pass`): passing check dots.
- **Amber Warn** (`status-warn`): warning dots; also the key colour in spec Markdown syntax (`type:`, `height:`).
- **Clay Fail** (`status-fail`): failing check dots and the status-line problem dot.

### Named Rules
**The Status-Only Colour Rule.** Hue appears only to report a check result (and amber for spec keys). Any other coloured fill is a defect; user data swatches (skin colour) are content, not chrome.

**The One Cream Rule.** A view has one cream button: the primary action (Build, New project, Create). Selected clips may be cream because they are state, not action.

## Typography

**Interface Font:** Inter (with system-ui, sans-serif)
**Mono Font:** DM Mono (with ui-monospace, Menlo, monospace)

**Character:** A neutral grotesk for every label and control, paired with a soft mono that marks text BlenderForge itself reads or prints.

### Hierarchy
- **Headline** (500, 32px/40px, -0.8px): page titles on full-page views (Projects, New project).
- **Title** (500, 18px/24px, -0.2px): section heads in settings. Panel subheads inside the workspace drop to 14px/600.
- **Body** (400 or 500, 14px/20px): controls, buttons, inputs, list rows. Intro copy may run 15px/22px.
- **Label** (400-500, 13px/18px): field labels, segment and clip text, hints, template group heads (500, `mute`). Sentence case.
- **Mono** (400, 13px, line-height 20-24px): spec Markdown and command previews.
- **Mono Small** (400, 12px/16px): file paths and frame counters (`examples/base_male.md`, `1 / 48`).

### Named Rules
**The Machine Text Rule.** DM Mono is for spec text, paths, hex values, numbers the build reports, and frame counts. Never for headings, buttons or prose.

**The Sentence Case Rule.** Labels and group heads are sentence case in `mute`; hierarchy comes from size, weight and colour, not uppercase tracking.

## Layout

Desktop only, minimum width 1280px. The workspace is a fixed three-band column: top bar (10px 16px padding, hairline below), the working split, and a single status line (10px 20px, hairline above). The split is a form pane of 360-440px on the left and the model stage filling the rest (`flex: 999`), separated by one vertical hairline. The stage has its own toolbar row (view segments, fit button) and a clip bar below the image.

Full-page views centre a single column: Projects at max 1040px with 56px top padding, Advanced settings at max 1200px with a 180-220px section nav and a 760px content column. The New project view pairs a template tile grid (`auto-fill, minmax(132px, 1fr)`, 12px gap, square tiles) with a 400-520px recessed aside.

Spacing steps on 4/8 with 12 and 20 as working values: 8px between toolbar controls, 12px tile and row gaps, 16px stage padding, 20px form-pane padding, 24-32px between page sections, 48px between nav and content.

**The Model Gets the Room Rule.** The model stage is always the largest region; side panes cap at 440px (520px for the template aside).

## Elevation & Depth

Flat. Depth is tonal: the stage (`stage`) and recessed panels (`panel-recessed`) sit darker than the `canvas`, and fills (`canvas-soft`) sit lighter. Panes are separated by 1px `hairline` borders. The only overlay is the stage hint label on a translucent stage fill (`rgba(34,30,27,.8)`).

**The Hairline Rule.** No box-shadows anywhere. If two regions need separation, use a 1px hairline or a lightness step.

## Shapes

Small, near-square corners: 3px on every control (buttons, inputs, chips, segments, clips, nav items, thumbnails), 4px on containers (segmented tracks, template tiles, code blocks). Circles appear only as 8px status dots. Selection on tiles is a 2px cream outline offset 2px; focus everywhere is the same 2px cream outline. Dashed `hairline-strong` borders mark "add" affordances only.

## Components

### Buttons
Quiet, compact, one loud.
- **Shape:** 3px radius, 36px min height, 8px 14px padding, Inter 500 14px, 8px icon gap.
- **Primary:** cream fill, charcoal text; hover drops to `body-strong`.
- **Ghost:** transparent, `body-strong` text, no border; hover fills `canvas-soft` and text goes `ink`. Used for Check, Export, Open .blend.
- **Line:** ghost with a 1px `hairline` border, for actions inside settings rows (Choose, Run sweep, Copy).
- **Icon:** 36px square, `mute` glyph (inline SVG, 1.6-2px stroke), hover `canvas-soft`.
- **Focus:** 2px `ink` outline, 2px offset.

### Segmented controls
The default for every exclusive choice: Headless/Live Blender, Form/Markdown, view angle, body build, render engine. Track in `canvas-soft` with 2px padding and 4px radius; segments are transparent `mute` text, 32px tall; the selected segment takes the `canvas` fill and `ink` text.

### Chips
- **Style:** `canvas-soft` fill, `ink` 13px text, 3px radius, a trailing 20px remove button in `mute`.
- **Add:** a transparent sibling with a 1px dashed `hairline-strong` border; hover brightens border and text.

### Animation clips
Toggle buttons in the clip bar: 1px `hairline` border, `body` text, 32px tall; the playing clip turns cream with charcoal text.

### Inputs / Fields
- **Style:** `canvas-soft` fill, 1px `hairline` border, 3px radius, 9px 10px padding, Inter 14px; numeric and hex inputs switch to DM Mono.
- **Hover:** border moves to `hairline-strong`.
- **Focus:** 2px `ink` outline.
- **Form row:** 104px label column in `mute` 13px, 44px min row height.

### Navigation
Top bar holds the project mark (icon link home), project switcher (ghost, 600 weight, chevron), save state in `mute`, then right-aligned mode segments, ghost actions, primary Build and a settings icon. Settings nav items are 3px-radius rows in `body`; hover and active fill `canvas-soft` with `ink` text.

### Template tile
Square real render, 4px radius, 1px inset `hairline` outline that brightens to `mute` on hover (150ms ease-out); selected tiles get the 2px cream offset ring and `ink` caption. Captions are Inter 500 13px below the image.

### Status line and checks
One line at the foot of the workspace: an 8px status dot, a plain-language count ("1 problem, 1 warning"), key measures in `mute`, and a Details link. Check rows repeat the pattern: dot, 500-weight name in `ink`, `body` detail, hairline rule below.

## Do's and Don'ts

### Do:
- **Do** keep the model stage the largest region and side panes at or under 440px.
- **Do** use one cream primary button per view and ghost or line buttons for everything else.
- **Do** separate panes with a 1px `hairline` (#3f3a36) and step surfaces by lightness for depth.
- **Do** use segmented controls for exclusive choices and chips for part lists.
- **Do** set spec text, paths, hex values and build numbers in DM Mono; everything else in Inter.
- **Do** show real BlenderForge renders for templates, thumbnails and the stage.

### Don't:
- **Don't** add box-shadows or glows; this world is flat.
- **Don't** use status colours (#a8c69f, #e0b36a, #e88a72) for decoration, branding or non-status emphasis.
- **Don't** round controls past 4px or make pill buttons; circles are for 8px status dots only.
- **Don't** introduce a third working pane or a dense multi-panel IDE layout.
- **Don't** use uppercase tracked labels or eyebrows above headings; labels are sentence case.
