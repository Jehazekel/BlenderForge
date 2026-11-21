"""Procedural animation: every pose is a pure function of the cycle phase.

An animation is `fn(an, meta, p)` with p in [0, 1]. It calls `an.rot` and
`an.loc` using armature-space axes (X = character's left, -Y = forward, Z = up),
so the maths never depends on bone rolls. The Animator converts to bone-local
keyframes, stores each cycle as its own Action and parks it on an NLA track.
"""

import math

import bpy
from mathutils import Quaternion, Vector

from .log import warn
from .meshkit import smooth

TAU = math.tau
AXES = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}
SIDES = (("L", 1.0), ("R", -1.0))


def action_fcurves(action):
    """F-curves of an action on both the legacy and the layered (4.4+) API."""
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    out = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in getattr(strip, "channelbags", []):
                out.extend(bag.fcurves)
    return out


def _push_nla(anim_data, action, label, start, mute):
    track = anim_data.nla_tracks.new()
    track.name = label
    strip = track.strips.new(label, int(start), action)
    strip.name = label
    if getattr(strip, "action_slot", 1) is None and getattr(action, "slots", None):
        try:
            strip.action_slot = action.slots[0]
        except Exception:
            pass
    track.mute = mute
    return strip


class Animator:
    def __init__(self, arm_obj, name, meta, fps=24, start=1, keyset=None, fill=False):
        self.arm = arm_obj
        # keyset: bone names this animator owns (all bones when None); a generated
        # rig (Rigify) keys only its controls, never its ORG/MCH/DEF bones
        self.keyset = keyset
        self.fill = fill        # key rest on frames where a moved bone is left unset
        self.name = name
        self.meta = meta
        self.fps = fps
        self.start = start
        self.rest = {pb.name: pb.bone.matrix_local.to_3x3() for pb in self._bones()}
        self.rest_inv = {n: m.inverted() for n, m in self.rest.items()}
        self.actions = []       # (label, action, loop)
        self._rot, self._loc, self._last = {}, {}, {}
        # quadruped leg chains: (foot target, chain root bone, reach)
        self.legs = []
        for pb in arm_obj.pose.bones:
            for c in pb.constraints:
                if c.type == "IK" and c.subtarget.startswith(("h_ik", "f_ik")) and c.chain_count > 0:
                    chain = [pb.bone]
                    while len(chain) < c.chain_count and chain[-1].parent:
                        chain.append(chain[-1].parent)
                    self.legs.append((c.subtarget, chain[-1].name, sum(b.length for b in chain) * 0.999))

    def _bones(self):
        bones = self.arm.pose.bones
        if self.keyset is None:
            return list(bones)
        return [bones[n] for n in self.keyset if n in bones]

    # -- pose calls used by animation functions ------------------------------
    def rot(self, bone, *steps):
        """Rotate a bone about armature axes, e.g. rot('head', ('Z', 0.2))."""
        if bone not in self.rest:
            return
        q = self._rot.get(bone, Quaternion())
        for axis, angle in steps:
            q = Quaternion(AXES[axis] if isinstance(axis, str) else axis, angle) @ q
        self._rot[bone] = q

    def loc(self, bone, offset):
        if bone in self.rest:
            self._loc[bone] = self._loc.get(bone, Vector()) + Vector(offset)

    # -- ground contact -----------------------------------------------------
    def _posed(self, bone):
        """(rotation, head) of a bone in armature space for the pose set so far.
        Plain forward kinematics: only valid above any IK chain (hips, tail)."""
        b = self.arm.data.bones[bone]
        q = self._rot.get(bone, Quaternion())
        v = self._loc.get(bone, Vector())
        if b.parent is None:
            return q.copy(), b.head_local + v
        qp, hp = self._posed(b.parent.name)
        return qp @ q, hp + qp @ (b.head_local - b.parent.head_local + v)

    def keep_above(self, chain, floor):
        """Pitch each bone of a chain (root first) just enough that its far end
        stays at or above z = floor. Tails rest on the ground, not through it."""
        for name in chain:
            if name not in self.rest:
                continue
            b = self.arm.data.bones[name]
            q, head = self._posed(name)
            v = q @ (b.tail_local - b.head_local)
            if head.z + v.z >= floor:
                continue
            reach = math.hypot(v.y, v.z)
            if reach < 1e-9:
                continue
            want = math.asin(max(-1.0, min(1.0, (floor - head.z) / reach)))
            lift = Quaternion((1, 0, 0), want - math.atan2(v.z, abs(v.y)))
            if v.y < 0:
                lift.invert()
            qp = self._posed(b.parent.name)[0] if b.parent else Quaternion()
            self._rot[name] = qp.inverted() @ lift @ qp @ self._rot.get(name, Quaternion())

    def reach_down(self):
        """Lower the hips just enough that every foot reaches its IK target.
        A target out of reach leaves the leg straight and the foot in the air
        (a trunk pitch or a bob carried the hip or shoulder too high), so the
        body comes down instead of the target moving. Horizontal overreach is
        left alone: no drop can fix it."""
        if "hips" not in self.rest or not self.legs or self.meta.get("sprawl"):
            return
        drop = 0.0
        for target, root, reach in self.legs:
            if target not in self.rest or root not in self.rest:
                continue
            r = self._posed(root)[1]
            t = self._posed(target)[1]
            flat = (t.x - r.x) ** 2 + (t.y - r.y) ** 2
            if flat >= reach * reach:
                continue
            drop = max(drop, (r.z - t.z) - math.sqrt(reach * reach - flat))
        if drop > 0.0:
            self.loc("hips", (0, 0, -drop))

    # -- baking -------------------------------------------------------------
    def _reset(self):
        for pb in self._bones():
            pb.location = (0, 0, 0)
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.scale = (1, 1, 1)

    def _key(self, frame):
        bones = self.arm.pose.bones
        for name, q in self._rot.items():
            r = self.rest[name]
            ql = (self.rest_inv[name] @ q.to_matrix() @ r).to_quaternion()
            last = self._last.get(name)
            if last is not None and last.dot(ql) < 0:
                ql.negate()
            self._last[name] = ql.copy()
            pb = bones[name]
            pb.rotation_quaternion = ql
            if frame is not None:
                pb.keyframe_insert("rotation_quaternion", frame=frame, group=name)
        for name, v in self._loc.items():
            pb = bones[name]
            pb.location = self.rest_inv[name] @ v
            if frame is not None:
                pb.keyframe_insert("location", frame=frame, group=name)
        self._rot, self._loc = {}, {}

    def bake(self, label, fn, frames, loop=True):
        self._reset()
        action = bpy.data.actions.new("%s_%s" % (self.name, label))
        action.use_fake_user = True
        ad = self.arm.animation_data or self.arm.animation_data_create()
        ad.action = action
        self._last = {}
        # every bone the action never moves is keyed at rest, so the action owns
        # its whole pose and never inherits feet or rolls from the one played before
        moved, turned = set(), set()
        per_frame = []
        for f in range(frames + 1):
            fn(self, self.meta, f / frames)
            self.reach_down()
            if self.meta.get("tail"):
                self.keep_above(self.meta["tail"], self.meta.get("tail_floor", 0.0))
            moved.update(self._loc)
            turned.update(self._rot)
            per_frame.append((set(self._loc), set(self._rot)))
            self._key(self.start + f)
        if self.fill:
            self._fill_rest(action, per_frame, moved, turned)
        for pb in self._bones():
            if pb.name not in moved:
                pb.location = (0, 0, 0)
                pb.keyframe_insert("location", frame=self.start, group=pb.name)
            if pb.name not in turned:
                pb.rotation_quaternion = (1, 0, 0, 0)
                pb.keyframe_insert("rotation_quaternion", frame=self.start, group=pb.name)
        try:
            action.use_frame_range = True
            action.frame_start = self.start
            action.frame_end = self.start + frames
            action.use_cyclic = loop
        except Exception:
            pass
        if loop:
            for fc in action_fcurves(action):
                fc.modifiers.new("CYCLES")
        self.actions.append((label, action, loop))
        return action

    def _fill_rest(self, action, per_frame, moved, turned):
        """A bone left unset on a frame means rest, not 'interpolate across':
        key it there so cycles and holds stay exact."""
        bones = self.arm.pose.bones
        curves = {(fc.data_path, fc.array_index): fc for fc in action_fcurves(action)}
        for f, (locs, rots) in enumerate(per_frame):
            frame = self.start + f
            for name in moved - locs:
                pb = bones[name]
                pb.location = (0, 0, 0)
                pb.keyframe_insert("location", frame=frame, group=name)
            for name in turned - rots:
                fc = curves.get(('pose.bones["%s"].rotation_quaternion' % name, 0))
                w = fc.evaluate(frame) if fc else 1.0
                pb = bones[name]
                pb.rotation_quaternion = (1, 0, 0, 0) if w >= 0 else (-1, 0, 0, 0)
                pb.keyframe_insert("rotation_quaternion", frame=frame, group=name)

    def finish(self):
        """Park every action on its own NLA track; the first one plays."""
        ad = self.arm.animation_data
        if ad is None:
            return
        ad.action = None
        self._reset()
        for i, (label, action, loop) in enumerate(self.actions):
            _push_nla(ad, action, label, self.start, mute=i > 0)


# =============================================================================
# shared helpers
# =============================================================================

def _step(p, phase, stride, lift):
    """In-place foot path: forward offset, lift and a 0..1 swing amount."""
    a = TAU * (p + phase)
    swing = max(0.0, math.cos(a))
    return stride * math.sin(a), lift * swing, swing


def _tail(an, m, p, amp=0.25, cycles=1, pitch=0.0):
    names = m.get("tail", [])
    for i, b in enumerate(names):
        an.rot(b, ("Z", amp * math.sin(TAU * p * cycles - i * 0.7)), ("X", pitch))


COLLAR_SWING = 0.3


def _arm_axis(m, sg, axis="Z"):
    """An armature axis as the arm sees it: arms rest `arm_rest` below the T-pose."""
    return Quaternion((0, 1, 0), sg * m.get("arm_rest", 0.0)) @ AXES[axis]


def _arms_down(an, m, bend=0.25, swing_l=0.0, swing_r=0.0, down=1.32):
    """Hang the arms `down` radians below horizontal; the collar bone takes a
    share of the drop and COLLAR_SWING of the swing (approximation of the
    shoulder girdle moving with the arm, roughly 1 part in 3 for large swings)."""
    collar = 0.04
    for (s, sg), sw in zip(SIDES, (swing_l, swing_r)):
        an.rot("shoulder." + s, ("Y", sg * collar), ("X", sw * COLLAR_SWING))
        an.rot("upper_arm." + s, ("Y", sg * (down - collar - m.get("arm_rest", 0.0))), ("X", sw * (1 - COLLAR_SWING)))
        an.rot("forearm." + s, (_arm_axis(m, sg), -sg * bend))


# =============================================================================
# biped
# =============================================================================

def _biped_gait(an, m, p, run):
    leg = m["leg"]
    stride = leg * (0.40 if run else 0.24)
    lift = leg * (0.30 if run else 0.11)
    s1 = math.sin(TAU * p)
    for (s, sg), ph in zip(SIDES, (0.0, 0.5)):
        fwd, up, swing = _step(p, ph, stride, lift)
        an.loc("foot_ik." + s, (0, -fwd, up + (leg * 0.05 * swing if run else 0)))
        an.rot("foot_ik." + s, ("X", (0.7 if run else 0.4) * swing))
    drop = leg * (0.10 if run else 0.045)
    bob = leg * (0.05 if run else 0.022) * math.cos(2 * TAU * p + (0.6 if run else 0.0))
    lean = 0.26 if run else 0.05
    an.loc("hips", (0.012 * m["height"] * math.cos(TAU * p) * (0 if run else 1), 0, bob - drop))
    an.rot("hips", ("Z", -0.10 * s1), ("X", lean * 0.4))
    an.rot("spine", ("X", lean * 0.6), ("Z", 0.08 * s1))
    an.rot("chest", ("Z", 0.12 * s1))
    an.rot("head", ("X", -lean * 0.7), ("Z", -0.08 * s1))
    sw = (0.95 if run else 0.5) * s1
    bend = 1.45 if run else 0.3
    _arms_down(an, m, bend + 0.12 * abs(s1), sw, -sw, down=1.25 if run else 1.32)


def biped_walk(an, m, p):
    _biped_gait(an, m, p, False)


def biped_run(an, m, p):
    _biped_gait(an, m, p, True)


def biped_idle(an, m, p):
    br = math.sin(TAU * p)
    an.loc("hips", (0.004 * m["height"] * math.sin(TAU * p + 1.0), 0, -0.004 * m["height"] * (1 + br)))
    an.rot("spine", ("X", -0.012 * br))
    an.rot("chest", ("X", -0.025 * br))
    an.rot("head", ("X", 0.02 * br), ("Z", 0.06 * math.sin(TAU * p + 0.8)))
    for s, sg in SIDES:
        an.rot("shoulder." + s, ("Y", -sg * 0.03 * (1 + br)))
    _arms_down(an, m, 0.22 + 0.03 * br, 0.03 * br, 0.03 * br)


def biped_talk(an, m, p):
    """Body for dialogue: the idle with small nods. The mouth is `talk_action`."""
    biped_idle(an, m, p)
    an.rot("head", ("X", 0.04 * math.sin(TAU * p * 3)), ("Y", 0.03 * math.sin(TAU * p * 2 + 0.5)))


def biped_wave(an, m, p):
    biped_idle(an, m, p)
    e = smooth(p / 0.18) * smooth((1 - p) / 0.18)
    w = math.sin(TAU * p * 3)
    # right arm: blend from hanging (-1.32 about Y) up to a raised greeting
    an._rot.pop("upper_arm.R", None)
    an._rot.pop("forearm.R", None)
    an.rot("upper_arm.R", ("Y", -1.22 + m.get("arm_rest", 0.0) + e * 1.85), ("X", -0.15 * e))
    an.rot("forearm.R", (_arm_axis(m, -1), 0.22 * (1 - e)), ("Y", e * (1.0 + 0.4 * w)))
    an.rot("hand.R", ("Y", e * 0.25 * w))
    an.rot("head", ("Z", -0.12 * e))


def biped_jump(an, m, p):
    leg = m["leg"]
    hips, feet, arm, lean = 0.0, 0.0, 0.0, 0.0
    if p < 0.28:
        c = smooth(p / 0.28)
        hips, arm, lean = -0.30 * leg * c, 0.7 * c, 0.35 * c
    elif p < 0.38:
        c = smooth((p - 0.28) / 0.10)
        hips, arm, lean = -0.30 * leg * (1 - c), 0.7 - 2.6 * c, 0.35 * (1 - c)
    elif p < 0.74:
        u = (p - 0.38) / 0.36
        h = 4 * u * (1 - u) * 0.55 * leg
        hips, feet, arm = h, h + 0.16 * leg * math.sin(math.pi * u), -1.9 + 1.2 * u
    else:
        v = (p - 0.74) / 0.26
        hips = -0.24 * leg * math.sin(math.pi * v) * (1 - 0.3 * v)
        arm, lean = -0.7 * (1 - smooth(v)), 0.28 * math.sin(math.pi * v)
    an.loc("hips", (0, 0, hips))
    an.rot("spine", ("X", lean))
    an.rot("head", ("X", -lean * 0.6))
    for s, sg in SIDES:
        an.loc("foot_ik." + s, (0, 0, feet))
        an.rot("foot_ik." + s, ("X", 0.6 * min(1.0, feet / (0.3 * leg))))
    _arms_down(an, m, 0.35, arm, arm)


def biped_sit(an, m, p):
    e = smooth(p / 0.4)
    br = math.sin(TAU * p * 2) * e
    an.loc("hips", (0, m["thigh"] * 0.85 * e, -m["thigh"] * 0.92 * e))
    an.rot("hips", ("X", -0.12 * e))
    an.rot("spine", ("X", 0.16 * e - 0.01 * br))
    an.rot("chest", ("X", 0.05 * e - 0.02 * br))
    an.rot("head", ("X", -0.08 * e))
    _arms_down(an, m, 0.25 + 0.75 * e, -0.55 * e, -0.55 * e, down=1.32 - 0.15 * e)


# =============================================================================
# quadruped
# =============================================================================

def _quad_legs(an, m, p, phases, stride, lift):
    for (pair, s), ph in phases.items():
        fwd, up, swing = _step(p, ph, stride * m["leg_" + pair], lift * m["leg_" + pair])
        an.loc("%s_ik.%s" % (pair, s), (0, -fwd, up))
        # toe flick in the swing, never so far that a long foot dips into the ground
        flick = math.asin(min(1.0, up / max(m.get("foot_" + pair, 0.0), 1e-6)))
        an.rot("%s_ik.%s" % (pair, s), ("X", min(0.55 * swing, flick)))


# Shared quadruped clip amplitudes (approximation, tuned against the deform gate
# in tools/check_character.py on rabbit, toy cat and wolf; earlier values in brackets).
SIT_DROP = 0.42        # hip drop, share of leg height [0.62]
SIT_PITCH_MAX = 0.60   # sin of the largest trunk pitch when sitting [0.95, i.e. 72 deg]
RUN_STRIDE = 0.40      # [0.46]
RUN_LIFT = 0.24        # [0.30]
JUMP_CROUCH = 0.18     # [0.32]
JUMP_PITCH = 0.22      # take-off pitch, rad [0.30]
JUMP_LAND = 0.12       # [0.22]
JUMP_REACH = 0.08      # fore feet reach forward at take-off, share of leg height [0.15]
RUN_BOB = 0.10         # largest run bob, share of leg height [none: 0.04 * size]
SIT_FORE_FOLLOW = -1.0 # share of the shoulder shift the fore feet follow [0]


# Sprawled bodies (lizards, frogs) hang between the legs and were not re-tuned:
# they keep the earlier amplitudes.
_SPRAWL_AMP = {"RUN_BOB": 1e9, 'SIT_DROP': 0.62, 'SIT_PITCH_MAX': 0.95, 'RUN_STRIDE': 0.46, 'RUN_LIFT': 0.3, 'JUMP_CROUCH': 0.32, 'JUMP_PITCH': 0.3, 'JUMP_LAND': 0.22, 'JUMP_REACH': 0.15, 'SIT_FORE_FOLLOW': 0.0}


def _amp(m, name):
    return _SPRAWL_AMP[name] if m.get("sprawl") else globals()[name]


def quad_walk(an, m, p):
    g = m.get("gait", {})
    _quad_legs(an, m, p, {("h", "L"): 0.0, ("f", "L"): 0.25, ("h", "R"): 0.5, ("f", "R"): 0.75},
               g.get("stride", 0.24), g.get("lift", 0.13))
    s1 = math.sin(TAU * p)
    bob = min(0.012 * m["size"], 0.03 * m["leg_h"])     # short legs: the bob never lifts hips above rest
    an.loc("hips", (0, 0, -g.get("crouch", 0.04) * m["leg_h"] + bob * math.cos(2 * TAU * p)))
    an.rot("hips", ("Z", 0.05 * s1))
    an.rot("spine1", ("Z", -0.05 * s1))
    an.rot("spine2", ("Z", -0.05 * s1), ("X", 0.02 * math.cos(2 * TAU * p)))
    an.rot("neck", ("X", 0.05 * math.sin(2 * TAU * p + 0.5)), ("Z", 0.05 * s1))
    an.rot("head", ("X", -0.04 * math.sin(2 * TAU * p + 0.5)))
    _tail(an, m, p, 0.16, 1, -0.05)


def quad_run(an, m, p):
    _quad_legs(an, m, p, {("f", "L"): 0.0, ("f", "R"): 0.1, ("h", "L"): 0.5, ("h", "R"): 0.6},
               _amp(m, "RUN_STRIDE"), _amp(m, "RUN_LIFT"))
    a = TAU * p
    bob = min(0.04 * m["size"], _amp(m, "RUN_BOB") * m["leg_h"])    # short legs: the bob stays within reach
    an.loc("hips", (0, 0, -0.06 * m["leg_h"] + bob * math.sin(a + 0.6)))
    an.rot("hips", ("X", 0.10 * math.sin(a + 1.2)))
    an.rot("spine1", ("X", -0.10 * math.sin(a + 1.2)))
    an.rot("spine2", ("X", -0.12 * math.sin(a + 1.9)))
    an.rot("neck", ("X", (0.25 + 0.10 * math.sin(a + 2.4)) * m.get("neck_dip", 1.0)))
    an.rot("head", ("X", -0.12 + 0.06 * math.sin(a + 2.9)))
    for i, b in enumerate(m.get("tail", [])):
        an.rot(b, ("X", -0.18 + 0.12 * math.sin(a - i * 0.6)))
    for s, sg in SIDES:
        an.rot("ear." + s, ("X", -0.25))


def quad_idle(an, m, p):
    br = math.sin(TAU * p)
    an.loc("hips", (0, 0, -0.006 * m["size"] * (1 + br)))
    an.rot("spine2", ("X", -0.012 * br))
    an.rot("neck", ("X", 0.03 * br), ("Z", 0.10 * math.sin(TAU * p + 0.9)))
    an.rot("head", ("Z", 0.10 * math.sin(TAU * p + 0.4)), ("X", -0.02 * br))
    for s, sg in SIDES:
        an.rot("ear." + s, ("Y", sg * 0.12 * max(0.0, math.sin(TAU * p * 3 + sg))))
    _tail(an, m, p, 0.22, 2)


def quad_sit(an, m, p):
    e = smooth(p / 0.4)
    drop = m["leg_h"] * _amp(m, "SIT_DROP") * e
    ang = math.asin(min(_amp(m, "SIT_PITCH_MAX"), drop / max(m["torso"], 1e-3)))
    an.loc("hips", (0, m["leg_h"] * 0.10 * e, -drop))
    an.rot("hips", ("X", -ang))
    an.rot("spine2", ("X", -0.10 * e))
    an.rot("neck", ("X", ang * 0.55 + 0.02 * math.sin(TAU * p * 2) * e))
    an.rot("head", ("X", ang * 0.45))
    for s, sg in SIDES:
        an.loc("h_ik." + s, (sg * m["size"] * 0.02 * e, -m["leg_h"] * 0.28 * e, 0))
        # pitching the trunk carries the shoulders back: the fore feet follow
        an.loc("f_ik." + s, (0, m["torso"] * (1 - math.cos(ang)) * _amp(m, "SIT_FORE_FOLLOW"), 0))
    for i, b in enumerate(m.get("tail", [])):
        an.rot(b, ("X", ang * (0.9 if i == 0 else 0.15)),
               ("Z", 0.25 * e * math.sin(TAU * p * 3 - i * 0.7)))


def quad_jump(an, m, p):
    lh = m["leg_h"]
    hips, front, hind, pitch = 0.0, 0.0, 0.0, 0.0
    if p < 0.3:
        c = smooth(p / 0.3)
        hips, pitch = -_amp(m, "JUMP_CROUCH") * lh * c, 0.10 * c
    elif p < 0.4:
        c = smooth((p - 0.3) / 0.1)
        hips, pitch, front = -_amp(m, "JUMP_CROUCH") * lh * (1 - c), 0.10 - (0.10 + _amp(m, "JUMP_PITCH")) * c, 0.3 * lh * c
    elif p < 0.76:
        u = (p - 0.4) / 0.36
        h = 4 * u * (1 - u) * 0.8 * lh
        hips, pitch = h, -_amp(m, "JUMP_PITCH") + (_amp(m, "JUMP_PITCH") + 0.25) * u
        front = h + 0.3 * lh * (1 - u)
        hind = h + 0.25 * lh * math.sin(math.pi * u)
    else:
        v = (p - 0.76) / 0.24
        hips = -_amp(m, "JUMP_LAND") * lh * math.sin(math.pi * v)
        pitch = 0.25 * (1 - smooth(v))
    an.loc("hips", (0, 0, hips))
    an.rot("hips", ("X", pitch))
    an.rot("neck", ("X", -pitch * 0.6))
    for s, sg in SIDES:
        an.loc("f_ik." + s, (0, -_amp(m, "JUMP_REACH") * lh * (front > 0), front))
        an.loc("h_ik." + s, (0, 0.2 * lh * (hind > 0), hind))
    for i, b in enumerate(m.get("tail", [])):
        an.rot(b, ("X", -pitch * 0.5))


def quad_tail_sway(an, m, p):
    quad_idle(an, m, p)
    for b in m.get("tail", []):
        an._rot.pop(b, None)
    _tail(an, m, p, 0.42, 2, -0.04)


# =============================================================================
# bird
# =============================================================================

def _wings_folded(an, m, flutter=0.0):
    for s, sg in SIDES:
        w = m["wings"][s]
        an.rot(w[0], ("X", -1.15), ("Z", sg * (1.30 + flutter)))
        for b in w[1:]:
            an.rot(b, ("Z", sg * 0.12))


def bird_fly(an, m, p):
    a = TAU * p
    for s, sg in SIDES:
        for i, b in enumerate(m["wings"][s]):
            up = (0.55, 0.28, 0.22)[min(i, 2)] * math.sin(a - i * 0.6) + (0.10 if i == 0 else 0.0)
            an.rot(b, ("Y", -sg * up))
        an.rot("thigh." + s, ("X", 1.0))
        an.rot("shin." + s, ("X", -0.5))
    an.loc("body", (0, 0, -0.06 * m["size"] * math.sin(a + 0.4)))
    an.rot("body", ("X", 0.05 * math.sin(a + 0.4)))
    an.rot("neck", ("X", -0.05 * math.sin(a + 0.4)))
    for i, b in enumerate(m.get("tail", [])):
        an.rot(b, ("X", 0.12 * math.sin(a + 1.5)))


def bird_idle(an, m, p):
    br = math.sin(TAU * p)
    _wings_folded(an, m, 0.03 * br)
    an.loc("body", (0, 0, -0.01 * m["size"] * (1 + br)))
    look = math.sin(TAU * p)
    an.rot("neck", ("Z", 0.25 * smooth(abs(look)) * math.copysign(1, look)))
    an.rot("head", ("X", 0.05 * br))
    for b in m.get("tail", []):
        an.rot(b, ("X", 0.06 * math.sin(TAU * p * 2)))


def bird_walk(an, m, p):
    a = TAU * p
    _wings_folded(an, m)
    for (s, sg), ph in zip(SIDES, (0.0, math.pi)):
        an.rot("thigh." + s, ("X", 0.45 * math.sin(a + ph)))
        an.rot("shin." + s, ("X", -0.35 * max(0.0, math.cos(a + ph))))
    an.loc("body", (0, 0, 0.02 * m["size"] * abs(math.sin(a))))
    an.rot("neck", ("X", 0.18 * math.sin(2 * a)))
    an.rot("head", ("X", -0.18 * math.sin(2 * a)))


# =============================================================================
# fish
# =============================================================================

def _fish(an, m, p, amp, fin):
    a = TAU * p
    spine = m["spine"]
    n = max(1, len(spine) - 1)
    for i, b in enumerate(spine):
        an.rot(b, ("Z", amp * (0.15 + 0.85 * i / n) * math.sin(a - i * 0.85) * (-0.6 if i == 0 else 1)))
    for s, sg in SIDES:
        an.rot("fin." + s, ("Y", sg * fin * math.sin(a * 2 + 0.5)), ("Z", sg * 0.25))
    an.loc(spine[0], (0.02 * m["size"] * amp * math.sin(a + 1.2), 0, 0.01 * m["size"] * math.sin(a)))


def fish_swim(an, m, p):
    _fish(an, m, p, 0.30, 0.35)


def fish_idle(an, m, p):
    _fish(an, m, p, 0.09, 0.45)


# =============================================================================
# serpent
# =============================================================================

def _serpent(an, m, a, gain):
    """Lateral undulation: centre line x(s) = A sin(k s - a), s = 0 at the nose.
    Each bone takes the change of heading from the bone before it."""
    spine = m["spine"]
    n = len(spine)
    k = TAU * m["waves"]
    amp = m["amplitude"] * gain
    prev = 0.0
    for i, b in enumerate(spine):
        s = (i + 0.5) / n
        env = 0.35 + 0.65 * min(1.0, s * 4.0)             # the head swings less than the body
        heading = -math.atan(amp * env * k * math.cos(k * s - a))
        an.rot(b, ("Z", heading - prev))
        prev = heading
    an.loc(spine[0], (0.35 * amp * m["size"] * math.sin(-a), 0, 0))


def serpent_slither(an, m, p):
    _serpent(an, m, TAU * p, 1.0)


def serpent_idle(an, m, p):
    _serpent(an, m, 0.35 * math.sin(TAU * p), 0.85)


# =============================================================================
# vehicle
# =============================================================================

def vehicle_drive(an, m, p):
    for b in m["wheels"]:
        an.rot(b, ("X", TAU * p * m.get("turns", 2)))
    an.loc("body", (0, 0, 0.012 * m["size"] * math.sin(TAU * p * 2)))
    an.rot("body", ("X", 0.008 * math.sin(TAU * p * 2 + 1.0)))


def vehicle_idle(an, m, p):
    an.loc("body", (0, 0, 0.003 * m["size"] * math.sin(TAU * p * 8)))


# rig kind -> name -> (function, frames at 24 fps, loops by default)
LIBRARY = {
    "biped": {
        "walk": (biped_walk, 28, True), "run": (biped_run, 16, True),
        "idle": (biped_idle, 72, True), "wave": (biped_wave, 60, True),
        "jump": (biped_jump, 36, True), "sit": (biped_sit, 60, False),
        "talk": (biped_talk, 72, True),
    },
    "quadruped": {
        "walk": (quad_walk, 32, True), "run": (quad_run, 14, True),
        "idle": (quad_idle, 72, True), "sit": (quad_sit, 60, False),
        "jump": (quad_jump, 32, True), "tail_sway": (quad_tail_sway, 48, True),
    },
    "bird": {
        "fly": (bird_fly, 14, True), "idle": (bird_idle, 72, True), "walk": (bird_walk, 20, True),
    },
    "fish": {
        "swim": (fish_swim, 28, True), "idle": (fish_idle, 60, True),
    },
    "serpent": {
        "slither": (serpent_slither, 40, True), "idle": (serpent_idle, 96, True),
    },
    "vehicle": {
        "drive": (vehicle_drive, 24, True), "idle": (vehicle_idle, 24, True),
    },
}

ALIASES = {
    "breathe": "idle", "breathing": "idle", "idle_breathing": "idle", "stand": "idle",
    "gallop": "run", "trot": "walk", "sprint": "run", "flap": "fly", "glide": "fly",
    "tail": "tail_sway", "sway": "tail_sway", "wag": "tail_sway", "hop": "jump",
    "greet": "wave", "hello": "wave", "move": "drive",
}

# sensible stand-ins when a rig has no such cycle
FALLBACK = {
    "bird": {"run": "walk", "swim": "fly", "tail_sway": "idle", "sit": "idle", "jump": "fly"},
    "fish": {"walk": "swim", "run": "swim", "fly": "swim", "tail_sway": "swim"},
    "serpent": {"walk": "slither", "run": "slither", "swim": "slither", "tail_sway": "idle"},
    "biped": {"fly": "jump", "swim": "walk", "tail_sway": "idle"},
    "quadruped": {"fly": "jump", "swim": "walk", "wave": "tail_sway"},
    "vehicle": {"run": "drive", "walk": "drive"},
}


def animate(arm_obj, rig, spec, ctx):
    """Bake the `animation:` list of a spec. Returns the action labels."""
    names = spec.items("animation") + spec.items("animations")
    speed = spec.num("speed", 1.0, 0.05, 20)
    loop_text = spec.get("loop")
    cycle = spec.get("cycle_frames")
    if not names:
        return []
    lib = LIBRARY.get(rig.kind, {})
    an = Animator(arm_obj, rig.name, rig.meta, ctx.fps, ctx.frame_start)
    done = []
    for raw in names:
        name = ALIASES.get(raw, raw)
        if name not in lib:
            alt = FALLBACK.get(rig.kind, {}).get(name, "idle" if "idle" in lib else next(iter(lib), None))
            if alt is None:
                continue
            warn("'%s' has no '%s' animation, using '%s' (available: %s)"
                 % (spec.name, raw, alt, ", ".join(sorted(lib))), spec.line_of("animation"))
            name = alt
        if name in done:
            continue
        fn, frames, loop = lib[name]
        if loop_text is not None:
            loop = spec.flag("loop", loop)
        n = spec.integer("cycle_frames", 0, 2, 2000) if cycle else 0
        period = rig.meta.get("gait", {}).get("period") if name == "walk" else None
        if not n and period:                        # profile walk cycle length in seconds
            n = max(4, int(round(period * ctx.fps / speed)))
        if not n:
            n = max(4, int(round(frames * ctx.fps / 24.0 / speed)))
        an.bake(name, fn, n, loop)
        done.append(name)
    an.finish()
    return done


def pose(arm_obj, rig, fn, p=0.0):
    """Leave the armature posed at phase `p` of an animation function, with no keys."""
    an = Animator(arm_obj, rig.name, rig.meta)
    an._reset()
    fn(an, rig.meta, p)
    an._key(None)


# one cycle of placeholder speech: (frame at 24 fps, {shape key: value}); replace with real lip sync
TALK = ((0, {}), (4, {"MouthOpen": 0.55}), (8, {"Wide": 0.7, "MouthOpen": 0.2}), (12, {}),
        (16, {"Pucker": 0.8, "MouthOpen": 0.25}), (21, {"MouthOpen": 0.7}), (26, {"Wide": 0.4}),
        (30, {}), (36, {"MouthOpen": 0.4, "Pucker": 0.3}), (41, {"Wide": 0.8, "MouthOpen": 0.3}),
        (46, {"MouthOpen": 0.15}), (52, {}), (72, {}))


def talk_action(mesh_obj, name, fps, start):
    """A looping mouth cycle on the viseme shape keys, on its own NLA track."""
    keys = mesh_obj.data.shape_keys
    names = [n for n in ("MouthOpen", "Wide", "Pucker") if keys is not None and n in keys.key_blocks]
    if not names:
        return
    action = bpy.data.actions.new(name + "_talk")
    action.use_fake_user = True
    ad = keys.animation_data or keys.animation_data_create()
    ad.action = action
    k = fps / 24.0
    for frame, pose in TALK:
        for n in names:
            kb = keys.key_blocks[n]
            kb.value = pose.get(n, 0.0)
            kb.keyframe_insert("value", frame=start + int(round(frame * k)))
    for n in names:
        keys.key_blocks[n].value = 0.0
    for fc in action_fcurves(action):
        fc.modifiers.new("CYCLES")
    ad.action = None
    _push_nla(ad, action, "talk", start, mute=False)


def blink_action(mesh_obj, name, fps, start):
    """A looping blink on the shape keys, kept on its own NLA track."""
    keys = mesh_obj.data.shape_keys
    if keys is None or "Blink" not in keys.key_blocks:
        return
    kb = keys.key_blocks["Blink"]
    action = bpy.data.actions.new(name + "_blink")
    action.use_fake_user = True
    ad = keys.animation_data or keys.animation_data_create()
    ad.action = action
    k = fps / 24.0
    for frame, value in ((0, 0), (60, 0), (63, 1), (67, 0), (96, 0)):
        kb.value = value
        kb.keyframe_insert("value", frame=start + int(round(frame * k)))
    kb.value = 0.0
    for fc in action_fcurves(action):
        fc.modifiers.new("CYCLES")
    ad.action = None
    _push_nla(ad, action, "blink", start, mute=False)
