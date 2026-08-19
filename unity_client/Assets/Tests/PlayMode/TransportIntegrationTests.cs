using System.Collections;
using System.Diagnostics;
using System.IO;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace NpcAi.Client.Tests
{
    /// <summary>
    /// End-to-end smoke tests that run against a real authoritative Python
    /// transport server (spawned as a subprocess). Verifies the full pipeline:
    /// HTTP snapshot → TransportClient → WorldVisual → NpcVisual creation.
    /// These tests never modify simulation state; they only read /snapshot.
    /// </summary>
    public class TransportIntegrationTests
    {
        private const int Port = 8772;
        private Process _server;

        static string ProjectDir()
        {
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "project"));
        }

        [UnitySetUp]
        public IEnumerator StartServer()
        {
            _server = new Process();
            _server.StartInfo.FileName = "python";
            _server.StartInfo.Arguments = "-m world_sim.presentation.transport --seed 42 --days 0 --port " + Port;
            _server.StartInfo.WorkingDirectory = ProjectDir();
            _server.StartInfo.UseShellExecute = false;
            _server.StartInfo.RedirectStandardOutput = true;
            _server.StartInfo.RedirectStandardError = true;
            _server.StartInfo.CreateNoWindow = true;
            _server.Start();

            float timeout = Time.time + 20f;
            bool ready = false;
            while (Time.time < timeout && !ready)
            {
                using (var req = new UnityEngine.Networking.UnityWebRequest("http://127.0.0.1:" + Port + "/healthz"))
                {
                    req.timeout = 2;
                    yield return req.SendWebRequest();
                    if (req.result == UnityEngine.Networking.UnityWebRequest.Result.Success)
                        ready = true;
                }
                if (!ready)
                    yield return new WaitForSeconds(0.5f);
            }
            Assert.IsTrue(ready, "Python transport server did not become ready");
        }

        [UnityTearDown]
        public IEnumerator StopServer()
        {
            foreach (var v in Object.FindObjectsOfType<NpcVisual>())
                Object.Destroy(v.gameObject);
            foreach (var v in Object.FindObjectsOfType<WorldVisual>())
                Object.Destroy(v.gameObject);
            foreach (var v in Object.FindObjectsOfType<TransportClient>())
                Object.Destroy(v.gameObject);
            if (_server != null && !_server.HasExited)
                _server.Kill();
            _server = null;
            yield return null;
        }

        static IEnumerator WaitUntil(System.Func<bool> condition, float timeoutSec)
        {
            float deadline = Time.time + timeoutSec;
            while (!condition() && Time.time < deadline)
                yield return null;
        }

        [UnityTest]
        public IEnumerator CreatesNpcsFromLiveSnapshot()
        {
            var go = new GameObject("Visual");
            var transport = go.AddComponent<TransportClient>();
            transport.port = Port;
            transport.pollInterval = 0.05f;
            var visual = go.AddComponent<WorldVisual>();
            visual.transport = transport;
            visual.npcSmoothTime = 0.1f;

            transport.Connect();
            yield return WaitUntil(() => transport.IsConnected && transport.Latest != null && transport.Latest.npcs.Length > 0, 15f);
            Assert.IsTrue(transport.IsConnected, "transport should connect to the live server");
            Assert.GreaterOrEqual(transport.Latest.npcs.Length, 1, "snapshot should contain NPCs");

            yield return WaitUntil(() => visual.SelectedNpc(transport.Latest.npcs[0].npc_id) != null, 10f);
            var first = visual.SelectedNpc(transport.Latest.npcs[0].npc_id);
            Assert.IsNotNull(first, "NpcVisual should exist for the first NPC");

            var all = Object.FindObjectsOfType<NpcVisual>();
            Assert.AreEqual(transport.Latest.npcs.Length, all.Length,
                "exactly one NpcVisual per snapshot NPC (no duplicates)");

            Assert.AreEqual(transport.Latest.npcs[0].name, first.NpcName,
                "NpcVisual name should come from the payload");

            Object.Destroy(go);
        }

        [UnityTest]
        public IEnumerator RepeatedSnapshotsDoNotDuplicateNpcs()
        {
            var go = new GameObject("Visual");
            var transport = go.AddComponent<TransportClient>();
            transport.port = Port;
            transport.pollInterval = 0.05f;
            var visual = go.AddComponent<WorldVisual>();
            visual.transport = transport;
            visual.npcSmoothTime = 0.1f;

            transport.Connect();
            yield return WaitUntil(() => transport.Latest != null && transport.Latest.npcs.Length > 0, 15f);

            // Let several snapshots land and WorldVisual reconcile repeatedly.
            yield return new WaitForSeconds(3f);

            var all = Object.FindObjectsOfType<NpcVisual>();
            Assert.AreEqual(transport.Latest.npcs.Length, all.Length,
                "repeated snapshots must not create duplicate NPC objects");

            var ids = new System.Collections.Generic.HashSet<string>();
            foreach (var v in all)
                Assert.IsTrue(ids.Add(v.NpcId), "NPC ids must be unique");

            Object.Destroy(go);
        }

        [UnityTest]
        public IEnumerator NpcsMoveAndFaceTargetsWithoutCrashing()
        {
            var go = new GameObject("Visual");
            var transport = go.AddComponent<TransportClient>();
            transport.port = Port;
            transport.pollInterval = 0.05f;
            var visual = go.AddComponent<WorldVisual>();
            visual.transport = transport;
            visual.npcSmoothTime = 0.1f;

            transport.Connect();
            yield return WaitUntil(() => transport.Latest != null && transport.Latest.npcs.Length > 0, 15f);

            var before = new System.Collections.Generic.Dictionary<string, Vector3>();
            foreach (var entry in transport.Latest.npcs)
            {
                var v = visual.SelectedNpc(entry.npc_id);
                Assert.IsNotNull(v, "every snapshot NPC must have a visual");
                Assert.IsFalse(float.IsNaN(v.transform.position.x), "NPC position must be finite");
                v.Tick(); // any pose/payload must not throw
                before[entry.npc_id] = v.transform.position;
            }

            yield return new WaitForSeconds(5f);

            bool anyMoved = false;
            foreach (var entry in transport.Latest.npcs)
            {
                var v = visual.SelectedNpc(entry.npc_id);
                if (v != null && (v.transform.position - before[entry.npc_id]).sqrMagnitude > 0.01f)
                {
                    anyMoved = true;
                    break;
                }
            }
            Assert.IsTrue(anyMoved, "at least one NPC should have moved during the window");

            Object.Destroy(go);
        }
    }
}