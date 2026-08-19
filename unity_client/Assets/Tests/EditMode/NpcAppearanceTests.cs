using System.Collections.Generic;
using NUnit.Framework;
using NpcAi.Client;
using UnityEngine;

namespace NpcAi.Client.Tests
{
    public class NpcAppearanceTests
    {
        [Test]
        public void SameIdProducesSameProfile()
        {
            var a = NpcAppearance.Generate("npc_007");
            var b = NpcAppearance.Generate("npc_007");
            Assert.AreEqual(a.robeColor, b.robeColor);
            Assert.AreEqual(a.trimColor, b.trimColor);
            Assert.AreEqual(a.pantsColor, b.pantsColor);
            Assert.AreEqual(a.skinTone, b.skinTone);
            Assert.AreEqual(a.hairColor, b.hairColor);
            Assert.AreEqual(a.hairStyle, b.hairStyle);
            Assert.AreEqual(a.accessory, b.accessory);
            Assert.AreEqual(a.robeStyle, b.robeStyle);
            Assert.AreEqual(a.heightScale, b.heightScale);
            Assert.AreEqual(a.build, b.build);
        }

        [Test]
        public void ProfilesDifferAcrossIds()
        {
            var seen = new List<Color>();
            int distinct = 0;
            for (int i = 0; i < 24; i++)
            {
                var p = NpcAppearance.Generate("npc_" + i.ToString("000"));
                bool found = false;
                foreach (var c in seen)
                    if (c == p.robeColor) { found = true; break; }
                if (!found)
                {
                    seen.Add(p.robeColor);
                    distinct++;
                }
            }
            Assert.GreaterOrEqual(distinct, 2, "a handful of ids should already yield variation");
        }

        [Test]
        public void HeightAndBuildStayWithinRanges()
        {
            for (int i = 0; i < 32; i++)
            {
                var p = NpcAppearance.Generate("npc_" + i);
                Assert.GreaterOrEqual(p.heightScale, 0.9f);
                Assert.LessOrEqual(p.heightScale, 1.1f);
                Assert.GreaterOrEqual(p.build, 0.85f);
                Assert.LessOrEqual(p.build, 1.15f);
            }
        }

        [Test]
        public void EmptyAndNullIdsAreStable()
        {
            var a = NpcAppearance.Generate(null);
            var b = NpcAppearance.Generate("");
            Assert.AreEqual(a.robeColor, b.robeColor);
            Assert.AreEqual(a.heightScale, b.heightScale);
        }
    }
}