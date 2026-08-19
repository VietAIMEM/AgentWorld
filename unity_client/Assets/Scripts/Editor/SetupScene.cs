using UnityEditor;
using UnityEngine;

namespace NpcAi.Client.EditorTools
{
    /// <summary>
    /// One-click scene setup: ground, camera, directional light, the
    /// visualization root (TransportClient + WorldVisual + SimulationControls),
    /// the player character, and the interactive UI overlays.
    /// </summary>
    public static class SetupScene
    {
        [MenuItem("NPC AI/Create Visualization Scene")]
        public static void CreateScene()
        {
            if (Object.FindObjectOfType<WorldVisual>() == null)
            {
                var root = new GameObject("NPC_AI_World");
                root.AddComponent<TransportClient>();
                root.AddComponent<WorldVisual>();
                root.AddComponent<SimulationControls>();
            }

            if (Object.FindObjectOfType<Camera>() == null)
            {
                var camGo = new GameObject("Main Camera");
                camGo.tag = "MainCamera";
                var cam = camGo.AddComponent<Camera>();
                camGo.AddComponent<AudioListener>();
                cam.transform.position = new Vector3(50f, 45f, 50f);
                cam.transform.rotation = Quaternion.Euler(50f, -45f, 0f);
            }

            if (Object.FindObjectOfType<PlayerController>() == null)
            {
                var playerGo = new GameObject("Player");
                playerGo.transform.position = new Vector3(50f, 1f, 55f);
                playerGo.AddComponent<PlayerController>();
                playerGo.AddComponent<InteractionSystem>();
            }

            if (Object.FindObjectOfType<Light>() == null)
            {
                var lightGo = new GameObject("Directional Light");
                var light = lightGo.AddComponent<Light>();
                light.type = LightType.Directional;
                light.intensity = 1.15f;
                light.shadows = LightShadows.Soft;
                light.color = new Color(1f, 0.96f, 0.9f);
                lightGo.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            }

            if (Object.FindObjectOfType<DayNightCycle>() == null)
            {
                var dncGo = new GameObject("DayNightCycle");
                dncGo.AddComponent<DayNightCycle>();
            }

            RenderSettings.ambientLight = new Color(0.45f, 0.5f, 0.55f);
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Flat;
            if (Object.FindObjectOfType<Camera>() != null)
                Object.FindObjectOfType<Camera>().clearFlags = CameraClearFlags.SolidColor;

            if (Object.FindObjectOfType<ConversationUI>() == null)
            {
                var uiGo = new GameObject("UI");
                uiGo.AddComponent<ConversationUI>();
                uiGo.AddComponent<TimeUI>();
            }

            Selection.activeGameObject = GameObject.Find("NPC_AI_World");
            Debug.Log("NPC AI interactive scene ready. Start the Python server with: "
                + "python -m world_sim.presentation.transport");
        }
    }
}