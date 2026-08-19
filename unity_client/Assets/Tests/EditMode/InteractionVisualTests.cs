using NUnit.Framework;
using NpcAi.Client;

namespace NpcAi.Client.Tests
{
    public class InteractionVisualTests
    {
        [Test]
        public void FirstNameSplitsFullName()
        {
            Assert.AreEqual("Elena", InteractionVisual.FirstName("Elena Chen"));
            Assert.AreEqual("Bo", InteractionVisual.FirstName("Bo"));
            Assert.AreEqual("Someone", InteractionVisual.FirstName(null));
            Assert.AreEqual("Someone", InteractionVisual.FirstName(""));
        }

        [Test]
        public void CapitalizeTurnsIdsIntoTitles()
        {
            Assert.AreEqual("Herbalist", InteractionVisual.Capitalize("herbalist"));
            Assert.AreEqual("Shopkeeper", InteractionVisual.Capitalize("shopkeeper"));
            Assert.AreEqual("SwordSmith", InteractionVisual.Capitalize("sword_smith"));
            Assert.AreEqual("", InteractionVisual.Capitalize(""));
            Assert.AreEqual("", InteractionVisual.Capitalize(null));
        }

        [Test]
        public void NpcPromptUsesFirstNameAndJob()
        {
            Assert.AreEqual("Elena — Herbalist", InteractionVisual.NpcPrompt("Elena Chen", "herbalist"));
            Assert.AreEqual("Elena", InteractionVisual.NpcPrompt("Elena Chen", null));
            Assert.AreEqual("Elena", InteractionVisual.NpcPrompt("Elena Chen", ""));
        }

        [Test]
        public void ObjectPromptCombinesNameAndType()
        {
            Assert.AreEqual("Old Well (Well)", InteractionVisual.ObjectPrompt("Old Well", "well"));
        }

        [Test]
        public void LocationPromptCombinesNameAndType()
        {
            Assert.AreEqual("Green Market — Commercial", InteractionVisual.LocationPrompt("Green Market", "commercial"));
        }

        [Test]
        public void ObjectActionHintPerType()
        {
            Assert.AreEqual("E — Sit", InteractionVisual.ObjectActionHint("bench"));
            Assert.AreEqual("E — Use", InteractionVisual.ObjectActionHint("well"));
            Assert.AreEqual("E — Tend", InteractionVisual.ObjectActionHint("plant"));
            Assert.AreEqual("E — Interact", InteractionVisual.ObjectActionHint("unknown"));
            Assert.AreEqual("", InteractionVisual.NpcActionHint(false));
            Assert.AreEqual("E — Talk", InteractionVisual.NpcActionHint(true));
        }

        [Test]
        public void PromptsAreDeterministic()
        {
            Assert.AreEqual(
                InteractionVisual.NpcPrompt("Elena Chen", "herbalist"),
                InteractionVisual.NpcPrompt("Elena Chen", "herbalist"));
            Assert.AreEqual(
                InteractionVisual.ObjectPrompt("Old Well", "well"),
                InteractionVisual.ObjectPrompt("Old Well", "well"));
        }
    }
}