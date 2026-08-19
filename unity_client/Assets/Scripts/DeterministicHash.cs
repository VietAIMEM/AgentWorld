using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Deterministic, culture-independent hashing used for stable variation
    /// (NPC appearance offsets, prop placement, jitter). Never the runtime
    /// hash — the same input always yields the same output, across sessions.
    /// </summary>
    public static class DeterministicHash
    {
        public static int Hash(string s)
        {
            if (string.IsNullOrEmpty(s)) return 17;
            int h = 17;
            for (int i = 0; i < s.Length; i++)
                h = h * 31 + s[i];
            return h;
        }

        /// <summary>Bounded int in [0, max) from a stable hash.</summary>
        public static int Range(string s, int max)
        {
            if (max <= 0) return 0;
            int h = Hash(s);
            return ((h % max) + max) % max;
        }

        /// <summary>Float in [0, 1) from a stable hash.</summary>
        public static float Unit(string s)
        {
            int h = Hash(s);
            return ((h & 0x7fffffff) % 10000) / 10000f;
        }

        /// <summary>Float in [min, max] from a stable hash.</summary>
        public static float Range(string s, float min, float max)
        {
            return min + Unit(s) * (max - min);
        }
    }
}