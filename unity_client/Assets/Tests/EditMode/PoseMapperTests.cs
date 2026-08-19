using NUnit.Framework;
using NpcAi.Client;

namespace NpcAi.Client.Tests
{
    public class PoseMapperTests
    {
        [Test]
        public void EveryValidPoseMapsToExpectedAnimatorState()
        {
            Assert.AreEqual("Idle", PoseMapper.MapAnimatorState("idle"));
            Assert.AreEqual("Walk", PoseMapper.MapAnimatorState("walk"));
            Assert.AreEqual("Work", PoseMapper.MapAnimatorState("work"));
            Assert.AreEqual("Eat", PoseMapper.MapAnimatorState("eat"));
            Assert.AreEqual("Buy", PoseMapper.MapAnimatorState("buy"));
            Assert.AreEqual("Sleep", PoseMapper.MapAnimatorState("sleep"));
            Assert.AreEqual("Sit", PoseMapper.MapAnimatorState("sit"));
            Assert.AreEqual("Stand", PoseMapper.MapAnimatorState("stand"));
            Assert.AreEqual("Talk", PoseMapper.MapAnimatorState("talk"));
            Assert.AreEqual("Listen", PoseMapper.MapAnimatorState("listen"));
            Assert.AreEqual("Wave", PoseMapper.MapAnimatorState("wave"));
            Assert.AreEqual("Inspect", PoseMapper.MapAnimatorState("inspect"));
            Assert.AreEqual("Stretch", PoseMapper.MapAnimatorState("stretch"));
            Assert.AreEqual("Interact", PoseMapper.MapAnimatorState("interact"));
            Assert.AreEqual("Dead", PoseMapper.MapAnimatorState("dead"));
        }

        [Test]
        public void UnknownPoseMapsToIdle()
        {
            Assert.AreEqual("Idle", PoseMapper.MapAnimatorState("typo"));
            Assert.AreEqual("Idle", PoseMapper.MapAnimatorState(""));
            Assert.AreEqual("Idle", PoseMapper.MapAnimatorState(null));
            Assert.AreEqual("Idle", PoseMapper.MapAnimatorState("dance"));
        }

        [Test]
        public void MovingWalkProducesWalkState()
        {
            var state = new AnimationStateData { pose = "walk", moving = true };
            Assert.AreEqual("Walk", PoseMapper.MapAnimatorState(state.pose));
            Assert.IsTrue(state.moving);
        }

        [Test]
        public void ConversationPosesMapToTalkListenWave()
        {
            Assert.AreEqual("Talk", PoseMapper.MapAnimatorState("talk"));
            Assert.AreEqual("Listen", PoseMapper.MapAnimatorState("listen"));
            Assert.AreEqual("Wave", PoseMapper.MapAnimatorState("wave"));
        }

        [Test]
        public void KnownPosesAreRecognized()
        {
            Assert.IsTrue(PoseMapper.IsKnownPose("idle"));
            Assert.IsTrue(PoseMapper.IsKnownPose("dead"));
            Assert.IsFalse(PoseMapper.IsKnownPose("bogus"));
        }

        [Test]
        public void FallbackStyleForDeadLiesDown()
        {
            var style = PoseMapper.Map("dead");
            Assert.IsTrue(style.layDown);
            Assert.IsTrue(style.heightScale < 0.5f);
        }

        [Test]
        public void UnknownPoseFallsBackToIdleStyle()
        {
            var unknown = PoseMapper.Map("zzz");
            var idle = PoseMapper.Map("idle");
            Assert.AreEqual(idle.tint, unknown.tint);
            Assert.AreEqual(idle.layDown, unknown.layDown);
        }
    }
}