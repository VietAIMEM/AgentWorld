using System.Collections.Generic;
using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Fades a lantern / ember / lit window glow on and off with the night
    /// state. Self-registers in a static registry so DayNightCycle can drive
    /// every glow without per-frame scene scans. Purely presentational.
    /// </summary>
    public class LanternGlow : MonoBehaviour
    {
        static readonly Color DayColor = new Color(0.92f, 0.55f, 0.20f);
        static readonly Color NightColor = new Color(1f, 0.72f, 0.30f);

        static readonly List<LanternGlow> AllGlows = new List<LanternGlow>();

        Renderer _renderer;
        Renderer _glow;
        Material _material;
        bool _night;

        public static IList<LanternGlow> All
        {
            get { return AllGlows; }
        }

        void OnEnable()
        {
            AllGlows.Add(this);
        }

        void OnDisable()
        {
            AllGlows.Remove(this);
        }

        void Start()
        {
            _renderer = GetComponent<Renderer>();
            if (_renderer != null)
                _material = _renderer.material;
            var glow = transform.Find("Glow");
            if (glow != null)
                _glow = glow.GetComponent<Renderer>();
            if (_glow != null)
                _glow.enabled = false;
        }

        /// <summary>Idempotent — safe to call every frame. Never touches simulation state.</summary>
        public void SetNight(bool night)
        {
            if (_night == night) return;
            _night = night;
            if (_glow != null)
                _glow.enabled = night;
            if (_material != null)
                _material.color = night ? NightColor : DayColor;
        }
    }
}