using NUnit.Framework;
using NpcAi.Client;
using UnityEngine;

namespace NpcAi.Client.Tests
{
    public class DayNightCycleTests
    {
        [Test]
        public void NoonIsBrightDaytime()
        {
            var s = DayNightMath.ComputeSunState(1, 12, 0);
            Assert.IsFalse(s.isNight);
            Assert.IsFalse(s.lanternsOn);
            Assert.Greater(s.dayFactor, 0.5f, "noon should be bright");
            Assert.Greater(s.lightIntensity, 0.7f, "noon should be strongly lit");
        }

        [Test]
        public void MidnightIsNightWithLanterns()
        {
            var s = DayNightMath.ComputeSunState(1, 0, 0);
            Assert.IsTrue(s.isNight);
            Assert.IsTrue(s.lanternsOn);
            Assert.Less(s.dayFactor, 0.1f, "midnight should be dark");
            Assert.Less(s.lightIntensity, 0.3f, "midnight should be dim");
        }

        [Test]
        public void DawnIsDimmingTowardLight()
        {
            var before = DayNightMath.ComputeSunState(1, 5, 0);
            var after = DayNightMath.ComputeSunState(1, 6, 0);
            Assert.Less(before.lightIntensity, after.lightIntensity, "light grows after dawn");
            Assert.Greater(before.fogDensity, after.fogDensity, "fog thins as the sun rises");
        }

        [Test]
        public void LightingIsDeterministicForSameTime()
        {
            var a = DayNightMath.ComputeSunState(7, 9, 30);
            var b = DayNightMath.ComputeSunState(7, 9, 30);
            Assert.IsTrue(SunState.Equivalent(a, b));
            Assert.IsTrue(SunState.Equivalent(a, a));
        }

        [Test]
        public void DifferentDaysSameClockAreEquivalent()
        {
            var a = DayNightMath.ComputeSunState(1, 9, 0);
            var b = DayNightMath.ComputeSunState(99, 9, 0);
            Assert.AreEqual(a.dayFactor, b.dayFactor, 0.0001f, "clock determines lighting, not the day number");
        }

        [Test]
        public void SunElevationIsHighestAtNoon()
        {
            var noon = DayNightMath.ComputeSunState(1, 12, 0);
            var dusk = DayNightMath.ComputeSunState(1, 18, 0);
            Assert.Greater(noon.sunElevation, dusk.sunElevation);
        }
    }
}