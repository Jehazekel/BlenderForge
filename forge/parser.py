"""Reads the Markdown / text input format into a list of Spec objects.

Format
------
    # character: Knight
    type: humanoid  height: 1.8  build: muscular  skin: #c68642
    outfit: armor  accessories: helmet, sword

A heading `# kind: Name` starts a section. Every other line holds one or more
`key: value` pairs. Values run until the next `key:` so they may contain commas
and spaces. Bullets, blank lines, code fences, block quotes and `//` comments
are ignored. A plain title such as `# My scene` starts a notes block: prose
under it is skipped until the next `# kind: Name` heading.
"""

import difflib
import os
import re

from .log import ForgeError, warn

# heading word -> canonical kind
KINDS = {
    "character": "character", "human": "character",
    "animal": "animal", "creature": "animal",
    "structure": "structure", "building": "structure",
    "prop": "prop", "object": "prop",
    "vehicle": "vehicle",
    "tree": "tree", "plant": "tree",
    "map": "map", "terrain": "map",
    "settings": "settings", "scene": "settings",
    "edit": "edit",
}

_KEY = re.compile(r"(?:^|(?<=\s))([A-Za-z_][\w.]*):(?=\s|$)")
_HEAD = re.compile(r"^(#{1,6})\s*(.*?)\s*$")
_TRUE = {"true", "yes", "on", "1", "y"}
_FALSE = {"false", "no", "off", "0", "n", "none"}

NAMED_COLORS = {
    "white": "#f2f2f2", "black": "#101010", "grey": "#808080", "gray": "#808080",
    "red": "#c0392b", "green": "#3f8f3a", "blue": "#2f6fc0", "yellow": "#e0c040",
    "orange": "#d9772b", "purple": "#7d4fa8", "pink": "#e59ab8", "brown": "#6b4a2f",
    "tan": "#c9a67a", "gold": "#d4a637", "silver": "#b8bec6", "beige": "#d8c8a8",
    "cream": "#efe6cf", "navy": "#1f2f55", "teal": "#2f8f8a", "olive": "#6b7032",
}


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def parse_color(text):
    """'#rrggbb', '#rgb' or a colour name -> linear (r, g, b, 1). None if invalid."""
    t = text.strip().lower()
    t = NAMED_COLORS.get(t, t)
    if t.startswith("#"):
        t = t[1:]
    if len(t) == 3:
        t = "".join(ch * 2 for ch in t)
    if len(t) != 6 or any(ch not in "0123456789abcdef" for ch in t):
        return None
    rgb = [int(t[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(srgb_to_linear(c) for c in rgb) + (1.0,)


class Spec:
    """One section of the input file: a kind, a name and its key/value pairs."""

    def __init__(self, kind, name, line):
        self.kind = kind
        self.name = name
        self.line = line
        self.props = {}     # key -> (text, line)
        self.used = set()

    # -- raw access ---------------------------------------------------------
    def has(self, key):
        return key in self.props

    def line_of(self, key):
        return self.props[key][1] if key in self.props else self.line

    def get(self, key, default=None):
        self.used.add(key)
        if key in self.props:
            return self.props[key][0]
        return default

    def set_default(self, key, value):
        if key not in self.props:
            self.props[key] = (str(value), self.line)

    # -- typed access -------------------------------------------------------
    def num(self, key, default, lo=None, hi=None):
        text = self.get(key)
        if text is None:
            return default
        cleaned = text.strip().lower().rstrip("m").strip()
        try:
            value = float(cleaned)
        except ValueError:
            raise ForgeError("'%s' expects a number, got '%s'" % (key, text), self.line_of(key))
        if lo is not None and value < lo:
            warn("'%s: %s' is below the minimum, using %g" % (key, text, lo), self.line_of(key))
            value = lo
        if hi is not None and value > hi:
            warn("'%s: %s' is above the maximum, using %g" % (key, text, hi), self.line_of(key))
            value = hi
        return value

    def integer(self, key, default, lo=None, hi=None):
        return int(round(self.num(key, default, lo, hi)))

    def flag(self, key, default=False):
        text = self.get(key)
        if text is None:
            return default
        t = text.strip().lower()
        if t in _TRUE:
            return True
        if t in _FALSE:
            return False
        warn("'%s: %s' is not true/false, using %s" % (key, text, default), self.line_of(key))
        return default

    def choice(self, key, options, default):
        """Value from a fixed list. Unknown values fall back to the default."""
        text = self.get(key)
        if text is None:
            return default
        t = text.strip().lower().replace(" ", "_").replace("-", "_")
        if t in options:
            return t
        near = difflib.get_close_matches(t, list(options), n=1, cutoff=0.7)
        if near:
            warn("unknown %s '%s', assuming '%s'" % (key, text, near[0]), self.line_of(key))
            return near[0]
        warn("unknown %s '%s', using '%s' (options: %s)"
             % (key, text, default, ", ".join(sorted(options))), self.line_of(key))
        return default

    def color(self, key, default):
        text = self.get(key)
        if text is None:
            return parse_color(default) if isinstance(default, str) else default
        col = parse_color(text)
        if col is None:
            warn("'%s: %s' is not a colour (#rrggbb or a name), using default" % (key, text),
                 self.line_of(key))
            return parse_color(default) if isinstance(default, str) else default
        return col

    def items(self, key, default=()):
        text = self.get(key)
        if text is None:
            return list(default)
        out = [p.strip().lower().replace(" ", "_").replace("-", "_")
               for p in re.split(r"[,;]", text)]
        return [p for p in out if p and p not in ("none", "no")]

    def vec(self, key, default=None, size=3):
        text = self.get(key)
        if text is None:
            return default
        parts = [p for p in re.split(r"[,\s]+", text.strip()) if p]
        try:
            vals = [float(p) for p in parts]
        except ValueError:
            raise ForgeError("'%s' expects numbers like '1, 2, 0', got '%s'" % (key, text),
                             self.line_of(key))
        if len(vals) == 1 and size > 1 and key in ("scale",):
            vals = vals * size
        while len(vals) < size:
            vals.append(0.0)
        return vals[:size]

    def given_count(self, key):
        """How many numbers were written for a vector key."""
        text = self.props.get(key, ("", 0))[0]
        return len([p for p in re.split(r"[,\s]+", text.strip()) if p])

    def warn_unused(self):
        for key, (text, line) in self.props.items():
            if key not in self.used:
                warn("unknown keyword '%s' for %s '%s', ignored" % (key, self.kind, self.name), line)


def _strip_comment(line):
    for mark in ("//", "<!--"):
        pos = line.find(mark)
        if pos >= 0:
            line = line[:pos]
    return line


def _split_pairs(text, lineno):
    matches = list(_KEY.finditer(text))
    if not matches:
        raise ForgeError("expected 'key: value', got '%s'" % text.strip(), lineno)
    lead = text[:matches[0].start()].strip()
    if lead:
        raise ForgeError("unexpected text '%s' before '%s:'" % (lead, matches[0].group(1)), lineno)
    pairs = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        value = text[m.end():end].strip()
        if not value:
            raise ForgeError("'%s:' has no value" % m.group(1), lineno)
        pairs.append((m.group(1).lower(), value))
    return pairs


def _kind_for(word, lineno):
    w = word.lower()
    if w in KINDS:
        return KINDS[w]
    near = difflib.get_close_matches(w, list(KINDS), n=1, cutoff=0.7)
    if near:
        warn("unknown section '%s', assuming '%s'" % (word, near[0]), lineno)
        return KINDS[near[0]]
    raise ForgeError("unknown section '%s' (expected one of: %s)"
                     % (word, ", ".join(sorted(set(KINDS.values())))), lineno)


def parse_text(text):
    specs = []
    current = None
    names = set()
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw).strip()
        if not line or line.startswith(("```", "~~~", ">", "---", "===", ";")):
            continue
        head = _HEAD.match(line)
        body = head.group(2) if head else line
        if not head:
            body = re.sub(r"^[-*+]\s+", "", body)

        # Section heading: "# kind: Name", or "kind: Name" alone on a line.
        m = re.match(r"^([A-Za-z_]+)\s*:\s*(\S.*)$", body)
        is_heading = False
        if head:
            if m:
                is_heading = True
            elif body.lower() in ("settings", "scene"):
                current = Spec("settings", "settings", lineno)
                specs.append(current)
                continue
            else:
                current = None  # a plain Markdown title, e.g. "# My scene": notes follow
                continue
        elif m and m.group(1).lower() in KINDS and len(_KEY.findall(body)) == 1:
            is_heading = True
        if is_heading:
            kind = _kind_for(m.group(1), lineno)
            name = re.sub(r"[^\w\- ]", "", m.group(2)).strip() or kind.title()
            if kind not in ("settings", "edit"):
                base, n = name, 2
                while name.lower() in names:
                    name = "%s_%d" % (base, n)
                    n += 1
                if name != base:
                    warn("duplicate name '%s', renamed to '%s'" % (base, name), lineno)
                names.add(name.lower())
            current = Spec(kind, name, lineno)
            specs.append(current)
            continue

        if current is None and not _KEY.search(body):
            continue            # free-form notes before the first section
        if current is None:
            raise ForgeError("'%s' appears before any '# kind: Name' heading" % body, lineno)
        for key, value in _split_pairs(body, lineno):
            if key in current.props:
                warn("'%s' given twice for '%s', using the later value" % (key, current.name), lineno)
            current.props[key] = (value, lineno)
    if not any(s.kind not in ("settings",) for s in specs):
        raise ForgeError("no sections found; add a heading such as '# character: Knight'")
    return specs


IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".tga", ".tif", ".tiff", ".exr", ".webp")


def parse_file(path):
    """Markdown / text -> specs. An image becomes a terrain map built from it."""
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        name = re.sub(r"\W+", "_", os.path.splitext(os.path.basename(path))[0]) or "Map"
        spec = Spec("map", name, 1)
        spec.props = {"type": ("terrain", 1), "heightmap": (path, 1), "colors": ("image", 1)}
        return [spec]
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            text = fh.read()
    except OSError as exc:
        raise ForgeError("cannot read input file: %s" % exc)
    except UnicodeDecodeError:
        raise ForgeError("input is not UTF-8 text (images must end in .png/.jpg/...)")
    return parse_text(text)
