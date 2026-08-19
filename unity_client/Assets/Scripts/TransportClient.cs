using System.Collections;
using UnityEngine;
using UnityEngine.Networking;

namespace NpcAi.Client
{
    /// <summary>
    /// Localhost HTTP transport client. Polls GET /snapshot for the latest
    /// presentation payload and POSTs control commands (play/pause/step/reset).
    /// Purely a renderer-side client: it never modifies simulation state except
    /// through the explicit /control API boundary.
    /// </summary>
    public class TransportClient : MonoBehaviour
    {
        public string host = "127.0.0.1";
        public int port = 8770;
        public float pollInterval = 0.1f;
        public float interactionPollInterval = 0.25f;

        public WorldPayload Latest { get; private set; }
        public InteractionPayload LatestInteraction { get; private set; }
        public bool IsConnected { get; private set; }
        public string LastError { get; private set; }

        private Coroutine _poll;
        private Coroutine _interactionPoll;

        public string BaseUrl
        {
            get { return "http://" + host + ":" + port; }
        }

        void Start()
        {
            Connect();
        }

        public void Connect()
        {
            if (_poll == null)
                _poll = StartCoroutine(PollLoop());
            if (_interactionPoll == null)
                _interactionPoll = StartCoroutine(InteractionPollLoop());
        }

        IEnumerator InteractionPollLoop()
        {
            while (true)
            {
                using (var req = UnityWebRequest.Get(BaseUrl + "/interaction"))
                {
                    req.timeout = 2;
                    yield return req.SendWebRequest();
                    if (req.result == UnityWebRequest.Result.Success)
                    {
                        try
                        {
                            var payload = JsonUtility.FromJson<InteractionPayload>(req.downloadHandler.text);
                            if (payload != null)
                                LatestInteraction = payload;
                        }
                        catch (System.Exception e)
                        {
                            LastError = e.Message;
                        }
                    }
                }
                yield return new WaitForSeconds(interactionPollInterval);
            }
        }

        IEnumerator PollLoop()
        {
            while (true)
            {
                using (var req = UnityWebRequest.Get(BaseUrl + "/snapshot"))
                {
                    req.timeout = 2;
                    yield return req.SendWebRequest();
                    if (req.result == UnityWebRequest.Result.Success)
                    {
                        try
                        {
                            var payload = JsonUtility.FromJson<WorldPayload>(req.downloadHandler.text);
                            if (payload != null && payload.npcs != null)
                            {
                                Latest = payload;
                                IsConnected = true;
                                LastError = null;
                            }
                        }
                        catch (System.Exception e)
                        {
                            LastError = e.Message;
                            IsConnected = false;
                        }
                    }
                    else
                    {
                        IsConnected = false;
                        LastError = req.error;
                    }
                }
                yield return new WaitForSeconds(pollInterval);
            }
        }

        public void Play() { StartCoroutine(SendControl("play")); }
        public void Pause() { StartCoroutine(SendControl("pause")); }
        public void Step() { StartCoroutine(SendControl("step")); }
        public void Reset() { StartCoroutine(SendControl("reset")); }

        IEnumerator SendControl(string action)
        {
            var req = new UnityWebRequest(BaseUrl + "/control", "POST");
            byte[] body = System.Text.Encoding.UTF8.GetBytes("{\"action\":\"" + action + "\"}");
            req.uploadHandler = new UploadHandlerRaw(body);
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.timeout = 2;
            yield return req.SendWebRequest();
            req.Dispose();
        }

        /// <summary>Report the player's world position to the authoritative layer.</summary>
        public void SendPlayerUpdate(float x, float z)
        {
            string json = "{\"type\":\"player_update\",\"x\":" +
                x.ToString(System.Globalization.CultureInfo.InvariantCulture) +
                ",\"z\":" + z.ToString(System.Globalization.CultureInfo.InvariantCulture) + "}";
            StartCoroutine(SendCommand(json, null));
        }

        /// <summary>Send an authoritative player command. Callback gets ok/error status.</summary>
        public void SendPlayerCommand(string type, string targetId, string option, System.Action<bool, string> callback)
        {
            string body = "{\"type\":\"" + type + "\"";
            if (!string.IsNullOrEmpty(targetId))
                body += ",\"target_id\":\"" + targetId + "\"";
            if (!string.IsNullOrEmpty(option))
                body += ",\"option\":\"" + option + "\"";
            body += "}";
            StartCoroutine(SendCommand(body, callback));
        }

        IEnumerator SendCommand(string body, System.Action<bool, string> callback)
        {
            var req = new UnityWebRequest(BaseUrl + "/command", "POST");
            byte[] bytes = System.Text.Encoding.UTF8.GetBytes(body);
            req.uploadHandler = new UploadHandlerRaw(bytes);
            req.downloadHandler = new DownloadHandlerBuffer();
            req.SetRequestHeader("Content-Type", "application/json");
            req.timeout = 2;
            yield return req.SendWebRequest();
            if (req.result == UnityWebRequest.Result.Success)
            {
                try
                {
                    var result = JsonUtility.FromJson<CommandResult>(req.downloadHandler.text);
                    if (callback != null)
                        callback(result.ok, result.ok ? null : result.error);
                }
                catch (System.Exception e)
                {
                    if (callback != null) callback(false, e.Message);
                }
            }
            else
            {
                if (callback != null) callback(false, req.error);
            }
            req.Dispose();
        }

        [System.Serializable]
        class CommandResult
        {
            public bool ok;
            public string error;
        }
    }
}