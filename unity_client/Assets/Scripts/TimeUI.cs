using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Simulated time readout (authoritative clock from the transport payload).
    /// Purely presentational.
    /// </summary>
    public class TimeUI : MonoBehaviour
    {
        public TransportClient transport;

        void Start()
        {
            if (transport == null)
                transport = FindObjectOfType<TransportClient>();
        }

        void OnGUI()
        {
            var payload = transport != null ? transport.Latest : null;
            if (payload == null) return;

            string text = "Day " + payload.day + "  " +
                payload.hour.ToString("00") + ":" + payload.minute.ToString("00");
            var style = new GUIStyle(GUI.skin.label);
            style.alignment = TextAnchor.MiddleCenter;
            style.fontSize = 16;
            GUI.Label(new Rect(Screen.width / 2f - 120f, 10f, 240f, 30f), text, style);
        }
    }
}