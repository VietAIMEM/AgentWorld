using NUnit.Framework;
using NpcAi.Client;
using UnityEngine;

namespace NpcAi.Client.Tests
{
    public class ProceduralRigTests
    {
        [Test]
        public void IdleBreathingMovesChest()
        {
            var p = ProceduralAnimator.ComputePose("idle", false, 0.5f);
            Assert.AreNotEqual(0f, p.chestX, "idle should breathe (chest bob)");
            Assert.AreEqual(Quaternion.identity, p.rootRot, "idle stays upright");
        }

        [Test]
        public void WalkSwingsLegsOppositely()
        {
            var p = ProceduralAnimator.ComputePose("walk", true, 0.25f);
            Assert.AreNotEqual(0f, p.hipLX, "left hip should swing");
            Assert.AreEqual(-p.hipLX, p.hipRX, 0.0001f, "legs swing opposite each other");
            Assert.AreEqual(-p.shoulderLX, p.shoulderRX, 0.0001f, "arms swing opposite the legs");
        }

        [Test]
        public void WaveRaisesRightArm()
        {
            var p = ProceduralAnimator.ComputePose("wave", false, 0f);
            Assert.Less(p.shoulderRX, -2f, "right shoulder should be raised for a wave");
        }

        [Test]
        public void ToneAdjustsWavePresentationOnly()
        {
            var warm = ProceduralAnimator.ForState("wave", false, "", 1f, "warm");
            var tense = ProceduralAnimator.ForState("wave", false, "", 1f, "tense");
            var neutral = ProceduralAnimator.ForState("wave", false, "", 1f, "neutral");
            Assert.Greater(
                Mathf.Abs(warm.shoulderRX - (-3f)),
                Mathf.Abs(tense.shoulderRX - (-3f)),
                "a warm greeting waves more energetically than a tense one");
            Assert.AreEqual(
                neutral.shoulderRX,
                ProceduralAnimator.ForState("wave", false, "", 1f).shoulderRX,
                0.0001f,
                "neutral tone matches the default pose");
        }

        [Test]
        public void ToneNeverChangesNonGreetingPoses()
        {
            Assert.IsTrue(RigPose.Equivalent(
                ProceduralAnimator.ForState("idle", false, "", 1f, "warm"),
                ProceduralAnimator.ForState("idle", false, "", 1f, "neutral")));
            Assert.IsTrue(RigPose.Equivalent(
                ProceduralAnimator.ForState("walk", true, "", 1f, "tense"),
                ProceduralAnimator.ForState("walk", true, "", 1f, "neutral")));
        }

        [Test]
        public void SitBendsKneesAndLowersHips()
        {
            var p = ProceduralAnimator.ComputePose("sit", false, 0f);
            Assert.Less(p.kneeLX, -1f);
            Assert.Less(p.kneeRX, -1f);
            Assert.Less(p.hipsOffset, 0f, "sitting lowers the hips");
        }

        [Test]
        public void SleepAndDeadLayTheRigDown()
        {
            Assert.AreNotEqual(Quaternion.identity, ProceduralAnimator.ComputePose("sleep", false, 0f).rootRot);
            Assert.AreNotEqual(Quaternion.identity, ProceduralAnimator.ComputePose("dead", false, 0f).rootRot);
        }

        [Test]
        public void UnknownPoseFallsBackToIdle()
        {
            Assert.IsTrue(RigPose.Equivalent(
                ProceduralAnimator.ComputePose("typo", false, 0.3f),
                ProceduralAnimator.ComputePose("idle", false, 0.3f)));
        }

        [Test]
        public void PoseIsDeterministicForSameTime()
        {
            var a = ProceduralAnimator.ComputePose("walk", true, 1.1f);
            var b = ProceduralAnimator.ComputePose("walk", true, 1.1f);
            Assert.IsTrue(RigPose.Equivalent(a, b));
        }

        [Test]
        public void ApplyDrivesJointsOnARealRig()
        {
            var go = new GameObject("RigHost");
            try
            {
                var rig = ProceduralRig.Build(go.transform, NpcAppearance.Generate("npc_042"), 1.8f);
                Assert.IsNotNull(rig.Head, "head joint must exist");
                Assert.IsNotNull(rig.HipL, "hip joint must exist");
                Assert.IsNotNull(rig.ShoulderR, "shoulder joint must exist");
                Assert.IsNotNull(rig.Hips.Find("Torso/Chest/Head"), "head must hang under hips/torso/chest");

                ProceduralAnimator.Apply(rig, "walk", true, 0.25f);
                Assert.AreNotEqual(Quaternion.identity, rig.HipL.localRotation, "walk animates the left hip");

                ProceduralAnimator.Apply(rig, "sleep", false, 0f);
                Assert.AreNotEqual(Quaternion.identity, rig.Root.localRotation, "lay-down poses rotate the rig root");
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void SitPlacesHipsNearGround()
        {
            var p = ProceduralAnimator.Sit(0f);
            Assert.Less(p.hipsOffset, -0.2f, "sitting must drop the hips well below standing height");
            Assert.Less(p.kneeLX, -1f, "knees bend sharply when seated");
            Assert.AreEqual(Quaternion.identity, p.rootRot, "sitting stays upright");
        }

        [Test]
        public void LyingRestsOnTheGround()
        {
            var p = ProceduralAnimator.Lying(0f);
            Assert.AreNotEqual(Quaternion.identity, p.rootRot, "lying rotates the root");
            Assert.Greater(p.rootHeightOffset, 0f, "root is raised so the body rests on the floor");
            Assert.Greater(0.5f, p.rootHeightOffset, "the lift is a small fraction of character height");
        }

        [Test]
        public void ApplyInterpolatesRatherThanSnapping()
        {
            var go = new GameObject("RigHost");
            try
            {
                var rig = ProceduralRig.Build(go.transform, NpcAppearance.Generate("npc_042"), 1.8f);
                var idle = ProceduralAnimator.Idle(0f);
                var walk = ProceduralAnimator.Walk(0.25f);

                ProceduralAnimator.Apply(rig, idle, false, 0f, 0.0f);
                var idleHipRot = rig.HipL.localRotation;

                ProceduralAnimator.Apply(rig, walk, true, 0.25f, 0.001f);
                var stepped = rig.HipL.localRotation;
                Assert.AreNotEqual(idleHipRot, stepped, "first step should move toward the walk pose");

                for (int i = 0; i < 10; i++)
                    ProceduralAnimator.Apply(rig, walk, true, 0.25f, 0.016f);
                var settled = rig.HipL.localRotation;
                var target = ProceduralAnimator.Walk(0.25f);
                Assert.AreNotEqual(stepped, settled, "repeated frames keep approaching the target");
                Assert.Less(Quaternion.Angle(settled, Quaternion.Euler(target.hipLX, 0, 0)), 2f,
                    "after enough frames the hip settles onto the walk pose");
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void FirstApplySnapsInstantly()
        {
            var go = new GameObject("RigHost");
            try
            {
                var rig = ProceduralRig.Build(go.transform, NpcAppearance.Generate("npc_042"), 1.8f);
                var walk = ProceduralAnimator.Walk(0.25f);
                ProceduralAnimator.Apply(rig, walk, true, 0.25f, 0.0f);
                Assert.AreEqual(Quaternion.Euler(walk.hipLX, 0, 0), rig.HipL.localRotation,
                    "first apply snaps directly to the target");
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void ForStateMatchesOldComputePose()
        {
            Assert.IsTrue(RigPose.Equivalent(
                ProceduralAnimator.ComputePose("sit", false, 0f),
                ProceduralAnimator.ForState("sit", false, "", 0f)));
            Assert.IsTrue(RigPose.Equivalent(
                ProceduralAnimator.ComputePose("typo", false, 0.3f),
                ProceduralAnimator.ForState("typo", false, "idle", 0.3f)));
        }

        [Test]
        public void FallbackNpcBuildsHumanoidRig()
        {
            var go = new GameObject("NpcVisual");
            var visual = go.AddComponent<NpcVisual>();
            visual.EnsureBuilt();
            try
            {
                Assert.IsNotNull(visual.CharacterModel);
                Assert.IsNotNull(visual.CharacterModel.Find("RigRoot"), "fallback must contain the procedural rig");
                Assert.IsNotNull(visual.CharacterModel.Find("RigRoot/Hips/Torso/Chest/Head"), "rig must contain a head joint");
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }
    }
}