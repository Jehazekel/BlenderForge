"""Animation library for Rigify-generated rigs (the `base_sample` template).

Clips drive Rigify controls only: FK arms, IK legs (`foot_ik`), torso / chest /
hips, neck / head, shoulders, fingers and root. Baking reuses `anims.Animator`
with a keyset, so ORG / MCH / DEF bones are never keyed.

Poses are written for the LEFT side in armature axes (X = character's left,
-Y = forward, Z = up), degrees, as "Y56 X-3" (applied in order). Keys without a
side affect both sides; the right side is mirrored (X kept, Y and Z negated,
location x negated). "@bone" keys are location offsets in metres.
Axis notes, left arm: Y+ lowers, Y- raises, X- swings forward from hanging,
Z- swings forward from sideways. Forearm X- bends the elbow. Torso / chest X+
bows forward, Z+ turns to face left, Y+ leans left. Head Z+ looks left.

Every amplitude here is an approximation tuned by eye and checked with
tools/check_anims.py; none comes from measured data.
"""
import math
from mathutils import Quaternion, Vector

import bpy

from .anims import AXES, Animator, action_fcurves
from .log import warn

TAU = math.tau
SIDED = {"ua": "upper_arm_fk", "fa": "forearm_fk", "hand": "hand_fk", "sh": "shoulder",
         "foot": "foot_ik", "heel": "foot_heel_ik", "toe": "toe", "thumb": "thumb.01"}
CENTER = ("root", "torso", "hips", "chest", "neck", "head")
FINGERS = ("f_index", "f_middle", "f_ring", "f_pinky")
CURL_SHARE = (0.8, 1.0, 0.7)     # curl split over the three finger segments
CURL_GAIN = 0.55                 # low-poly knuckles tear past ~50 deg (deform check)
for _f in FINGERS:
    for _i in (1, 2, 3):
        SIDED["%s.0%d" % (_f, _i)] = "%s.0%d" % (_f, _i)
for _i in (2, 3):
    SIDED["thumb.0%d" % _i] = "thumb.0%d" % _i

# relaxed arms: the base sample rests in an A-pose
BASE = {"ua": "Y56 X-3", "fa": "X-10", "curl": 15}

POSES = {
    "stand": {},
    "tpose": {"ua": "", "fa": "", "curl": 0},
    # posture and mood
    "crouch": {"@torso": [0, 0.05, -0.3], "torso": "X18", "chest": "X6", "head": "X-14"},
    "crouch_low": {"@torso": [0, 0.08, -0.45], "torso": "X28", "chest": "X8", "head": "X-22"},
    "sneak": {"@torso": [0, 0.04, -0.22], "torso": "X14", "head": "X-10", "ua": "Y58 X-25", "fa": "X-55"},
    "kneel": {"@torso": [0, 0.05, -0.55], "@foot.R": [0, 0.45, 0], "chest": "X18", "head": "X20"},
    "sit": {"@torso": [0, 0.32, -0.5], "@foot": [0, -0.32, 0], "torso": "X-4", "ua": "Y58 X-30", "fa": "X-45"},
    "prone": {"@torso": [0, 0.5, -0.72], "torso": "X82", "@foot": [0, 1.3, 0.02], "head": "X-55",
              "ua": "Y25 Z-55", "fa": "Z-70"},
    "relaxed": {"chest": "X3", "head": "X4", "ua": "Y58 X-2", "@torso": [0.02, 0, -0.01]},
    "alert": {"chest": "X-4", "head": "X-4", "@torso": [0, 0, -0.04], "ua": "Y52 X-8", "fa": "X-25", "curl": 45},
    "nervous": {"chest": "X8", "head": "X10", "sh": "Y-10", "ua": "Y60 X-15", "fa": "X-60 Z-25"},
    "angry": {"chest": "X5", "@torso": [0, 0, -0.03], "ua": "Y60 X-10", "fa": "X-35", "curl": 90, "head": "X10"},
    "tired": {"head": "X20", "chest": "X18", "@torso": [0, 0, -0.06], "sh": "Y12", "ua": "Y62"},
    "injured": {"chest": "X15 Y-8", "head": "X12", "@torso": [0.04, 0, -0.08], "ua.L": "Y60 X-35",
                "fa.L": "X-95 Z-40", "@foot.R": [0, 0, 0.04]},
    "sad": {"head": "X25", "chest": "X15", "sh": "Y8"},
    "confident": {"chest": "X-10", "head": "X-8", "ua": "Y30 X15", "fa": "Y95"},
    "fear": {"ua": "Y20 X-60", "fa": "X-120", "@torso": [0, 0.1, -0.12], "chest": "X5", "head": "X10 Z10", "curl": 30},
    "defeat": {"head": "X40", "chest": "X25", "@torso": [0, 0, -0.05], "ua": "Y62", "sh": "Y10"},
    "cheer": {"ua": "Y-95", "fa": "Y-20", "head": "X-20", "chest": "X-15", "curl": 85},
    "look_l": {"head": "Z45", "neck": "Z15", "chest": "Z8"},
    "look_r": {"head": "Z-45", "neck": "Z-15", "chest": "Z-8"},
    "look_up": {"head": "X-30", "neck": "X-10"},
    "look_down": {"head": "X35", "neck": "X10"},
    "stretch_up": {"ua": "Y-115", "fa": "", "chest": "X-15", "head": "X-15", "@torso": [0, 0, 0.03]},
    "nod": {"head": "X22"},
    "shake_l": {"head": "Z25"},
    "shake_r": {"head": "Z-25"},
    "tilt": {"head": "Y15"},
    # gestures (right hand unless both)
    "wave_a": {"ua.R": "Y-50", "fa.R": "Y-80 Z-15", "curl.R": 0},
    "wave_b": {"ua.R": "Y-50", "fa.R": "Y-80 Z25", "curl.R": 0},
    "point": {"ua.R": "Z-80 Y-5", "fa.R": "", "curl.R": 75, "uncurl.R": "f_index", "chest": "Z12"},
    "clap_a": {"ua": "Y40 Z-55", "fa": "Z-65", "curl": 0},
    "clap_b": {"ua": "Y40 Z-60", "fa": "Z-80", "curl": 0},
    "thumbs_up": {"ua.R": "Y60 X-40", "fa.R": "X-90", "curl.R": 85},
    "thumbs_down": {"ua.R": "Y60 X-40", "fa.R": "X-90", "hand.R": "Y180", "curl.R": 85},
    "shrug": {"sh": "Y-18", "ua": "Y40 Z-20", "fa": "Z-60", "head": "Y8", "curl": 0},
    "cross_arms": {"ua": "Y55 X-35", "fa": "X-90 Z-75"},
    "hands_hips": {"ua": "Y30 X15", "fa": "Y95"},
    "hands_back": {"ua": "Y60 X35", "fa": "X50 Z-40"},
    "facepalm": {"ua.R": "Y60 X-40", "fa.R": "X-145", "head": "X30", "chest": "X10"},
    "scratch_head": {"ua.R": "Y-40 Z-30", "fa.R": "Y-110", "head": "Y-10"},
    "salute": {"ua.R": "Y-10 Z-35", "fa.R": "Y-125 Z-20", "curl.R": 0, "chest": "X-5"},
    "talk_a": {"ua.R": "Y55 X-35", "fa.R": "X-80 Z-20", "curl.R": 25},
    "talk_b": {"ua.R": "Y50 X-30 Z10", "fa.R": "X-70 Z20", "ua.L": "Y55 X-25", "fa.L": "X-60", "head": "Z8"},
    "whisper": {"head": "X15 Z15", "chest": "X10 Z10", "ua.R": "Y55 X-45", "fa.R": "X-130"},
    "shout": {"chest": "X-10", "head": "X-20", "ua": "Y60 X10", "fa": "X-50", "curl": 90},
    "listen": {"head": "Y10 X5", "chest": "X-3"},
    # combat
    "guard": {"ua": "Y62 X-25", "fa": "X-120", "chest": "Z-12", "@torso": [0, 0, -0.06], "head": "X8",
              "@foot.L": [0.02, -0.12, 0], "@foot.R": [0.02, 0.14, 0], "curl": 75},
    "block": {"ua": "Y45 X-55", "fa": "X-130", "head": "X15", "@torso": [0, 0, -0.08], "curl": 80, "chest": "X10",
              "@foot.L": [0.02, -0.12, 0], "@foot.R": [0.02, 0.14, 0]},
    "parry": {"ua.L": "Z-60 Y-10", "fa.L": "Z-60 X-40", "chest": "Z15"},
    "jab": {"ua.L": "Z-82 Y8", "fa.L": "X-5", "chest": "Z-20", "curl": 85},
    "cross": {"ua.R": "Z-82 Y8", "fa.R": "X-5", "chest": "Z25", "@torso": [0, -0.06, -0.06], "curl": 85},
    "hook": {"ua.L": "Z-50", "fa.L": "Z-90", "chest": "Z-30", "curl": 85},
    "uppercut": {"ua.R": "Y60 X-40", "fa.R": "X-130", "chest": "Z20 X-10", "@torso": [0, 0, 0.02], "curl": 85},
    "elbow": {"ua.L": "Z-40 Y-5", "fa.L": "Z-150", "chest": "Z-35"},
    "windup": {"chest": "Z-35 X-8", "ua.R": "Y58 X50", "fa.R": "X-90", "@torso": [0, 0.04, -0.08], "curl": 85},
    "heavy_hit": {"chest": "Z35 X15", "ua.R": "Z-75 Y15", "fa.R": "X-5", "@torso": [0, -0.1, -0.1],
                  "@foot.L": [0, -0.25, 0], "curl": 85},
    "knee_up": {"@foot.R": [0, -0.12, 0.36], "chest": "X-5", "ua": "Y62 X-40", "fa": "X-110", "curl": 75},
    "front_kick": {"@foot.R": [0, -0.45, 0.42], "torso": "X-15", "ua": "Y50 X-20", "fa": "X-90", "curl": 75},
    "side_kick": {"@foot.R": [0.42, -0.1, 0.45], "torso": "Y25", "chest": "Z20", "ua": "Y40", "fa": "X-90"},
    "spin": {"root": "Z180"},
    "dodge_l": {"@torso": [0.3, 0, -0.15], "chest": "Y25", "@foot.L": [0.3, 0, 0]},
    "dodge_r": {"@torso": [-0.3, 0, -0.15], "chest": "Y-25", "@foot.R": [0.3, 0, 0]},
    "dodge_back": {"@torso": [0, 0.25, -0.12], "chest": "X-15", "@foot.R": [0, 0.35, 0]},
    "roll": {"@torso": [0, -0.1, -0.42], "torso": "X60", "head": "X40", "ua": "Y56 X-60", "fa": "X-60"},
    "dodge_fwd": {"@torso": [0, -0.3, -0.4], "torso": "X40", "@foot.L": [0, -0.3, 0]},
    "grab": {"ua": "Z-70 Y15", "fa": "Z-25", "curl": 70, "@torso": [0, -0.08, -0.08], "chest": "X12"},
    "hit_front": {"chest": "X-20", "head": "X-25", "@torso": [0, 0.08, -0.04], "ua": "Y40 X20", "fa": "X-40"},
    "hit_back": {"chest": "X20", "head": "X20", "@torso": [0, -0.08, 0]},
    "hit_head": {"head": "X-35 Z15", "chest": "X-10"},
    "hit_arm": {"ua.L": "Y35 X25", "chest": "Z20 Y-10"},
    "hit_leg": {"@torso": [0, 0, -0.12], "@foot.L": [0, 0.1, 0.1], "chest": "X15"},
    "stagger": {"@torso": [0.1, 0.15, -0.06], "chest": "X-15 Y-10", "ua": "Y20", "fa": "X-30", "@foot.R": [0, 0.3, 0]},
    "shock": {"ua": "Y10", "fa": "Y-20", "chest": "X-10", "head": "X-15", "curl": 0},
    "clutch": {"ua": "Y60 X-40", "fa": "X-100 Z-40", "chest": "X25", "head": "X20", "@torso": [0, 0, -0.1]},
    "lie_back": {"root": "X-90", "@root": [0, 0, 0.27], "ua": "Y-20", "fa": "X-20"},
    "lie_front": {"root": "X90", "@root": [0, 0, 0.3], "ua": "Y75", "fa": "", "head": "Z60"},
    "lie_side": {"root": "Y90", "@root": [0, 0, 0.34], "ua.R": "Z-60", "@foot.L": [0, -0.15, 0.1]},
    # jumping
    "jump_crouch": {"@torso": [0, 0.04, -0.2], "torso": "X15", "ua": "Y56 X40", "fa": "X-20"},
    "air": {"@root": [0, 0, 0.5], "ua": "Y56 X-120", "fa": "X-20", "@foot": [0, 0.1, 0.15]},
    "air_high": {"@root": [0, 0, 0.9], "ua": "Y56 X-140", "@foot": [0, 0.15, 0.3]},
    "fall": {"@root": [0, 0, 0.6], "ua": "Y-10", "fa": "X-40", "@foot.L": [0, -0.1, 0.2],
             "@foot.R": [0, 0.15, 0.1], "chest": "X-10"},
    "land": {"@torso": [0, 0.05, -0.24], "torso": "X20", "ua": "Y30 X-20"},
    "land_hard": {"@torso": [0, 0.08, -0.42], "torso": "X35", "ua": "Y70 X-50", "fa": "X-10", "head": "X-20"},
    # interaction
    "reach": {"ua.R": "Z-80 Y20", "fa.R": "X-10", "chest": "Z15", "curl.R": 40},
    "pull": {"ua.R": "Y50 X20", "fa.R": "X-80", "@torso": [0, 0.1, -0.05], "chest": "X-10", "curl.R": 85},
    "push": {"ua": "Z-75 Y10", "fa": "Z-20", "@torso": [0, -0.1, -0.05], "chest": "X15", "@foot.R": [0, 0.3, 0], "curl": 10},
    "pick": {"@torso": [0, 0.1, -0.45], "torso": "X35", "chest": "X15", "ua.R": "Y75 X-40", "fa.R": "X-10", "head": "X-10", "curl.R": 70},
    "carry": {"ua": "Y60 X-35", "fa": "X-80", "chest": "X-8", "@torso": [0, 0, -0.03], "curl": 60},
    "lift": {"@torso": [0, 0.08, -0.4], "torso": "X25", "ua": "Y80 X-20", "fa": "X-20", "curl": 85},
    "throw_back": {"ua.R": "Y-50 Z30", "fa.R": "Y-90", "chest": "Z-30 X-10", "curl.R": 70},
    "throw_out": {"ua.R": "Z-80 Y-10", "fa.R": "", "chest": "Z30 X15", "@torso": [0, -0.1, -0.05], "curl.R": 0},
    "type": {"ua": "Y60 X-50", "fa": "X-70", "head": "X15", "curl": 30},
    "lever_up": {"ua.R": "Z-70 Y-25", "fa.R": "Z-15", "curl.R": 85},
    "lever_down": {"ua.R": "Y40 X-30", "fa.R": "X-30", "@torso": [0, 0, -0.15], "curl.R": 85},
    "twist": {"ua.R": "Z-80 Y20", "fa.R": "X-10", "hand.R": "Y70", "curl.R": 70},
    "search": {"@torso": [0, 0.05, -0.3], "torso": "X40", "ua": "Y70 X-50", "fa": "X-30", "head": "X10"},
    # weapons (mimed, no prop)
    "aim": {"ua.L": "Z-60 Y20", "fa.L": "Z-20 X-20", "ua.R": "Y60 X-50 Z15", "fa.R": "X-100 Z-20",
            "head": "Z10 X5", "chest": "Z25", "curl": 60},
    "aim_low": {"ua": "Y60 X-30", "fa": "X-60 Z-30", "chest": "Z15", "curl": 60},
    "recoil": {"chest": "X-8", "head": "X-5"},
    "draw": {"ua.R": "Y40 X30", "fa.R": "X-60", "chest": "Z-10", "curl.R": 70},
    "inspect": {"ua.R": "Y60 X-45", "fa.R": "X-110 Z-30", "hand.R": "Y60", "head": "X20 Z-15", "curl.R": 70},
    "reload_a": {"ua": "Y60 X-40", "fa": "X-90 Z-30", "head": "X25", "curl": 60},
    "reload_b": {"ua.L": "Y60 X-20", "fa.L": "X-60 Z-10", "head": "X25"},
    "sword_up": {"ua.R": "Y-100", "fa.R": "Y-40", "chest": "Z-25 X-10", "curl.R": 85},
    "sword_down": {"ua.R": "Y50 Z-60", "fa.R": "Z-10", "chest": "Z30 X20", "@torso": [0, -0.1, -0.1], "curl.R": 85},
    "thrust": {"ua.R": "Z-85 Y5", "fa.R": "", "chest": "Z30 X10", "@torso": [0, -0.2, -0.1],
               "@foot.L": [0, -0.35, 0], "curl.R": 85},
    # traversal
    "climb_a": {"ua.L": "Y-110", "fa.L": "Y-20", "ua.R": "Y-60", "fa.R": "Y-60", "@foot.L": [0, -0.1, 0.25],
                "@foot.R": [0, -0.1, 0.6], "head": "X-20", "curl": 70},
    "climb_b": {"ua.R": "Y-110", "fa.R": "Y-20", "ua.L": "Y-60", "fa.L": "Y-60", "@foot.R": [0, -0.1, 0.25],
                "@foot.L": [0, -0.1, 0.6], "head": "X-20", "curl": 70},
    "hang": {"ua": "Y-115", "fa": "Y-5", "@torso": [0, 0, 0.25], "@foot": [0, 0.05, 0.22], "curl": 80},
    "vault": {"@torso": [0, -0.2, 0.2], "torso": "X40", "ua": "Y56 X-90", "@foot": [0, 0.2, 0.5]},
    "slide": {"@torso": [0, 0.5, -0.75], "torso": "X-55", "@foot.L": [0, -0.6, 0.05], "@foot.R": [0, -0.25, 0], "ua": "Y40 X20"},
    "mantle": {"@torso": [0, -0.1, 0.1], "ua": "Y56 X-60", "fa": "X-40", "@foot.R": [0, 0, 0.6], "torso": "X30"},
    "swim_a": {"root": "X85", "@root": [0, 0, 0.6], "ua.L": "Y-115", "ua.R": "Y60 X20", "@foot.L": [0, 0, 0.1]},
    "swim_b": {"root": "X85", "@root": [0, 0, 0.6], "ua.R": "Y-115", "ua.L": "Y60 X20", "@foot.R": [0, 0, 0.1]},
    "dive": {"root": "X150", "@root": [0, -0.6, 1.85], "ua": "Y-120"},
    "tread_a": {"ua": "Y10 Z-25", "fa": "Z-20", "@foot.L": [0, -0.1, 0.2]},
    "tread_b": {"ua": "Y10 Z20", "fa": "Z15", "@foot.R": [0, -0.1, 0.2]},
    "balance": {"ua": "Y-25", "fa": "", "@foot.L": [-0.1, 0, 0], "@foot.R": [-0.1, 0, 0], "curl": 0},
    "rope_a": {"ua.L": "Y-120", "ua.R": "Y-85", "fa": "Y-30", "@foot": [0, -0.05, 0.3], "@torso": [0, 0, 0.3], "curl": 85},
    "rope_b": {"ua.R": "Y-120", "ua.L": "Y-85", "fa": "Y-30", "@foot": [0, -0.05, 0.3], "@torso": [0, 0, 0.3], "curl": 85},
    "zip": {"ua": "Y-115", "fa": "Y-5", "@torso": [0, 0, 0.25], "@foot": [0, -0.3, 0.35], "curl": 85},
    # vehicles
    "drive": {"@torso": [0, 0.32, -0.5], "@foot": [0, -0.35, 0], "ua": "Y55 X-55", "fa": "X-50 Z-20", "curl": 70},
    "steer_l": {"chest": "Z10", "ua.L": "Y45 X-60", "ua.R": "Y65 X-45"},
    "steer_r": {"chest": "Z-10", "ua.R": "Y45 X-60", "ua.L": "Y65 X-45"},
    "gear": {"ua.R": "Y65 X-20", "fa.R": "X-60", "chest": "Z-8"},
    "moto": {"@torso": [0, 0.2, -0.32], "torso": "X25", "ua": "Y45 X-70", "fa": "X-10", "curl": 70,
             "@foot": [0, -0.1, 0.05]},
    "crash": {"chest": "X40", "head": "X40", "@torso": [0, -0.15, 0]},
    "step": {"@foot.L": [0, -0.25, 0], "@foot.R": [0, 0.25, 0], "ua.L": "Y56 X20", "ua.R": "Y56 X-20"},
    "run_pose": {"@foot.L": [0, -0.4, 0], "@foot.R": [0, 0.4, 0.15], "torso": "X12", "ua.L": "Y56 X45",
                 "ua.R": "Y56 X-45", "fa": "X-80"},
    "turn_l": {"root": "Z90"},
    "turn_r": {"root": "Z-90"},
}


# -- clip table -----------------------------------------------------------------
def _gait(frames, **k):
    return dict(gen="gait", frames=frames, loop=k.pop("loop", True), **k)


def _idle(frames=72, **k):
    return dict(gen="idle", frames=frames, loop=k.pop("loop", True), **k)


def _keys(frames, seq, loop=False, **k):
    """seq: '0 stand | .4 crouch | 1 stand' (time 0..1, pose expression)."""
    keys = []
    for part in seq.split("|"):
        t, expr = part.split()
        keys.append((float(t), expr))
    return dict(gen="keys", frames=frames, loop=loop, keys=keys, **k)


WALK = dict(stride=0.52, lift=0.09, bob=0.025, swing=18, lean=3, duty=0.6)
RUN = dict(stride=0.9, lift=0.2, bob=0.04, swing=35, lean=12, duty=0.38, crouch=0.06, pose="run_arms")
POSES["run_arms"] = {"fa": "X-80", "curl": 60}

CLIPS = {
    # idles
    "idle": _idle(breath=1.5, sway=0.008),
    "idle_relaxed": _idle(96, pose="relaxed", breath=1.2, sway=0.012),
    "idle_combat": _idle(48, pose="guard", breath=2.0, bob=0.012, rate=2),
    "idle_alert": _idle(72, pose="alert", breath=1.5, look=25),
    "idle_nervous": _idle(72, pose="nervous", breath=2.5, rate=4, tremble=1.2, look=20),
    "idle_angry": _idle(48, pose="angry", breath=3.0, rate=3),
    "idle_tired": _idle(96, pose="tired", breath=3.0, rate=2, sway=0.015),
    "idle_injured": _idle(72, pose="injured", breath=2.5, rate=3, tremble=0.5),
    "idle_heavy_breath": _idle(48, pose="tired", breath=5.0, rate=4, bob=0.015),
    "look_around": _keys(96, "0 stand | .25 look_l | .5 stand | .75 look_r | 1 stand", loop=True),
    "look_up_down": _keys(72, "0 stand | .3 look_up | .7 look_down | 1 stand", loop=True),
    "stretch": _keys(96, "0 stand | .35 stretch_up | .65 stretch_up | 1 stand"),
    "scratch_head": _keys(72, "0 stand | .25 scratch_head | .4 scratch_head+tilt | .55 scratch_head | .8 scratch_head | 1 stand"),
    "adjust_clothing": _keys(64, "0 stand | .3 grab+look_down | .6 grab+look_down+recoil | 1 stand"),
    "weight_shift": _idle(120, breath=1.2, shift=0.06),
    # locomotion
    "walk": _gait(28, **WALK),
    "walk_back": _gait(32, **dict(WALK, heading=180, stride=0.45, lean=-3)),
    "walk_left": _gait(32, **dict(WALK, heading=90, stride=0.4, swing=6)),
    "walk_right": _gait(32, **dict(WALK, heading=-90, stride=0.4, swing=6)),
    "jog": _gait(20, stride=0.66, lift=0.13, bob=0.03, swing=25, lean=6, duty=0.45, pose="run_arms"),
    "run": _gait(17, **RUN),
    "run_back": _gait(20, **dict(RUN, heading=180, stride=0.6, lean=-4)),
    "run_left": _gait(20, **dict(RUN, heading=90, stride=0.7, lean=0, swing=12)),
    "run_right": _gait(20, **dict(RUN, heading=-90, stride=0.7, lean=0, swing=12)),
    "sprint": _gait(15, **dict(RUN, stride=1.15, lift=0.26, swing=50, lean=18, duty=0.32)),
    "turn_left": _gait(30, stride=0.08, lift=0.07, bob=0.01, swing=4, turn=90, loop=False),
    "turn_right": _gait(30, stride=0.08, lift=0.07, bob=0.01, swing=4, turn=-90, loop=False),
    "turn_180": _gait(40, stride=0.08, lift=0.07, bob=0.01, swing=4, turn=180, cycles=2, loop=False),
    "turn_360": _gait(64, stride=0.08, lift=0.07, bob=0.01, swing=4, turn=360, cycles=3, loop=False),
    "walk_start": _keys(20, "0 stand | .5 step | 1 step"),
    "walk_stop": _keys(20, "0 step | .6 stand+recoil | 1 stand"),
    "sudden_stop": _keys(18, "0 run_pose | .35 dodge_back+land | 1 stand"),
    "accelerate": _gait(56, **dict(RUN, cycles=3, ramp="up"), loop=False),
    "decelerate": _gait(56, **dict(RUN, cycles=3, ramp="down"), loop=False),
    "pivot": _gait(20, **dict(RUN, turn=90), loop=False),
    "walk_circle": _gait(84, **dict(WALK, turn=360, cycles=3)),
    "run_circle": _gait(85, **dict(RUN, turn=360, cycles=5)),
    "limp": _gait(40, **dict(WALK, stride=0.4, limp=1.0, pose="injured")),
    "sneak": _gait(44, stride=0.35, lift=0.08, bob=0.01, swing=5, pose="sneak", duty=0.65),
    "sneak_back": _gait(44, stride=0.3, lift=0.08, bob=0.01, swing=5, pose="sneak", heading=180),
    "sneak_side": _gait(44, stride=0.3, lift=0.08, bob=0.01, swing=3, pose="sneak", heading=90),
    "crouch_walk": _gait(36, stride=0.45, lift=0.08, bob=0.015, swing=10, pose="crouch"),
    "crouch_run": _gait(22, stride=0.8, lift=0.14, bob=0.02, swing=20, lean=8, duty=0.45, pose="crouch"),
    "crouch_turn": _gait(36, stride=0.06, lift=0.05, swing=0, pose="crouch", turn=90, loop=False),
    "tactical_walk": _gait(30, stride=0.5, lift=0.08, bob=0.01, swing=0, pose="aim_low"),
    "crawl": _gait(48, stride=0.3, lift=0.04, swing=15, pose="prone", duty=0.5),
    "crawl_back": _gait(48, stride=0.25, lift=0.04, swing=12, pose="prone", heading=180),
    "crawl_side": _gait(48, stride=0.2, lift=0.04, swing=10, pose="prone", heading=90),
    "crawl_injured": _gait(64, stride=0.18, lift=0.03, swing=10, pose="prone", limp=1.0),
    "slope_walk": _gait(30, **dict(WALK, lean=10, lift=0.14)),
    "slope_run": _gait(18, **dict(RUN, lean=20, lift=0.24)),
    "uneven_walk": _gait(56, **dict(WALK, cycles=2, lift=0.16, rough=0.05)),
    "heavy_walk": _gait(36, **dict(WALK, stride=0.45, lift=0.14, bob=0.04, lean=10, swing=8)),
    "swim": _keys(40, "0 swim_a | .5 swim_b | 1 swim_a", loop=True),
    "tread_water": _keys(48, "0 tread_a | .5 tread_b | 1 tread_a", loop=True, bob=0.03),
    "float": _idle(96, pose="swim_a", breath=1.0, bob=0.03),
    "dive": _keys(36, "0 stand | .3 jump_crouch | .6 air+stretch_up | 1 dive"),
    # jumping and air
    "jump": _keys(36, "0 stand | .25 jump_crouch | .5 air | .75 land | 1 stand"),
    "jump_run": _keys(30, "0 run_pose | .2 jump_crouch | .5 air+run_pose | .8 land | 1 run_pose"),
    "jump_long": _keys(44, "0 run_pose | .2 jump_crouch | .5 air_high+run_pose | .8 land_hard | 1 stand"),
    "jump_high": _keys(48, "0 stand | .25 crouch | .55 air_high | .8 land | 1 stand"),
    "jump_double": _keys(56, "0 stand | .15 jump_crouch | .35 air | .45 air+jump_crouch | .65 air_high+spin | .85 land | 1 stand"),
    "jump_back": _keys(36, "0 stand | .25 jump_crouch | .5 air+dodge_back | .8 land | 1 stand"),
    "jump_side": _keys(36, "0 stand | .25 jump_crouch | .5 air+dodge_l | .8 land | 1 stand"),
    "jump_turn": _keys(40, "0 stand | .25 jump_crouch | .5 air+turn_l | .8 land+turn_l | 1 turn_l"),
    "jump_prep": _keys(20, "0 stand | 1 jump_crouch"),
    "fall": _keys(24, "0 fall | .5 fall+look_down | 1 fall", loop=True),
    "air_idle": _idle(48, pose="air", breath=1.0, sway=0.02),
    "air_attack": _keys(30, "0 air | .4 air+sword_up | .7 air+sword_down | 1 land"),
    "land": _keys(20, "0 air | .3 land | 1 stand"),
    "land_hard": _keys(32, "0 fall | .25 land_hard | .7 land_hard | 1 stand"),
    "land_roll": _keys(36, "0 fall | .2 land | .45 roll | .75 crouch | 1 stand"),
    "land_stumble": _keys(36, "0 air | .25 land | .5 stagger | 1 stand"),
    # crouch and stealth
    "crouch_idle": _idle(72, pose="crouch", breath=1.5),
    "stand_to_crouch": _keys(16, "0 stand | 1 crouch"),
    "crouch_to_stand": _keys(16, "0 crouch | 1 stand"),
    "prone_idle": _idle(72, pose="prone", breath=1.0),
    "get_down": _keys(40, "0 stand | .4 kneel | 1 prone"),
    "get_up": _keys(40, "0 prone | .6 kneel | 1 stand"),
    "crouch_roll": _keys(30, "0 crouch | .5 roll | 1 crouch"),
    "peek": _keys(60, "0 crouch | .35 crouch+dodge_l+look_l | .65 crouch+dodge_l+look_l | 1 crouch"),
    # combat
    "guard_block": _keys(24, "0 guard | .3 block | .8 block | 1 guard"),
    "parry": _keys(20, "0 guard | .35 parry | 1 guard"),
    "dodge_left": _keys(20, "0 guard | .4 dodge_l | 1 guard"),
    "dodge_right": _keys(20, "0 guard | .4 dodge_r | 1 guard"),
    "dodge_back": _keys(20, "0 guard | .4 dodge_back | 1 guard"),
    "dodge_forward": _keys(24, "0 guard | .45 dodge_fwd | 1 guard"),
    "punch": _keys(16, "0 guard | .4 guard+jab | 1 guard"),
    "punch_cross": _keys(18, "0 guard | .4 guard+cross | 1 guard"),
    "combo_light": _keys(40, "0 guard | .15 guard+jab | .3 guard | .45 guard+cross | .6 guard | .75 guard+hook | 1 guard"),
    "attack_heavy": _keys(36, "0 guard | .4 windup | .55 heavy_hit | 1 guard"),
    "combo_heavy": _keys(64, "0 guard | .2 windup | .3 heavy_hit | .5 guard+uppercut | .65 guard | .8 front_kick | 1 guard"),
    "uppercut": _keys(22, "0 guard | .3 guard+crouch | .55 guard+uppercut | 1 guard"),
    "hook": _keys(18, "0 guard | .45 guard+hook | 1 guard"),
    "elbow": _keys(18, "0 guard | .45 guard+elbow | 1 guard"),
    "knee_strike": _keys(20, "0 guard | .45 knee_up | 1 guard"),
    "kick": _keys(26, "0 guard | .2 knee_up | .45 front_kick | .7 knee_up | 1 guard"),
    "roundhouse": _keys(32, "0 guard | .25 knee_up | .5 side_kick | .75 knee_up | 1 guard"),
    "spin_attack": _keys(32, "0 guard | .3 windup | .6 heavy_hit+spin | 1 guard+spin"),
    "jump_attack": _keys(40, "0 guard | .2 jump_crouch | .45 air+sword_up | .7 land+sword_down | 1 guard"),
    "counter": _keys(30, "0 guard | .25 parry | .5 guard+cross | 1 guard"),
    "grapple": _keys(40, "0 guard | .35 grab | .7 grab+dodge_back | 1 guard"),
    "throw_opponent": _keys(40, "0 grab | .4 grab+windup | .7 heavy_hit+spin | 1 guard+spin"),
    "victory": _keys(60, "0 stand | .3 cheer | .5 cheer+look_up | .7 cheer | 1 stand"),
    "defeat": _keys(60, "0 stand | .5 defeat | 1 kneel+defeat"),
    # damage
    "hit_light": _keys(16, "0 stand | .25 hit_front | 1 stand"),
    "hit_heavy": _keys(30, "0 stand | .2 hit_front+stagger | .6 stagger | 1 stand"),
    "hit_head": _keys(18, "0 stand | .25 hit_head | 1 stand"),
    "hit_chest": _keys(18, "0 stand | .25 hit_front | 1 stand"),
    "hit_arm": _keys(18, "0 stand | .25 hit_arm | 1 stand"),
    "hit_leg": _keys(22, "0 stand | .25 hit_leg | 1 stand"),
    "hit_back": _keys(18, "0 stand | .25 hit_back | 1 stand"),
    "hit_explosion": _keys(48, "0 stand | .15 hit_front+air | .45 lie_back | .8 lie_back | 1 lie_back"),
    "burning": _keys(48, "0 stand | .2 shock+look_down | .4 clutch | .6 shock | .8 clutch | 1 stand", loop=True, shake=4),
    "electric": _keys(36, "0 stand | .1 shock | 1 shock", shake=6),
    "poisoned": _keys(60, "0 stand | .4 clutch | .7 clutch+tired | 1 stand", shake=1),
    "stagger": _keys(30, "0 stand | .3 stagger | .7 stagger+dodge_l | 1 stand"),
    "knockback": _keys(30, "0 guard | .2 hit_front | .5 dodge_back+hit_front | 1 guard"),
    "knockdown": _keys(40, "0 stand | .2 hit_front | .5 kneel | 1 lie_back"),
    "get_up_back": _keys(48, "0 lie_back | .4 kneel | .8 crouch | 1 stand"),
    "recover": _keys(48, "0 injured | .5 tired | 1 stand"),
    # death
    "death": _keys(48, "0 stand | .3 clutch | .6 kneel+defeat | 1 lie_front"),
    "death_forward": _keys(36, "0 stand | .3 hit_back | 1 lie_front"),
    "death_backward": _keys(36, "0 stand | .3 hit_front | 1 lie_back"),
    "death_side": _keys(36, "0 stand | .3 hit_arm | 1 lie_side"),
    "death_height": _keys(48, "0 fall | .5 fall+shock | .8 land_hard | 1 lie_front"),
    "collapse": _keys(40, "0 stand | .4 kneel+defeat | 1 lie_side"),
    "death_run": _keys(30, "0 run_pose | .25 hit_back+run_pose | 1 lie_front"),
    "death_jump": _keys(40, "0 air | .4 fall+hit_front | 1 lie_back"),
    "ragdoll_get_up": _keys(56, "0 lie_front | .35 prone | .65 kneel | 1 stand"),
    # weapons
    "weapon_idle": _idle(72, pose="aim_low", breath=1.5),
    "weapon_draw": _keys(24, "0 stand | .4 draw | 1 aim_low"),
    "weapon_holster": _keys(24, "0 aim_low | .6 draw | 1 stand"),
    "weapon_switch": _keys(36, "0 aim_low | .3 draw | .5 stand | .7 draw | 1 aim_low"),
    "weapon_inspect": _keys(72, "0 aim_low | .3 inspect | .6 inspect+look_l | 1 aim_low"),
    "aim": _idle(48, pose="aim", breath=0.8),
    "fire": _keys(8, "0 aim | .3 aim+recoil | 1 aim", loop=True),
    "reload": _keys(60, "0 aim_low | .25 reload_a | .45 reload_b | .65 reload_a | .85 reload_a+recoil | 1 aim_low"),
    "sword_swing": _keys(28, "0 guard | .35 sword_up | .6 sword_down | 1 guard"),
    "sword_thrust": _keys(24, "0 guard | .35 windup | .55 thrust | 1 guard"),
    "weapon_charge": _keys(48, "0 aim_low | .7 windup | 1 windup", shake=1),
    "weapon_throw": _keys(30, "0 stand | .4 throw_back | .6 throw_out | 1 stand"),
    # interaction
    "door_open": _keys(48, "0 stand | .3 reach | .5 twist | .8 pull | 1 stand"),
    "door_close": _keys(40, "0 stand | .4 reach | .7 push | 1 stand"),
    "door_push": _keys(40, "0 stand | .4 push | 1 stand"),
    "pick_up": _keys(40, "0 stand | .45 pick | .6 pick | 1 carry"),
    "drop": _keys(30, "0 carry | .5 carry+look_down | 1 stand"),
    "carry_idle": _idle(72, pose="carry", breath=1.5),
    "carry_walk": _gait(30, **dict(WALK, swing=0, pose="carry")),
    "place": _keys(40, "0 carry | .5 lift | 1 stand"),
    "throw": _keys(30, "0 carry | .4 throw_back | .6 throw_out | 1 stand"),
    "push_walk": _gait(40, stride=0.4, lift=0.08, swing=0, lean=15, pose="push"),
    "pull_walk": _gait(40, stride=0.35, lift=0.08, swing=0, lean=-10, heading=180, pose="pull"),
    "lift_heavy": _keys(60, "0 stand | .3 lift | .7 carry | 1 carry", shake=0.6),
    "press_button": _keys(30, "0 stand | .4 reach | .55 reach+recoil | 1 stand"),
    "lever": _keys(40, "0 stand | .3 lever_up | .7 lever_down | 1 stand"),
    "turn_handle": _keys(40, "0 stand | .3 reach | .7 twist | 1 stand"),
    "typing": _keys(16, "0 type | .5 type+nod | 1 type", loop=True),
    "use_computer": _idle(72, pose="type", breath=1.0, look=8),
    "machinery": _keys(48, "0 lever_up | .5 lever_down | 1 lever_up", loop=True),
    "search_container": _keys(72, "0 stand | .25 search | .5 search+look_l | .75 search+look_r | 1 stand"),
    "gather": _keys(48, "0 stand | .4 pick | .6 pick+twist | 1 stand"),
    # traversal
    "climb_ladder": _keys(40, "0 climb_a | .5 climb_b | 1 climb_a", loop=True),
    "descend_ladder": _keys(40, "0 climb_b | .5 climb_a | 1 climb_b", loop=True),
    "ledge_hang": _idle(72, pose="hang", breath=1.0, sway=0.01),
    "ledge_pull_up": _keys(48, "0 hang | .5 mantle | 1 stand"),
    "shimmy_left": _keys(36, "0 hang | .5 hang+dodge_l | 1 hang", loop=True),
    "shimmy_right": _keys(36, "0 hang | .5 hang+dodge_r | 1 hang", loop=True),
    "vault": _keys(32, "0 run_pose | .3 vault | .7 land | 1 run_pose"),
    "slide": _keys(36, "0 run_pose | .25 slide | .75 slide | 1 run_pose"),
    "mantle": _keys(40, "0 stand | .4 mantle | 1 stand"),
    "wall_jump": _keys(40, "0 climb_a | .3 jump_crouch | .6 air+turn_l | 1 land+turn_l"),
    "swing": _keys(48, "0 hang | .25 hang+dodge_fwd | .75 hang+dodge_back | 1 hang", loop=True),
    "rope_climb": _keys(40, "0 rope_a | .5 rope_b | 1 rope_a", loop=True),
    "rope_descend": _keys(40, "0 rope_b | .5 rope_a | 1 rope_b", loop=True),
    "zipline": _idle(48, pose="zip", breath=1.0, sway=0.03),
    "balance": _idle(72, pose="balance", breath=1.0, sway=0.04, tremble=0.6),
    # facial / talking (head and hands only: the base mesh has no face rig)
    "nod": _keys(30, "0 stand | .25 nod | .5 stand | .75 nod | 1 stand"),
    "shake_head": _keys(36, "0 stand | .2 shake_l | .45 shake_r | .7 shake_l | 1 stand"),
    "talk": _keys(72, "0 talk_a | .3 talk_b | .55 talk_a+nod | .8 talk_b | 1 talk_a", loop=True),
    "talk_idle": _idle(72, pose="listen", breath=1.2, nod=4),
    "whisper": _keys(72, "0 whisper | .5 whisper+nod | 1 whisper", loop=True),
    "shout": _keys(48, "0 stand | .3 shout | .7 shout+nod | 1 stand", shake=0.6),
    "listen": _idle(96, pose="listen", breath=1.0, nod=6),
    "laugh": _keys(48, "0 stand | .2 look_up+cheer | .4 nod | .6 look_up | .8 nod | 1 stand", shake=1.5),
    "cry": _keys(72, "0 sad | .3 facepalm+sad | .7 facepalm+sad | 1 sad", shake=0.8),
    # body language
    "wave": _keys(48, "0 stand | .2 wave_a | .4 wave_b | .6 wave_a | .8 wave_b | 1 stand"),
    "point": _keys(40, "0 stand | .35 point | .7 point | 1 stand"),
    "clap": _keys(24, "0 clap_a | .5 clap_b | 1 clap_a", loop=True),
    "thumbs_up": _keys(40, "0 stand | .35 thumbs_up | .7 thumbs_up | 1 stand"),
    "thumbs_down": _keys(40, "0 stand | .35 thumbs_down | .7 thumbs_down | 1 stand"),
    "shrug": _keys(36, "0 stand | .4 shrug | .6 shrug | 1 stand"),
    "cross_arms": _idle(72, pose="cross_arms", breath=1.2),
    "hands_hips": _idle(72, pose="hands_hips", breath=1.2),
    "hands_back": _idle(72, pose="hands_back", breath=1.2),
    "facepalm": _keys(60, "0 stand | .35 facepalm | .75 facepalm | 1 stand"),
    "salute": _keys(48, "0 stand | .3 salute | .75 salute | 1 stand"),
    "celebrate": _keys(48, "0 stand | .25 cheer | .5 cheer+jump_crouch | .75 cheer | 1 stand"),
    "frustrated": _keys(48, "0 stand | .3 angry+look_down | .6 facepalm | 1 stand"),
    "disappointed": _keys(60, "0 stand | .5 sad+shake_l | 1 sad"),
    "confident": _idle(72, pose="confident", breath=1.2),
    "scared": _idle(48, pose="fear", breath=3.0, rate=4, tremble=1.5),
    "confused": _keys(60, "0 stand | .4 shrug+tilt | .7 scratch_head | 1 stand"),
    "curious": _keys(60, "0 stand | .4 tilt+look_down | .7 tilt+look_l | 1 stand"),
    "exhausted": _idle(72, pose="tired", breath=5.0, rate=3),
    # cinematic
    "dramatic_turn": _keys(40, "0 stand | .6 look_l+turn_l | 1 turn_l+turn_l"),
    "confront": _idle(60, pose="angry", breath=2.0, look=6),
    "finisher": _keys(48, "0 guard | .3 windup+jump_crouch | .5 sword_up | .7 sword_down+crouch | 1 guard"),
    "slow_walk": _gait(48, **dict(WALK, stride=0.5, bob=0.02)),
    "breakdown": _keys(96, "0 stand | .3 sad | .6 kneel+facepalm | 1 kneel+sad", shake=0.8),
    "entrance": _keys(60, "0 stand | .3 look_l | .6 confident | 1 confident"),
    "exit": _keys(48, "0 confident | .4 turn_l | 1 turn_l+turn_l"),
    # vehicles
    "vehicle_enter": _keys(48, "0 stand | .4 crouch+turn_l | 1 drive"),
    "vehicle_exit": _keys(48, "0 drive | .6 crouch+turn_l | 1 stand"),
    "drive_idle": _idle(72, pose="drive", breath=1.0, look=6),
    "steer": _keys(48, "0 drive | .3 drive+steer_l | .7 drive+steer_r | 1 drive", loop=True),
    "gear_shift": _keys(30, "0 drive | .5 drive+gear | 1 drive"),
    "drive_look": _keys(72, "0 drive | .3 drive+look_l | .7 drive+look_r | 1 drive", loop=True),
    "moto_ride": _idle(48, pose="moto", breath=1.0, bob=0.01),
    "moto_mount": _keys(48, "0 stand | .5 knee_up+turn_l | 1 moto"),
    "moto_dismount": _keys(48, "0 moto | .5 knee_up | 1 stand"),
    "passenger": _idle(72, pose="sit", breath=1.0, look=20),
    "vehicle_crash": _keys(30, "0 drive | .25 drive+crash | .6 drive+hit_front | 1 drive"),
    # environment
    "wind": _idle(48, pose="tired", breath=1.0, sway=0.03, tremble=0.4),
    "balance_recover": _keys(40, "0 stagger | .5 balance | 1 stand"),
    "push_against": _keys(48, "0 stand | .4 push | .7 push | 1 stand", shake=0.5),
    # transitions
    "idle_to_walk": _keys(16, "0 stand | 1 step"),
    "idle_to_run": _keys(14, "0 stand | .4 jump_crouch | 1 run_pose"),
    "walk_to_run": _keys(16, "0 step | 1 run_pose"),
    "run_to_sprint": _keys(14, "0 run_pose | 1 run_pose+crouch"),
    "sprint_stop": _keys(24, "0 run_pose | .4 dodge_back+land | 1 stand"),
    "walk_to_idle": _keys(16, "0 step | 1 stand"),
    "run_to_idle": _keys(24, "0 run_pose | .5 land | 1 stand"),
    "stand_to_prone": _keys(40, "0 stand | .4 kneel | 1 prone"),
    "prone_to_stand": _keys(40, "0 prone | .6 kneel | 1 stand"),
    "to_combat": _keys(16, "0 stand | 1 guard"),
    "combat_to_idle": _keys(20, "0 guard | 1 stand"),
    "jump_to_fall": _keys(20, "0 air | 1 fall"),
    "landing_to_run": _keys(20, "0 land | 1 run_pose"),
    "attack_recover": _keys(24, "0 heavy_hit | 1 guard"),
    "hit_to_idle": _keys(24, "0 hit_front | 1 stand"),
}

# reference list (references/character_animations.md, sections 1-17) -> clip
REFERENCE = {
    "idle": "default idle=idle|relaxed idle=idle_relaxed|combat idle=idle_combat|alert idle=idle_alert|"
            "nervous idle=idle_nervous|angry idle=idle_angry|tired idle=idle_tired|injured idle=idle_injured|"
            "breathing idle=idle|heavy breathing=idle_heavy_breath|looking around=look_around|"
            "head movement=look_up_down|eye movement=look_around|blinking=idle|stretching=stretch|"
            "scratching head=scratch_head|adjusting clothing=adjust_clothing|shifting body weight=weight_shift|"
            "standing transitions=stand_to_crouch",
    "locomotion": "walking forward=walk|walking backward=walk_back|walking left=walk_left|walking right=walk_right|"
                  "running forward=run|running backward=run_back|sprinting=sprint|slow jogging=jog|"
                  "sideways running=run_left,run_right|strafing left and right=walk_left,walk_right|turning left and right=turn_left,turn_right|"
                  "90-degree turns=turn_right|180-degree turns=turn_180|360-degree turns=turn_360|"
                  "starting movement=walk_start|stopping movement=walk_stop|sudden stopping=sudden_stop|"
                  "acceleration=accelerate|deceleration=decelerate|pivoting=pivot|direction changes=pivot|"
                  "walking in circles=walk_circle|running in circles=run_circle|limping=limp|sneaking=sneak|"
                  "crouch walking=crouch_walk|crouch running=crouch_run|tactical movement=tactical_walk",
    "jumping": "jump preparation=jump_prep|standing jump=jump|running jump=jump_run|long jump=jump_long|"
               "short jump=jump|high jump=jump_high|double jump=jump_double|jump forward=jump_run|"
               "jump backward=jump_back|jump sideways=jump_side|jump turning=jump_turn|falling=fall|"
               "freefall=fall|midair idle=air_idle|midair movement=air_idle|midair attack=air_attack|"
               "landing=land|hard landing=land_hard|soft landing=land|rolling landing=land_roll|"
               "landing recovery=land|stumble after landing=land_stumble",
    "crouching": "crouching=stand_to_crouch|crouch idle=crouch_idle|crouch walking=crouch_walk|"
                 "crouch running=crouch_run|crouch turning=crouch_turn|crouch transitions=crouch_to_stand|"
                 "sneaking forward=sneak|sneaking backward=sneak_back|sneaking sideways=sneak_side|"
                 "prone position=prone_idle|crawling forward=crawl|crawling backward=crawl_back|"
                 "crawling sideways=crawl_side|getting down=get_down|getting up=get_up|"
                 "rolling while crouched=crouch_roll|peeking around corners=peek",
    "combat": "combat stance=idle_combat|combat idle=idle_combat|guarding=guard_block|blocking=guard_block|"
              "parrying=parry|dodging left=dodge_left|dodging right=dodge_right|dodging backward=dodge_back|"
              "dodging forward=dodge_forward|evading=dodge_back|quick attacks=punch,hook|heavy attacks=attack_heavy|"
              "light attack combos=combo_light|heavy attack combos=combo_heavy|punching=punch_cross|kicking=kick|"
              "elbow strikes=elbow|knee strikes=knee_strike|uppercuts=uppercut|roundhouse kicks=roundhouse|"
              "spinning attacks=spin_attack|jump attacks=jump_attack|aerial attacks=air_attack|"
              "counterattacks=counter|grappling=grapple|throwing=throw_opponent|knockback reactions=knockback|"
              "hit reactions=hit_light|staggering=stagger|stumbling=stagger|falling from attacks=knockdown|"
              "getting knocked down=knockdown|getting back up=get_up_back|victory animations=victory|"
              "defeat animations=defeat",
    "weapon": "weapon idle=weapon_idle|weapon drawing=weapon_draw|weapon holstering=weapon_holster|"
              "weapon equipping=weapon_draw|weapon switching=weapon_switch|weapon inspection=weapon_inspect|"
              "weapon aiming=aim|weapon firing=fire|recoil=fire|reloading=reload|magazine removal=reload|"
              "magazine insertion=reload|weapon cocking=reload|melee weapon attacks=sword_swing|"
              "sword swings=sword_swing|sword thrusts=sword_thrust|sword blocking=guard_block|sword parrying=parry|"
              "weapon recoil recovery=fire|weapon charging=weapon_charge|weapon throwing=weapon_throw|"
              "weapon pickup=pick_up|weapon drop=drop|weapon recovery=pick_up",
    "interaction": "opening doors=door_open|closing doors=door_close|pushing doors=door_push|pulling doors=door_open|"
                   "opening drawers=door_open|picking up objects=pick_up|dropping objects=drop|"
                   "carrying objects=carry_walk,carry_idle|placing objects=place|throwing objects=throw|pushing objects=push_walk,push_against|"
                   "pulling objects=pull_walk|lifting heavy objects=lift_heavy|moving furniture=push_walk|"
                   "pressing buttons=press_button|pulling levers=lever|turning handles=turn_handle|"
                   "using computers=use_computer|typing=typing|operating machinery=machinery|"
                   "interacting with vehicles=vehicle_enter|picking up items from the ground=pick_up|"
                   "searching containers=search_container|collecting resources=gather",
    "climbing": "climbing ladders=climb_ladder|descending ladders=descend_ladder|climbing walls=climb_ladder|"
                "pulling up ledges=ledge_pull_up|hanging from ledges=ledge_hang|shimmying left=shimmy_left|"
                "shimmying right=shimmy_right|vaulting obstacles=vault|jumping over obstacles=vault|"
                "sliding under obstacles=slide|mantling=mantle|wall climbing=climb_ladder|wall jumping=wall_jump|"
                "swinging=swing|rope climbing=rope_climb|rope descending=rope_descend|zipline movement=zipline|"
                "balancing on narrow surfaces=balance|swimming=swim|diving underwater=dive|floating=float|"
                "treading water=tread_water",
    "facial": "neutral expression=idle|happiness=celebrate|sadness=disappointed|anger=idle_angry|fear=scared|"
              "surprise=hit_light|disgust=shake_head|confusion=confused|curiosity=curious|frustration=frustrated|"
              "pain=poisoned|exhaustion=exhausted|crying=cry|laughing=laugh|smiling=nod|smirking=confident|"
              "frowning=idle_angry|eyebrow movement=look_up_down|eye squinting=idle_alert|eye widening=scared|"
              "blinking=idle|looking around=look_around|jaw movement=talk|lip movement=talk|"
              "natural breathing expressions=idle|emotional transitions=disappointed",
    "talking": "talking idle=talk_idle|normal conversation=talk|whispering=whisper|shouting=shout|screaming=shout|"
               "laughing while talking=laugh|crying while talking=cry|angry dialogue=shout|emotional dialogue=talk|"
               "lip synchronization=talk|phoneme animation=talk|mouth shape transitions=talk|"
               "jaw articulation=talk|head gestures=nod|conversational hand gestures=talk|listening animations=listen",
    "emotional": "nodding=nod|shaking head=shake_head|waving=wave|pointing=point|clapping=clap|thumbs up=thumbs_up|"
                 "thumbs down=thumbs_down|shrugging=shrug|crossing arms=cross_arms|hands on hips=hands_hips|"
                 "hands behind back=hands_back|facepalm=facepalm|head scratching=scratch_head|saluting=salute|"
                 "hand gestures=talk|laughing=laugh|crying=cry|celebrating=celebrate|"
                 "expressing frustration=frustrated|expressing disappointment=disappointed|"
                 "expressing confidence=confident|expressing fear=scared|expressing confusion=confused|"
                 "expressing curiosity=curious|expressing exhaustion=exhausted",
    "damage": "light damage reaction=hit_light|heavy damage reaction=hit_heavy|head hit reaction=hit_head|"
              "chest hit reaction=hit_chest|arm hit reaction=hit_arm|leg hit reaction=hit_leg|"
              "back hit reaction=hit_back|explosive impact reaction=hit_explosion|burning reaction=burning|"
              "electric shock reaction=electric|poison reaction=poisoned|staggering=stagger|limping=limp|"
              "holding injured body parts=idle_injured|falling=knockdown|crawling while injured=crawl_injured|"
              "recovering from injury=recover",
    "death": "death animation=death|falling forward=death_forward|falling backward=death_backward|"
             "falling sideways=death_side|falling from height=death_height|collapsing=collapse|"
             "kneeling before collapse=death|death while standing=death|death while running=death_run|"
             "death while jumping=death_jump|death from impact=death_backward|ragdoll activation=collapse|"
             "ragdoll collision=death_side|ragdoll recovery=ragdoll_get_up|getting up from ragdoll=ragdoll_get_up",
    "cinematic": "dramatic entrances=entrance|dramatic exits=exit|character introductions=entrance|"
                 "character reveals=dramatic_turn|walking cinematic shots=slow_walk|running cinematic shots=run|"
                 "slow-motion movement=slow_walk|emotional reactions=disappointed|dramatic turns=dramatic_turn|"
                 "character confrontations=confront|dialogue performances=talk|conversation gestures=talk|"
                 "emotional breakdowns=breakdown|dramatic fighting=combo_heavy|finishing moves=finisher|"
                 "victory scenes=victory|defeat scenes=defeat|story-driven interactions=door_open",
    "vehicle": "entering vehicles=vehicle_enter|exiting vehicles=vehicle_exit|sitting in vehicles=drive_idle|"
               "driving idle=drive_idle|steering=steer|gear shifting=gear_shift|accelerating=drive_idle|"
               "braking=vehicle_crash|looking around while driving=drive_look|motorcycle riding=moto_ride|"
               "mounting a motorcycle=moto_mount|dismounting a motorcycle=moto_dismount|"
               "passenger animations=passenger|vehicle crash reactions=vehicle_crash",
    "environmental": "wind reactions=wind|clothing movement=idle|hair movement=idle|secondary body motion=idle|"
                     "foot placement=walk|ground adaptation=uneven_walk|slope walking=slope_walk|"
                     "slope running=slope_run|uneven terrain movement=uneven_walk|water interaction=tread_water|"
                     "mud movement=heavy_walk|snow movement=heavy_walk|sand movement=heavy_walk|"
                     "body collision reactions=hit_light|object collision reactions=stagger|"
                     "physics-driven movement=stagger|dynamic balance=balance_recover|inertia=sudden_stop|"
                     "weight shifting=weight_shift",
    "transition": "idle to walk=idle_to_walk|idle to run=idle_to_run|walk to run=walk_to_run|"
                  "run to sprint=run_to_sprint|sprint to stop=sprint_stop|walk to idle=walk_to_idle|"
                  "run to idle=run_to_idle|standing to crouching=stand_to_crouch|"
                  "crouching to standing=crouch_to_stand|standing to prone=stand_to_prone|"
                  "prone to standing=prone_to_stand|movement to combat stance=to_combat|"
                  "combat stance to idle=combat_to_idle|jump to fall=jump_to_fall|fall to landing=land|"
                  "landing to running=landing_to_run|attack to recovery=attack_recover|"
                  "hit reaction to idle=hit_to_idle|knockdown to recovery=get_up_back|"
                  "weapon switching transitions=weapon_switch|direction change transitions=pivot",
}


def _norm(text):
    return text.strip().lower().replace(" ", "_").replace("-", "_")


def reference_map():
    """{category: {normalised reference name: [clips]}} (a name may list several, comma-separated)."""
    out = {}
    for cat, text in REFERENCE.items():
        out[cat] = {_norm(a): b.split(",") for a, b in (pair.split("=") for pair in text.split("|"))}
    return out


def category_of():
    cats = {}
    for cat, names in reference_map().items():
        for clips in names.values():
            for clip in clips:
                cats.setdefault(clip, cat)
    for clip in CLIPS:
        cats.setdefault(clip, "misc")
    return cats


def resolve(names):
    """Animation names (clip, reference name, '@category' or 'all') -> clip list."""
    ref = reference_map()
    flat = {}
    for names_in in ref.values():           # first category wins, as in category_of
        for n, clips in names_in.items():
            flat.setdefault(n, clips)
    out = []
    for raw in names:
        n = _norm(raw)
        if n == "all":
            picks = list(CLIPS)
        elif n.startswith("@"):
            cat = n[1:]
            if cat not in ref:
                warn("unknown animation category '%s' (known: %s)" % (raw, ", ".join(sorted(ref))))
                continue
            picks = list(dict.fromkeys(c for clips in ref[cat].values() for c in clips))
        elif n in CLIPS:
            picks = [n]
        elif n in flat:
            picks = flat[n]
        else:
            warn("unknown animation '%s'" % raw)
            continue
        out.extend(p for p in picks if p not in out)
    return out


# -- pose compilation ---------------------------------------------------------------
def _steps(text):
    out = []
    for tok in text.split():
        out.append((tok[0].upper(), math.radians(float(tok[1:]))))
    return out


def _quat(steps):
    q = Quaternion()
    for axis, ang in steps:
        q = Quaternion(AXES[axis], ang) @ q
    return q


def _expand_curl(raw):
    """Turn curl / curl.L / curl.R (+ uncurl) into finger segment entries."""
    out = {}
    for key, val in raw.items():
        if not key.startswith("curl"):
            continue
        side = key[4:]                       # "", ".L" or ".R"
        skip = raw.get("uncurl" + side, "")
        for f in FINGERS:
            v = 0.0 if f in skip else float(val) * CURL_GAIN
            for i, share in enumerate(CURL_SHARE, 1):
                out["%s.0%d%s" % (f, i, side)] = "Y%g" % (v * share)
        for i in (2, 3):
            out["thumb.0%d%s" % (i, side)] = "Y%g" % (float(val) * 0.35 * CURL_GAIN)
    return out


def _raw(expr):
    """Pose expression 'a+b' -> merged raw dict (later parts compose after earlier)."""
    if isinstance(expr, dict):
        parts = [expr]
    else:
        parts = []
        for name in expr.split("+"):
            if name not in POSES:
                raise KeyError("unknown pose '%s'" % name)
            parts.append(POSES[name])
    merged = {}
    for part in parts:
        part = dict(part)
        part.update(_expand_curl(part))
        for key, val in part.items():
            if key.startswith(("curl", "uncurl")):
                continue
            if key.startswith("@"):
                prev = merged.get(key, [0, 0, 0])
                merged[key] = [a + b for a, b in zip(prev, val)]
            elif key in CENTER:
                # trunk, head and root rotations add up ("aim+recoil")
                merged[key] = (merged.get(key, "") + " " + val).strip()
            else:
                # limbs and fingers: the later pose replaces the earlier one
                if key[-2:] in (".L", ".R"):
                    stem = key[:-2]
                    if stem in merged:
                        old = merged.pop(stem)
                        merged.setdefault(stem + ".L", old)
                        merged.setdefault(stem + ".R", old)
                else:
                    merged.pop(key + ".L", None)
                    merged.pop(key + ".R", None)
                merged[key] = val
    return merged


class Pose:
    """Compiled pose: {bone: Quaternion} and {bone: Vector} for one rig."""
    __slots__ = ("rot", "loc")

    def __init__(self, rot, loc):
        self.rot, self.loc = rot, loc


def compile_pose(expr, bones, base=True):
    raw = {}
    if base:
        b = dict(BASE)
        b.update(_expand_curl(b))
        for k, v in b.items():
            if not k.startswith("curl"):
                raw[k + ".L"] = v
                raw[k + ".R"] = v
    pose = _raw(expr)
    # a pose that names a bone (sided or both sides) replaces the base value
    for k in pose:
        if k.startswith("@"):
            continue
        if k[-2:] in (".L", ".R"):
            raw.pop(k, None)
        else:
            raw.pop(k + ".L", None)
            raw.pop(k + ".R", None)
    raw.update(pose)
    rot, loc = {}, {}
    for key, val in raw.items():
        is_loc = key.startswith("@")
        k = key[1:] if is_loc else key
        targets = []
        if k in CENTER:
            targets = [(k, False)]
        else:
            stem, side = (k[:-2], k[-1]) if k[-2:] in (".L", ".R") else (k, None)
            real = SIDED.get(stem)
            if real is None:
                raise KeyError("unknown pose key '%s'" % key)
            for s in ("L", "R"):
                if side in (None, s):
                    targets.append(("%s.%s" % (real, s), s == "R"))
        for bone, mirror in targets:
            if bone not in bones:
                continue
            if is_loc:
                v = Vector(val)
                if mirror:
                    v.x = -v.x
                loc[bone] = loc.get(bone, Vector()) + v
            else:
                steps = _steps(val)
                if mirror:
                    steps = [(a, g if a == "X" else -g) for a, g in steps]
                rot[bone] = _quat(steps) @ rot.get(bone, Quaternion())
    return Pose(rot, loc)


def _apply(an, pose, extra_rot=None):
    for bone, q in pose.rot.items():
        if q.angle > 1e-6:
            an.rot(bone, (q.axis, q.angle))
    for bone, v in pose.loc.items():
        an.loc(bone, v)


def _blend(a, b, u):
    rot, loc = {}, {}
    for bone in set(a.rot) | set(b.rot):
        qa = a.rot.get(bone, Quaternion())
        qb = b.rot.get(bone, Quaternion())
        if qa.dot(qb) < 0:
            qb = -qb
        rot[bone] = qa.slerp(qb, u)
    for bone in set(a.loc) | set(b.loc):
        loc[bone] = a.loc.get(bone, Vector()).lerp(b.loc.get(bone, Vector()), u)
    return Pose(rot, loc)


def _smooth(u):
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


# -- generators -----------------------------------------------------------------------
def _overlays(an, k, p):
    """Breath, bob, tremble and shake layered on any clip."""
    rate = k.get("rate", 2)
    b = math.sin(TAU * rate * p)
    if k.get("breath"):
        an.rot("chest", ("X", -math.radians(k["breath"]) * b))
    if k.get("bob"):
        an.loc("torso", (0, 0, k["bob"] * b))
    if k.get("sway"):
        an.loc("torso", (k["sway"] * math.sin(TAU * p), 0, 0))
    for key, freq in (("tremble", 11), ("shake", 17)):
        amp = math.radians(k.get(key, 0.0))
        if amp:
            an.rot("chest", ("Z", amp * math.sin(TAU * freq * p)), ("X", amp * 0.6 * math.sin(TAU * (freq + 2) * p)))
            an.rot("head", ("Z", amp * 0.8 * math.sin(TAU * (freq - 3) * p + 1.0)))


def gen_idle(an, k, p, ctx):
    _apply(an, ctx["pose"])
    if k.get("look"):
        a = math.radians(k["look"]) * math.sin(TAU * p)
        an.rot("head", ("Z", a))
        an.rot("neck", ("Z", a * 0.4))
    if k.get("nod"):
        an.rot("head", ("X", math.radians(k["nod"]) * max(0.0, math.sin(TAU * 3 * p))))
    if k.get("shift"):
        s = math.sin(TAU * p)
        an.loc("torso", (k["shift"] * s, 0, -0.02 * abs(s)))
        an.rot("hips", ("Y", -0.08 * s))
        an.rot("chest", ("Y", 0.05 * s))
    _overlays(an, k, p)


def gen_gait(an, k, p, ctx):
    _apply(an, ctx["pose"])
    cycles = k.get("cycles", 1)
    stride, lift, duty = k.get("stride", 0.6), k.get("lift", 0.1), k.get("duty", 0.6)
    ramp = k.get("ramp")
    if ramp == "up":
        stride *= 0.25 + 0.75 * p
    elif ramp == "down":
        stride *= 1.0 - 0.75 * p
    h = math.radians(k.get("heading", 0.0))
    d = Vector((math.sin(h), -math.cos(h), 0.0))
    q = p * cycles
    limp = k.get("limp", 0.0)
    roll = math.radians(k.get("roll", 18))
    for side, off in (("L", 0.0), ("R", 0.5)):
        ph = (q + off) % 1.0
        bad = limp if side == "L" else 0.0
        st = stride * (1.0 - 0.5 * bad)
        if ph < duty:
            u = ph / duty
            along, z, pitch = (0.5 - u) * st, 0.0, 0.0
        else:
            u = (ph - duty) / (1.0 - duty)
            along = (-0.5 + _smooth(u)) * st
            z = lift * (1.0 - 0.6 * bad) * math.sin(math.pi * u)
            pitch = roll * math.sin(TAU * u)
        rough = k.get("rough", 0.0)
        if rough:
            z += rough * (0.5 + 0.5 * math.sin(TAU * (3 * q + off * 1.7)))
        an.loc("foot_ik." + side, d * along + Vector((0, 0, z)))
        if pitch:
            an.rot("foot_ik." + side, ("X", pitch))
    c = math.cos(TAU * 2 * q)
    drop = k.get("crouch", 0.0) + limp * 0.04 * max(0.0, math.sin(TAU * q))
    an.loc("torso", (k.get("sway", 0.02) * math.sin(TAU * q), 0, -k.get("bob", 0.02) * c - drop))
    yaw = math.radians(k.get("yaw", 6)) * math.cos(TAU * q)
    an.rot("hips", ("Z", yaw))
    an.rot("chest", ("Z", -yaw * 1.2))
    if k.get("lean"):
        an.rot("torso", ("X", math.radians(k["lean"])))
    sw = math.radians(k.get("swing", 18)) * math.cos(TAU * q)
    an.rot("upper_arm_fk.L", ("X", sw))
    an.rot("upper_arm_fk.R", ("X", -sw))
    if k.get("turn"):
        an.rot("root", ("Z", math.radians(k["turn"]) * p))
    _overlays(an, k, p)


def gen_keys(an, k, p, ctx):
    keys = ctx["keys"]
    for i in range(len(keys) - 1):
        t0, a = keys[i]
        t1, b = keys[i + 1]
        if p <= t1 or i == len(keys) - 2:
            u = _smooth((p - t0) / max(t1 - t0, 1e-6))
            _apply(an, _blend(a, b, u))
            break
    _overlays(an, k, p)


GENERATORS = {"idle": gen_idle, "gait": gen_gait, "keys": gen_keys}


def keyset(arm_obj):
    """Every control a clip may key, present on this rig."""
    names = set(CENTER)
    for real in SIDED.values():
        names.update((real + ".L", real + ".R"))
    return sorted(n for n in names if n in arm_obj.pose.bones)


REF_HEIGHT = 2.115     # body the offsets above were tuned on: the sample male at rest, rig units


# rest directions (left side) of the FK arm chain on that male, an A-pose
REF_ARM = (("upper_arm_fk", (0.8696, -0.1207, -0.4787)),
           ("forearm_fk", (0.9024, -0.3708, -0.2197)),
           ("hand_fk", (0.9754, -0.0414, -0.2166)))


class _Scaled(Animator):
    """Animator whose location offsets scale with body height and whose arm
    rotations are re-based on the reference male's rest arm, so a body rigged
    in another rest pose (the female is a T-pose) lands on the same poses."""
    size = 1.0
    arm_fix = {}                        # bone -> (fix of parent link, own fix)

    def loc(self, bone, offset):
        super().loc(bone, Vector(offset) * self.size)

    def fit_arms(self):
        """Per arm bone: the rotation C taking its rest direction onto the
        reference one, accumulated down the chain (direction only; roll kept)."""
        self.arm_fix = {}
        bones = self.arm.data.bones
        for side, sx in (("L", 1.0), ("R", -1.0)):
            chain, c = {}, Quaternion()
            for name, ref in REF_ARM:
                b = bones.get("%s.%s" % (name, side))
                if b is None:
                    break
                d = c @ (b.tail_local - b.head_local).normalized()
                c = d.rotation_difference(Vector((ref[0] * sx, ref[1], ref[2]))) @ c
                chain[b.name] = c.copy()
            top = bones.get("upper_arm_fk." + side)
            if not chain or top is None or max(q.angle for q in chain.values()) < 1e-3:
                continue
            for b in [top] + list(top.children_recursive):
                p = b.parent
                while p is not None and p.name not in chain and p != top.parent:
                    p = p.parent
                own = chain.get(b.name)
                if own is None:             # not in the chain: take the nearest chain parent's
                    q = b.parent
                    while q.name not in chain:
                        q = q.parent
                    own = chain[q.name]
                par = chain[p.name] if p is not None and p.name in chain else Quaternion()
                self.arm_fix[b.name] = (par, own)

    def reach_down(self):
        # q' = C_parent^-1 @ q @ C_own: the posed arm equals the reference arm
        # posed by the same armature-space rotations
        for n, (par, own) in self.arm_fix.items():
            q = self._rot.get(n)
            if q is None and (par.inverted() @ own).angle < 1e-4:
                continue
            self._rot[n] = par.inverted() @ (q or Quaternion()) @ own
        super().reach_down()


HAND_BONES = ("DEF-hand", "DEF-palm", "DEF-f_", "DEF-thumb")
FOOT_BONES = ("DEF-foot", "DEF-toe")
UNDER_FLOOR = {"dive"}                  # meant to go below z = 0 (water entry)


def _bone_floor(arm):
    """World height of the lowest foot bone at rest, when the soles stand on
    z = 0: the skin under a bone. Used as the floor for bone ends (fingers are
    taken to be about as thick as the sole; approximation)."""
    ad = arm.animation_data
    keep = ad.action if ad else None
    if ad:
        ad.action = None
    saved = [(pb, pb.matrix_basis.copy()) for pb in arm.pose.bones]
    for pb, _ in saved:
        pb.matrix_basis.identity()
    bpy.context.view_layer.update()
    mw = arm.matrix_world
    z = min((min((mw @ pb.head).z, (mw @ pb.tail).z) for pb in arm.pose.bones
             if pb.name.startswith(FOOT_BONES)), default=0.0)
    for pb, m in saved:
        pb.matrix_basis = m
    if ad:
        ad.action = keep
    return max(0.0, z)


def _lift_hands(an, action, frames, tol=0.005, prefixes=HAND_BONES, lifter="torso", floor=0.0, step=None, margin=0.1):
    """Raise `lifter` on frames where a bone named `prefixes*` goes through the
    floor. Clips are tuned on the reference body; a body with longer arms or
    fingers (the female) would otherwise plant its fingertips under z = 0 in
    crawls. Hands lift the torso (planted IK feet stay put); IK feet and toes
    lift the root (FOOT_BONES), e.g. a foot swung through the floor mid-fall."""
    arm, scene = an.arm, bpy.context.scene
    hands = [pb for pb in arm.pose.bones if pb.name.startswith(prefixes)]
    if not hands or lifter not in arm.pose.bones:
        return 0.0
    mw = arm.matrix_world               # the rig is raised so the soles sit on z = 0:
    to_arm = mw.inverted().to_3x3()     # measure the floor in world space, not rig space
    def low(f):
        scene.frame_set(an.start + f)
        return min(min((mw @ pb.head).z, (mw @ pb.tail).z) for pb in hands)

    step = step or max(1, frames // 6)  # coarse pass first: most clips keep hands high
    if min(low(f) for f in range(0, frames + 1, step)) > floor + margin:
        return 0.0
    torso = arm.pose.bones[lifter]
    lifts, frames_3x3 = [], []
    for f in range(frames + 1):
        z = low(f)
        lifts.append(floor - z if z < floor - tol else 0.0)
        # torso location lives in its parent's posed frame, which a lying-down
        # clip rotates; map world up through that frame, not the rest frame
        frames_3x3.append((torso.matrix @ torso.matrix_basis.inverted()).to_3x3().inverted())
    if not any(lifts):
        return 0.0
    path = 'pose.bones["%s"].location' % lifter
    curves = {fc.array_index: fc for fc in action_fcurves(action) if fc.data_path == path}
    for f, dz in enumerate(lifts):
        if not dz:
            continue
        frame = an.start + f
        d = frames_3x3[f] @ (to_arm @ Vector((0.0, 0.0, dz)))
        for i in range(3):
            fc = curves.get(i)
            if fc is None:
                fc = curves[i] = action.fcurve_ensure_for_datablock(arm, path, index=i)                     if hasattr(action, "fcurve_ensure_for_datablock") else None
                if fc is None:
                    continue
            k = next((k for k in fc.keyframe_points if abs(k.co.x - frame) < 0.01), None)
            if k is None:
                fc.keyframe_points.insert(frame, fc.evaluate(frame) + d[i])
            else:
                k.co.y += d[i]
                k.handle_left.y += d[i]
                k.handle_right.y += d[i]
    for fc in curves.values():
        fc.update()
    return max(lifts)


def bake(arm_obj, label, names, fps=24, start=1, speed=1.0, height=REF_HEIGHT):
    """Bake clips onto a Rigify armature. `height` is the body height in rig
    units; strides, lifts and drops scale with it. Returns [(clip, action, category)]."""
    bones = set(arm_obj.pose.bones.keys())
    an = _Scaled(arm_obj, label, {}, fps, start, keyset=keyset(arm_obj), fill=True)
    an.size = height / REF_HEIGHT if height > 1e-6 else 1.0
    an.fit_arms()
    floor = _bone_floor(arm_obj)
    cats = category_of()
    done = []
    for name in names:
        k = CLIPS[name]
        ctx = {"pose": compile_pose(k.get("pose", "stand"), bones)}
        if k["gen"] == "keys":
            ctx["keys"] = [(t, compile_pose(e, bones)) for t, e in k["keys"]]
        gen = GENERATORS[k["gen"]]
        frames = max(4, int(round(k["frames"] * fps / 24.0 / speed)))
        action = an.bake(name, lambda a, m, p, g=gen, kk=k, c=ctx: g(a, kk, p, c), frames, k["loop"])
        if name not in UNDER_FLOOR:
            _lift_hands(an, action, frames, floor=floor)
            _lift_hands(an, action, frames, prefixes=FOOT_BONES, lifter="root", floor=floor,
                        step=2, margin=0.02)
        done.append((name, action, cats.get(name, "misc")))
    an.finish()
    return done
