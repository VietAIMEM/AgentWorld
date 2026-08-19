# Unity 3D Interactive Client (NPC AI v0.6 / Phase 12)

Presentation + interaction Unity client for the authoritative Python simulation
in `../project/world_sim`. Unity contains **zero** AI/simulation logic; it only
renders the `world_sim.presentation.animation.AnimationState` contract and the
`/interaction` payload delivered over localhost HTTP, and sends explicit player
commands that Python validates.

## Architecture

```
Python (authoritative)                          Unity (presentation + input)
  Simulation / ManagedSimulation                  WorldVisual (terrain, locations,
      | tick-by-tick                               objects, NPC GameObjects)
  build_payload(world) ---------JSON--------->     GET /snapshot  (latest payload)
  PlayerSession (player pos/target/conversation)   GET /interaction (player context)
      ^                                            POST /command (player commands)
  handle_command: validate + respond  <-----------  POST /control  (play/pause/step/reset)
      |                                              |
  world_sim.presentation.transport                  PlayerController (WASD/camera)
  (SnapshotHTTPServer, localhost)                   InteractionSystem (raycast select)
                                                    ConversationUI / TimeUI / panels
```

- The **only** simulation-to-rendering contract is `AnimationState` (mirrored in
  `Assets/Scripts/Models.cs`). Interaction context mirrors `PlayerSession` via
  the `/interaction` payload.
- Unity never decides whether an interaction is valid — every command is
  validated against authoritative state Python-side and may be rejected.
- Transport is stdlib HTTP on `127.0.0.1:8770`. No database, no cloud, no
  WebSocket.

## Running

1. Start the Python server (from the `project/` directory):

   ```
   python -m world_sim.presentation.transport --seed 42 --days 0
   ```

   `--days 0` = run indefinitely (live mode). Options: `--host`, `--port`,
   `--config`, `--npcs`, `--seed`, `--days`.

2. Open this folder in Unity (any recent 2022.3+ LTS). Click the menu
   **NPC AI → Create Visualization Scene**. If your Unity version differs,
   `ProjectSettings/ProjectVersion.txt` is only cosmetic.

3. Press Play. The world builds from the first snapshot; NPCs, locations and
   objects appear. Use the top-left buttons: **Connect / Play / Pause / Step /
   Reset**.

## Controls

| Input                    | Action                                          |
|--------------------------|-------------------------------------------------|
| `WASD`                   | Move the player (third-person)                  |
| Mouse                    | Orbit the camera (right-click to look)          |
| Mouse wheel              | Zoom the camera (2–14 units, smoothed)          |
| `Shift` + `WASD`         | Sprint                                          |
| Left-click               | Select an NPC / object / location (raycast)     |
| `E`                      | Talk to selected NPC / inspect selected object  |
| `Escape`                 | Lock/unlock cursor (menu)                       |

Conversation options (**Ask about work / Ask about this place / Goodbye**) are
sent as `player_talk` commands. **Follow** is intentionally disabled (no
NPC-follow AI in this phase).

## Protocol

`GET /snapshot` → JSON payload:

```json
{
  "version": 1,
  "tick": 1234,
  "day": 8,
  "hour": 13,
  "minute": 40,
  "npcs": [ { "npc_id": "...", "pose": "walk", "moving": true, ... } ],
  "locations": [ { "location_id": "...", "name": "...", "type": "social", "x": 12.3, "z": 45.6 } ],
  "objects": [ { "object_id": "...", "name": "...", "location_id": "...", "object_type": "stall", "state": "available" } ]
}
```

`GET /interaction` → JSON payload:

```json
{
  "version": 1, "tick": 1234, "day": 8, "hour": 13, "minute": 40,
  "player": { "x": 12.3, "z": 45.6, "location_id": "settlement_0_market" },
  "location": { "location_id": "...", "name": "...", "type": "market", "settlement_id": "settlement_0",
                "npc_count": 3, "npc_ids": ["npc_001"], "objects": [...], "activities": [...] },
  "nearby": { "npc_ids": ["npc_001"], "object_ids": ["obj_..."] },
  "target": { "npc_id": "...", "name": "...", "job": "...", "behavior_state": "...", "needs": {...}, ... },
  "object": { "object_id": "...", "name": "...", "state": "available", "interactions": [...] },
  "conversation": { "active": true, "npc_id": "...", "npc_name": "...", "text": "...", "category": "...",
                    "emotion": null, "topic": null, "llm": false,
                    "options": [ {"key":"work","label":"Ask about work"}, ... ] },
  "chatter": [ { "conversation_id": "...", "tick": 123, "speaker_name": "...", "listener_name": "...",
                 "dialogue": "...", "emotion": "content", "topic": "weather", "source": "llm" } ]
}
```

`POST /command` → validated command. Types: `player_update`, `player_talk`,
`player_inspect`, `player_observe`, `player_interact`. Invalid targets are
rejected (HTTP 200 with `{"ok": false, "error": "..."}`); malformed requests
are HTTP 400.

`GET /healthz` → `{"ok": true}`. `POST /control {"action":"play"}` (also
`pause`, `step`, `reset`).

## Pose mapping

`PoseMapper.cs` maps every pose from the Python contract
(`idle, walk, work, eat, buy, sleep, sit, stand, talk, listen, wave, inspect,
stretch, interact, dead`) to a deterministic Animator state name
(`Idle, Walk, Work, Eat, Buy, Sleep, Sit, Stand, Talk, Listen, Wave, Inspect,
Stretch, Interact, Dead`). Unknown poses fall back to `Idle`. The same mapper
also produces a deterministic placeholder color / scale / rotation per pose for
the primitive fallback (no animation assets required).

## Character system (Phase 11)

`NpcVisual` is the per-NPC presentation wrapper. Hierarchy:

```
NPC_<id> (NpcVisual)
 ├── CharacterRoot          (scale, ground offset, facing yaw)
 │    └── CharacterModel    (humanoid prefab OR procedural humanoid rig)
 │         └── RigRoot      (pivot for lay-down poses)
 │              └── Hips → Torso → Chest → Head / Shoulders→Elbows→Hands
 │                       HipL/R → KneeL/R → FootL/R
 ├── ShadowDisc             (readability)
 ├── NameLabel              (world-space TextMesh, billboarded, distance-scaled)
 ├── ThoughtBubble          (world-space TextMesh, billboarded, fades in/out)
 ├── ConversationIndicator  (chat bubble + 💬 glyph, fades in/out)
 └── EmotionIndicator       (subtle colored dot; configurable)
```

- **Procedural humanoid (default, no assets)** — when no prefab is assigned, a
  stylized humanoid is built from Unity primitives (`ProceduralRig`): robe,
  tunic or sash torso, arms, legs, head, hair style, conical hat / head wrap.
  Every NPC's look is derived **only from its id** via `NpcAppearance.Generate`
  (deterministic palette + stable hash), so the same NPC always looks the same
  across restarts and no two NPCs are forced to be clones.
- **Procedural animation (no Animator Controller needed)** —
  `ProceduralAnimator` is a pure, time-parameterized pose function
  (`ForState`) that animates the rig's joints for every pose: idle breathing,
  walk stride (opposite leg/arm swing), work, eat (hand to mouth), buy, sit
  (bent knees + lowered hips), sleep/dead (rig lays down), talk/listen (head
  nod/tilt), wave, inspect, stretch, interact. It is deterministic and
  testable — the same `(pose, moving, time)` always produces the same pose.
  Transitions between poses are smoothed per rig (`poseBlendSpeed`,
  `hipsBlendSpeed`) so poses never pop; sitting drops the hips to ~bench height
  with knees bent (feet planted) and lying/dead rotates the rig onto the ground
  (`rootHeightOffset` keeps the body resting on the floor).
- **Selection & profession** — `SetSelected` toggles a ground highlight ring
  under the NPC; `SetProfession(job)` shows a styled profession line under the
  name (fed from the `/interaction` payload `target.job` when the player
  inspects an NPC). Name labels now sit on a dark backing plate for legibility
  and scale with distance.
- **Prefab path still works** — assign `WorldVisual.characterPrefab` (or the
  per-NPC `NpcVisual.characterPrefab`) any humanoid prefab (auto-detected from
  `Assets/Resources/Models/NPC_Humanoid.prefab`). The pose is then bridged to
  the Animator via `PoseMapper.MapAnimatorState` +
  `Animator.CrossFadeInFixedTime`; a `Moving` bool is driven from `state.moving`.
  Missing Animator / controller / state never crash and fall back to the rig.
- **Facing** — `FacingResolver` resolves the visual target with priority
  conversation partner NPC → interaction object → movement/location target.
  The character turns smoothly with an anti-jitter deadzone; the authoritative
  Python `facing_*` fields are never mutated.
- **Conversation / thought / emotion / name** — all rendered from the existing
  snapshot payload (`in_conversation`, `thought`, `emotion`, `name`). Name
  labels scale up with distance so they stay legible from afar. No Unity-side
  AI, LLM calls or conversation logic.
- **Config** — `NpcVisual` exposes `characterHeight`, `characterScale`,
  `groundOffset`, `rotationOffset`, `showNameLabel`, `showEmotion`,
  `showThoughtBubble`, `showConversationIndicator`, `thoughtMaxLength`.
- **Performance** — NPC GameObjects are created once and reused; `WorldVisual`
  keeps ID-keyed dictionaries and only creates/destroys on add/remove diffs
  (`PlanReconciliation`), so 20 NPCs / 31 locations / 68 objects render with no
  per-frame searches or allocations of objects.

## World environment (Phase 11)

`CourtyardPresenter` builds an ancient-Chinese courtyard from primitives:
sandy ground + paved plaza, stone paths from the plaza to each gate,
deterministic flower/grass patches, perimeter walls with gates and lantern
posts, and a ring of courtyard trees. Each location gets a themed structure by
type — residence/social/workplace buildings (two-tier pagoda roofs, corner
posts, framed glowing windows), market stalls with canopies + banners + goods,
tavern benches + fire + barrels, farm well/crates/plants/fences/hay, natural
groves with bushes and rocks — offset so the marker center stays open for NPCs.
Lanterns, embers and lit windows carry a `LanternGlow` component that fades a
warm glow in at night. Every `Obj_*` / `Loc_*` marker keeps the exact names the
Python layer expects and gets a hidden `SelectionRing` disc that
`WorldVisual.SetObjectHighlighted` / `SetLocationHighlighted` toggle on select;
props are placed deterministically from their id (no overlap, stable layout).
The camera (`PlayerController`) zooms with the mouse wheel (smoothed, clamped),
follows smoothly, raycasts against walls/trees/ground so it never clips through
geometry or the player, and clamps pitch to −15°..65°.

## Day / night cycle (Phase 12)

`DayNightCycle` reads the authoritative `day/hour/minute` from the snapshot
every frame and applies a deterministic `SunState` computed by pure
`DayNightMath` (1 at noon, 0 at midnight): sun rotation + intensity + color,
ambient light, exponential-squared fog color/density, and the camera background
(sky) color. When `dayFactor < LanternThreshold` the lanterns come on: every
`LanternGlow` in the scene (self-registered registry, no per-frame scans)
brightens its source and activates its `Glow` disc. All values are pure
functions of the clock — no randomness, no simulation mutation — and verified by
`DayNightCycleTests`.

## Interaction visuals (Phase 12)

`InteractionSystem` adds a screen-center crosshair and a contextual prompt at
the bottom of the screen: an NPC shows first name + profession (`E — Talk`),
objects show name + type + action hint (`E — Sit`/`Use`/`Tend`/`Inspect`), and
locations show name + type. Prompts are produced by pure `InteractionVisual`
helpers (unit-tested, deterministic). Selected targets get a ground highlight
ring (NPCs via `NpcVisual.SetSelected`, objects/locations via WorldVisual).
`ConversationUI` now shows an explicit **Goodbye** button when the conversation
offers no options so the player can always end it.

## Tests

EditMode tests live in `Assets/Tests/EditMode` (run via the Unity Test Runner or
batch mode): pose mapping for every valid pose, unknown-pose fallback, missing
Animator / missing prefab resilience, moving→Walk, conversation pose mapping,
facing resolution priorities, thought show/hide + truncation, emotion safety,
NPC id association, snapshot dedup / removal planning, deterministic appearance
per NPC id, procedural animation correctness (idle breathing, walk leg/arm
swing, sit knee bend + hip drop, lying/dead ground contact, pose-transition
interpolation, first-apply snap, determinism, rig integrity), day/night math
(noon bright, midnight dark + lanterns, dawn ramp, determinism, clock-not-day),
interaction prompt helpers (names, capitalization, per-type action hints,
determinism), NPC selection ring toggling, and profession label show/hide.

## Determinism

- Unity and the player layer consume **zero** simulation RNG and never mutate
  simulation state. Player commands only mutate the Python-side `PlayerSession`.
- Same seed + same commands ⇒ identical final save (byte-identical, verified by
  the phase 8 audit). Opening/closing the Unity client does not alter sim state.
- Rendering the same `AnimationState` sequence twice yields the same visual
  state (all transforms/colors are deterministic functions of the payload).
- Connected vs disconnected runs are byte-identical (verified by tests).

## Scope

No LLM SDK, multiplayer, non-localhost networking, combat, quests, inventory UI,
player economy, physics simulation, Unity pathfinding, Unity-side AI, economy
UI, voice/speech, or save/load in Unity. Player movement is purely visual; all
validity decisions happen in Python. When the optional Python-side LLM layer is
enabled (`behavior.llm.enabled`), NPC dialogue/emotion/topic and thought
indicators arrive as additive fields in the same payloads; Unity only renders
them and never makes LLM calls itself. Procedural animation is a visual
placeholder (no root motion / collision-corrected contact) — the authoritative
poses, positions and facing come from Python.