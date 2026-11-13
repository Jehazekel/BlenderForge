"""Animation check: one line per armature and action.

    blender --background scene.blend --python tools/check_anims.py 2>&1 | grep ANIM

ik_miss   worst distance between an IK chain end and its target (0 = reached)
lowest    lowest deform-bone end, below 0 means under the ground
max_bend  sharpest angle between connected limb bones
All lengths are fractions of the armature size. Bones under -0.02 are listed.
"""
import bpy
sc = bpy.context.scene
for arm in sorted((o for o in bpy.data.objects if o.type == "ARMATURE"), key=lambda o: o.name):
    ad = arm.animation_data
    if not ad: continue
    size = max(arm.dimensions) or 1.0
    iks = [(pb, c.subtarget) for pb in arm.pose.bones for c in pb.constraints if c.type == "IK" and c.influence > 0]
    for tr in ad.nla_tracks:
        for t2 in ad.nla_tracks: t2.mute = t2 != tr
        st = tr.strips[0]; act = st.action
        f0, f1 = int(act.frame_start), int(act.frame_end)
        worst, low, bend = 0.0, 0.0, 0.0; who={}
        for f in range(f0, f1 + 1, 2):
            sc.frame_set(f)
            for pb, tgt in iks:
                d = (pb.tail - arm.pose.bones[tgt].head).length / size
                worst = max(worst, d)
            for pb in arm.pose.bones:
                if pb.bone.use_deform:
                    low = min(low, pb.head.z / size, pb.tail.z / size); who[pb.name]=min(who.get(pb.name,0), pb.tail.z/size, pb.head.z/size)
                    if pb.parent and pb.bone.use_connect and ("_" in pb.name[:2]):
                        a = pb.parent.vector.angle(pb.vector); bend = max(bend, a)
        print("ANIM %-8s %-10s ik_miss=%.3f lowest=%.3f max_bend=%.0fdeg" % (arm.name, tr.name, worst, low, bend * 57.3), sorted((v,k) for k,v in who.items() if v<-0.02)[:4])
