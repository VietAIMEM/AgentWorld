using System;
using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Data model mirroring the Python-only simulation-to-rendering contract:
    /// world_sim.presentation.animation.AnimationState. Unity never reads Python
    /// internals; it only consumes these fields from the transport payload.
    /// </summary>
    [Serializable]
    public class AnimationStateData
    {
        public string npc_id;
        public string name;
        public string pose;
        public bool moving;
        public string behavior_state;
        public string facing_location_id;
        public string facing_object_id;
        public string facing_npc_id;
        public string target_location_id;
        public string target_npc_id;
        public string target_object_id;
        public string emotion;
        public bool in_conversation;
        public string intent;
        public float pose_progress;
        public string thought;
        public string tone;
    }

    [Serializable]
    public class LocationData
    {
        public string location_id;
        public string name;
        public string type;
        public float x;
        public float z;
    }

    [Serializable]
    public class ObjectData
    {
        public string object_id;
        public string name;
        public string location_id;
        public string object_type;
        public string state;
    }

    [Serializable]
    public class WorldPayload
    {
        public int version;
        public int tick;
        public int day;
        public int hour;
        public int minute;
        public AnimationStateData[] npcs;
        public LocationData[] locations;
        public ObjectData[] objects;
    }

    [Serializable]
    public class PlayerData
    {
        public float x;
        public float z;
        public string location_id;
    }

    [Serializable]
    public class NearbyData
    {
        public string[] npc_ids;
        public string[] object_ids;
    }

    [Serializable]
    public class ObjectSummaryData
    {
        public string object_id;
        public string name;
        public string object_type;
        public string state;
    }

    [Serializable]
    public class LocationDetailData
    {
        public string location_id;
        public string name;
        public string type;
        public string settlement_id;
        public int npc_count;
        public string[] npc_ids;
        public ObjectSummaryData[] objects;
        public string[] activities;
    }

    [Serializable]
    public class NeedsData
    {
        public float hunger;
        public float energy;
        public float social;
    }

    [Serializable]
    public class RelationshipData
    {
        public string npc_id;
        public int value;
    }

    [Serializable]
    public class TargetData
    {
        public string npc_id;
        public string name;
        public int age;
        public string job;
        public string settlement_id;
        public string location_id;
        public bool alive;
        public string behavior_state;
        public string pose;
        public string emotion;
        public string intent;
        public string goal;
        public string action;
        public float money;
        public NeedsData needs;
        public RelationshipData[] relationships;
    }

    [Serializable]
    public class ObjectDetailData
    {
        public string object_id;
        public string name;
        public string object_type;
        public string state;
        public string location_id;
        public string[] interactions;
    }

    [Serializable]
    public class ConversationOptionData
    {
        public string key;
        public string label;
    }

    [Serializable]
    public class ConversationData
    {
        public bool active;
        public string npc_id;
        public string npc_name;
        public string text;
        public string category;
        public string emotion;
        public string topic;
        public bool llm;
        public ConversationOptionData[] options;
    }

    [Serializable]
    public class ChatterEntryData
    {
        public string conversation_id;
        public int tick;
        public string speaker_id;
        public string speaker_name;
        public string listener_id;
        public string listener_name;
        public string dialogue;
        public string emotion;
        public string topic;
        public string source;
    }

    [Serializable]
    public class InteractionPayload
    {
        public int version;
        public int tick;
        public int day;
        public int hour;
        public int minute;
        public PlayerData player;
        public LocationDetailData location;
        public NearbyData nearby;
        public TargetData target;
        public ObjectDetailData @object;
        public ConversationData conversation;
        public ChatterEntryData[] chatter;
    }
}