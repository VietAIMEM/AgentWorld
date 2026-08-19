using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// A fully deterministic visual profile for one NPC, derived only from the
    /// NPC id. The same id always produces the same profile — no simulation RNG,
    /// no time-dependence — so characters keep their look across restarts.
    /// </summary>
    public struct AppearanceProfile
    {
        public Color robeColor;
        public Color trimColor;
        public Color pantsColor;
        public Color skinTone;
        public Color hairColor;
        public int hairStyle;     // 0 topknot, 1 bun, 2 short cap, 3 long back
        public int accessory;     // 0 none, 1 conical hat, 2 head wrap
        public int robeStyle;     // 0 long robe, 1 tunic + sash
        public float heightScale; // ~0.92..1.08
        public float build;       // ~0.9..1.12 width factor
    }

    public static class NpcAppearance
    {
        static readonly Color[] RobePalette =
        {
            new Color(0.16f, 0.26f, 0.46f), // indigo
            new Color(0.74f, 0.15f, 0.12f), // vermilion
            new Color(0.26f, 0.50f, 0.40f), // jade
            new Color(0.15f, 0.42f, 0.47f), // teal
            new Color(0.80f, 0.50f, 0.14f), // amber
            new Color(0.52f, 0.20f, 0.42f), // plum
            new Color(0.46f, 0.46f, 0.20f), // olive
            new Color(0.34f, 0.40f, 0.45f), // slate
        };

        static readonly Color[] TrimPalette =
        {
            new Color(0.92f, 0.85f, 0.62f), // pale gold
            new Color(0.98f, 0.96f, 0.86f), // ivory
            new Color(0.85f, 0.62f, 0.25f), // brass
            new Color(0.42f, 0.30f, 0.22f), // dark bronze
        };

        static readonly Color[] PantsPalette =
        {
            new Color(0.22f, 0.20f, 0.24f), // charcoal
            new Color(0.30f, 0.26f, 0.20f), // dun
            new Color(0.55f, 0.42f, 0.24f), // tan
            new Color(0.20f, 0.30f, 0.26f), // dark teal
        };

        static readonly Color[] SkinPalette =
        {
            new Color(0.96f, 0.86f, 0.74f),
            new Color(0.90f, 0.76f, 0.62f),
            new Color(0.84f, 0.66f, 0.52f),
            new Color(0.76f, 0.58f, 0.44f),
            new Color(0.70f, 0.50f, 0.38f),
        };

        static readonly Color[] HairPalette =
        {
            new Color(0.12f, 0.10f, 0.12f),
            new Color(0.20f, 0.16f, 0.14f),
            new Color(0.28f, 0.20f, 0.16f),
            new Color(0.40f, 0.34f, 0.26f),
            new Color(0.55f, 0.48f, 0.38f),
        };

        public static AppearanceProfile Generate(string npcId)
        {
            string key = npcId ?? "";
            var p = new AppearanceProfile();
            p.robeColor = RobePalette[DeterministicHash.Range(key, RobePalette.Length)];
            p.trimColor = TrimPalette[DeterministicHash.Range(key + "t", TrimPalette.Length)];
            p.pantsColor = PantsPalette[DeterministicHash.Range(key + "p", PantsPalette.Length)];
            p.skinTone = SkinPalette[DeterministicHash.Range(key + "s", SkinPalette.Length)];
            p.hairColor = HairPalette[DeterministicHash.Range(key + "h", HairPalette.Length)];
            p.hairStyle = DeterministicHash.Range(key + "hs", 4);
            p.accessory = DeterministicHash.Range(key + "a", 3);
            p.robeStyle = DeterministicHash.Range(key + "r", 2);
            p.heightScale = DeterministicHash.Range(key, 0.92f, 1.08f);
            p.build = DeterministicHash.Range(key + "b", 0.9f, 1.12f);
            return p;
        }
    }
}