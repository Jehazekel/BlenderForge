"""Anatomical profile database: JSON files with inheritance and user overrides."""

import copy
import json
import os

from ..log import ForgeError, warn

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_db = {}
_meta = {}


def _merge(base, over):
    """Deep-merge dicts. Lists (limb segment chains) are replaced whole."""
    out = copy.deepcopy(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _load():
    if _db:
        return
    for fname in sorted(os.listdir(_DATA)):
        if not fname.endswith(".json"):
            continue
        with open(os.path.join(_DATA, fname), "r", encoding="utf-8") as fh:
            try:
                data = json.load(fh)
            except ValueError as exc:
                raise ForgeError("anatomy data file %s is not valid JSON: %s" % (fname, exc))
        for name, entry in data.items():
            if name in ("_measured", "_sources", "_stature"):
                _meta.setdefault(name, {}).update(entry)
                continue
            if name.startswith("_"):
                continue
            if fname == "classes.json" and name in ("limits", "joint_rules"):
                _meta[name] = entry
            else:
                _db[name] = entry


def get(name):
    """Fully resolved profile (inheritance applied). Returns a private copy."""
    _load()
    if name not in _db:
        raise ForgeError("no anatomical profile named '%s'" % name)
    chain, seen = [], set()
    cur = name
    while cur:
        if cur in seen or cur not in _db:
            raise ForgeError("anatomy profile '%s' has a broken 'inherits' chain at '%s'" % (name, cur))
        seen.add(cur)
        chain.append(_db[cur])
        cur = _db[cur].get("inherits")
    profile = {}
    for entry in reversed(chain):
        profile = _merge(profile, entry)
    profile.pop("inherits", None)
    profile["name"] = name
    # measured values (data/measured.json) belong to this exact taxon, so they
    # are laid over last and are never inherited by breeds or relatives
    measured = _meta.get("_measured", {}).get(name)
    if measured:
        profile = _merge(profile, measured["values"])
        profile["source"] = dict(measured, source=_meta.get("_sources", {}).get(measured["dataset"], {}))
    elif profile.get("cite"):
        # hand-entered published values (humans.json): inherited by presets
        # that keep the proportions, dropped by those that set "cite": null
        cite = profile["cite"]
        profile["source"] = dict(cite, source=_meta.get("_sources", {}).get(cite["dataset"], {}))
    else:
        profile["source"] = None
    profile["stature"] = _meta.get("_stature", {}).get(name)
    # class limits, widened or narrowed by the profile's own "limits"
    limits = dict(_meta.get("limits", {}).get(profile.get("class", ""), {}))
    limits.update(profile.get("limits", {}))
    profile["limits"] = limits
    return profile


def names(plan=None):
    """Concrete profile names, optionally for one body plan."""
    _load()
    out = []
    for name in _db:
        try:
            p = get(name)
        except ForgeError:
            continue
        if plan is None or p.get("plan") == plan:
            out.append(name)
    return out


def joint_rules(posture):
    _load()
    return _meta.get("joint_rules", {}).get(posture, {"fore": [], "hind": []})


def _coerce(text, old):
    if isinstance(old, bool):
        return text.strip().lower() in ("true", "yes", "on", "1")
    if isinstance(old, (int, float)):
        return float(text)
    if old is None and text.strip().lower() in ("none", "null", "false", "no"):
        return None
    return text.strip()


def apply_overrides(profile, spec):
    """Artistic overrides: any dotted key in the input replaces a profile value.

        trunk.chest_depth: 0.5        hind.tibia: 0.42
        hind.tibia.angle: -30         tail.style: bushy

    Returns the list of paths that were overridden (validation reports them).
    """
    changed = []
    for key in list(spec.props):
        if "." not in key or key.startswith("color."):
            continue
        text = spec.get(key)
        parts = key.split(".")
        line = spec.line_of(key)
        try:
            if parts[0] in ("fore", "hind") and isinstance(profile.get(parts[0]), list):
                seg = next((s for s in profile[parts[0]] if s[0] == parts[1]), None)
                if seg is None:
                    warn("'%s': %s limb has no segment '%s' (has: %s)"
                         % (key, parts[0], parts[1], ", ".join(s[0] for s in profile[parts[0]])), line)
                    continue
                field = {"length": 1, "angle": 2, "out": 3}.get(parts[2] if len(parts) > 2 else "length")
                if field is None:
                    warn("'%s': use .length, .angle or .out" % key, line)
                    continue
                seg[field] = float(text)
            else:
                node = profile
                for p in parts[:-1]:
                    node = node[p]
                if parts[-1] not in node or isinstance(node[parts[-1]], (dict, list)):
                    raise KeyError(parts[-1])
                node[parts[-1]] = _coerce(text, node[parts[-1]])
        except (KeyError, TypeError):
            warn("'%s' is not a value in the '%s' anatomical profile, ignored" % (key, profile["name"]), line)
            continue
        except ValueError:
            raise ForgeError("'%s' expects a number, got '%s'" % (key, text), line)
        changed.append(key)
    return changed
