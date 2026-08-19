using NUnit.Framework;
using NpcAi.Client;
using UnityEngine;

namespace NpcAi.Client.Tests
{
    public class NpcVisualTests
    {
        static AnimationStateData State(string pose, string emotion = "content", bool conv = false, string thought = null)
        {
            return new AnimationStateData
            {
                npc_id = "npc_001",
                name = "Elena",
                pose = pose,
                moving = pose == "walk",
                behavior_state = "idle",
                emotion = emotion,
                in_conversation = conv,
                thought = thought,
            };
        }

        static NpcVisual Spawn()
        {
            var go = new GameObject("NpcVisual");
            var visual = go.AddComponent<NpcVisual>();
            visual.EnsureBuilt();
            return visual;
        }

        [TearDown]
        public void TearDown()
        {
            var roots = Object.FindObjectsOfType<NpcVisual>();
            foreach (var v in roots)
                if (v != null && v.gameObject != null)
                    Object.DestroyImmediate(v.gameObject);
        }

        [Test]
        public void MissingPrefabBuildsFallbackCharacter()
        {
            var visual = Spawn();
            Assert.IsNull(visual.characterPrefab);
            Assert.IsNotNull(visual.CharacterModel, "fallback model must exist");
            Assert.IsNull(visual.Animator, "fallback has no animator");
            Assert.IsNotNull(visual.CharacterRoot);
        }

        [Test]
        public void MissingAnimatorDoesNotCrashOnAnyPose()
        {
            var visual = Spawn();
            foreach (var pose in new[] { "idle", "walk", "work", "eat", "buy", "sleep", "sit",
                "stand", "talk", "listen", "wave", "inspect", "stretch", "interact", "dead", "typo" })
            {
                Assert.DoesNotThrow(() => visual.Apply(State(pose),
                    Vector3.zero, Vector3.forward, true));
            }
        }

        [Test]
        public void AnimatorWithoutControllerDoesNotCrash()
        {
            var prefab = new GameObject("Prefab");
            prefab.AddComponent<Animator>();

            var go = new GameObject("NpcVisual");
            var visual = go.AddComponent<NpcVisual>();
            visual.characterPrefab = prefab;
            visual.EnsureBuilt();

            Assert.IsNotNull(visual.Animator);
            Assert.DoesNotThrow(() => visual.Apply(State("walk"),
                Vector3.zero, Vector3.forward, true));

            Object.DestroyImmediate(prefab);
            Object.DestroyImmediate(go);
        }

        [Test]
        public void IdsRemainAssociatedWithTheirVisual()
        {
            var a = Spawn();
            var b = Spawn();
            a.Init("npc_1", "Aria");
            b.Init("npc_2", "Bo");
            Assert.AreEqual("npc_1", a.NpcId);
            Assert.AreEqual("npc_2", b.NpcId);
            Assert.AreEqual("NPC_npc_1", a.gameObject.name);
            Assert.AreEqual("NPC_npc_2", b.gameObject.name);
        }

        [Test]
        public void EnsureBuiltIsIdempotent()
        {
            var visual = Spawn();
            var model = visual.CharacterModel;
            visual.EnsureBuilt();
            visual.EnsureBuilt();
            Assert.AreSame(model, visual.CharacterModel, "must not rebuild/duplicate the model");
        }

        [Test]
        public void ThoughtAppearsAndDisappears()
        {
            var visual = Spawn();
            var thoughtBubble = visual.transform.Find("ThoughtBubble");
            Assert.IsNotNull(thoughtBubble);

            visual.Apply(State("idle", thought: "I wonder if the market is still open..."),
                Vector3.zero, Vector3.forward, false);
            visual.Tick();
            Assert.IsTrue(thoughtBubble.gameObject.activeSelf);

            visual.Apply(State("idle", thought: null), Vector3.zero, Vector3.forward, false);
            for (int i = 0; i < 30; i++) visual.Tick();
            Assert.IsFalse(thoughtBubble.gameObject.activeSelf);
        }

        [Test]
        public void ThoughtTextIsTruncated()
        {
            string longThought = new string('x', 300);
            string result = ThoughtBubble.Truncate(longThought, 140);
            Assert.AreEqual(140, result.Length);
            Assert.AreEqual('\u2026', result[result.Length - 1]);
            Assert.AreEqual("short", ThoughtBubble.Truncate("short", 140));
            Assert.AreEqual("", ThoughtBubble.Truncate("", 140));
        }

        [Test]
        public void ValidEmotionsNeverCrash()
        {
            var visual = Spawn();
            foreach (var e in new[] { "calm", "content", "happy", "hungry", "tired", "lonely", "stressed", "bogus", "" })
            {
                Assert.DoesNotThrow(() => visual.Apply(State("idle", emotion: e),
                    Vector3.zero, Vector3.forward, false));
            }
        }

        [Test]
        public void ConversationIndicatorShowsWhenConversing()
        {
            var visual = Spawn();
            var indicator = visual.transform.Find("ConversationIndicator");
            Assert.IsNotNull(indicator);

            visual.Apply(State("talk", conv: true), Vector3.zero, Vector3.forward, true);
            visual.Tick();
            Assert.IsTrue(indicator.gameObject.activeSelf);

            visual.Apply(State("idle", conv: false), Vector3.zero, Vector3.forward, false);
            for (int i = 0; i < 30; i++) visual.Tick();
            Assert.IsFalse(indicator.gameObject.activeSelf);
        }

        [Test]
        public void SelectionRingToggles()
        {
            var visual = Spawn();
            var ring = visual.transform.Find("CharacterRoot/SelectionRing");
            Assert.IsNotNull(ring, "every NPC gets a selection ring");
            Assert.IsFalse(ring.gameObject.activeSelf, "ring starts hidden");

            visual.SetSelected(true);
            Assert.IsTrue(ring.gameObject.activeSelf, "SetSelected(true) shows the ring");

            visual.SetSelected(false);
            Assert.IsFalse(ring.gameObject.activeSelf, "SetSelected(false) hides the ring");
        }

        [Test]
        public void ProfessionLabelShowsJobWhenSet()
        {
            var visual = Spawn();
            visual.Init("npc_001", "Elena Chen");
            var label = visual.transform.Find("ProfessionLabel");
            Assert.IsNotNull(label, "every NPC gets a profession label");
            Assert.IsFalse(label.gameObject.activeSelf, "profession hidden until known");

            visual.SetProfession("herbalist");
            Assert.IsTrue(label.gameObject.activeSelf);
            var text = label.GetComponent<TextMesh>();
            Assert.AreEqual("Herbalist", text.text);

            visual.SetProfession(null);
            Assert.IsFalse(label.gameObject.activeSelf, "clearing the job hides the label");
        }

        [Test]
        public void FacingResolvesToNpcPosition()
        {
            var visual = Spawn();
            var other = Spawn();
            other.Init("npc_2", "Bo");
            other.transform.position = new Vector3(5f, 0f, 5f);

            var state = State("talk", conv: true);
            state.facing_npc_id = "npc_2";

            visual.Apply(state, Vector3.zero, other.transform.position, true);
            visual.transform.position = Vector3.zero;

            for (int i = 0; i < 60; i++) visual.Tick();
            var forward = visual.CharacterModel.forward;
            Assert.IsTrue(Vector3.Dot(forward, new Vector3(1, 0, 1).normalized) > 0.9f,
                "character should rotate toward the conversation partner");
        }
    }
}