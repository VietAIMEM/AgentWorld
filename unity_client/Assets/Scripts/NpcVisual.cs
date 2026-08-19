using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Presentation wrapper for one NPC character. Hierarchy:
    ///
    ///   NpcVisual (root — moves, raycast target)
    ///    ├── CharacterRoot (scale / ground offset / facing yaw)
    ///    │    ├── CharacterModel (humanoid prefab OR primitive fallback)
    ///    │    └── Animator (only when a controller is available)
    ///    ├── ShadowDisc
    ///    ├── NameLabel (world-space TextMesh, billboarded)
    ///    ├── ThoughtBubble (world-space TextMesh, billboarded)
    ///    ├── ConversationIndicator (chat bubble + optional glyph)
    ///    └── EmotionIndicator (subtle colored dot)
    ///
    /// This component contains ZERO simulation/AI logic. It only interpolates
    /// toward the presentation targets it is given each frame and renders the
    /// authoritative AnimationState payload (pose → Animator state via
    /// PoseMapper, emotion, conversation, thought, name).
    /// </summary>
    public class NpcVisual : MonoBehaviour
    {
        // ---- Configuration (Inspector-editable) ----
        [Tooltip("Optional humanoid prefab. Leave empty to use the primitive fallback.")]
        public GameObject characterPrefab;
        [Tooltip("Character height in world units (used for fallback model + UI offsets).")]
        public float characterHeight = 1.8f;
        [Tooltip("Uniform scale applied to the whole character.")]
        public float characterScale = 1f;
        [Tooltip("Raises/lowers the character so the feet touch the ground.")]
        public float groundOffset = 0f;
        [Tooltip("Additional Euler rotation applied on top of the facing yaw.")]
        public Vector3 rotationOffset = Vector3.zero;
        public bool showNameLabel = true;
        public bool showEmotion = true;
        public bool showThoughtBubble = true;
        public bool showConversationIndicator = true;
        [Tooltip("Glyph shown on the conversation indicator (may not render on all fonts).")]
        public string conversationGlyph = "\uD83D\uDCAC";
        public float smoothTime = 0.3f;
        public float rotationSpeed = 5f;
        [Tooltip("Minimum squared distance before the character starts turning (anti-jitter).")]
        public float facingDeadzone = 0.0025f;
        public int thoughtMaxLength = 140;

        // ---- Identity / last payload ----
        public string NpcId { get; private set; }
        public string NpcName { get; private set; }
        public string Profession { get; private set; }
        public AnimationStateData State { get; private set; }
        public Vector3 TargetPosition { get; set; }
        public Vector3 FacingPosition { get; set; }
        public bool HasFacing { get; set; }

        // ---- Structure ----
        public Transform CharacterRoot { get; private set; }
        public Transform CharacterModel { get; private set; }
        public Animator Animator { get; private set; }

        private ProceduralRig _rig;
        private Transform _emotionIndicator;
        private Renderer _emotionRenderer;
        private Material _emotionMat;
        private Transform _conversationBubble;
        private Renderer _conversationRenderer;
        private Material _conversationMat;
        private TextMesh _conversationGlyphText;
        private GameObject _thoughtBubble;
        private TextMesh _thoughtText;
        private GameObject _nameLabel;
        private TextMesh _nameText;
        private GameObject _professionLabel;
        private TextMesh _professionText;
        private GameObject _selectionRing;

        private Vector3 _velocity;
        private float _currentYaw;
        private float _thoughtScale;
        private float _conversationScale;
        private bool _built;
        private Camera _cam;
        private static GameObject _cachedDefaultPrefab;
        private static bool _defaultPrefabSearched;

        void Awake()
        {
            EnsureBuilt();
        }

        /// <summary>Builds the character hierarchy once. Idempotent and safe to call from tests.</summary>
        public void EnsureBuilt()
        {
            if (_built) return;
            BuildCharacter();
            _built = true;
        }

        public void Init(string id, string name)
        {
            EnsureBuilt();
            bool hadId = NpcId != null;
            NpcId = id;
            NpcName = name;
            gameObject.name = "NPC_" + id;
            if (_nameText != null)
                _nameText.text = name;
            // The character may have been built (via Awake) before the id was
            // known; appearance is derived from the id, so rebuild when needed.
            if (!hadId && _rig != null)
                RebuildModel();
        }

        /// <summary>Sets the profession line shown under the name (idempotent).</summary>
        public void SetProfession(string job)
        {
            Profession = job;
            if (_professionText != null)
            {
                _professionText.text = string.IsNullOrEmpty(job) ? "" : InteractionVisual.Capitalize(job);
                bool show = !string.IsNullOrEmpty(job) && _professionLabel != null;
                if (_professionLabel != null)
                    _professionLabel.SetActive(show);
            }
        }

        /// <summary>Toggles the ground highlight ring under this NPC (idempotent).</summary>
        public void SetSelected(bool selected)
        {
            if (_selectionRing != null)
                _selectionRing.SetActive(selected);
        }

        public void Apply(AnimationStateData state, Vector3 targetPos, Vector3 facingPos, bool hasFacing)
        {
            EnsureBuilt();
            State = state;
            TargetPosition = targetPos;
            FacingPosition = facingPos;
            HasFacing = hasFacing;
        }

        // ------------------------------------------------------------------
        // Building
        // ------------------------------------------------------------------

        void BuildCharacter()
        {
            CharacterRoot = new GameObject("CharacterRoot").transform;
            CharacterRoot.SetParent(transform, false);
            CharacterRoot.localScale = Vector3.one * Mathf.Max(0.01f, characterScale);
            CharacterRoot.localPosition = new Vector3(0f, groundOffset, 0f);

            BuildModel();
            BuildShadowDisc();
            BuildSelectionRing();
            BuildNameLabel();
            BuildProfessionLabel();
            BuildThoughtBubble();
            BuildConversationIndicator();
            BuildEmotionIndicator();
        }

        void BuildModel()
        {
            var prefab = characterPrefab != null ? characterPrefab : DefaultCharacterPrefab();
            var modelGo = prefab != null ? Instantiate(prefab) : BuildFallbackModel();
            modelGo.name = "CharacterModel";
            CharacterModel = modelGo.transform;
            CharacterModel.SetParent(CharacterRoot, false);
            CharacterModel.localPosition = prefab != null
                ? Vector3.zero
                : new Vector3(0f, 0f, 0f);

            if (prefab != null)
            {
                Animator = modelGo.GetComponentInChildren<Animator>();
                if (Animator != null)
                    Animator.applyRootMotion = false;
                AddSelectionCollider();
            }
            else
            {
                Animator = modelGo.GetComponent<Animator>();
                AddSelectionCollider();
            }
        }

        void RebuildModel()
        {
            if (CharacterModel != null)
                PrimitiveUtils.DestroyObj(CharacterModel.gameObject);
            if (Animator != null)
                Animator = null;
            if (_rig != null)
                _rig = null;
            BuildModel();
        }

        /// <summary>
        /// Optional automatic lookup: if a prefab exists at
        /// Assets/Resources/Models/NPC_Humanoid.prefab it is used automatically.
        /// Cached after the first call (Resources.Load is then a dictionary hit).
        /// </summary>
        static GameObject DefaultCharacterPrefab()
        {
            if (!_defaultPrefabSearched)
            {
                _defaultPrefabSearched = true;
                _cachedDefaultPrefab = Resources.Load<GameObject>("Models/NPC_Humanoid");
            }
            return _cachedDefaultPrefab;
        }

        GameObject BuildFallbackModel()
        {
            var model = new GameObject("FallbackModel");
            AppearanceProfile appearance = NpcAppearance.Generate(NpcId);
            float height = Mathf.Max(0.5f, characterHeight) * appearance.heightScale;
            _rig = ProceduralRig.Build(model.transform, appearance, height);
            ProceduralAnimator.Apply(_rig, "idle", false, 0f);
            return model;
        }

        void AddSelectionCollider()
        {
            if (GetComponent<Collider>() != null) return;
            var cap = gameObject.AddComponent<CapsuleCollider>();
            float h = Mathf.Max(0.5f, characterHeight * characterScale);
            cap.height = h;
            cap.radius = Mathf.Clamp(h * 0.22f, 0.3f, 0.6f);
            cap.center = new Vector3(0f, groundOffset + h * 0.5f, 0f);
        }

        void BuildShadowDisc()
        {
            var disc = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            disc.name = "ShadowDisc";
            disc.transform.SetParent(CharacterRoot, false);
            PrimitiveUtils.DestroyObj(disc.GetComponent<Collider>());
            disc.transform.localPosition = new Vector3(0f, 0.02f, 0f);
            disc.transform.localScale = new Vector3(1.1f, 0.02f, 1.1f);
            disc.GetComponent<Renderer>().sharedMaterial = PrimitiveUtils.ColoredMaterial(new Color(0.1f, 0.12f, 0.1f));
        }

        // ---- World-space UI labels ----

        float UiHeight(float extra)
        {
            return characterHeight * Mathf.Max(0.01f, characterScale) + extra;
        }

        void BuildNameLabel()
        {
            _nameLabel = new GameObject("NameLabel");
            _nameLabel.transform.SetParent(transform, false);
            _nameLabel.transform.localPosition = new Vector3(0f, UiHeight(0.4f), 0f);

            var plate = GameObject.CreatePrimitive(PrimitiveType.Cube);
            plate.name = "Plate";
            plate.transform.SetParent(_nameLabel.transform, false);
            PrimitiveUtils.DestroyObj(plate.GetComponent<Collider>());
            plate.transform.localPosition = new Vector3(0f, 0f, 0.06f);
            plate.transform.localScale = new Vector3(1.5f, 0.24f, 0.02f);
            plate.GetComponent<Renderer>().sharedMaterial =
                PrimitiveUtils.ColoredMaterial(new Color(0.08f, 0.08f, 0.10f, 0.62f));

            _nameText = _nameLabel.AddComponent<TextMesh>();
            _nameText.font = DefaultFont();
            _nameText.text = NpcName;
            _nameText.fontSize = 64;
            _nameText.characterSize = 0.02f;
            _nameText.anchor = TextAnchor.MiddleCenter;
            _nameText.alignment = TextAlignment.Center;
            _nameText.color = new Color(1f, 1f, 1f, 0.92f);
            _nameLabel.SetActive(showNameLabel);
        }

        void BuildProfessionLabel()
        {
            _professionLabel = new GameObject("ProfessionLabel");
            _professionLabel.transform.SetParent(transform, false);
            _professionLabel.transform.localPosition = new Vector3(0f, UiHeight(0.18f), 0f);
            _professionText = _professionLabel.AddComponent<TextMesh>();
            _professionText.font = DefaultFont();
            _professionText.text = "";
            _professionText.fontSize = 40;
            _professionText.characterSize = 0.018f;
            _professionText.anchor = TextAnchor.MiddleCenter;
            _professionText.alignment = TextAlignment.Center;
            _professionText.color = new Color(1f, 0.85f, 0.5f, 0.9f);
            _professionLabel.SetActive(false);
        }

        void BuildSelectionRing()
        {
            _selectionRing = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            _selectionRing.name = "SelectionRing";
            _selectionRing.transform.SetParent(CharacterRoot, false);
            PrimitiveUtils.DestroyObj(_selectionRing.GetComponent<Collider>());
            _selectionRing.transform.localPosition = new Vector3(0f, 0.03f, 0f);
            _selectionRing.transform.localScale = new Vector3(1.4f, 0.02f, 1.4f);
            _selectionRing.GetComponent<Renderer>().sharedMaterial =
                PrimitiveUtils.ColoredMaterial(new Color(0.95f, 0.85f, 0.3f));
            _selectionRing.SetActive(false);
        }

        void BuildThoughtBubble()
        {
            _thoughtBubble = new GameObject("ThoughtBubble");
            _thoughtBubble.transform.SetParent(transform, false);
            _thoughtBubble.transform.localPosition = new Vector3(0f, UiHeight(0.85f), 0f);

            var backing = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            backing.name = "Backing";
            backing.transform.SetParent(_thoughtBubble.transform, false);
            PrimitiveUtils.DestroyObj(backing.GetComponent<Collider>());
            backing.transform.localScale = new Vector3(1.0f, 0.01f, 0.62f);
            backing.GetComponent<Renderer>().sharedMaterial = PrimitiveUtils.ColoredMaterial(new Color(0.94f, 0.93f, 0.88f));

            _thoughtText = _thoughtBubble.AddComponent<TextMesh>();
            _thoughtText.font = DefaultFont();
            _thoughtText.text = "";
            _thoughtText.fontSize = 48;
            _thoughtText.characterSize = 0.018f;
            _thoughtText.anchor = TextAnchor.MiddleCenter;
            _thoughtText.alignment = TextAlignment.Center;
            _thoughtText.color = new Color(0.15f, 0.15f, 0.18f);

            _thoughtBubble.SetActive(false);
            _thoughtScale = 0f;
        }

        void BuildConversationIndicator()
        {
            var indicator = new GameObject("ConversationIndicator");
            indicator.transform.SetParent(transform, false);
            indicator.transform.localPosition = new Vector3(0f, UiHeight(1.4f), 0f);

            _conversationBubble = GameObject.CreatePrimitive(PrimitiveType.Sphere).transform;
            _conversationBubble.name = "Bubble";
            _conversationBubble.SetParent(indicator.transform, false);
            PrimitiveUtils.DestroyObj(_conversationBubble.GetComponent<Collider>());
            _conversationBubble.localScale = new Vector3(0.5f, 0.36f, 0.32f);
            _conversationRenderer = _conversationBubble.GetComponent<Renderer>();
            _conversationMat = PrimitiveUtils.ColoredMaterial(new Color(1f, 0.95f, 0.55f));
            _conversationRenderer.sharedMaterial = _conversationMat;

            var tail = GameObject.CreatePrimitive(PrimitiveType.Sphere).transform;
            tail.name = "Tail";
            tail.SetParent(indicator.transform, false);
            PrimitiveUtils.DestroyObj(tail.GetComponent<Collider>());
            tail.localPosition = new Vector3(-0.1f, -0.22f, 0.1f);
            tail.localScale = new Vector3(0.16f, 0.16f, 0.16f);
            tail.GetComponent<Renderer>().sharedMaterial = _conversationMat;

            _conversationGlyphText = indicator.AddComponent<TextMesh>();
            _conversationGlyphText.font = DefaultFont();
            _conversationGlyphText.text = conversationGlyph;
            _conversationGlyphText.fontSize = 56;
            _conversationGlyphText.characterSize = 0.014f;
            _conversationGlyphText.anchor = TextAnchor.MiddleCenter;
            _conversationGlyphText.alignment = TextAlignment.Center;
            _conversationGlyphText.color = new Color(0.35f, 0.3f, 0.05f);

            indicator.SetActive(false);
            _conversationScale = 0f;
        }

        void BuildEmotionIndicator()
        {
            _emotionIndicator = GameObject.CreatePrimitive(PrimitiveType.Sphere).transform;
            _emotionIndicator.name = "EmotionIndicator";
            _emotionIndicator.SetParent(transform, false);
            _emotionIndicator.localPosition = new Vector3(0.55f, UiHeight(0.5f), 0f);
            _emotionIndicator.localScale = Vector3.one * 0.22f;
            PrimitiveUtils.DestroyObj(_emotionIndicator.GetComponent<Collider>());
            _emotionRenderer = _emotionIndicator.GetComponent<Renderer>();
            _emotionMat = PrimitiveUtils.ColoredMaterial(Color.clear);
            _emotionRenderer.sharedMaterial = _emotionMat;
            _emotionIndicator.gameObject.SetActive(showEmotion);
        }

        static Font DefaultFont()
        {
            var font = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            if (font == null)
                font = Resources.GetBuiltinResource<Font>("Arial.ttf");
            return font;
        }

        // ------------------------------------------------------------------
        // Per-frame update
        // ------------------------------------------------------------------

        void Update()
        {
            Tick();
        }

        /// <summary>Per-frame update, public so EditMode tests can drive it directly.</summary>
        public void Tick()
        {
            EnsureBuilt();
            UpdatePosition();
            UpdateFacing();

            if (State == null)
            {
                UpdateBillboards();
                return;
            }

            UpdatePose(State);
            UpdateConversation(State);
            UpdateThought(State);
            UpdateEmotion(State);
            UpdateBillboards();
        }

        void UpdatePosition()
        {
            transform.position = Vector3.SmoothDamp(transform.position, TargetPosition, ref _velocity, Mathf.Max(0.01f, smoothTime));
        }

        void UpdateFacing()
        {
            float targetYaw = _currentYaw;
            if (HasFacing)
            {
                Vector3 dir = FacingPosition - transform.position;
                dir.y = 0f;
                if (dir.sqrMagnitude > facingDeadzone)
                {
                    targetYaw = Mathf.Atan2(dir.x, dir.z) * Mathf.Rad2Deg;
                }
            }
            _currentYaw = Mathf.MoveTowardsAngle(_currentYaw, targetYaw, rotationSpeed * 360f * Time.deltaTime);
            if (CharacterModel != null)
                CharacterModel.rotation = Quaternion.Euler(rotationOffset) * Quaternion.Euler(0f, _currentYaw, 0f);
        }

        void UpdatePose(AnimationStateData state)
        {
            string pose = string.IsNullOrEmpty(state.pose) ? "idle" : state.pose;

            if (_rig != null)
                ProceduralAnimator.Apply(_rig, pose, state.moving, state.tone, Time.time);

            ApplyAnimator(state);
        }

        /// <summary>
        /// Bridges the pose into the Animator. Safe when the Animator is missing,
        /// has no controller, or does not contain the requested state — in which
        /// case it silently does nothing (the fallback visual still works).
        /// </summary>
        void ApplyAnimator(AnimationStateData state)
        {
            if (Animator == null || Animator.runtimeAnimatorController == null)
                return;
            try
            {
                string stateName = PoseMapper.MapAnimatorState(state.pose);
                if (Animator.HasState(0, Animator.StringToHash(stateName)))
                    Animator.CrossFadeInFixedTime(stateName, 0.15f, 0);
                if (HasParameter(Animator, "Moving"))
                    Animator.SetBool("Moving", state.moving);
            }
            catch (System.Exception)
            {
                // Animator misconfigured (e.g. no Avatar / bad controller).
                // Pose styling and movement still render via the fallback path.
            }
        }

        static bool HasParameter(Animator animator, string name)
        {
            var parameters = animator.parameters;
            if (parameters == null) return false;
            for (int i = 0; i < parameters.Length; i++)
                if (parameters[i].name == name)
                    return true;
            return false;
        }

        void UpdateConversation(AnimationStateData state)
        {
            if (_conversationBubble == null) return;
            bool show = state.in_conversation && showConversationIndicator;
            float target = show ? 1f : 0f;
            _conversationScale = Mathf.MoveTowards(_conversationScale, target, Time.deltaTime * 6f);
            _conversationBubble.parent.gameObject.SetActive(_conversationScale > 0.01f);
            _conversationBubble.parent.localScale = Vector3.one * Mathf.Max(0.01f, _conversationScale);
            if (_conversationMat != null)
                _conversationMat.color = new Color(1f, 0.95f, 0.55f);
        }

        void UpdateThought(AnimationStateData state)
        {
            if (_thoughtBubble == null) return;
            bool hasThought = showThoughtBubble && !string.IsNullOrEmpty(state.thought);
            _thoughtText.text = hasThought ? ThoughtBubble.Truncate(state.thought, thoughtMaxLength) : "";
            float target = hasThought ? 1f : 0f;
            _thoughtScale = Mathf.MoveTowards(_thoughtScale, target, Time.deltaTime * 6f);
            _thoughtBubble.SetActive(_thoughtScale > 0.01f);
            _thoughtBubble.transform.localScale = Vector3.one * Mathf.Max(0.01f, _thoughtScale);
        }

        void UpdateEmotion(AnimationStateData state)
        {
            if (_emotionIndicator == null) return;
            bool show = showEmotion && !string.IsNullOrEmpty(state.emotion);
            _emotionIndicator.gameObject.SetActive(show);
            if (_emotionMat != null && show)
                _emotionMat.color = EmotionColor(state.emotion);
        }

        /// <summary>Deterministic presentation-only emotion tint.</summary>
        public static Color EmotionColor(string emotion)
        {
            switch (emotion)
            {
                case "happy":   return new Color(1f, 0.95f, 0.25f);
                case "hungry":  return new Color(1f, 0.6f, 0.2f);
                case "tired":   return new Color(0.6f, 0.4f, 1f);
                case "lonely":  return new Color(0.5f, 0.7f, 1f);
                case "stressed":return new Color(1f, 0.2f, 0.2f);
                case "calm":    return new Color(0.55f, 0.85f, 0.7f);
                case "content": return new Color(0.6f, 1f, 0.6f);
                default:        return new Color(0.8f, 0.8f, 0.8f);
            }
        }

        void UpdateBillboards()
        {
            if (_cam == null)
                _cam = Camera.main;
            if (_cam == null)
                return;
            Vector3 camPos = _cam.transform.position;
            RotateBillboard(_nameLabel, camPos);
            ScaleNameLabel(camPos);
            RotateBillboard(_professionLabel, camPos);
            RotateBillboard(_thoughtBubble, camPos);
            if (_conversationBubble != null)
                RotateBillboard(_conversationBubble.parent.gameObject, camPos);
            if (_emotionIndicator != null)
                RotateBillboard(_emotionIndicator.gameObject, camPos);
        }

        /// <summary>
        /// Name labels scale up with distance so they stay legible from afar and
        /// unobtrusive up close. Scale is a deterministic function of distance.
        /// </summary>
        void ScaleNameLabel(Vector3 camPos)
        {
            if (_nameLabel == null) return;
            float dist = Vector3.Distance(camPos, _nameLabel.transform.position);
            float s = Mathf.Clamp(dist * 0.012f, 1f, 2.4f);
            _nameLabel.transform.localScale = Vector3.one * s;
        }

        static void RotateBillboard(GameObject go, Vector3 camPos)
        {
            if (go == null) return;
            Vector3 dir = camPos - go.transform.position;
            dir.y = 0f;
            if (dir.sqrMagnitude > 0.0001f)
                go.transform.rotation = Quaternion.LookRotation(dir.normalized);
        }
    }

    /// <summary>Pure thought-text helpers (no simulation, no LLM).</summary>
    public static class ThoughtBubble
    {
        /// <summary>Trims a thought to fit the bubble, appending an ellipsis.</summary>
        public static string Truncate(string text, int maxLength)
        {
            if (string.IsNullOrEmpty(text))
                return "";
            if (text.Length <= maxLength)
                return text;
            return text.Substring(0, Mathf.Max(1, maxLength - 1)) + "\u2026";
        }
    }
}