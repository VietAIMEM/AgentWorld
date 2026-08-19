using System.Collections.Generic;
using NUnit.Framework;
using NpcAi.Client;

namespace NpcAi.Client.Tests
{
    public class WorldModelTests
    {
        [Test]
        public void RepeatedSnapshotsDoNotCreateDuplicates()
        {
            var current = new Dictionary<string, NpcVisual> { { "npc_1", null }, { "npc_2", null } };
            var toCreate = new List<string>();
            var toRemove = new List<string>();
            WorldVisual.PlanReconciliation(new[] { "npc_1", "npc_2", "npc_3" }, current, toCreate, toRemove);
            Assert.AreEqual(new List<string> { "npc_3" }, toCreate);
            Assert.IsEmpty(toRemove);
        }

        [Test]
        public void RemovedNpcsArePlannedForDestruction()
        {
            var current = new Dictionary<string, NpcVisual> { { "npc_1", null }, { "npc_2", null } };
            var toCreate = new List<string>();
            var toRemove = new List<string>();
            WorldVisual.PlanReconciliation(new[] { "npc_1" }, current, toCreate, toRemove);
            Assert.AreEqual(new List<string> { "npc_2" }, toRemove);
        }

        [Test]
        public void EmptySnapshotRemovesEverything()
        {
            var current = new Dictionary<string, NpcVisual> { { "npc_1", null } };
            var toCreate = new List<string>();
            var toRemove = new List<string>();
            WorldVisual.PlanReconciliation(new string[0], current, toCreate, toRemove);
            Assert.AreEqual(new List<string> { "npc_1" }, toRemove);
        }

        [Test]
        public void NullSnapshotIsTreatedAsEmpty()
        {
            var current = new Dictionary<string, NpcVisual> { { "npc_1", null } };
            var toCreate = new List<string>();
            var toRemove = new List<string>();
            WorldVisual.PlanReconciliation(null, current, toCreate, toRemove);
            Assert.AreEqual(new List<string> { "npc_1" }, toRemove);
        }

        [Test]
        public void EmptyIdsAreIgnored()
        {
            var current = new Dictionary<string, NpcVisual>();
            var toCreate = new List<string>();
            var toRemove = new List<string>();
            WorldVisual.PlanReconciliation(new[] { "", null, "npc_9" }, current, toCreate, toRemove);
            Assert.AreEqual(new List<string> { "npc_9" }, toCreate);
        }

        [Test]
        public void IdenticalSnapshotChangesNothing()
        {
            var current = new Dictionary<string, NpcVisual> { { "npc_1", null }, { "npc_2", null } };
            var toCreate = new List<string>();
            var toRemove = new List<string>();
            WorldVisual.PlanReconciliation(new[] { "npc_2", "npc_1" }, current, toCreate, toRemove);
            Assert.IsEmpty(toCreate);
            Assert.IsEmpty(toRemove);
        }
    }
}