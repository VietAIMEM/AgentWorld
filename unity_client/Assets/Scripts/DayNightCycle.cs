using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Pure, deterministic day/night math derived only from the authoritative
    /// snapshot's (day, hour, minute). No simulation/AI, no randomness, no
    /// mutation — the same inputs always produce the same SunState.
    /// </summary>
    public static class DayNightMath
    {
        public const float LanternThreshold = 0.12f;

        /// <summary>
        /// Day factor 0..1: 1 at noon, 0 at midnight. The solar cycle peaks at
        /// 12:00 and bottoms at 00:00.
        /// </summary>
        public static float DayFactor(int hour, int minute)
        {
            float hod = hour + minute / 60f;
            float cycle = ((hod - 6f) / 12f) * Mathf.PI;
            return 0.5f + 0.5f * Mathf.Sin(cycle);
        }

        /// <summary>Elevation of the sun in degrees from the horizon (-90..90).</summary>
        public static float SunElevation(int hour, int minute)
        {
            float hod = hour + minute / 60f;
            float cycle = ((hod - 6f) / 24f) * Mathf.PI * 2f;
            return Mathf.Sin(cycle) * 90f;
        }

        public static SunState ComputeSunState(int day, int hour, int minute)
        {
            float dayFactor = Mathf.Clamp01(DayFactor(hour, minute));
            bool isNight = dayFactor < LanternThreshold;

            var s = new SunState();
            s.day = day;
            s.hour = hour;
            s.minute = minute;
            s.dayFactor = dayFactor;
            s.isNight = isNight;
            s.lanternsOn = isNight;
            s.sunElevation = SunElevation(hour, minute);
            s.sunPitch = Mathf.Clamp(90f - s.sunElevation, -30f, 180f);
            s.lightIntensity = Mathf.Clamp(dayFactor * 1.2f + 0.02f, 0.02f, 1.2f);
            s.ambientColor = Color.Lerp(
                new Color(0.18f, 0.22f, 0.36f),
                new Color(0.68f, 0.72f, 0.78f),
                dayFactor);
            s.skyColor = Color.Lerp(
                new Color(0.05f, 0.06f, 0.13f),
                new Color(0.44f, 0.66f, 0.92f),
                dayFactor);
            s.fogColor = Color.Lerp(
                new Color(0.06f, 0.07f, 0.15f),
                new Color(0.82f, 0.84f, 0.80f),
                dayFactor);
            s.fogDensity = Mathf.Lerp(0.014f, 0.0012f, dayFactor);
            s.sunColor = Color.Lerp(
                new Color(1f, 0.60f, 0.30f),
                new Color(1f, 0.98f, 0.90f),
                Mathf.Clamp01(dayFactor * 2f));
            return s;
        }
    }

    /// <summary>Deterministic lighting snapshot for a moment in the day.</summary>
    public struct SunState
    {
        public int day;
        public int hour;
        public int minute;
        public float dayFactor;
        public bool isNight;
        public bool lanternsOn;
        public float sunElevation;
        public float sunPitch;
        public float lightIntensity;
        public Color ambientColor;
        public Color skyColor;
        public Color fogColor;
        public float fogDensity;
        public Color sunColor;

        public static bool Equivalent(SunState a, SunState b)
        {
            return a.day == b.day
                && a.hour == b.hour
                && a.minute == b.minute
                && Mathf.Approximately(a.dayFactor, b.dayFactor)
                && a.isNight == b.isNight
                && a.lanternsOn == b.lanternsOn
                && Mathf.Approximately(a.sunElevation, b.sunElevation)
                && Mathf.Approximately(a.sunPitch, b.sunPitch)
                && Mathf.Approximately(a.lightIntensity, b.lightIntensity)
                && a.ambientColor == b.ambientColor
                && a.skyColor == b.skyColor
                && a.fogColor == b.fogColor
                && Mathf.Approximately(a.fogDensity, b.fogDensity)
                && a.sunColor == b.sunColor;
        }
    }

    /// <summary>
    /// Applies the authoritative day/hour/minute to the scene: sun light,
    /// ambient, sky, fog and every LanternGlow. Presentation only.
    /// </summary>
    public class DayNightCycle : MonoBehaviour
    {
        public TransportClient transport;
        public Light sun;
        public bool enableFog = true;

        Camera _camera;

        void Start()
        {
            if (transport == null)
                transport = FindObjectOfType<TransportClient>();
            if (sun == null)
            {
                var lights = FindObjectsOfType<Light>();
                foreach (var l in lights)
                    if (l.type == LightType.Directional) { sun = l; break; }
            }
            _camera = Camera.main;
        }

        void Update()
        {
            if (transport == null || transport.Latest == null) return;
            var p = transport.Latest;
            Apply(DayNightMath.ComputeSunState(p.day, p.hour, p.minute));
        }

        public void Apply(SunState s)
        {
            if (sun != null)
            {
                sun.transform.rotation = Quaternion.Euler(s.sunPitch, -40f, 0f);
                sun.intensity = s.lightIntensity;
                sun.color = s.sunColor;
            }
            RenderSettings.ambientLight = s.ambientColor;
            if (enableFog)
            {
                RenderSettings.fog = true;
                RenderSettings.fogMode = FogMode.ExponentialSquared;
                RenderSettings.fogColor = s.fogColor;
                RenderSettings.fogDensity = s.fogDensity;
            }
            if (_camera != null)
                _camera.backgroundColor = s.skyColor;
            for (int i = 0; i < LanternGlow.All.Count; i++)
                LanternGlow.All[i].SetNight(s.lanternsOn);
        }
    }
}