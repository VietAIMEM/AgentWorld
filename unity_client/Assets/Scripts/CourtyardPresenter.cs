using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Builds the ancient-Chinese courtyard presentation: sandy ground, paved
    /// plaza, perimeter walls with lanterns, courtyard trees, and themed,
    /// deterministic props per location type and object type. Purely visual —
    /// no simulation/AI. All placement is derived from stable ids so the same
    /// snapshot always renders the same scene.
    /// </summary>
    public static class CourtyardPresenter
    {
        static readonly Color Sandy = new Color(0.78f, 0.72f, 0.55f);
        static readonly Color Rim = new Color(0.55f, 0.48f, 0.38f);
        static readonly Color Plaza = new Color(0.64f, 0.62f, 0.58f);
        static readonly Color WallStone = new Color(0.80f, 0.80f, 0.78f);
        static readonly Color WallCap = new Color(0.45f, 0.45f, 0.48f);
        static readonly Color Wood = new Color(0.55f, 0.36f, 0.20f);
        static readonly Color DarkWood = new Color(0.40f, 0.25f, 0.14f);
        static readonly Color RoofDark = new Color(0.32f, 0.18f, 0.10f);
        static readonly Color RoofGreen = new Color(0.30f, 0.42f, 0.32f);
        static readonly Color Leaf = new Color(0.25f, 0.45f, 0.22f);
        static readonly Color Lantern = new Color(0.92f, 0.55f, 0.20f);
        static readonly Color Canopy = new Color(0.80f, 0.30f, 0.25f);
        static readonly Color Fire = new Color(0.98f, 0.60f, 0.15f);
        static readonly Color Stone = new Color(0.55f, 0.54f, 0.52f);

        // ------------------------------------------------------------------
        // Environment
        // ------------------------------------------------------------------

        public static void BuildEnvironment(float worldScale)
        {
            Vector3 center = new Vector3(50f * worldScale, 0f, 50f * worldScale);

            var ground = Part(PrimitiveType.Plane, null, center + new Vector3(0f, -0.01f, 0f),
                Vector3.one * 8f, Sandy, true);
            ground.name = "Ground";

            var rim = Part(PrimitiveType.Plane, null, center + new Vector3(0f, -0.04f, 0f),
                Vector3.one * 9.2f, Rim, true);
            rim.name = "GroundRim";

            Part(PrimitiveType.Cylinder, null, center + new Vector3(0f, 0.025f, 0f),
                new Vector3(14f, 0.04f, 14f), Plaza, false).name = "Plaza";

            BuildStonePaths(center, worldScale);
            BuildFlowerPatches(center, worldScale);

            BuildWalls(center, worldScale);
            BuildCourtyardTrees(center, worldScale);
        }

        /// <summary>Cross of stone slabs from the plaza to each gate.</summary>
        static void BuildStonePaths(Vector3 center, float ws)
        {
            float half = 35f * ws;
            for (int i = 0; i < 4; i++)
            {
                Vector3 dir = i == 0 ? Vector3.forward : i == 1 ? -Vector3.forward :
                              i == 2 ? Vector3.right : -Vector3.right;
                Vector3 start = center + dir * 14f;
                Vector3 end = center + dir * (half - 3f);
                float len = Vector3.Distance(start, end);
                var slab = Part(PrimitiveType.Cube, null, (start + end) * 0.5f + Vector3.up * 0.015f,
                    new Vector3(i >= 2 ? 2.2f * ws : 2.6f * ws, 0.06f, i >= 2 ? 2.6f * ws : 2.2f * ws), Stone, false);
                slab.transform.rotation = Quaternion.identity;
                slab.name = "Path" + i;
            }
        }

        /// <summary>Deterministic flower/grass patches around the courtyard.</summary>
        static void BuildFlowerPatches(Vector3 center, float ws)
        {
            var flower = new Color(0.95f, 0.6f, 0.7f);
            var grass = new Color(0.45f, 0.65f, 0.35f);
            for (int i = 0; i < 14; i++)
            {
                string key = "flower_" + i;
                float angle = i / 14f * Mathf.PI * 2f + DeterministicHash.Unit(key) * 0.5f;
                float radius = (16f + DeterministicHash.Unit(key + "r") * 12f) * ws;
                Vector3 pos = center + new Vector3(Mathf.Cos(angle) * radius, 0f, Mathf.Sin(angle) * radius);
                bool flowers = DeterministicHash.Unit(key + "f") > 0.5f;
                Color c = flowers ? flower : grass;
                int n = 3 + DeterministicHash.Range(key + "n", 7);
                for (int j = 0; j < n; j++)
                {
                    Vector3 p = pos + new Vector3(DeterministicHash.Unit(key + j + "x") * 2f - 1f, 0f,
                        DeterministicHash.Unit(key + j + "z") * 2f - 1f) * ws;
                    PrimitiveUtils.Part(PrimitiveType.Sphere, null, p + Vector3.up * (0.14f * ws),
                        Vector3.one * (0.28f * ws), c, false).name = flowers ? "Flower" : "Grass";
                }
            }
        }

        static void BuildWalls(Vector3 center, float ws)
        {
            float half = 35f * ws;
            float height = 3.2f * ws;
            float thick = 0.35f * ws;
            float segLen = 4f * ws;
            float gate = 6f * ws;

            // South wall (z = center.z + half), gate centered on x.
            BuildWallSide(new Vector3(center.x - half, 0f, center.z + half), Vector3.right, half * 2f, center.x, gate, height, thick, segLen, ws);
            // North wall (z = center.z - half).
            BuildWallSide(new Vector3(center.x - half, 0f, center.z - half), Vector3.right, half * 2f, center.x, gate, height, thick, segLen, ws);
            // East wall (x = center.x + half), gate centered on z.
            BuildWallSide(new Vector3(center.x + half, 0f, center.z - half), Vector3.forward, half * 2f, center.z, gate, height, thick, segLen, ws);
            // West wall (x = center.x - half).
            BuildWallSide(new Vector3(center.x - half, 0f, center.z - half), Vector3.forward, half * 2f, center.z, gate, height, thick, segLen, ws);

            Vector3[] corners =
            {
                new Vector3(center.x - half, 0f, center.z - half),
                new Vector3(center.x + half, 0f, center.z - half),
                new Vector3(center.x + half, 0f, center.z + half),
                new Vector3(center.x - half, 0f, center.z + half),
            };
            for (int i = 0; i < corners.Length; i++)
            {
                BuildCornerPost(corners[i], height, thick, ws);
                BuildLanternPost(corners[i] + new Vector3(0f, 0f, 0f), ws);
            }
        }

        static void BuildWallSide(Vector3 start, Vector3 dir, float length, float gateCenter, float gate, float height, float thick, float segLen, float ws)
        {
            float gateStart = gateCenter - gate * 0.5f;
            float gateEnd = gateCenter + gate * 0.5f;
            int segs = Mathf.Max(1, Mathf.CeilToInt(length / segLen));
            Quaternion rot = dir == Vector3.right ? Quaternion.identity : Quaternion.Euler(0f, 90f, 0f);
            for (int i = 0; i < segs; i++)
            {
                float s0 = i * segLen;
                float s1 = Mathf.Min(length, (i + 1f) * segLen);
                if (s1 <= gateStart || s0 >= gateEnd) continue;
                float len = s1 - s0;
                Vector3 pos = start + dir * ((s0 + s1) * 0.5f);

                var wall = PrimitiveUtils.Part(PrimitiveType.Cube, null, pos + Vector3.up * (height * 0.5f),
                    new Vector3(len, height, thick), WallStone, true);
                wall.transform.rotation = rot;
                wall.name = "Wall";

                var cap = PrimitiveUtils.Part(PrimitiveType.Cube, null, pos + Vector3.up * (height + 0.16f),
                    new Vector3(len, 0.32f, thick + 0.24f), WallCap, false);
                cap.transform.rotation = rot;
                cap.name = "WallCap";

                if (i % 3 == 0)
                    BuildLanternPost(pos, ws);
            }
        }

        static void BuildCornerPost(Vector3 pos, float height, float thick, float ws)
        {
            PrimitiveUtils.Part(PrimitiveType.Cube, null, pos + Vector3.up * ((height + 0.5f) * 0.5f),
                new Vector3(thick * 2.4f, height + 0.5f, thick * 2.4f), WallStone, true);
        }

        static void BuildLanternPost(Vector3 pos, float ws)
        {
            PrimitiveUtils.Part(PrimitiveType.Cylinder, null, pos + Vector3.up * 2.0f * ws,
                new Vector3(0.07f, 2.0f, 0.07f), DarkWood, false);
            var lantern = PrimitiveUtils.Part(PrimitiveType.Sphere, null, pos + Vector3.up * 2.35f * ws,
                Vector3.one * 0.34f * ws, Lantern, false);
            lantern.name = "Lantern";
            AddGlow(lantern, 0.5f);
            PrimitiveUtils.Part(PrimitiveType.Cylinder, null, pos + Vector3.up * 2.62f * ws,
                new Vector3(0.16f, 0.12f, 0.16f), DarkWood, false);
        }

        /// <summary>
        /// Adds a "Glow" child that lights up at night, driven by LanternGlow.
        /// The glow is a flat, warm disc that reads as light spill.
        /// </summary>
        static void AddGlow(GameObject host, float radius)
        {
            var glow = PrimitiveUtils.Part(PrimitiveType.Cylinder, host.transform, new Vector3(0f, 0.02f, 0f),
                new Vector3(radius, 0.02f, radius), new Color(1f, 0.75f, 0.35f), false);
            glow.name = "Glow";
            glow.GetComponent<Renderer>().sharedMaterial =
                PrimitiveUtils.ColoredMaterial(new Color(1f, 0.78f, 0.35f, 0.9f));
            host.AddComponent<LanternGlow>();
        }

        /// <summary>
        /// Adds a "SelectionRing" ground disc under a marker root, initially
        /// hidden. WorldVisual toggles it when the player selects the target.
        /// </summary>
        public static GameObject BuildSelectionRing(GameObject root)
        {
            var ring = PrimitiveUtils.Part(PrimitiveType.Cylinder, root.transform, new Vector3(0f, 0.035f, 0f),
                new Vector3(1.5f, 0.02f, 1.5f), new Color(0.95f, 0.85f, 0.3f), false);
            ring.name = "SelectionRing";
            ring.SetActive(false);
            return ring;
        }

        static void BuildCourtyardTrees(Vector3 center, float ws)
        {
            const int count = 20;
            for (int i = 0; i < count; i++)
            {
                string key = "court_tree_" + i;
                float angle = i / (float)count * Mathf.PI * 2f + DeterministicHash.Unit(key) * 0.6f;
                float radius = (24f + DeterministicHash.Unit(key + "r") * 20f) * ws;
                if (radius < 16.5f * ws) continue;
                Vector3 pos = center + new Vector3(Mathf.Cos(angle) * radius, 0f, Mathf.Sin(angle) * radius);
                BuildTree(null, pos, ws, DeterministicHash.Range(key + "s", 0.9f, 1.4f));
            }
        }

        public static void BuildTree(Transform parent, Vector3 pos, float ws, float scale)
        {
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + Vector3.up * (1.1f * scale),
                new Vector3(0.16f * scale, 1.1f, 0.16f * scale), Wood, true).name = "Trunk";
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + Vector3.up * (2.6f * scale),
                Vector3.one * (1.3f * scale), Leaf, false);
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + new Vector3(0.5f * scale, 2.1f * scale, 0.3f * scale),
                Vector3.one * (0.8f * scale), Leaf, false);
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + new Vector3(-0.45f * scale, 2.0f * scale, -0.35f * scale),
                Vector3.one * (0.7f * scale), Leaf, false);
        }

        // ------------------------------------------------------------------
        // Location decor
        // ------------------------------------------------------------------

        public static void BuildLocationDecor(GameObject root, string locationId, string name, string type, Vector3 pos)
        {
            root.transform.position = pos;
            BuildSelectionRing(root);
            switch (type)
            {
                case "residence":  BuildHouse(root.transform, pos, 1.0f, RoofDark); break;
                case "commercial": BuildMarketCluster(root.transform, pos); break;
                case "social":     BuildTavernCluster(root.transform, pos); break;
                case "workplace":  BuildWorkyard(root.transform, pos); break;
                case "natural":    BuildGrove(root.transform, pos); break;
                default:           BuildHouse(root.transform, pos, 0.8f, RoofDark); break;
            }
        }

        static void BuildHouse(Transform parent, Vector3 pos, float s, Color roof)
        {
            Vector3 o = new Vector3(3.5f * s, 0f, 0f); // offset keeps the marker center open for NPCs
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, o + new Vector3(0f, 0.1f * s, 0f),
                new Vector3(4.4f * s, 0.2f * s, 4.4f * s), Stone, true).name = "Platform";
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, o + new Vector3(0f, 1.6f * s, 0f),
                new Vector3(4.2f * s, 3.0f * s, 4.2f * s), WallStone, true).name = "Walls";

            float w = 2.1f * s, d = 2.1f * s;
            Vector3[] posts =
            {
                o + new Vector3(-w, 0f, -d),
                o + new Vector3(w, 0f, -d),
                o + new Vector3(-w, 0f, d),
                o + new Vector3(w, 0f, d),
            };
            foreach (var p in posts)
                PrimitiveUtils.Part(PrimitiveType.Cube, parent, p + new Vector3(0f, 1.8f * s, 0f),
                    new Vector3(0.18f * s, 3.6f * s, 0.18f * s), DarkWood, false).name = "Post";

            PrimitiveUtils.Part(PrimitiveType.Cube, parent, o + new Vector3(2.15f * s, 1.0f * s, 0f),
                new Vector3(0.12f * s, 1.8f * s, 1.3f * s), DarkWood, false).name = "Door";

            PrimitiveUtils.Part(PrimitiveType.Cube, parent, o + new Vector3(1.5f * s, 1.7f * s, 1.5f * s),
                new Vector3(0.7f * s, 0.7f * s, 0.7f * s), Lantern, false).name = "Window";
            AddGlow(Part(PrimitiveType.Cube, parent, o + new Vector3(1.5f * s, 1.7f * s, 1.5f * s),
                new Vector3(0.72f * s, 0.72f * s, 0.72f * s), new Color(1f, 0.8f, 0.45f), false), 0.8f);
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, o + new Vector3(-1.5f * s, 1.7f * s, 1.5f * s),
                new Vector3(0.7f * s, 0.7f * s, 0.7f * s), Lantern, false).name = "Window";
            AddGlow(Part(PrimitiveType.Cube, parent, o + new Vector3(-1.5f * s, 1.7f * s, 1.5f * s),
                new Vector3(0.72f * s, 0.72f * s, 0.72f * s), new Color(1f, 0.8f, 0.45f), false), 0.8f);

            // Two-tier pagoda roof: large cone + finial cone on top.
            PrimitiveUtils.Cone(parent, o + new Vector3(0f, 3.4f * s, 0f), 3.3f * s, 2.2f * s, roof, false).name = "Roof";
            PrimitiveUtils.Cone(parent, o + new Vector3(0f, 4.3f * s, 0f), 1.9f * s, 1.5f * s, roof, false).name = "RoofUpper";
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, o + new Vector3(0f, 4.9f * s, 0f),
                Vector3.one * (0.3f * s), DarkWood, false).name = "RoofFinial";
            BuildLanternPost(pos + o + new Vector3(2.2f * s, 0f, 2.0f * s), s);
        }

        static void BuildMarketCluster(Transform parent, Vector3 pos)
        {
            BuildStall(parent, new Vector3(-3.0f, 0f, 1.2f), 1.0f, true);
            BuildStall(parent, new Vector3(3.0f, 0f, -1.0f), 0.9f, true);
            BuildCounter(parent, new Vector3(-3.6f, 0f, -1.6f), 1.0f, true);
            BuildGoods(parent, new Vector3(2.6f, 0f, -0.6f), 1f);
            BuildGoods(parent, new Vector3(-2.6f, 0f, 1.8f), 0.8f);
            BuildBanner(parent, new Vector3(0f, 0f, 0.5f), 1f);
            BuildLanternPost(pos + new Vector3(0f, 0f, 2.6f), 1f);
        }

        static void BuildBanner(Transform parent, Vector3 pos, float s)
        {
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 2.4f * s, 0f),
                new Vector3(0.06f, 2.4f, 0.06f), DarkWood, false).name = "BannerPole";
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0.3f * s, 2.5f * s, 0f),
                new Vector3(0.9f * s, 0.7f * s, 0.06f), Canopy, false).name = "Banner";
        }

        static void BuildGoods(Transform parent, Vector3 pos, float s)
        {
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.4f * s, 0f),
                new Vector3(0.5f * s, 0.6f * s, 0.5f * s), new Color(0.85f, 0.6f, 0.35f), false).name = "Goods";
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0.5f * s, 0.35f * s, 0.2f * s),
                new Vector3(0.4f * s, 0.5f * s, 0.4f * s), new Color(0.7f, 0.5f, 0.2f), false).name = "Goods";
        }

        static void BuildTavernCluster(Transform parent, Vector3 pos)
        {
            BuildHouse(parent, pos, 1.2f, RoofDark);
            BuildBench(parent, new Vector3(-3.2f, 0f, 1.5f), 1.0f, true);
            BuildBench(parent, new Vector3(-3.2f, 0f, -1.5f), 1.0f, true);
            BuildFire(parent, new Vector3(-3.0f, 0f, 0f), 1.0f, true);
            BuildBarrel(parent, new Vector3(3.6f, 0f, 1.2f), 1f);
            BuildBarrel(parent, new Vector3(3.6f, 0f, 0.4f), 0.85f);
            BuildBanner(parent, new Vector3(2.6f, 0f, 0f), 1.1f);
            BuildLanternPost(pos + new Vector3(3.4f, 0f, -2.4f), 1f);
            BuildLanternPost(pos + new Vector3(-1.6f, 0f, 2.4f), 1f);
        }

        static void BuildBarrel(Transform parent, Vector3 pos, float s)
        {
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 0.5f * s, 0f),
                new Vector3(0.45f * s, 1.0f, 0.45f * s), Wood, false).name = "Barrel";
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 0.05f * s, 0f),
                new Vector3(0.48f * s, 0.1f, 0.48f * s), DarkWood, false).name = "BarrelRim";
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 0.95f * s, 0f),
                new Vector3(0.48f * s, 0.1f, 0.48f * s), DarkWood, false).name = "BarrelRim";
        }

        static void BuildWorkyard(Transform parent, Vector3 pos)
        {
            BuildHouse(parent, pos, 1.1f, RoofGreen);
            BuildWell(parent, new Vector3(-3.8f, 0f, 0.6f), 1.0f, true);
            BuildCrate(parent, new Vector3(-2.6f, 0f, -2.8f), 1.0f, true);
            BuildPlant(parent, new Vector3(-3.8f, 0f, -1.8f), 1.0f, false);
            BuildFence(parent, new Vector3(0f, 0f, 3.2f), 1f, 6f, true);
            BuildHay(parent, new Vector3(3.4f, 0f, 2.6f), 1f);
            BuildHay(parent, new Vector3(3.9f, 0f, 2.2f), 0.8f);
        }

        static void BuildFence(Transform parent, Vector3 pos, float s, float width, bool horizontal)
        {
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.5f * s, 0f),
                new Vector3(horizontal ? width * s : 0.08f * s, 1.0f * s, horizontal ? 0.08f * s : width * s),
                Wood, false).name = "Fence";
            Vector3[] posts =
            {
                pos + new Vector3(horizontal ? -width * 0.5f * s : 0f, 0f, horizontal ? 0f : -width * 0.5f * s),
                pos + new Vector3(horizontal ? width * 0.5f * s : 0f, 0f, horizontal ? 0f : width * 0.5f * s),
            };
            foreach (var p in posts)
                PrimitiveUtils.Part(PrimitiveType.Cube, parent, p + new Vector3(0f, 0.6f * s, 0f),
                    new Vector3(0.1f, 1.2f * s, 0.1f), DarkWood, false).name = "FencePost";
        }

        static void BuildHay(Transform parent, Vector3 pos, float s)
        {
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + new Vector3(0f, 0.4f * s, 0f),
                new Vector3(1.0f * s, 0.8f * s, 0.8f * s), new Color(0.8f, 0.7f, 0.4f), false).name = "Hay";
        }

        static void BuildGrove(Transform parent, Vector3 pos)
        {
            BuildTree(parent, new Vector3(2.5f, 0f, 1.5f), 1f, 1.3f);
            BuildTree(parent, new Vector3(-2.5f, 0f, -1.0f), 1f, 1.1f);
            BuildTree(parent, new Vector3(0.5f, 0f, -2.6f), 1f, 0.95f);
            BuildLog(parent, new Vector3(-2.8f, 0f, 1.8f), 1.0f, true);
            BuildBush(parent, new Vector3(2.0f, 0f, -1.8f), 1f);
            BuildBush(parent, new Vector3(-1.4f, 0f, 2.4f), 0.8f);
            BuildRock(parent, new Vector3(3.2f, 0f, -0.4f), 1f);
            BuildRock(parent, new Vector3(-0.8f, 0f, -1.2f), 0.7f);
        }

        static void BuildBush(Transform parent, Vector3 pos, float s)
        {
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + new Vector3(0f, 0.4f * s, 0f),
                new Vector3(1.2f * s, 0.9f * s, 0.9f * s), Leaf, false).name = "Bush";
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + new Vector3(0.4f * s, 0.3f * s, 0.3f * s),
                Vector3.one * (0.6f * s), Leaf, false).name = "Bush";
        }

        static void BuildRock(Transform parent, Vector3 pos, float s)
        {
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + new Vector3(0f, 0.3f * s, 0f),
                new Vector3(0.9f * s, 0.6f * s, 0.7f * s), Stone, false).name = "Rock";
        }

        // ------------------------------------------------------------------
        // Object props
        // ------------------------------------------------------------------

        public static void BuildObjectProp(GameObject root, string objectId, string objectType, Vector3 locationPos)
        {
            Vector3 offset = DeterministicOffset(objectId, 2.6f);
            root.transform.position = locationPos + offset;
            BuildSelectionRing(root);
            switch (objectType)
            {
                case "stall":  BuildStall(root.transform, Vector3.zero, 0.9f, true); break;
                case "counter": BuildCounter(root.transform, Vector3.zero, 1.0f, true); break;
                case "table":  BuildTable(root.transform, Vector3.zero, 1.0f, true); break;
                case "bench":  BuildBench(root.transform, Vector3.zero, 1.0f, true); break;
                case "fire":   BuildFire(root.transform, Vector3.zero, 1.0f, true); break;
                case "bed":    BuildBed(root.transform, Vector3.zero, 1.0f, true); break;
                case "chair":  BuildChair(root.transform, Vector3.zero, 1.0f, true); break;
                case "well":   BuildWell(root.transform, Vector3.zero, 1.0f, true); break;
                case "crate":  BuildCrate(root.transform, Vector3.zero, 1.0f, true); break;
                case "plant":  BuildPlant(root.transform, Vector3.zero, 1.0f, false); break;
                case "tree":   BuildTree(root.transform, Vector3.zero, 1f, 1.2f); break;
                case "log":    BuildLog(root.transform, Vector3.zero, 1.0f, true); break;
                default:       PrimitiveUtils.Part(PrimitiveType.Cube, root.transform, new Vector3(0f, 0.35f, 0f),
                    new Vector3(0.6f, 0.7f, 0.6f), Wood, true); break;
            }
        }

        public static Vector3 DeterministicOffset(string id, float radius)
        {
            float angle = DeterministicHash.Unit(id) * Mathf.PI * 2f;
            float r = (0.6f + DeterministicHash.Unit(id + "d") * 0.4f) * radius;
            return new Vector3(Mathf.Cos(angle) * r, 0f, Mathf.Sin(angle) * r);
        }

        static void BuildStall(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            Vector3 basePos = pos;
            float w = 2.4f * s;
            float d = 1.8f * s;
            float h = 1.5f * s;
            Vector3[] corners =
            {
                basePos + new Vector3(-w * 0.5f, 0f, -d * 0.5f),
                basePos + new Vector3(w * 0.5f, 0f, -d * 0.5f),
                basePos + new Vector3(-w * 0.5f, 0f, d * 0.5f),
                basePos + new Vector3(w * 0.5f, 0f, d * 0.5f),
            };
            foreach (var c in corners)
                PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, c + Vector3.up * (h * 0.5f),
                    new Vector3(0.08f, h, 0.08f), DarkWood, false);
            PrimitiveUtils.Cone(parent, basePos + Vector3.up * h, w * 0.72f, 1.2f * s, Canopy, false).name = "Canopy";
            BuildCounter(parent, basePos + new Vector3(0f, 0f, d * 0.5f - 0.2f), 0.8f * s, keepCollider);
        }

        static void BuildCounter(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.6f * s, 0f),
                new Vector3(1.8f * s, 1.1f * s, 0.8f * s), Wood, keepCollider).name = "Counter";
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 1.16f * s, 0f),
                new Vector3(1.9f * s, 0.08f * s, 0.9f * s), DarkWood, false).name = "CounterTop";
        }

        static void BuildTable(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.65f * s, 0f),
                new Vector3(1.8f * s, 0.1f * s, 1.0f * s), Wood, keepCollider).name = "TableTop";
            Vector3[] legs =
            {
                new Vector3(-0.8f * s, 0f, -0.4f * s),
                new Vector3(0.8f * s, 0f, -0.4f * s),
                new Vector3(-0.8f * s, 0f, 0.4f * s),
                new Vector3(0.8f * s, 0f, 0.4f * s),
            };
            foreach (var l in legs)
                PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + l + new Vector3(0f, 0.3f * s, 0f),
                    new Vector3(0.12f * s, 0.6f * s, 0.12f * s), DarkWood, false);
        }

        static void BuildBench(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.45f * s, 0f),
                new Vector3(1.7f * s, 0.1f * s, 0.5f * s), Wood, keepCollider).name = "Seat";
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(-0.6f * s, 0.15f * s, 0f),
                new Vector3(0.14f * s, 0.3f * s, 0.5f * s), DarkWood, false);
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0.6f * s, 0.15f * s, 0f),
                new Vector3(0.14f * s, 0.3f * s, 0.5f * s), DarkWood, false);
        }

        static void BuildFire(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 0.12f * s, 0f),
                new Vector3(1.0f * s, 0.22f * s, 1.0f * s), Stone, keepCollider).name = "FireRing";
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + new Vector3(0f, 0.5f * s, 0f),
                Vector3.one * (0.8f * s), Fire, false).name = "Ember";
            var ember = PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + new Vector3(0f, 0.5f * s, 0f),
                Vector3.one * (0.5f * s), Fire, false);
            ember.name = "EmberCore";
            AddGlow(ember, 0.9f);
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0.3f * s, 0.2f * s, 0.1f * s),
                new Vector3(0.7f * s, 0.12f * s, 0.5f * s), DarkWood, false);
        }

        static void BuildBed(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.25f * s, 0f),
                new Vector3(2.0f * s, 0.35f * s, 1.1f * s), Wood, keepCollider).name = "BedBase";
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.75f * s, -0.45f * s),
                new Vector3(2.0f * s, 0.75f * s, 0.1f * s), DarkWood, false).name = "Headboard";
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.62f * s, 0f),
                new Vector3(1.8f * s, 0.3f * s, 1.0f * s), new Color(0.85f, 0.82f, 0.74f), false).name = "Blanket";
        }

        static void BuildChair(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.45f * s, 0f),
                new Vector3(0.5f * s, 0.08f * s, 0.5f * s), Wood, keepCollider).name = "ChairSeat";
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.85f * s, -0.2f * s),
                new Vector3(0.5f * s, 0.8f * s, 0.08f * s), DarkWood, false).name = "ChairBack";
            Vector3[] legs =
            {
                new Vector3(-0.2f * s, 0f, -0.2f * s),
                new Vector3(0.2f * s, 0f, -0.2f * s),
                new Vector3(-0.2f * s, 0f, 0.2f * s),
                new Vector3(0.2f * s, 0f, 0.2f * s),
            };
            foreach (var l in legs)
                PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + l + new Vector3(0f, 0.22f * s, 0f),
                    new Vector3(0.1f * s, 0.45f * s, 0.1f * s), DarkWood, false);
        }

        static void BuildWell(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 0.4f * s, 0f),
                new Vector3(0.7f * s, 0.7f * s, 0.7f * s), Stone, keepCollider).name = "WellBrick";
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 0.78f * s, 0f),
                new Vector3(0.75f * s, 0.08f * s, 0.75f * s), WallStone, false).name = "WellLip";
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 1.3f * s, 0f),
                new Vector3(0.1f * s, 0.7f * s, 0.1f * s), DarkWood, false).name = "WellPost";
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0.5f * s, 1.45f * s, 0f),
                new Vector3(0.08f * s, 0.5f * s, 0.08f * s), DarkWood, false).name = "WellPost2";
            PrimitiveUtils.Cone(parent, pos + new Vector3(0f, 1.65f * s, 0f), 0.9f * s, 0.7f * s, RoofDark, false).name = "WellRoof";
        }

        static void BuildCrate(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.35f * s, 0f),
                new Vector3(0.8f * s, 0.7f * s, 0.8f * s), Wood, keepCollider).name = "Crate";
            PrimitiveUtils.Part(PrimitiveType.Cube, parent, pos + new Vector3(0f, 0.71f * s, 0f),
                new Vector3(0.86f * s, 0.06f * s, 0.86f * s), DarkWood, false).name = "CrateLid";
        }

        static void BuildPlant(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 0.2f * s, 0f),
                new Vector3(0.4f * s, 0.3f * s, 0.4f * s), new Color(0.65f, 0.5f, 0.3f), keepCollider).name = "Pot";
            PrimitiveUtils.Part(PrimitiveType.Sphere, parent, pos + new Vector3(0f, 0.65f * s, 0f),
                Vector3.one * (0.7f * s), Leaf, false).name = "Plant";
        }

        static void BuildLog(Transform parent, Vector3 pos, float s, bool keepCollider)
        {
            PrimitiveUtils.Part(PrimitiveType.Cylinder, parent, pos + new Vector3(0f, 0.18f * s, 0f),
                new Vector3(0.3f * s, 0.36f * s, 1.4f * s), Wood, keepCollider).name = "Log";
        }

        static GameObject Part(PrimitiveType type, Transform parent, Vector3 localPos, Vector3 localScale, Color color, bool keepCollider)
        {
            return PrimitiveUtils.Part(type, parent, localPos, localScale, color, keepCollider);
        }
    }
}