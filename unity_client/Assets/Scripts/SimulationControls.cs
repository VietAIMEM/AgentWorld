using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Minimal IMGUI control + debug panel. Buttons only affect simulation
    /// through the TransportClient /control API boundary; nothing here touches
    /// simulation state directly.
    /// </summary>
    public class SimulationControls : MonoBehaviour
    {
        public TransportClient transport;
        public WorldVisual worldVisual;
        public Camera cam;

        private NpcVisual _selected;

        void Start()
        {
            if (transport == null) transport = FindObjectOfType<TransportClient>();
            if (worldVisual == null) worldVisual = FindObjectOfType<WorldVisual>();
            if (cam == null) cam = Camera.main;
        }

        void Update()
        {
            if (cam == null || worldVisual == null || !Input.GetMouseButtonDown(0)) return;
            _selected = worldVisual.NpcAtScreenPoint(Input.mousePosition, cam);
        }

        void OnGUI()
        {
            GUI.Box(new Rect(10, 10, 150, 190), "Simulation");
            if (GUI.Button(new Rect(20, 35, 130, 28), "Connect"))
                transport.Connect();
            if (GUI.Button(new Rect(20, 68, 130, 28), "Play"))
                transport.Play();
            if (GUI.Button(new Rect(20, 101, 130, 28), "Pause"))
                transport.Pause();
            if (GUI.Button(new Rect(20, 134, 130, 28), "Step"))
                transport.Step();
            if (GUI.Button(new Rect(20, 167, 130, 28), "Reset"))
                transport.Reset();

            GUI.Box(new Rect(10, 210, 150, 70), "Status");
            GUI.Label(new Rect(20, 235, 130, 20), "Connected: " + (transport != null && transport.IsConnected ? "yes" : "no"));
            if (transport != null && transport.Latest != null)
                GUI.Label(new Rect(20, 255, 130, 20), "Tick: " + transport.Latest.tick);

            DrawDebugPanel();
        }

        void DrawDebugPanel()
        {
            var state = _selected != null ? _selected.State : null;
            if (state == null)
            {
                GUI.Box(new Rect(Screen.width - 260, 10, 250, 60), "Selected NPC");
                GUI.Label(new Rect(Screen.width - 250, 35, 240, 20), "Click an NPC to inspect");
                return;
            }
            GUI.Box(new Rect(Screen.width - 260, 10, 250, 200), "NPC: " + _selected.NpcId + " (" + _selected.NpcName + ")");
            GUILayout.BeginArea(new Rect(Screen.width - 250, 40, 240, 165));
            GUILayout.Label("behavior_state: " + Null(state.behavior_state));
            GUILayout.Label("pose: " + Null(state.pose) + "  progress: " + state.pose_progress.ToString("0.00"));
            GUILayout.Label("emotion: " + Null(state.emotion));
            GUILayout.Label("intent: " + Null(state.intent));
            GUILayout.Label("moving: " + state.moving);
            GUILayout.Label("in_conversation: " + state.in_conversation);
            GUILayout.Label("target loc/npc/obj: " + Null(state.target_location_id) + " / "
                + Null(state.target_npc_id) + " / " + Null(state.target_object_id));
            GUILayout.EndArea();
        }

        static string Null(string s)
        {
            return string.IsNullOrEmpty(s) ? "-" : s;
        }
    }
}