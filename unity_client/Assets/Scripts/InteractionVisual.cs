using System.Text;

namespace NpcAi.Client
{
    /// <summary>
    /// Pure string helpers for the interaction UI. No UnityEngine dependency
    /// so the interaction copy is unit-testable in EditMode. Deterministic:
    /// the same inputs always produce the same strings.
    /// </summary>
    public static class InteractionVisual
    {
        /// <summary>"First name" portion of a full NPC name.</summary>
        public static string FirstName(string fullName)
        {
            if (string.IsNullOrEmpty(fullName)) return "Someone";
            int i = fullName.IndexOf(' ');
            return i > 0 ? fullName.Substring(0, i) : fullName;
        }

        /// <summary>Human-readable label for a capitalized id-style string.</summary>
        public static string Capitalize(string s)
        {
            if (string.IsNullOrEmpty(s)) return s ?? "";
            var sb = new StringBuilder();
            bool cap = true;
            foreach (char c in s)
            {
                if (c == '_')
                {
                    cap = true;
                    continue;
                }
                sb.Append(cap ? char.ToUpperInvariant(c) : c);
                cap = false;
            }
            return sb.ToString();
        }

        public static string NpcPrompt(string npcName, string job)
        {
            string who = FirstName(npcName);
            if (!string.IsNullOrEmpty(job))
                return who + " — " + Capitalize(job);
            return who;
        }

        public static string ObjectPrompt(string objectName, string objectType)
        {
            return objectName + " (" + Capitalize(objectType) + ")";
        }

        public static string LocationPrompt(string locationName, string locationType)
        {
            return locationName + " — " + Capitalize(locationType);
        }

        /// <summary>What pressing E does for a selected target.</summary>
        public static string NpcActionHint(bool alive)
        {
            return alive ? "E — Talk" : "";
        }

        public static string ObjectActionHint(string objectType)
        {
            switch (objectType)
            {
                case "bench": return "E — Sit";
                case "well": return "E — Use";
                case "stall": return "E — Inspect";
                case "plant": return "E — Tend";
                case "crate": return "E — Inspect";
                default: return "E — Interact";
            }
        }
    }
}