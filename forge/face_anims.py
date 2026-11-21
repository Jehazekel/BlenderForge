"""Facial clip library keyed on ARKit blendshape names (the default face template).

Any mesh whose shape keys use ARKit names works: the bundled ICT-FaceKit head
(forge/assets/face, from tools/import_facekit.py), an iPhone capture, most avatar
heads. Names ending _L/_R are the face's own left/right; an expression may give a
bare name ("mouthSmile") to set both sides. Older forge heads with MouthOpen /
Wide / Pucker / Blink keys are reached through ALIASES.

Each clip is built per frame from layers that add up and clamp to 0..1:
  keys     expression timeline, "t expr[*w][+expr...] | ..." with smooth easing
  talk     lip-sync of a fixed line: letters -> visemes -> ARKit mouth shapes
  look     gaze timeline (yaw, pitch in units of a full eyeLook shape) with saccades
  blink    deterministic blinks every `blink` seconds (0 = none)
  breathe  slow nostril/jaw cycle, a whole number of cycles so loops close
Every clip is one Action on the shape-key datablock, on its own NLA track, named
<name>_face_<clip>. Expression and viseme weights are hand-tuned approximations.
"""
import math

from .anims import _push_nla, action_fcurves
from .rigify_anims import _norm

EXPR = {
    "neutral": {},
    "smile": {"mouthSmile": .55, "cheekSquint": .25, "eyeSquint": .1},
    "happy": {"mouthSmile": .75, "cheekSquint": .45, "eyeSquint": .25, "browOuterUp": .1, "mouthDimple": .2},
    "laugh": {"mouthSmile": .95, "cheekSquint": .7, "eyeSquint": .55, "eyeBlink": .2, "jawOpen": .4,
              "mouthUpperUp": .3, "mouthDimple": .3, "browInnerUp": .15},
    "smirk": {"mouthSmile_L": .6, "mouthDimple_L": .3, "cheekSquint_L": .25, "eyeSquint_L": .15,
              "browOuterUp_R": .2, "mouthPress_R": .2},
    "sad": {"browInnerUp": .7, "browDown": .1, "mouthFrown": .6, "mouthShrugLower": .3, "mouthPress": .2, "eyeSquint": .1},
    "angry": {"browDown": .85, "eyeSquint": .4, "noseSneer": .45, "mouthPress": .35, "mouthFrown": .3, "jawForward": .1},
    "fear": {"browInnerUp": .85, "browOuterUp": .4, "eyeWide": .8, "mouthStretch": .5, "jawOpen": .15},
    "surprise": {"browInnerUp": .8, "browOuterUp": .8, "eyeWide": .9, "jawOpen": .45, "mouthFunnel": .15},
    "disgust": {"noseSneer": .8, "mouthUpperUp": .55, "browDown": .4, "eyeSquint": .35, "mouthFrown": .3,
                "mouthShrugLower": .3},
    "confused": {"browDown_L": .55, "browOuterUp_R": .6, "eyeSquint_L": .3, "mouthPress_L": .3, "mouthLeft": .25,
                 "mouthShrugLower": .2},
    "curious": {"browInnerUp": .4, "browOuterUp": .45, "eyeWide": .3, "mouthPucker": .15, "jawOpen": .05},
    "frustrated": {"browDown": .6, "browInnerUp": .25, "mouthPress": .55, "mouthRollLower": .25, "noseSneer": .2,
                   "eyeSquint": .25},
    "pain": {"browDown": .7, "browInnerUp": .5, "eyeSquint": .8, "eyeBlink": .35, "noseSneer": .5,
             "mouthStretch": .6, "mouthUpperUp": .35, "jawOpen": .15},
    "exhausted": {"eyeBlink": .45, "browInnerUp": .3, "jawOpen": .2, "mouthFrown": .25, "mouthLowerDown": .15},
    "cry": {"browInnerUp": .95, "browDown": .25, "eyeSquint": .6, "eyeBlink": .3, "mouthFrown": .8,
            "mouthStretch": .4, "mouthShrugLower": .5, "jawOpen": .2, "noseSneer": .25},
    "sob": {"jawOpen": .25, "mouthStretch": .2, "browInnerUp": .05},
    "frown": {"browDown": .55, "mouthFrown": .55, "mouthPress": .2},
    "confident": {"mouthSmile": .3, "mouthSmile_L": .15, "eyeSquint": .2, "browDown": .1},
    "listen": {"browInnerUp": .2, "browOuterUp": .1, "mouthSmile": .12},
    "shout": {"browDown": .5, "eyeWide": .3, "noseSneer": .3},
    "scream": {"browInnerUp": .9, "eyeWide": 1.0, "jawOpen": .85, "mouthStretch": .8, "mouthUpperUp": .3,
               "mouthLowerDown": .5},
    "whisper": {"browInnerUp": .15, "eyeSquint": .1},
    "brows_up": {"browInnerUp": .8, "browOuterUp": .8},
    "brows_down": {"browDown": .8},
    "brow_l": {"browOuterUp_L": .8, "browInnerUp": .2},
    "brow_r": {"browOuterUp_R": .8, "browInnerUp": .2},
    "squint": {"eyeSquint": .8, "cheekSquint": .3, "browDown": .2},
    "widen": {"eyeWide": .9, "browOuterUp": .4, "browInnerUp": .3},
    "jaw_open": {"jawOpen": .7}, "jaw_left": {"jawLeft": .6, "jawOpen": .1}, "jaw_right": {"jawRight": .6, "jawOpen": .1},
    "jaw_fwd": {"jawForward": .6, "jawOpen": .1},
    "pucker": {"mouthPucker": .9}, "funnel": {"mouthFunnel": .7, "jawOpen": .15},
    "roll": {"mouthRollLower": .6, "mouthRollUpper": .6}, "press": {"mouthPress": .7},
    "lips_left": {"mouthLeft": .6}, "lips_right": {"mouthRight": .6}, "stretch": {"mouthStretch": .6},
    "shrug": {"mouthShrugLower": .6, "mouthShrugUpper": .4},
    "inhale": {"noseSneer": .08, "jawOpen": .03, "mouthClose": .02},
}

VISEME = {      # Oculus-style viseme set as ARKit mouth shapes
    "sil": {}, "PP": {"mouthPress": .5, "mouthRollLower": .2, "mouthRollUpper": .1},
    "FF": {"mouthRollLower": .6, "mouthUpperUp": .25, "jawOpen": .08},
    "TH": {"jawOpen": .15, "mouthRollLower": .2}, "DD": {"jawOpen": .2, "mouthStretch": .15},
    "kk": {"jawOpen": .25, "mouthStretch": .1}, "CH": {"mouthFunnel": .5, "mouthPucker": .2, "jawOpen": .15},
    "SS": {"jawOpen": .05, "mouthStretch": .3, "mouthSmile": .1}, "nn": {"jawOpen": .15, "mouthStretch": .1},
    "RR": {"mouthPucker": .3, "mouthFunnel": .2, "jawOpen": .15},
    "aa": {"jawOpen": .6, "mouthLowerDown": .2}, "E": {"jawOpen": .35, "mouthStretch": .3, "mouthUpperUp": .15},
    "I": {"jawOpen": .25, "mouthSmile": .3, "mouthStretch": .2}, "O": {"jawOpen": .4, "mouthFunnel": .5, "mouthPucker": .2},
    "U": {"jawOpen": .15, "mouthPucker": .7, "mouthFunnel": .2},
}
DIGRAPH = {"th": "TH", "sh": "CH", "ch": "CH", "ph": "FF", "wh": "U", "ng": "nn", "ck": "kk", "ee": "I",
           "ea": "I", "oo": "U", "ou": "O", "ow": "O", "ai": "E", "ay": "E", "oi": "O", "qu": "kk"}
LETTER = {"a": "aa", "e": "E", "i": "I", "o": "O", "u": "U", "y": "I", "b": "PP", "m": "PP", "p": "PP",
          "f": "FF", "v": "FF", "t": "DD", "d": "DD", "k": "kk", "g": "kk", "c": "kk", "q": "kk", "x": "kk",
          "j": "CH", "s": "SS", "z": "SS", "n": "nn", "l": "nn", "r": "RR", "w": "U", "h": "E"}
VOWELS = {"aa", "E", "I", "O", "U"}
STYLE = {"normal": (1.0, 1.0), "whisper": (.5, .8), "shout": (1.35, .85), "soft": (.75, 1.0)}   # (mouth size, pace)
ALIASES = {"jawOpen": ("MouthOpen",), "mouthStretch": ("Wide",), "mouthSmile": ("Wide",),
           "mouthPucker": ("Pucker",), "mouthFunnel": ("Pucker",), "eyeBlink": ("Blink",)}

LINE = "so I told them we would meet by the old bridge before the light was gone"


def _c(frames, keys, loop=True, **kw):
    d = {"frames": frames, "keys": keys, "loop": loop, "blink": 3.5, "breathe": True}
    d.update(kw)
    return d


def _hold(e, frames=96, **kw):
    """Hold an expression with a slight swell, so a loop stays alive."""
    keys = kw.pop("keys", "0 %s | .5 %s*0.9 | 1 %s" % (e, e, e))
    return _c(frames, keys, **kw)


DARTS = [(0, 0, 0), (.22, .35, .05), (.4, .35, .05), (.45, -.2, -.1), (.7, -.2, -.1), (.75, 0, 0), (1, 0, 0)]
CLIPS = {
    "neutral": _hold("neutral", look=DARTS),
    "happy": _hold("happy"), "sad": _hold("sad", look=[(0, 0, -.4), (1, 0, -.4)]), "angry": _hold("angry"),
    "fear": _hold("fear", look=[(0, -.5, 0), (.3, .5, .1), (.6, -.3, 0), (1, -.5, 0)], blink=2.0),
    "surprise": _c(48, "0 neutral | .15 surprise | .6 surprise*0.8 | 1 surprise*0.5", loop=False),
    "disgust": _hold("disgust", look=[(0, .3, -.2), (1, .3, -.2)]),
    "confused": _hold("confused", look=[(0, -.3, .3), (.5, .3, .25), (1, -.3, .3)]),
    "curious": _hold("curious", look=[(0, .4, 0), (.5, .2, .2), (1, .4, 0)]),
    "frustrated": _hold("frustrated", keys="0 frustrated | .4 frustrated+press*0.4 | 1 frustrated"),
    "pain": _c(72, "0 pain | .3 pain*0.8 | .5 pain | .8 pain*0.85 | 1 pain", blink=0),
    "exhausted": _hold("exhausted", look=[(0, 0, -.5), (1, 0, -.5)], blink=2.5),
    "cry": _c(72, "0 cry | .17 cry+sob | .33 cry | .5 cry+sob | .67 cry | .83 cry+sob | 1 cry", blink=0),
    "laugh": _c(48, "0 laugh | .25 laugh+jaw_open*0.3 | .5 laugh | .75 laugh+jaw_open*0.3 | 1 laugh", blink=0),
    "smile": _hold("smile"), "smirk": _hold("smirk"), "frown": _hold("frown"), "confident": _hold("confident"),
    "brows": _c(96, "0 neutral | .15 brows_up | .3 neutral | .45 brows_down | .6 neutral | .7 brow_l | "
                    ".8 neutral | .9 brow_r | 1 neutral"),
    "squint": _c(48, "0 neutral | .3 squint | .7 squint | 1 neutral"),
    "widen": _c(48, "0 neutral | .25 widen | .7 widen | 1 neutral"),
    "blink": _c(48, "0 neutral | 1 neutral", blink=0, blinks=[.2, .65, .78]),
    "look_around": _c(120, "0 neutral | 1 neutral", look=[(0, 0, 0), (.1, .8, 0), (.25, .8, .1), (.3, -.8, 0),
                                                          (.5, -.8, .1), (.55, 0, .6), (.7, 0, .6), (.75, 0, -.6),
                                                          (.88, 0, -.6), (.92, 0, 0), (1, 0, 0)]),
    "jaw": _c(96, "0 neutral | .15 jaw_open | .3 neutral | .45 jaw_left | .6 neutral | .75 jaw_right | "
                  ".85 jaw_fwd | 1 neutral"),
    "lips": _c(120, "0 neutral | .1 pucker | .2 funnel | .3 roll | .4 press | .5 lips_left | .6 lips_right | "
                    ".7 stretch | .8 shrug | .9 smile | 1 neutral"),
    "breathe": _c(96, "0 neutral | 1 neutral", look=[(0, 0, -.1), (1, 0, -.1)]),
    "transition": _c(144, "0 neutral | .15 happy | .3 happy | .45 sad | .6 sad | .75 angry | .9 angry*0.5 | "
                          "1 neutral", loop=False),
    # talking: lip-sync of LINE (or `say:` text) on top of a base expression
    "talk_idle": _c(96, "0 neutral | 1 neutral", talk="mm hm. yeah", talk_at=.3, style="soft", look=DARTS),
    "talk": _c(96, "0 neutral | .3 brows_up*0.3 | .5 neutral | 1 neutral", talk=LINE, look=DARTS),
    "whisper": _c(96, "0 whisper | 1 whisper", talk=LINE, style="whisper", look=[(0, .3, -.1), (1, .3, -.1)]),
    "shout": _c(72, "0 shout | 1 shout", talk="get back here right now", style="shout", blink=0),
    "scream": _c(48, "0 neutral | .2 scream | .8 scream | 1 scream*0.6", loop=False, blink=0),
    "laugh_talk": _c(96, "0 happy | .5 laugh*0.6 | 1 happy", talk="ha that was the best thing I ever saw", blink=4),
    "cry_talk": _c(96, "0 cry*0.8 | .5 cry*0.8+sob*0.5 | 1 cry*0.8", talk="I just wanted it to be over",
                   style="soft", blink=0),
    "angry_talk": _c(96, "0 angry | 1 angry", talk="I told you not to touch that", style="shout"),
    "emotional_talk": _c(144, "0 sad | .5 sad*0.4+smile*0.4 | 1 happy", talk=LINE + " but we found it", loop=False),
    "lipsync": _c(144, "0 neutral | 1 neutral", talk=LINE + " and then we walked home together", look=DARTS),
    "phonemes": _c(len(VISEME) * 10, "0 neutral | 1 neutral", visemes=list(VISEME), blink=0),
    "mouth_transitions": _c(96, "0 neutral | 1 neutral", visemes=["aa", "O", "U", "I", "E", "PP", "FF", "aa", "sil"]),
    "jaw_talk": _c(96, "0 neutral | 1 neutral", talk="ma pa ba da ta ga ka", style="shout"),
    "listen": _c(144, "0 listen | .3 listen+smile*0.3 | .5 listen | .7 brows_up*0.3+listen | 1 listen", look=DARTS),
}

REFERENCE = {
    "facial": "neutral expression=neutral|happiness=happy|sadness=sad|anger=angry|fear=fear|surprise=surprise|"
              "disgust=disgust|confusion=confused|curiosity=curious|frustration=frustrated|pain=pain|"
              "exhaustion=exhausted|crying=cry|laughing=laugh|smiling=smile|smirking=smirk|frowning=frown|"
              "eyebrow movement=brows|eye squinting=squint|eye widening=widen|blinking=blink|"
              "looking around=look_around|jaw movement=jaw|lip movement=lips|natural breathing expressions=breathe|"
              "emotional transitions=transition",
    "talking": "talking idle=talk_idle|normal conversation=talk|whispering=whisper|shouting=shout|screaming=scream|"
               "laughing while talking=laugh_talk|crying while talking=cry_talk|angry dialogue=angry_talk|"
               "emotional dialogue=emotional_talk|lip synchronization=lipsync|phoneme animation=phonemes|"
               "mouth shape transitions=mouth_transitions|jaw articulation=jaw_talk|listening animations=listen",
    "emotional": "expressing frustration=frustrated|expressing disappointment=sad|expressing confidence=confident|"
                 "expressing fear=fear|expressing confusion=confused|expressing curiosity=curious|"
                 "expressing exhaustion=exhausted|celebrating=laugh",
}


def reference_map():
    return {cat: {_norm(a): b.split(",") for a, b in (p.split("=") for p in text.split("|"))}
            for cat, text in REFERENCE.items()}


def category_of():
    out = {}
    for cat, names in reference_map().items():
        for clips in names.values():
            for c in clips:
                out.setdefault(c, cat)
    return out


def resolve(names):
    """Names (face clip, reference name, '@category', 'all') -> face clips; unknown names are skipped
    (they are body clips, resolved by rigify_anims)."""
    ref, out = reference_map(), []
    flat = {}
    for names_in in ref.values():
        for n, clips in names_in.items():
            flat.setdefault(n, clips)
    for raw in names:
        n = _norm(raw)
        if n == "all":
            picks = list(CLIPS)
        elif n.startswith("@"):
            picks = [c for clips in ref.get(n[1:], {}).values() for c in clips]
        else:
            picks = [n] if n in CLIPS else flat.get(n, [])
        out.extend(p for p in picks if p not in out)
    return out


# -- evaluation ---------------------------------------------------------------------
def _ease(t):
    return t * t * (3 - 2 * t)


def _parse_mix(text):
    mix = {}
    for part in text.split("+"):
        name, _, w = part.strip().partition("*")
        if name not in EXPR:
            raise KeyError("unknown expression '%s'" % name)
        for k, v in EXPR[name].items():
            mix[k] = mix.get(k, 0.0) + v * (float(w) if w else 1.0)
    return mix


def _timeline(keys):
    out = []
    for item in keys.split("|"):
        t, _, e = item.strip().partition(" ")
        out.append((float(t), _parse_mix(e)))
    return out


def _sample(tl, t):
    """Smoothly eased value of a [(t, {name: w})] timeline at t (0..1)."""
    if t <= tl[0][0]:
        return dict(tl[0][1])
    for (t0, a), (t1, b) in zip(tl, tl[1:]):
        if t <= t1:
            u = _ease((t - t0) / (t1 - t0)) if t1 > t0 else 1.0
            return {k: a.get(k, 0.0) * (1 - u) + b.get(k, 0.0) * u for k in set(a) | set(b)}
    return dict(tl[-1][1])


def visemes_of(text):
    """Letters -> [(viseme, length in frames at 24 fps)]; spaces and punctuation are rests."""
    out, i, s = [], 0, text.lower()
    while i < len(s):
        if s[i] in ",.;!?":
            out.append(("sil", 6))
            i += 1
            continue
        if not s[i].isalpha():
            out.append(("sil", 2))
            i += 1
            continue
        v = DIGRAPH.get(s[i:i + 2])
        step = 2 if v else 1
        v = v or LETTER.get(s[i], "sil")
        if out and out[-1][0] == v and v not in VOWELS:
            i += step
            continue                    # doubled consonant: one closure
        out.append((v, 3 if v in VOWELS else 2))
        i += step
    return out


def _talk_track(clip, frames, fps, say):
    """[(frame, {shape: w})] mouth keys for a clip's line, scaled by style."""
    size, pace = STYLE[clip.get("style", "normal")]
    if clip.get("visemes"):
        seq = [(v, 10) for v in clip["visemes"]]
        pace = fps / 24.0 * frames / sum(n for _, n in seq)
    else:
        seq = visemes_of(say or clip["talk"])
        pace *= fps / 24.0
    f = clip.get("talk_at", 0.05) * frames
    keys = [(f, {})]
    for i, (v, n) in enumerate(seq):
        amp = size * (0.85 + 0.15 * ((i * 7) % 5) / 4.0)       # syllable-to-syllable variation, deterministic
        f += n * pace
        if f > frames - 4:
            break
        keys.append((f - n * pace * 0.5, {k: w * amp for k, w in VISEME[v].items()}))
    keys.append((min(f + 3, frames - 1), {}))
    keys.append((frames, {}))
    return keys


def _sample_frames(keys, f):
    if f <= keys[0][0]:
        return keys[0][1]
    for (f0, a), (f1, b) in zip(keys, keys[1:]):
        if f <= f1:
            u = _ease((f - f0) / (f1 - f0)) if f1 > f0 else 1.0
            return {k: a.get(k, 0.0) * (1 - u) + b.get(k, 0.0) * u for k in set(a) | set(b)}
    return keys[-1][1]


def _look(track, t):
    """Gaze (yaw, pitch) with quick saccades: hold, then move over 4 % of the clip."""
    for (t0, y0, p0), (t1, y1, p1) in zip(track, track[1:]):
        if t <= t1:
            u = _ease(min(1.0, max(0.0, (t - t0) / max(1e-6, min(0.04, t1 - t0)))))
            return y0 + (y1 - y0) * u, p0 + (p1 - p0) * u
    return track[-1][1], track[-1][2]


def _gaze_shapes(yaw, pitch):
    """yaw > 0: look toward the face's left (+X); pitch > 0: up."""
    out = {}
    if yaw > 0:
        out["eyeLookOut_L"], out["eyeLookIn_R"] = yaw, yaw
    elif yaw < 0:
        out["eyeLookIn_L"], out["eyeLookOut_R"] = -yaw, -yaw
    if pitch > 0:
        out["eyeLookUp_L"] = out["eyeLookUp_R"] = pitch
    elif pitch < 0:
        out["eyeLookDown_L"] = out["eyeLookDown_R"] = -pitch
        out["eyeBlink_L"] = out["eyeBlink_R"] = -pitch * 0.25       # lids follow a downward gaze
    return out


def _blinks(clip, frames, fps):
    if clip.get("blinks"):
        return [t * frames for t in clip["blinks"]]
    every = clip.get("blink", 0) * fps
    if not every:
        return []
    out, f, i = [], every * 0.35, 0
    while f < frames - 7:
        out.append(f)
        f += every * (1.0, 0.6, 1.3)[i % 3]    # irregular but fixed rhythm
        i += 1
    return out


def _blink_at(starts, f):
    for s in starts:
        d = f - s
        if 0 <= d <= 6:
            return (1.0, 1.0, 1.0, .7, .4, .15, 0.0)[int(d)] if d < 6 else 0.0
    return 0.0


def evaluate(clip, frames, fps, say=None):
    """Per-frame [{shape: weight}] for a clip (frame 0..frames)."""
    tl = _timeline(clip["keys"])
    talk = _talk_track(clip, frames, fps, say) if clip.get("talk") or clip.get("visemes") else None
    blinks = _blinks(clip, frames, fps)
    cycles = max(1, round(frames / (4.0 * fps)))
    out = []
    for f in range(frames + 1):
        t = f / frames
        w = _sample(tl, t)
        if talk:
            for k, v in _sample_frames(talk, f).items():
                w[k] = w.get(k, 0.0) + v
        if clip.get("breathe"):
            for k, v in EXPR["inhale"].items():
                w[k] = w.get(k, 0.0) + v * 0.5 * (1 - math.cos(2 * math.pi * cycles * t))
        if clip.get("look"):
            for k, v in _gaze_shapes(*_look(clip["look"], t)).items():
                w[k] = w.get(k, 0.0) + v
        b = _blink_at(blinks, f)
        if b:
            w["eyeBlink"] = max(w.get("eyeBlink", 0.0), b)
            for s in ("_L", "_R"):
                w["eyeBlink" + s] = max(w.get("eyeBlink" + s, 0.0), b)
        out.append(w)
    return out


def _expand(weights, keys):
    """Bare names -> both sides, aliases for older heads, clamp to 0..1; only keys the mesh has."""
    out = {}
    for k, v in weights.items():
        names = [k] if k in keys else [k + "_L", k + "_R"] if k + "_L" in keys else \
            [a for a in ALIASES.get(k, ()) if a in keys]
        for n in names:
            out[n] = out.get(n, 0.0) + v
    return {k: max(0.0, min(1.0, v)) for k, v in out.items()}


def _key_values(key, action, kb, vals, start):
    """One key per frame on a shape's value, written in bulk where the API allows."""
    path = 'key_blocks["%s"].value' % kb.name
    fc = None
    if hasattr(action, "fcurve_ensure_for_datablock"):
        try:
            fc = action.fcurve_ensure_for_datablock(key, path)
        except Exception:
            fc = None
    if fc is None:
        for f, v in enumerate(vals):
            kb.value = v
            kb.keyframe_insert("value", frame=start + f)
        return
    fc.keyframe_points.add(len(vals))
    fc.keyframe_points.foreach_set("co", [c for f, v in enumerate(vals) for c in (start + f, v)])
    fc.keyframe_points.foreach_set("interpolation", [1] * len(vals))     # LINEAR (enum 1): every frame is keyed
    fc.update()


def bake(mesh_obj, label, names, fps=24, start=1, speed=1.0, say=None):
    """Bake face clips onto a mesh's shape keys. Returns [(clip, action, category)]."""
    key = mesh_obj.data.shape_keys
    if key is None:
        return []
    kbs = key.key_blocks
    shapes = set(kbs.keys()) - {kbs[0].name}
    ad = key.animation_data or key.animation_data_create()
    cats, done = category_of(), []
    import bpy
    for name in names:
        clip = CLIPS[name]
        frames = max(8, int(round(clip["frames"] * fps / 24.0 / speed)))
        per = [_expand(w, shapes) for w in evaluate(clip, frames, fps, say)]
        if clip["loop"]:
            per[-1] = per[0]
        action = bpy.data.actions.new("%s_face_%s" % (label, name))
        action.use_fake_user = True
        ad.action = action
        used = {k for w in per for k, v in w.items() if v > 1e-4}
        for n in sorted(shapes):
            vals = [w.get(n, 0.0) for w in per] if n in used else [0.0]
            _key_values(key, action, kbs[n], vals, start)
        try:
            action.use_frame_range = True
            action.frame_start, action.frame_end = start, start + frames
            action.use_cyclic = clip["loop"]
        except Exception:
            pass
        if clip["loop"]:
            for fc in action_fcurves(action):
                fc.modifiers.new("CYCLES")
        done.append((name, action, cats.get(name, "facial")))
    ad.action = None
    for kb in kbs:
        kb.value = 0.0
    for i, (name, action, _) in enumerate(done):
        _push_nla(ad, action, "face_" + name, start, mute=i > 0)
    return done
