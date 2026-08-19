using System.Collections.Generic;
using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// A stylized humanoid built entirely from Unity primitives. Proportions are
    /// relative to the target character height so the same rig works at any scale.
    /// The rig is a pure data holder of joint Transforms plus per-rig smoothing
    /// state; all animation is driven by ProceduralAnimator (time-parameterized,
    /// deterministic). No simulation/AI.
    ///
    /// Joint tree:
    ///   Root (RigRoot — pivot for lay-down poses, raised for ground contact)
    ///    ├── Hips
    ///    │    ├── HipL → KneeL → FootL
    ///    │    ├── HipR → KneeR → FootR
    ///    │    └── Torso → Chest
    ///    │         ├── Head (+ hair, accessory)
    ///    │         ├── ShoulderL → ElbowL → HandL
    ///    │         └── ShoulderR → ElbowR → HandR
    /// </summary>
    public class ProceduralRig
    {
        public Transform Root;
        public Transform Hips;
        public Transform Torso;
        public Transform Chest;
        public Transform Head;
        public Transform ShoulderL, ElbowL, HandL;
        public Transform ShoulderR, ElbowR, HandR;
        public Transform HipL, KneeL, FootL;
        public Transform HipR, KneeR, FootR;
        public float Height;

        /// <summary>Degrees/second used to blend between poses.</summary>
        public float poseBlendSpeed = 300f;
        /// <summary>Character-heights/second used to blend hip/root vertical offsets.</summary>
        public float hipsBlendSpeed = 1.5f;

        internal readonly Dictionary<Transform, Quaternion> _smoothedRot = new Dictionary<Transform, Quaternion>();
        internal readonly Dictionary<Transform, Vector3> _smoothedPos = new Dictionary<Transform, Vector3>();
        internal bool _hasSmoothedState;

        public static ProceduralRig Build(Transform parent, AppearanceProfile a, float height)
        {
            float H = height;
            var rig = new ProceduralRig { Height = H };

            var root = new GameObject("RigRoot").transform;
            root.SetParent(parent, false);
            root.localPosition = Vector3.zero;
            rig.Root = root;

            rig.Hips = Joint("Hips", root, new Vector3(0f, 0.42f * H, 0f));
            rig.HipL = Joint("HipL", rig.Hips, new Vector3(-0.075f * H, 0f, 0f));
            rig.HipR = Joint("HipR", rig.Hips, new Vector3(0.075f * H, 0f, 0f));
            BuildLeg(rig, rig.HipL, true, a, H);
            BuildLeg(rig, rig.HipR, false, a, H);

            rig.Torso = Joint("Torso", rig.Hips, Vector3.zero);
            rig.Chest = Joint("Chest", rig.Torso, new Vector3(0f, 0.24f * H, 0f));
            rig.Head = Joint("Head", rig.Chest, new Vector3(0f, 0.10f * H, 0f));

            float b = a.build;
            if (a.robeStyle == 0)
            {
                Part(PrimitiveType.Cube, rig.Torso, new Vector3(0f, 0.15f * H, 0f), new Vector3(0.28f * H * b, 0.42f * H, 0.19f * H), a.robeColor);
                Part(PrimitiveType.Cube, rig.Hips, new Vector3(0f, 0.03f * H, 0f), new Vector3(0.29f * H * b, 0.06f * H, 0.20f * H), a.trimColor);
            }
            else
            {
                Part(PrimitiveType.Cube, rig.Torso, new Vector3(0f, 0.13f * H, 0f), new Vector3(0.26f * H * b, 0.28f * H, 0.17f * H), a.robeColor);
                Part(PrimitiveType.Cube, rig.Hips, new Vector3(0f, 0.02f * H, 0f), new Vector3(0.27f * H * b, 0.06f * H, 0.18f * H), a.trimColor);
            }

            rig.ShoulderL = Joint("ShoulderL", rig.Chest, new Vector3(-0.13f * H * b, 0.05f * H, 0f));
            rig.ShoulderR = Joint("ShoulderR", rig.Chest, new Vector3(0.13f * H * b, 0.05f * H, 0f));
            BuildArm(rig, rig.ShoulderL, true, a, H);
            BuildArm(rig, rig.ShoulderR, false, a, H);

            Part(PrimitiveType.Sphere, rig.Head, new Vector3(0f, 0.05f * H, 0f), Vector3.one * (0.17f * H), a.skinTone);
            BuildHair(rig, a, H);
            BuildAccessory(rig, a, H);

            return rig;
        }

        static Transform Joint(string name, Transform parent, Vector3 localPos)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            return go.transform;
        }

        static GameObject Part(PrimitiveType type, Transform parent, Vector3 localPos, Vector3 localScale, Color color)
        {
            return PrimitiveUtils.Part(type, parent, localPos, localScale, color, false);
        }

        static void BuildArm(ProceduralRig rig, Transform shoulder, bool left, AppearanceProfile a, float H)
        {
            float b = a.build;
            Color sleeve = a.robeColor;
            Part(PrimitiveType.Cube, shoulder, new Vector3(0f, -0.09f * H, 0f),
                new Vector3(0.05f * H * b + 0.012f * H, 0.18f * H, 0.05f * H * b + 0.012f * H), sleeve);
            var elbow = Joint(left ? "ElbowL" : "ElbowR", shoulder, new Vector3(0f, -0.17f * H, 0f));
            if (left) rig.ElbowL = elbow; else rig.ElbowR = elbow;
            Part(PrimitiveType.Cube, elbow, new Vector3(0f, -0.08f * H, 0f),
                new Vector3(0.042f * H, 0.16f * H, 0.042f * H), sleeve);
            var hand = Joint(left ? "HandL" : "HandR", elbow, new Vector3(0f, -0.15f * H, 0f));
            if (left) rig.HandL = hand; else rig.HandR = hand;
            Part(PrimitiveType.Sphere, hand, new Vector3(0f, -0.02f * H, 0f), Vector3.one * (0.06f * H), a.skinTone);
        }

        static void BuildLeg(ProceduralRig rig, Transform hip, bool left, AppearanceProfile a, float H)
        {
            Part(PrimitiveType.Cube, hip, new Vector3(0f, -0.10f * H, 0f),
                new Vector3(0.075f * H, 0.20f * H, 0.08f * H), a.pantsColor);
            var knee = Joint(left ? "KneeL" : "KneeR", hip, new Vector3(0f, -0.19f * H, 0f));
            if (left) rig.KneeL = knee; else rig.KneeR = knee;
            Part(PrimitiveType.Cube, knee, new Vector3(0f, -0.095f * H, 0f),
                new Vector3(0.06f * H, 0.19f * H, 0.07f * H), a.pantsColor);
            var foot = Joint(left ? "FootL" : "FootR", knee, new Vector3(0f, -0.185f * H, 0.01f * H));
            if (left) rig.FootL = foot; else rig.FootR = foot;
            Part(PrimitiveType.Cube, foot, new Vector3(0f, -0.015f * H, 0.02f * H),
                new Vector3(0.1f * H, 0.03f * H, 0.13f * H), new Color(0.15f, 0.12f, 0.10f));
        }

        static void BuildHair(ProceduralRig rig, AppearanceProfile a, float H)
        {
            Color hair = a.hairColor;
            switch (a.hairStyle)
            {
                case 0:
                    Part(PrimitiveType.Cylinder, rig.Head, new Vector3(0f, 0.13f * H, 0f),
                        new Vector3(0.10f * H, 0.045f * H, 0.10f * H), hair);
                    Part(PrimitiveType.Sphere, rig.Head, new Vector3(0f, 0.175f * H, 0f),
                        Vector3.one * (0.09f * H), hair);
                    break;
                case 1:
                    Part(PrimitiveType.Sphere, rig.Head, new Vector3(0.01f * H, 0.12f * H, -0.02f * H),
                        Vector3.one * (0.12f * H), hair);
                    break;
                case 2:
                    Part(PrimitiveType.Cube, rig.Head, new Vector3(0f, 0.115f * H, 0.005f * H),
                        new Vector3(0.19f * H, 0.05f * H, 0.19f * H), hair);
                    break;
                default:
                    Part(PrimitiveType.Cube, rig.Head, new Vector3(0f, 0.115f * H, 0.005f * H),
                        new Vector3(0.19f * H, 0.05f * H, 0.19f * H), hair);
                    Part(PrimitiveType.Cube, rig.Head, new Vector3(-0.04f * H, 0.02f * H, -0.085f * H),
                        new Vector3(0.05f * H, 0.16f * H, 0.05f * H), hair);
                    Part(PrimitiveType.Cube, rig.Head, new Vector3(0.04f * H, 0.02f * H, -0.085f * H),
                        new Vector3(0.05f * H, 0.16f * H, 0.05f * H), hair);
                    break;
            }
        }

        static void BuildAccessory(ProceduralRig rig, AppearanceProfile a, float H)
        {
            switch (a.accessory)
            {
                case 1:
                    PrimitiveUtils.Cone(rig.Head, new Vector3(0f, 0.135f * H, 0f), 0.12f * H, 0.13f * H,
                        new Color(0.75f, 0.62f, 0.35f));
                    break;
                case 2:
                    Part(PrimitiveType.Cube, rig.Head, new Vector3(0f, 0.10f * H, 0f),
                        new Vector3(0.21f * H, 0.045f * H, 0.21f * H), a.trimColor);
                    break;
            }
        }
    }

    /// <summary>
    /// Pure, time-parameterized joint pose. Stored as radians so tests can
    /// verify values without touching Transforms. Deterministic: the same
    /// (pose, moving, time) always yields the same RigPose.
    /// </summary>
    public struct RigPose
    {
        public Quaternion rootRot;
        public float rootHeightOffset; // in H units — lifts the whole rig so lying bodies rest on the ground
        public float hipsOffset;       // in H units, relative to the standing hips height (0.42H)
        public float hipsX, hipsY, hipsZ;
        public float torsoX, torsoY, torsoZ;
        public float chestX, chestY, chestZ;
        public float headX, headY, headZ;
        public float shoulderLX, shoulderLY, shoulderLZ;
        public float shoulderRX, shoulderRY, shoulderRZ;
        public float elbowLX, elbowRX;
        public float hipLX, hipLZ;
        public float hipRX, hipRZ;
        public float kneeLX, kneeRX;
        public float footLX, footRX;

        public static bool Equivalent(RigPose a, RigPose b)
        {
            if (a.rootRot != b.rootRot) return false;
            return Mathf.Approximately(a.rootHeightOffset, b.rootHeightOffset)
                && Mathf.Approximately(a.hipsOffset, b.hipsOffset)
                && Mathf.Approximately(a.hipsX, b.hipsX) && Mathf.Approximately(a.hipsY, b.hipsY) && Mathf.Approximately(a.hipsZ, b.hipsZ)
                && Mathf.Approximately(a.torsoX, b.torsoX) && Mathf.Approximately(a.torsoY, b.torsoY) && Mathf.Approximately(a.torsoZ, b.torsoZ)
                && Mathf.Approximately(a.chestX, b.chestX) && Mathf.Approximately(a.chestY, b.chestY) && Mathf.Approximately(a.chestZ, b.chestZ)
                && Mathf.Approximately(a.headX, b.headX) && Mathf.Approximately(a.headY, b.headY) && Mathf.Approximately(a.headZ, b.headZ)
                && Mathf.Approximately(a.shoulderLX, b.shoulderLX) && Mathf.Approximately(a.shoulderLY, b.shoulderLY) && Mathf.Approximately(a.shoulderLZ, b.shoulderLZ)
                && Mathf.Approximately(a.shoulderRX, b.shoulderRX) && Mathf.Approximately(a.shoulderRY, b.shoulderRY) && Mathf.Approximately(a.shoulderRZ, b.shoulderRZ)
                && Mathf.Approximately(a.elbowLX, b.elbowLX) && Mathf.Approximately(a.elbowRX, b.elbowRX)
                && Mathf.Approximately(a.hipLX, b.hipLX) && Mathf.Approximately(a.hipLZ, b.hipLZ)
                && Mathf.Approximately(a.hipRX, b.hipRX) && Mathf.Approximately(a.hipRZ, b.hipRZ)
                && Mathf.Approximately(a.kneeLX, b.kneeLX) && Mathf.Approximately(a.kneeRX, b.kneeRX)
                && Mathf.Approximately(a.footLX, b.footLX) && Mathf.Approximately(a.footRX, b.footRX);
        }
    }

    /// <summary>
    /// Time-parameterized deterministic pose generator. Handles a fixed pose
    /// vocabulary (Idle, Walk, Sit, Sleep, Dead) plus conversation/behavior
    /// blend targets. Applies smoothed interpolation so pose changes never pop.
    /// All values are derived from the pose/time/rig — never from simulation
    /// state — and the visual layer never mutates simulation state.
    /// </summary>
    public static class ProceduralAnimator
    {
        /// <summary>Blend factor that makes the current pose weigh as "settled".</summary>
        const float PoseEpsilon = 1e-4f;

        /// <summary>
        /// Applies <paramref name="pose"/> to <paramref name="rig"/>, smoothly
        /// interpolating per joint. Pass deltaTime=-1 to use Time.deltaTime
        /// (falls back to a fixed 1/60 in edit mode so tests are deterministic).
        /// The first call for a rig snaps directly to the target.
        /// </summary>
        public static void Apply(ProceduralRig rig, RigPose pose, bool moving, float time, float deltaTime = -1f)
        {
            if (rig == null) return;

            if (deltaTime < 0f)
            {
                deltaTime = Time.deltaTime;
                if (deltaTime <= 0f) deltaTime = 1f / 60f;
            }

            bool snap = !rig._hasSmoothedState;
            rig._hasSmoothedState = true;

            Quaternion targetRot = pose.rootRot;
            float targetRootH = pose.rootHeightOffset;
            float targetHipsY = 0.42f + pose.hipsOffset;

            if (!snap)
            {
                targetRot = Smoothed(rig, rig.Root, targetRot, deltaTime, rig.poseBlendSpeed);
                targetRootH = Mathf.Lerp(rig.Root.localPosition.y / rig.Height, targetRootH, 1f - Mathf.Exp(-rig.hipsBlendSpeed * deltaTime));
                targetHipsY = Mathf.Lerp(rig.Hips.localPosition.y / rig.Height, targetHipsY, 1f - Mathf.Exp(-rig.hipsBlendSpeed * deltaTime));
            }

            rig.Root.localRotation = targetRot;
            rig.Root.localPosition = new Vector3(0f, targetRootH * rig.Height, 0f);
            rig.Hips.localPosition = new Vector3(0f, targetHipsY * rig.Height, 0f);

            ApplyJoint(rig, rig.Hips, pose.hipsX, pose.hipsY, pose.hipsZ, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.Torso, pose.torsoX, pose.torsoY, pose.torsoZ, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.Chest, pose.chestX, pose.chestY, pose.chestZ, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.Head, pose.headX, pose.headY, pose.headZ, snap, deltaTime, rig.poseBlendSpeed);

            ApplyJoint(rig, rig.ShoulderL, pose.shoulderLX, pose.shoulderLY, pose.shoulderLZ, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.ShoulderR, pose.shoulderRX, pose.shoulderRY, pose.shoulderRZ, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.ElbowL, pose.elbowLX, 0f, 0f, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.ElbowR, pose.elbowRX, 0f, 0f, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.HipL, pose.hipLX, 0f, pose.hipLZ, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.HipR, pose.hipRX, 0f, pose.hipRZ, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.KneeL, pose.kneeLX, 0f, 0f, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.KneeR, pose.kneeRX, 0f, 0f, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.FootL, pose.footLX, 0f, 0f, snap, deltaTime, rig.poseBlendSpeed);
            ApplyJoint(rig, rig.FootR, pose.footRX, 0f, 0f, snap, deltaTime, rig.poseBlendSpeed);
        }

        static Quaternion Smoothed(ProceduralRig rig, Transform t, Quaternion target, float dt, float speed)
        {
            Quaternion current;
            if (!rig._smoothedRot.TryGetValue(t, out current)) current = t.localRotation;
            Quaternion next = Quaternion.RotateTowards(current, target, speed * dt);
            rig._smoothedRot[t] = next;
            return next;
        }

        static void ApplyJoint(ProceduralRig rig, Transform t, float x, float y, float z, bool snap, float dt, float speed)
        {
            if (t == null) return;
            Quaternion target = Quaternion.Euler(x, y, z);
            if (snap)
            {
                t.localRotation = target;
                rig._smoothedRot[t] = target;
                return;
            }
            Quaternion next = Quaternion.RotateTowards(t.localRotation, target, speed * dt);
            t.localRotation = next;
            rig._smoothedRot[t] = next;
        }

        /// <summary>Idle sway. Mirrors the breathing cycle on the chest and head.</summary>
        public static RigPose Idle(float time)
        {
            float s = Mathf.Sin(time * 2.2f) * 2f;
            float s2 = Mathf.Sin(time * 2.2f + 0.6f) * 2.5f;
            var p = new RigPose();
            p.torsoX = s;
            p.chestX = s * 0.6f;
            p.chestY = s2 * 0.5f;
            p.headX = s * 0.4f;
            p.shoulderLY = -0.06f;
            p.shoulderRY = -0.06f;
            p.elbowLX = 0.18f;
            p.elbowRX = 0.18f;
            p.hipLX = 0.02f; p.hipRX = 0.02f;
            p.kneeLX = 0.02f; p.kneeRX = 0.02f;
            p.hipsOffset = 0f;
            p.rootRot = Quaternion.identity;
            return p;
        }

        /// <summary>Walking gait. Legs swing opposite arms; hips tilt with each stride.</summary>
        public static RigPose Walk(float time)
        {
            float stride = Mathf.Sin(time * 9.5f);
            float stride2 = Mathf.Sin(time * 9.5f + Mathf.PI);
            float bob = Mathf.Sin(time * 19f) * 0.015f;
            var p = new RigPose();
            p.hipsOffset = bob;
            p.hipsY = stride * 3f;
            p.torsoX = -stride * 3f;
            p.chestX = -stride * 2f;
            p.headX = stride * 2f;
            p.shoulderLX = stride * 22f; p.shoulderRX = stride2 * 22f;
            p.elbowLX = stride * 28f; p.elbowRX = stride2 * 28f;
            p.hipLX = stride * 30f; p.hipRX = stride2 * 30f;
            p.kneeLX = stride * 30f; p.kneeRX = stride2 * 30f;
            p.footLX = stride * 12f; p.footRX = stride2 * 12f;
            p.rootRot = Quaternion.identity;
            return p;
        }

        /// <summary>
        /// Sitting on a bench/stool. Hips drop so the character sits at bench
        /// height; knees bend sharply forward; feet plant on the ground.
        /// </summary>
        public static RigPose Sit(float time)
        {
            var p = new RigPose();
            p.hipsOffset = -0.33f;
            p.torsoX = 4f;
            p.chestX = -2f;
            p.headX = -1f;
            p.shoulderLY = -0.5f; p.shoulderRY = -0.5f;
            p.elbowLX = 0.5f; p.elbowRX = 0.5f;
            p.hipLX = 1.15f; p.hipRX = 1.15f;
            p.kneeLX = -1.5f; p.kneeRX = -1.5f;
            p.footLX = 0.4f; p.footRX = 0.4f;
            p.rootRot = Quaternion.identity;
            return p;
        }

        /// <summary>
        /// Sleeping / unconscious. The rig lies flat on the ground: the root is
        /// rotated 90 degrees around X and raised by a small fraction of H so the
        /// body rests on the floor instead of sinking through it. Feet hover by
        /// the same fraction — accepted as a stylization.
        /// </summary>
        public static RigPose Lying(float time)
        {
            var p = new RigPose();
            p.rootRot = Quaternion.Euler(90f, 0f, 0f);
            p.rootHeightOffset = 0.095f;
            p.torsoX = 0f; p.chestX = 0f; p.headX = 0f;
            p.shoulderLY = 0.4f; p.shoulderRY = 0.4f;
            p.elbowLX = 0.8f; p.elbowRX = 0.8f;
            p.hipLX = 0.1f; p.hipRX = 0.1f;
            p.kneeLX = 0.1f; p.kneeRX = 0.1f;
            return p;
        }

        /// <summary>Upright, relaxed conversational pose (no sway — stable in UI).</summary>
        public static RigPose Stand(float time)
        {
            var p = new RigPose();
            p.shoulderLY = -0.04f; p.shoulderRY = -0.04f;
            p.elbowLX = 0.15f; p.elbowRX = 0.15f;
            return p;
        }

        /// <summary>Waving the right arm (greeting gesture).</summary>
        public static RigPose Wave(float time)
        {
            return Wave(time, "neutral");
        }

        /// <summary>Waving with a presentation-only amplitude derived from conversational tone.</summary>
        public static RigPose Wave(float time, string tone)
        {
            var p = Stand(time);
            float amplitude = tone == "tense" ? 0.12f : (tone == "warm" ? 0.45f : 0.3f);
            p.shoulderRX = -3f + Mathf.Sin(time * 6f) * amplitude;
            p.elbowRX = 1.2f;
            return p;
        }

        /// <summary>Pose used when an NPC is busy with an object (well, stall, etc).</summary>
        public static RigPose UseObject(float time)
        {
            float s = Mathf.Sin(time * 3f) * 4f;
            var p = Stand(time);
            p.torsoX = 14f + s;
            p.chestX = 8f + s * 0.6f;
            p.headX = -6f;
            p.shoulderLX = -0.6f; p.shoulderRX = -0.6f;
            p.elbowLX = 1.3f; p.elbowRX = 1.3f;
            return p;
        }

        /// <summary>
        /// Selects the rig pose for an AnimationState + movement flag.
        /// Deterministic given (pose, moving, behavior_state, time).
        /// </summary>
        public static RigPose ForState(string pose, bool moving, string behavior, float time)
        {
            return ForState(pose, moving, behavior, time, "neutral");
        }

        /// <summary>
        /// Selects the rig pose for an AnimationState + movement flag + conversational
        /// tone. Tone only adjusts presentation amplitude; it never changes the pose.
        /// Deterministic given (pose, moving, behavior_state, time, tone).
        /// </summary>
        public static RigPose ForState(string pose, bool moving, string behavior, float time, string tone)
        {
            switch (pose)
            {
                case "sit": return Sit(time);
                case "sleep":
                case "dead": return Lying(time);
                case "use_object": return UseObject(time);
                case "wave": return Wave(time, tone);
                default:
                    if (moving) return Walk(time);
                    if (behavior == "talk") return Stand(time);
                    return Idle(time);
            }
        }

        /// <summary>Compatibility alias for the old pose API (no behavior hint).</summary>
        public static RigPose ComputePose(string pose, bool moving, float time)
        {
            return ForState(pose, moving, "", time);
        }

        /// <summary>Compatibility overload applying a pose by name.</summary>
        public static void Apply(ProceduralRig rig, string pose, bool moving, float time, float deltaTime = -1f)
        {
            Apply(rig, ComputePose(pose, moving, time), moving, time, deltaTime);
        }

        /// <summary>Tone-aware overload: same as the pose-name overload, but feeds the
        /// presentation tone into the pose so greetings reflect the conversation tone.</summary>
        public static void Apply(ProceduralRig rig, string pose, bool moving, string tone, float time, float deltaTime = -1f)
        {
            Apply(rig, ForState(pose, moving, "", time, tone), moving, time, deltaTime);
        }
    }
}