using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Deterministic placeholder styling per pose (no RNG, no external animations).
    /// Used by the fallback visual when no humanoid prefab / Animator Controller
    /// is available. The style is a pure function of the pose name.
    /// </summary>
    public struct PoseStyle
    {
        public Color tint;
        public float heightScale;
        public bool layDown;

        public PoseStyle(Color tint, float heightScale = 1f, bool layDown = false)
        {
            this.tint = tint;
            this.heightScale = heightScale;
            this.layDown = layDown;
        }
    }

    /// <summary>
    /// Deterministic pose → Animator-state bridge. Maps every pose from the
    /// authoritative Python AnimationState contract to a humanoid Animator state
    /// name. Unknown poses fall back to "Idle". Never throws.
    /// </summary>
    public static class PoseMapper
    {
        public static PoseStyle Map(string pose)
        {
            switch (pose)
            {
                case "idle":     return new PoseStyle(new Color(0.50f, 0.80f, 1.00f));
                case "walk":     return new PoseStyle(new Color(0.40f, 0.90f, 0.50f));
                case "work":     return new PoseStyle(new Color(1.00f, 0.80f, 0.30f));
                case "eat":      return new PoseStyle(new Color(1.00f, 0.60f, 0.40f), 0.9f);
                case "buy":      return new PoseStyle(new Color(1.00f, 0.90f, 0.50f), 0.9f);
                case "sleep":    return new PoseStyle(new Color(0.35f, 0.35f, 0.90f), 0.7f, true);
                case "sit":      return new PoseStyle(new Color(0.60f, 0.60f, 1.00f), 0.6f);
                case "stand":    return new PoseStyle(new Color(0.70f, 0.70f, 0.70f));
                case "talk":     return new PoseStyle(new Color(0.30f, 1.00f, 0.90f));
                case "listen":   return new PoseStyle(new Color(0.30f, 0.90f, 1.00f));
                case "wave":     return new PoseStyle(new Color(1.00f, 0.90f, 0.20f));
                case "inspect":  return new PoseStyle(new Color(0.80f, 0.80f, 1.00f), 0.9f);
                case "stretch":  return new PoseStyle(new Color(0.90f, 0.70f, 1.00f), 1.15f);
                case "interact": return new PoseStyle(new Color(1.00f, 0.50f, 0.50f));
                case "dead":     return new PoseStyle(new Color(0.40f, 0.40f, 0.40f), 0.3f, true);
                default:         return new PoseStyle(new Color(0.50f, 0.80f, 1.00f)); // idle fallback
            }
        }

        /// <summary>
        /// Maps a pose to the Animator state name used by a humanoid controller.
        /// Deterministic; unknown poses → "Idle".
        /// </summary>
        public static string MapAnimatorState(string pose)
        {
            switch (pose)
            {
                case "idle":     return "Idle";
                case "walk":     return "Walk";
                case "work":     return "Work";
                case "eat":      return "Eat";
                case "buy":      return "Buy";
                case "sleep":    return "Sleep";
                case "sit":      return "Sit";
                case "stand":    return "Stand";
                case "talk":     return "Talk";
                case "listen":   return "Listen";
                case "wave":     return "Wave";
                case "inspect":  return "Inspect";
                case "stretch":  return "Stretch";
                case "interact": return "Interact";
                case "dead":     return "Dead";
                default:         return "Idle";
            }
        }

        public static bool IsKnownPose(string pose)
        {
            switch (pose)
            {
                case "idle":
                case "walk":
                case "work":
                case "eat":
                case "buy":
                case "sleep":
                case "sit":
                case "stand":
                case "talk":
                case "listen":
                case "wave":
                case "inspect":
                case "stretch":
                case "interact":
                case "dead":
                    return true;
                default:
                    return false;
            }
        }
    }
}