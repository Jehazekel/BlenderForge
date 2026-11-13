"""Shared finishing for non-rigged templates (structures, props, trees)."""

from .core import Entity
from .meshkit import add_bevel

WALLS = {
    "stone": ("stone", "#8d8a84"), "brick": ("brick", "#9b4a36"), "wood": ("wood", "#8a5e3b"),
    "plaster": ("ground", "#d9cfb8"), "metal": ("metal", "#8e969e"), "concrete": ("ground", "#9a9a98"),
    "sandstone": ("stone", "#c9aa72"), "marble": ("stone", "#dcdad4"),
}


def wall_material(ctx, spec, default="stone", label="Wall", **opts):
    """Resolve `material:` and `color:` into a wall material."""
    choice = spec.choice("material", WALLS, default)
    kind, col = WALLS[choice]
    color = spec.color("color", col)
    if kind == "wood":
        opts.pop("cylindrical", None)
        opts.pop("radius", None)
    return ctx.mat(label, kind, color, **opts), choice


def finish(ctx, spec, mb, bevel=0.0, sharp=35.0):
    """One mesh object per entity; bevel modifier unless low-poly."""
    obj = mb.to_object(spec.name, ctx.collection, sharp_angle=sharp)
    if bevel > 0 and not ctx.spec_lowpoly(spec) and spec.flag("bevel", True):
        add_bevel(obj, bevel)
    return Entity(spec.name, obj, [obj])
