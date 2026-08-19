using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Player selection + interaction. Left-click raycasts the world for an NPC,
    /// object or location marker and reports the selection to the authoritative
    /// Python layer via player_inspect / player_interact commands. Press E to
    /// talk to a selected NPC. All validity decisions are made Python-side; this
    /// script only renders the authoritative /interaction payload.
    /// </summary>
    public class InteractionSystem : MonoBehaviour
    {
        public TransportClient transport;
        public WorldVisual worldVisual;
        public PlayerController player;
        public float interactRange = 30f;

        public string SelectedTargetId { get; private set; }
        public string SelectedKind { get; private set; }

        void Start()
        {
            if (transport == null) transport = FindObjectOfType<TransportClient>();
            if (worldVisual == null) worldVisual = FindObjectOfType<WorldVisual>();
            if (player == null) player = FindObjectOfType<PlayerController>();
        }

        void Update()
        {
            if (player != null && (player.IsRotating || player.CursorLocked)) return;
            if (Input.GetMouseButtonDown(0)) TrySelect();

            if (Input.GetKeyDown(KeyCode.E))
            {
                if (SelectedKind == "npc")
                    transport.SendPlayerCommand("player_talk", SelectedTargetId, null, null);
                else if (SelectedKind == "object")
                    transport.SendPlayerCommand("player_interact", SelectedTargetId, null, null);
            }

            UpdateHighlights();
            if (worldVisual != null)
                worldVisual.ApplyInteractionPresentation(transport != null ? transport.LatestInteraction : null);
        }

        void UpdateHighlights()
        {
            if (worldVisual == null) return;
            if (SelectedKind == "npc" && !string.IsNullOrEmpty(SelectedTargetId))
            {
                worldVisual.ClearNpcSelections(SelectedTargetId);
                var npc = worldVisual.SelectedNpc(SelectedTargetId);
                if (npc != null) npc.SetSelected(true);
            }
            else
            {
                worldVisual.ClearNpcSelections(null);
            }
            bool objSel = SelectedKind == "object" && !string.IsNullOrEmpty(SelectedTargetId);
            worldVisual.SetObjectHighlighted(objSel ? SelectedTargetId : null, objSel);
            worldVisual.ClearObjectSelections(objSel ? SelectedTargetId : null);
            bool locSel = SelectedKind == "location" && !string.IsNullOrEmpty(SelectedTargetId);
            worldVisual.SetLocationHighlighted(locSel ? SelectedTargetId : null, locSel);
            worldVisual.ClearLocationSelections(locSel ? SelectedTargetId : null);
        }

        void TrySelect()
        {
            Camera cam = Camera.main;
            if (cam == null) return;
            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            RaycastHit hit;
            if (!Physics.Raycast(ray, out hit, 500f)) return;
            GameObject go = hit.collider.gameObject;

            NpcVisual npc = go.GetComponentInParent<NpcVisual>();
            if (npc != null && npc.NpcId != null)
            {
                SelectedKind = "npc";
                SelectedTargetId = npc.NpcId;
                transport.SendPlayerCommand("player_inspect", npc.NpcId, null, null);
                return;
            }

            // Decor props are children of the "Obj_<id>" / "Loc_<id>" marker
            // root, so walk up the hierarchy to find the marker.
            GameObject marker = go;
            while (marker != null)
            {
                if (marker.name.StartsWith("Obj_"))
                {
                    string id = marker.name.Substring(4);
                    SelectedKind = "object";
                    SelectedTargetId = id;
                    transport.SendPlayerCommand("player_inspect", id, null, null);
                    return;
                }
                if (marker.name.StartsWith("Loc_"))
                {
                    SelectedKind = "location";
                    SelectedTargetId = marker.name.Substring(4);
                    return;
                }
                marker = marker.transform.parent != null ? marker.transform.parent.gameObject : null;
            }

            SelectedKind = null;
            SelectedTargetId = null;
        }

        void OnGUI()
        {
            DrawCrosshair();
            DrawPrompt();
            DrawInteractionPanel();
        }

        void DrawCrosshair()
        {
            var c = new GUIStyle();
            c.normal.textColor = Color.white;
            c.fontSize = 18;
            c.alignment = TextAnchor.MiddleCenter;
            GUI.Label(new Rect(Screen.width / 2f - 10f, Screen.height / 2f - 12f, 20f, 24f), "+", c);
        }

        void DrawPrompt()
        {
            if (SelectedKind == null) return;
            string text = null;
            var payload = transport != null ? transport.LatestInteraction : null;
            if (SelectedKind == "npc")
            {
                string job = null;
                if (payload != null && payload.target != null && payload.target.npc_id == SelectedTargetId)
                    job = payload.target.job;
                NpcVisual npc = worldVisual != null ? worldVisual.SelectedNpc(SelectedTargetId) : null;
                string name = npc != null ? npc.NpcName : null;
                text = InteractionVisual.NpcPrompt(name ?? SelectedTargetId, job);
                if (!string.IsNullOrEmpty(InteractionVisual.NpcActionHint(payload != null && payload.target != null ? payload.target.alive : true)))
                    text += "   [E]";
            }
            else if (SelectedKind == "object")
            {
                string objName = SelectedTargetId;
                string objType = null;
                if (payload != null && payload.@object != null && payload.@object.object_id == SelectedTargetId)
                {
                    objName = payload.@object.name;
                    objType = payload.@object.object_type;
                }
                text = InteractionVisual.ObjectPrompt(objName, objType ?? "object") + "   [" + InteractionVisual.ObjectActionHint(objType) + "]";
            }
            else if (SelectedKind == "location")
            {
                text = InteractionVisual.LocationPrompt(SelectedTargetId, "area");
            }
            if (text == null) return;

            var style = new GUIStyle(GUI.skin.box);
            style.fontSize = 14;
            style.normal.textColor = Color.white;
            float w = Mathf.Min(Screen.width - 40f, 360f);
            var rect = new Rect(Screen.width / 2f - w / 2f, Screen.height - 74f, w, 30f);
            GUI.Box(rect, text, style);
        }

        void DrawInteractionPanel()
        {
            var payload = transport != null ? transport.LatestInteraction : null;
            if (payload == null)
            {
                GUI.Box(new Rect(Screen.width - 300, 10, 290, 60), "Interaction");
                GUI.Label(new Rect(Screen.width - 290, 35, 280, 20), "Waiting for the simulation…");
                return;
            }

            GUI.Box(new Rect(Screen.width - 300, 10, 290, 78), "Location");
            if (payload.location != null)
            {
                GUI.Label(new Rect(Screen.width - 290, 32, 280, 18),
                    payload.location.name + " (" + Null(payload.location.type) + ")");
                GUI.Label(new Rect(Screen.width - 290, 50, 280, 18),
                    "NPCs here: " + (payload.location.npc_count) +
                    "   Settlement: " + Null(payload.location.settlement_id));
                GUI.Label(new Rect(Screen.width - 290, 66, 280, 18),
                    "Objects: " + (payload.location.objects != null ? payload.location.objects.Length : 0));
            }
            else
            {
                GUI.Label(new Rect(Screen.width - 290, 32, 280, 18), "Wilderness / unknown");
            }

            GUI.Box(new Rect(Screen.width - 300, 96, 290, 260), "Inspection");
            if (payload.target != null)
            {
                var t = payload.target;
                GUILayout.BeginArea(new Rect(Screen.width - 290, 122, 270, 230));
                GUILayout.Label(t.name + " — " + Null(t.job) + (t.alive ? "" : "  (deceased)"));
                GUILayout.Label("State: " + Null(t.behavior_state) + " / " + Null(t.pose) + " / " + Null(t.emotion));
                GUILayout.Label("Intent: " + Null(t.intent) + "   Goal: " + Null(t.goal) + "   Action: " + Null(t.action));
                GUILayout.Label("Money: " + t.money.ToString("0.00"));
                if (t.needs != null)
                    GUILayout.Label("Needs  H:" + t.needs.hunger.ToString("0") +
                        "  E:" + t.needs.energy.ToString("0") + "  S:" + t.needs.social.ToString("0"));
                if (t.relationships != null)
                    foreach (var rel in t.relationships)
                        GUILayout.Label("Relationship: " + rel.npc_id + " = " + rel.value);
                GUILayout.Label("Location: " + Null(t.location_id));
                GUILayout.EndArea();
            }
            else if (payload.@object != null)
            {
                var o = payload.@object;
                GUILayout.BeginArea(new Rect(Screen.width - 290, 122, 270, 230));
                GUILayout.Label("Object: " + o.name + " (" + Null(o.object_type) + ")");
                GUILayout.Label("State: " + Null(o.state));
                GUILayout.Label("Location: " + Null(o.location_id));
                if (o.interactions != null)
                {
                    GUILayout.Label("Interactions:");
                    foreach (var i in o.interactions) GUILayout.Label("  - " + i);
                }
                GUILayout.EndArea();
            }
            else
            {
                GUILayout.BeginArea(new Rect(Screen.width - 290, 122, 270, 230));
                GUILayout.Label("Click an NPC or object to inspect.");
                GUILayout.EndArea();
            }

            if (SelectedKind == "npc" && payload.target != null && payload.target.alive)
                GUI.Label(new Rect(Screen.width - 290, 362, 280, 20), "Press E to talk. Follow: coming soon.");

            if (payload.chatter != null && payload.chatter.Length > 0)
            {
                float cw = 300f;
                GUI.Box(new Rect(10, Screen.height - 112f, cw, 102f), "Chatter");
                GUILayout.BeginArea(new Rect(18, Screen.height - 88f, cw - 16, 74f));
                for (int i = Mathf.Max(0, payload.chatter.Length - 3); i < payload.chatter.Length; i++)
                {
                    var c = payload.chatter[i];
                    GUILayout.Label(c.speaker_name + ": " + c.dialogue);
                }
                GUILayout.EndArea();
            }
        }

        static string Null(string s)
        {
            return string.IsNullOrEmpty(s) ? "-" : s;
        }
    }
}