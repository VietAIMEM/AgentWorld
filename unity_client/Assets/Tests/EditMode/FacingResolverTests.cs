using System;
using UnityEngine;
using NUnit.Framework;
using NpcAi.Client;

namespace NpcAi.Client.Tests
{
    public class FacingResolverTests
    {
        static AnimationStateData State(string facingNpc, string facingObj, string facingLoc, string targetLoc)
        {
            return new AnimationStateData
            {
                facing_npc_id = facingNpc,
                facing_object_id = facingObj,
                facing_location_id = facingLoc,
                target_location_id = targetLoc,
            };
        }

        [Test]
        public void ConversationNpcTakesPriority()
        {
            var target = FacingResolver.Resolve(
                State("npc_2", "obj_9", "loc_1", "loc_1"),
                s => s == "npc_2", s => true, s => true);
            Assert.AreEqual(FacingKind.Npc, target.kind);
            Assert.AreEqual("npc_2", target.id);
        }

        [Test]
        public void InteractionObjectBeatsLocation()
        {
            var target = FacingResolver.Resolve(
                State(null, "obj_7", "loc_1", null),
                s => false, s => s == "obj_7", s => true);
            Assert.AreEqual(FacingKind.Object, target.kind);
            Assert.AreEqual("obj_7", target.id);
        }

        [Test]
        public void FacingLocationBeatsTargetLocation()
        {
            var target = FacingResolver.Resolve(
                State(null, null, "loc_1", "loc_2"),
                s => false, s => false, s => true);
            Assert.AreEqual(FacingKind.Location, target.kind);
            Assert.AreEqual("loc_1", target.id);
        }

        [Test]
        public void TargetLocationUsedWhenNoFacingSet()
        {
            var target = FacingResolver.Resolve(
                State(null, null, null, "loc_5"),
                s => false, s => false, s => s == "loc_5");
            Assert.AreEqual(FacingKind.Location, target.kind);
            Assert.AreEqual("loc_5", target.id);
        }

        [Test]
        public void TargetObjectUsedAsLastResort()
        {
            var target = FacingResolver.Resolve(
                new AnimationStateData { target_object_id = "obj_3" },
                s => false, s => s == "obj_3", s => false);
            Assert.AreEqual(FacingKind.Object, target.kind);
            Assert.AreEqual("obj_3", target.id);
        }

        [Test]
        public void NoTargetYieldsNone()
        {
            var target = FacingResolver.Resolve(
                State(null, null, null, null),
                s => false, s => false, s => false);
            Assert.AreEqual(FacingKind.None, target.kind);
            Assert.IsFalse(target.IsValid);
        }

        [Test]
        public void UnresolvedIdsAreSkipped()
        {
            // facing_npc_id references a non-visualized NPC; must fall through.
            var target = FacingResolver.Resolve(
                State("ghost", "obj_1", "loc_1", null),
                s => false, s => s == "obj_1", s => true);
            Assert.AreEqual(FacingKind.Object, target.kind);
        }

        [Test]
        public void NullStateYieldsNone()
        {
            Assert.AreEqual(FacingKind.None, FacingResolver.Resolve(null, null, null, null).kind);
        }

        [Test]
        public void TryResolvePositionReturnsNpcPosition()
        {
            Vector3 outPos;
            bool ok = FacingResolver.TryResolvePosition(
                State("npc_2", null, null, null),
                s => s == "npc_2", s => false, s => false,
                s => new Vector3(3f, 0f, 4f), null, null, out outPos);
            Assert.IsTrue(ok);
            Assert.AreEqual(new Vector3(3f, 0f, 4f), outPos);
        }
    }
}