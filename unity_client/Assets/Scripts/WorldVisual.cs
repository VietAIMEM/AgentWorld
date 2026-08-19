using System.Collections.Generic;
using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Builds and updates the visualization of the authoritative Python world:
    /// ground, location markers, object markers and NPC GameObjects. Purely
    /// presentational — contains no decision-making, needs, goals, routines,
    /// conversations, economy or pathfinding logic.
    /// </summary>
    public class WorldVisual : MonoBehaviour
    {
        public TransportClient transport;
        public GameObject characterPrefab;
        public float worldScale = 1f;
        public float npcSmoothTime = 0.3f;

        private readonly Dictionary<string, Vector3> _locationPos = new Dictionary<string, Vector3>();
        private readonly Dictionary<string, GameObject> _locationMarkers = new Dictionary<string, GameObject>();
        private readonly Dictionary<string, GameObject> _objectMarkers = new Dictionary<string, GameObject>();
        private readonly Dictionary<string, NpcVisual> _npcs = new Dictionary<string, NpcVisual>();

        void Start()
        {
            if (transport == null)
                transport = FindObjectOfType<TransportClient>();
            if (transport == null)
                transport = gameObject.AddComponent<TransportClient>();
            CourtyardPresenter.BuildEnvironment(worldScale);
        }

        void BuildGround()
        {
            CourtyardPresenter.BuildEnvironment(worldScale);
        }

        void Update()
        {
            if (transport == null || transport.Latest == null) return;
            var payload = transport.Latest;
            RebuildLocations(payload);
            RebuildObjects(payload);
            ReconcileNpcs(payload);
            ApplyNpcs(payload);
            if (transport.LatestInteraction != null)
                ApplyInteractionPresentation(transport.LatestInteraction);
        }

        void RebuildLocations(WorldPayload payload)
        {
            if (payload.locations == null) return;
            var seen = new HashSet<string>();
            foreach (var loc in payload.locations)
            {
                seen.Add(loc.location_id);
                Vector3 pos = new Vector3(loc.x * worldScale, 0f, loc.z * worldScale);
                _locationPos[loc.location_id] = pos;
                if (_locationMarkers.ContainsKey(loc.location_id)) continue;

                var marker = new GameObject("Loc_" + loc.location_id);
                CourtyardPresenter.BuildLocationDecor(marker, loc.location_id, loc.name, loc.type, pos);
                _locationMarkers[loc.location_id] = marker;
            }
            foreach (var key in new List<string>(_locationMarkers.Keys))
                if (!seen.Contains(key))
                {
                    Destroy(_locationMarkers[key]);
                    _locationMarkers.Remove(key);
                }
        }

        void RebuildObjects(WorldPayload payload)
        {
            var seen = new HashSet<string>();
            if (payload.objects != null)
            {
                foreach (var obj in payload.objects)
                {
                    seen.Add(obj.object_id);
                    if (_objectMarkers.ContainsKey(obj.object_id)) continue;
                    Vector3 pos;
                    if (!_locationPos.TryGetValue(obj.location_id, out pos)) continue;
                    var marker = new GameObject("Obj_" + obj.object_id);
                    CourtyardPresenter.BuildObjectProp(marker, obj.object_id, obj.object_type, pos);
                    _objectMarkers[obj.object_id] = marker;
                }
            }
            foreach (var key in new List<string>(_objectMarkers.Keys))
                if (!seen.Contains(key))
                {
                    Destroy(_objectMarkers[key]);
                    _objectMarkers.Remove(key);
                }
        }

        /// <summary>
        /// Pure diff between the incoming snapshot's NPC ids and the current
        /// visual dictionary. Returns the ids to create and the ids to remove
        /// so NPC GameObjects are created once and reused across snapshots.
        /// </summary>
        public static void PlanReconciliation(
            string[] incomingIds,
            Dictionary<string, NpcVisual> current,
            List<string> toCreate,
            List<string> toRemove)
        {
            var seen = new HashSet<string>();
            if (incomingIds != null)
            {
                foreach (var id in incomingIds)
                {
                    if (string.IsNullOrEmpty(id)) continue;
                    seen.Add(id);
                    if (!current.ContainsKey(id))
                        toCreate.Add(id);
                }
            }
            foreach (var key in current.Keys)
                if (!seen.Contains(key))
                    toRemove.Add(key);
        }

        void ReconcileNpcs(WorldPayload payload)
        {
            var toCreate = new List<string>();
            var toRemove = new List<string>();
            string[] ids = payload.npcs != null
                ? System.Array.ConvertAll(payload.npcs, e => e.npc_id)
                : new string[0];
            PlanReconciliation(ids, _npcs, toCreate, toRemove);

            foreach (var entry in payload.npcs ?? new AnimationStateData[0])
            {
                if (_npcs.ContainsKey(entry.npc_id)) continue;
                var go = new GameObject("NPC_" + entry.npc_id);
                go.transform.position = Vector3.zero;
                var visual = go.AddComponent<NpcVisual>();
                visual.characterPrefab = characterPrefab;
                visual.smoothTime = npcSmoothTime;
                visual.Init(entry.npc_id, entry.name);
                _npcs[entry.npc_id] = visual;
            }
            foreach (var id in toRemove)
            {
                Destroy(_npcs[id].gameObject);
                _npcs.Remove(id);
            }
        }

        void ApplyNpcs(WorldPayload payload)
        {
            foreach (var entry in payload.npcs)
            {
                NpcVisual visual;
                if (!_npcs.TryGetValue(entry.npc_id, out visual)) continue;

                Vector3 target = NpcPosition(entry);

                Vector3 facingPos;
                bool hasFacing = FacingResolver.TryResolvePosition(
                    entry,
                    npcId => _npcs.ContainsKey(npcId),
                    objId => _objectMarkers.ContainsKey(objId),
                    locId => _locationPos.ContainsKey(locId),
                    npcId => _npcs[npcId].transform.position,
                    objId => _objectMarkers[objId].transform.position,
                    locId => _locationPos[locId],
                    out facingPos);

                visual.Apply(entry, target, facingPos, hasFacing);
            }
        }

        Vector3 NpcPosition(AnimationStateData entry)
        {
            Vector3 pos;
            if (entry.target_location_id != null && _locationPos.TryGetValue(entry.target_location_id, out pos))
                return pos + Jitter(entry.npc_id, 2.2f);
            if (_locationPos.TryGetValue(entry.facing_location_id ?? "", out pos))
                return pos + Jitter(entry.npc_id, 2.2f);
            return Vector3.zero + Jitter(entry.npc_id, 2.2f);
        }

        /// <summary>Stable, deterministic per-NPC offset (never Unity's randomized hash).</summary>
        static Vector3 Jitter(string id, float radius)
        {
            int h = StableHash(id);
            float angle = (h % 360) * Mathf.Deg2Rad;
            float r = (h >> 3) % 1000 / 1000f * radius;
            return new Vector3(Mathf.Cos(angle) * r, 0f, Mathf.Sin(angle) * r);
        }

        static int StableHash(string s)
        {
            int h = 17;
            foreach (char c in s)
                h = h * 31 + c;
            return h;
        }

        public NpcVisual SelectedNpc(string npcId)
        {
            if (string.IsNullOrEmpty(npcId)) return null;
            NpcVisual visual;
            return _npcs.TryGetValue(npcId, out visual) ? visual : null;
        }

        /// <summary>
        /// Toggles the "SelectionRing" ground disc under an object marker.
        /// Purely visual; never mutates simulation state.
        /// </summary>
        public void SetObjectHighlighted(string objectId, bool highlighted)
        {
            if (string.IsNullOrEmpty(objectId)) return;
            GameObject marker;
            if (!_objectMarkers.TryGetValue(objectId, out marker)) return;
            var ring = marker.transform.Find("SelectionRing");
            if (ring != null)
                ring.gameObject.SetActive(highlighted);
        }

        /// <summary>
        /// Toggles the "SelectionRing" ground disc under a location marker.
        /// </summary>
        public void SetLocationHighlighted(string locationId, bool highlighted)
        {
            if (string.IsNullOrEmpty(locationId)) return;
            GameObject marker;
            if (!_locationMarkers.TryGetValue(locationId, out marker)) return;
            var ring = marker.transform.Find("SelectionRing");
            if (ring != null)
                ring.gameObject.SetActive(highlighted);
        }

        /// <summary>Deselects every NPC's ground ring (used when selection changes).</summary>
        public void ClearNpcSelections(string exceptId)
        {
            foreach (var pair in _npcs)
            {
                if (pair.Key == exceptId) continue;
                pair.Value.SetSelected(false);
            }
        }

        public void ClearObjectSelections(string exceptId)
        {
            foreach (var pair in _objectMarkers)
            {
                if (pair.Key == exceptId) continue;
                var ring = pair.Value.transform.Find("SelectionRing");
                if (ring != null)
                    ring.gameObject.SetActive(false);
            }
        }

        public void ClearLocationSelections(string exceptId)
        {
            foreach (var pair in _locationMarkers)
            {
                if (pair.Key == exceptId) continue;
                var ring = pair.Value.transform.Find("SelectionRing");
                if (ring != null)
                    ring.gameObject.SetActive(false);
            }
        }

        /// <summary>
        /// Reflects the latest authoritative interaction payload onto visuals:
        /// the inspected NPC's profession label. Presentation only.
        /// </summary>
        public void ApplyInteractionPresentation(InteractionPayload payload)
        {
            if (payload == null || payload.target == null) return;
            var visual = SelectedNpc(payload.target.npc_id);
            if (visual != null)
                visual.SetProfession(payload.target.job);
        }

        public NpcVisual NpcAtScreenPoint(Vector2 screenPos, Camera cam)
        {
            Ray ray = cam.ScreenPointToRay(screenPos);
            RaycastHit hit;
            if (!Physics.Raycast(ray, out hit, 500f)) return null;
            return hit.collider.GetComponentInParent<NpcVisual>();
        }
    }
}