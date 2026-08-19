using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Player-facing conversation UI. Displays the authoritative conversation
    /// state from the /interaction payload and sends conversation options back
    /// through player_talk commands. The "Follow" action is intentionally
    /// disabled (no NPC-follow AI in this phase).
    /// </summary>
    public class ConversationUI : MonoBehaviour
    {
        public TransportClient transport;

        void Start()
        {
            if (transport == null)
                transport = FindObjectOfType<TransportClient>();
        }

        void OnGUI()
        {
            var payload = transport != null ? transport.LatestInteraction : null;
            if (payload == null || payload.conversation == null || !payload.conversation.active)
                return;

            float w = 360f;
            float h = 230f;
            var rect = new Rect((Screen.width - w) / 2f, Screen.height - h - 20f, w, h);
            GUI.Box(rect, "Conversation — " + payload.conversation.npc_name);

            GUILayout.BeginArea(new Rect(rect.x + 10, rect.y + 28, rect.width - 20, 90));
            GUILayout.Label("\"" + payload.conversation.text + "\"");
            string meta = payload.conversation.llm
                ? "LLM"
                : "simulated";
            if (!string.IsNullOrEmpty(payload.conversation.emotion))
                meta += " · " + payload.conversation.emotion;
            if (!string.IsNullOrEmpty(payload.conversation.topic))
                meta += " · " + payload.conversation.topic;
            GUILayout.Label(meta);
            GUILayout.EndArea();

            float y = rect.y + 148f;
            bool drewOption = false;
            if (payload.conversation.options != null)
            {
                foreach (var opt in payload.conversation.options)
                {
                    if (GUI.Button(new Rect(rect.x + 10, y, 210f, 26f), opt.label))
                        transport.SendPlayerCommand("player_talk", payload.conversation.npc_id, opt.key, null);
                    y += 34f;
                    drewOption = true;
                }
            }

            // When the conversation has no choices (the NPC decides what to
            // say), offer an explicit Goodbye so the player can always end it.
            if (!drewOption)
            {
                if (GUI.Button(new Rect(rect.x + 10, y, 210f, 26f), "Goodbye"))
                    transport.SendPlayerCommand("player_talk", payload.conversation.npc_id, "goodbye", null);
                y += 34f;
            }

            GUI.enabled = false;
            GUI.Button(new Rect(rect.x + rect.width - 120f, y, 110f, 26f), "Follow (soon)");
            GUI.enabled = true;
        }
    }
}