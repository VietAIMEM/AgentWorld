using System;
using UnityEngine;

namespace NpcAi.Client
{
    public enum FacingKind
    {
        None,
        Npc,
        Object,
        Location
    }

    /// <summary>
    /// Resolved visual facing target. Purely presentational — never mutates any
    /// simulation field (the authoritative Python AnimationState is untouched).
    /// </summary>
    public struct FacingTarget
    {
        public FacingKind kind;
        public string id;

        public static FacingTarget None
        {
            get { return new FacingTarget { kind = FacingKind.None, id = null }; }
        }

        public bool IsValid
        {
            get { return kind != FacingKind.None && !string.IsNullOrEmpty(id); }
        }
    }

    /// <summary>
    /// Deterministic, pure facing resolution. Priority order (highest first):
    /// conversation partner NPC → interaction object → movement/location target.
    /// Targets that do not resolve against the known entity sets are skipped so
    /// the NPC never stares at thin air. Contains no animation or AI logic.
    /// </summary>
    public static class FacingResolver
    {
        /// <param name="hasNpc">True when the npc_id is a currently visualized NPC.</param>
        /// <param name="hasObject">True when the object_id is a currently visualized object.</param>
        /// <param name="hasLocation">True when the location_id is a currently visualized location.</param>
        public static FacingTarget Resolve(
            AnimationStateData state,
            Func<string, bool> hasNpc,
            Func<string, bool> hasObject,
            Func<string, bool> hasLocation)
        {
            if (state == null)
                return FacingTarget.None;

            // 1. Conversation partner NPC.
            if (hasNpc != null && !string.IsNullOrEmpty(state.facing_npc_id) && hasNpc(state.facing_npc_id))
                return new FacingTarget { kind = FacingKind.Npc, id = state.facing_npc_id };

            // 2. Interaction object.
            if (hasObject != null && !string.IsNullOrEmpty(state.facing_object_id) && hasObject(state.facing_object_id))
                return new FacingTarget { kind = FacingKind.Object, id = state.facing_object_id };

            // 3. Movement / location target.
            if (hasLocation != null && !string.IsNullOrEmpty(state.facing_location_id) && hasLocation(state.facing_location_id))
                return new FacingTarget { kind = FacingKind.Location, id = state.facing_location_id };
            if (hasLocation != null && !string.IsNullOrEmpty(state.target_location_id) && hasLocation(state.target_location_id))
                return new FacingTarget { kind = FacingKind.Location, id = state.target_location_id };

            // 4. Fallback to object target if an object is present but unfaced.
            if (hasObject != null && !string.IsNullOrEmpty(state.target_object_id) && hasObject(state.target_object_id))
                return new FacingTarget { kind = FacingKind.Object, id = state.target_object_id };

            return FacingTarget.None;
        }

        /// <summary>Resolves a facing target to its world position using provided lookups.</summary>
        public static bool TryResolvePosition(
            AnimationStateData state,
            Func<string, bool> hasNpc,
            Func<string, bool> hasObject,
            Func<string, bool> hasLocation,
            Func<string, Vector3> npcPos,
            Func<string, Vector3> objectPos,
            Func<string, Vector3> locationPos,
            out Vector3 position)
        {
            position = Vector3.zero;
            var target = Resolve(state, hasNpc, hasObject, hasLocation);
            if (!target.IsValid)
                return false;
            switch (target.kind)
            {
                case FacingKind.Npc:
                    if (npcPos == null) return false;
                    position = npcPos(target.id);
                    return true;
                case FacingKind.Object:
                    if (objectPos == null) return false;
                    position = objectPos(target.id);
                    return true;
                case FacingKind.Location:
                    if (locationPos == null) return false;
                    position = locationPos(target.id);
                    return true;
                default:
                    return false;
            }
        }
    }
}