"""LLM dialogue generation, validation, fallback, and integration.

This module is the only place the LLM layer turns context into text:

- ``generate_player_reply`` / ``generate_npc_exchange`` / ``generate_thought``
  produce optional LLM-sourced text with a deterministic fallback.
- ``validate_llm_response`` never trusts raw provider output: malformed JSON,
  invalid fields, empty/over-long dialogue, unknown emotions/topics all fall
  back to the deterministic response.
- ``LLMPlayerBridge`` / ``LLMConversationObserver`` / ``LLMThoughtWriter`` are
  presentation-side adapters. All provider calls go through an
  ``LLMExecutor`` worker thread; the simulation tick never blocks on LLM I/O.
- ``record_conversation_completed`` is the *only* explicit deterministic point
  where LLM dialogue may create a memory entry (a concise ``talked_with_npc``
  summary; the memory cap of 50 is enforced by ``Memory.add``).

The LLM never mutates needs, money, inventory, location, relationships,
memory (except through the explicit point above), goals, actions, economy,
clock, or RNG.
"""

from __future__ import annotations

import json
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from ..conversation import crc32
from .llm_cache import LLMCache
from .llm_client import (
    LLMError,
    LLMExecutor,
    LLMProvider,
    LLMRequest,
    OpenAICompatibleProvider,
)
from .llm_context import build_llm_context, _emotion as deterministic_emotion
from .llm_policy import LLMPolicy, llm_config, personality_instructions

SYSTEM_PROMPT_VERSION = 1
MAX_DIALOGUE_LENGTH = 300

KNOWN_EMOTIONS = frozenset(
    {"content", "happy", "calm", "worried", "hungry", "tired", "lonely", "stressed"}
)
KNOWN_TOPICS = frozenset(
    {
        "weather", "work", "food", "market", "family", "recent_event",
        "relationship", "place", "greeting", "farewell", "shopping",
        "resting", "socializing",
    }
)
KNOWN_FOLLOW_UPS = frozenset(
    {"work", "place", "farewell", "weather", "food", "market", "family", ""}
)

SYSTEM_PROMPT = (
    "You are roleplaying an NPC in a deterministic simulated world.\n"
    "Remain consistent with the provided character, memory, relationship, "
    "location, time and current activity.\n"
    "Never invent events that contradict the supplied context.\n"
    "Never claim to have moved, eaten, bought something, worked, slept, or "
    "changed relationships unless the context explicitly indicates it.\n"
    "Speak naturally and concisely (1-2 short sentences).\n"
    'Reply with ONLY a JSON object: {"dialogue": str, "emotion": str, '
    '"topic": str, "follow_up": str or null}.\n'
    "dialogue is the spoken line (or, for thoughts, a single short inner "
    "thought).\n"
    'emotion is one of: content, happy, calm, worried, hungry, tired, lonely, stressed.\n'
    'topic is one of: weather, work, food, market, family, recent_event, '
    "relationship, place, greeting, farewell.\n"
    'follow_up is one of: work, place, farewell, weather, food, market, family or null.'
)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass
class LLMResponse:
    dialogue: str
    emotion: str = "content"
    topic: Optional[str] = None
    follow_up: Optional[str] = None
    source: str = "llm"  # "llm" or "fallback"

    @property
    def llm(self) -> bool:
        return self.source == "llm"


def fingerprint(context: dict, kind: str, model: str = "", prompt_version: int = SYSTEM_PROMPT_VERSION) -> str:
    """Stable request fingerprint (context digest + identity fields)."""
    digest = crc32(
        json.dumps(context, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    )
    conv = context.get("conversation") or {}
    return "|".join(
        [
            str(prompt_version),
            kind,
            str(context.get("npc", {}).get("id", "")),
            str(conv.get("id") or ""),
            str(conv.get("topic") or ""),
            str(conv.get("partner") or ""),
            str(model or ""),
            str(digest),
        ]
    )


def _sanitize(text: str) -> str:
    return _CONTROL_CHARS.sub("", text).strip()


def validate_llm_response(raw: str, fallback: LLMResponse) -> LLMResponse:
    """Parse + validate provider JSON. Any failure returns ``fallback``."""
    if not isinstance(raw, str):
        return fallback
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        data = json.loads(text)
    except ValueError:
        return fallback
    if not isinstance(data, dict):
        return fallback

    dialogue = data.get("dialogue")
    if not isinstance(dialogue, str):
        return fallback
    dialogue = _sanitize(dialogue)
    if not dialogue or len(dialogue) > MAX_DIALOGUE_LENGTH:
        return fallback

    emotion = data.get("emotion", fallback.emotion)
    if emotion not in KNOWN_EMOTIONS:
        emotion = fallback.emotion

    topic = data.get("topic", fallback.topic)
    if topic is None:
        topic = fallback.topic
    if topic not in KNOWN_TOPICS:
        topic = fallback.topic

    follow_up = data.get("follow_up")
    if follow_up is None:
        follow_up = fallback.follow_up
    elif follow_up not in KNOWN_FOLLOW_UPS:
        follow_up = None

    return LLMResponse(
        dialogue=dialogue,
        emotion=emotion,
        topic=topic,
        follow_up=follow_up,
        source="llm",
    )


def build_request(npc, context: dict, config: dict, kind: str) -> LLMRequest:
    instructions = personality_instructions(npc.personality)
    if instructions:
        guidance = "Character guidance:\n" + "\n".join("- " + s for s in instructions)
    else:
        guidance = "Character guidance: - balanced, ordinary personality"
    kind_note = (
        "You are generating this NPC's private inner thought; keep it to one "
        "short sentence."
        if kind == "thought"
        else "You are generating dialogue this NPC would say out loud."
    )
    system = SYSTEM_PROMPT + "\n\n" + guidance + "\n" + kind_note
    user = json.dumps(context, sort_keys=True, ensure_ascii=False)
    return LLMRequest(
        system=system,
        user=user,
        temperature=float(config.get("temperature", 0.7)),
        max_tokens=int(config.get("max_tokens", 150)),
        model=config.get("model") or None,
        topic=context.get("conversation", {}).get("topic"),
    )


def _call_and_validate(npc, context, config, provider, topic, kind, fallback):
    request = build_request(npc, context, config, kind)
    raw = provider.generate(request)
    return validate_llm_response(raw, fallback)


def _deterministic_emotion(npc, world) -> str:
    return deterministic_emotion(npc, world)


def _line_for(npc, world, topic) -> str:
    hour = world.clock.hour
    pool = _TEMPLATES.get(topic, _TEMPLATES["greeting"])
    line = pool[crc32(npc.id + topic) % len(pool)]
    if hour >= 21 or hour < 6:
        line += " It is getting late."
    elif topic == "work" and hour >= 17:
        line += " The day is nearly done."
    return line


_TEMPLATES = {
    "weather": ("The weather has been fair lately.", "A fine day today, all around."),
    "work": ("I have been busy with work today.", "Work keeps me on my feet."),
    "food": ("I am glad to have enough food today.", "The pantry is stocked for now."),
    "market": ("The market has been quite busy.", "Trade has been brisk lately."),
    "family": ("Family matters most.", "I try to keep close with family."),
    "recent_event": ("Something notable is happening in the region.", "There is much to talk about these days."),
    "relationship": ("It is good to see a familiar face.", "We have known each other a while."),
    "place": ("This place suits me fine.", "It is a good spot to be."),
    "shopping": ("Just picking up a few supplies.", "A quick stop at the market."),
    "resting": ("Taking a well-earned rest.", "A moment of peace."),
    "socializing": ("Enjoying some company today.", "Good to be among people."),
    "greeting": ("Hello there.", "Good day to you.", "Ah, a visitor. Welcome."),
    "farewell": ("Take care.", "Goodbye for now.", "Until we meet again."),
}


def deterministic_response(npc, world, partner=None, topic=None, player=True) -> LLMResponse:
    """Fully deterministic fallback dialogue (no RNG, no provider)."""
    topic = topic if topic in _TEMPLATES else "greeting"
    emotion = _deterministic_emotion(npc, world)
    line = _line_for(npc, world, topic)
    follow_up = topic if topic in ("work", "place", "farewell", "weather", "food", "market", "family") else None
    return LLMResponse(dialogue=line, emotion=emotion, topic=topic, follow_up=follow_up, source="fallback")


def _background_reply(npc, context, config, provider, cache, fp, topic, fallback):
    try:
        resp = _call_and_validate(npc, context, config, provider, topic, "player", fallback)
    except Exception:
        return None
    if resp is not None and resp.llm and cache is not None:
        cache.put(fp, resp)
    return resp


def generate_player_reply(npc, world, config, provider=None, cache=None, executor=None, topic=None):
    """Returns ``(override_or_None, future_or_None)``.

    Only LLM-sourced dialogue overrides the caller's deterministic reply. When
    a background future is returned the caller keeps its deterministic reply
    until the future completes (polled via ``LLMPlayerBridge.poll``).
    """
    policy = LLMPolicy(config, provider)
    if not policy.should_generate("player") or not policy.provider_available():
        return None, None
    context = build_llm_context(
        npc, world, partner=None, topic=topic, player=True,
        max_memories=config.get("max_context_memories", 8),
    )
    fp = fingerprint(context, "player", config.get("model", ""))
    if cache is not None:
        cached = cache.get(fp)
        if cached is not None and cached.llm:
            return cached, None
    fallback = deterministic_response(npc, world, topic=topic, player=True)
    if executor is not None:
        future = executor.submit(
            _background_reply, npc, context, config, provider, cache, fp, topic, fallback
        )
        return None, future
    resp = _call_and_validate(npc, context, config, provider, topic, "player", fallback)
    if resp.llm:
        if cache is not None:
            cache.put(fp, resp)
        return resp, None
    return None, None


def _speaker_response(npc, other, world, topic, config, provider, cache):
    policy = LLMPolicy(config, provider)
    fallback = deterministic_response(npc, world, partner=other, topic=topic, player=False)
    if not policy.should_generate("npc") or not policy.provider_available():
        return fallback
    context = build_llm_context(
        npc, world, partner=other, topic=topic, player=False,
        max_memories=config.get("max_context_memories", 8),
    )
    fp = fingerprint(context, "npc", config.get("model", ""))
    if cache is not None:
        cached = cache.get(fp)
        if cached is not None and cached.llm:
            return cached
    resp = _call_and_validate(npc, context, config, provider, topic, "npc", fallback)
    if resp.llm and cache is not None:
        cache.put(fp, resp)
    return resp


def generate_npc_exchange(npc_a, npc_b, world, topic, config, provider=None, cache=None):
    """Two-speaker exchange entries (LLM or deterministic fallback)."""
    entries = []
    for npc, other in ((npc_a, npc_b), (npc_b, npc_a)):
        resp = _speaker_response(npc, other, world, topic, config, provider, cache)
        entries.append(
            {
                "speaker_id": npc.id,
                "speaker_name": npc.name,
                "listener_id": other.id,
                "listener_name": other.name,
                "dialogue": resp.dialogue,
                "emotion": resp.emotion,
                "topic": resp.topic,
                "source": resp.source,
            }
        )
    return entries


def _deterministic_thought(npc, world) -> Optional[str]:
    if not npc.alive:
        return None
    act = npc.current_action
    act_type = act.action_type if act is not None else None
    hour = world.clock.hour
    if act_type == "work":
        return "I should finish my work before sunset."
    if act_type == "sleep":
        return "Rest now; tomorrow is another day."
    if act_type == "eat":
        return "A meal always sets things right."
    if act_type == "buy_food":
        return "I need to keep food on the table."
    if npc.needs.hunger >= 60:
        return "I should find something to eat soon."
    if npc.needs.energy <= 30:
        return "I am getting tired; rest would help."
    if hour >= 21 or hour < 6:
        return "It is getting late. I should head home soon."
    return "Another day in this village."


def _background_thought(npc, context, config, provider, cache, fp, fallback_text):
    try:
        fallback = LLMResponse(dialogue=fallback_text or "Another day in this village.", emotion="content", topic=None, source="fallback")
        resp = _call_and_validate(npc, context, config, provider, None, "thought", fallback)
    except Exception:
        return None
    if resp is not None and resp.llm:
        if cache is not None:
            cache.put(fp, resp)
        return resp.dialogue
    return None


def generate_thought(npc, world, config, provider=None, cache=None, executor=None):
    """Returns ``(thought_or_None, future_or_None)``. Deterministic fallback
    when the LLM is disabled/unavailable; async via the executor otherwise."""
    policy = LLMPolicy(config, provider)
    fallback_text = _deterministic_thought(npc, world)
    if not policy.should_generate("thought"):
        return (fallback_text, None) if config.get("enabled") else (None, None)
    if not policy.provider_available():
        return fallback_text, None
    context = build_llm_context(
        npc, world, topic=None, max_memories=config.get("max_context_memories", 8)
    )
    fp = fingerprint(context, "thought", config.get("model", ""))
    if cache is not None:
        cached = cache.get(fp)
        if cached is not None and cached.llm:
            return cached.dialogue, None
    if executor is not None:
        future = executor.submit(
            _background_thought, npc, context, config, provider, cache, fp, fallback_text
        )
        return None, future
    fallback = deterministic_response(npc, world, topic=None, player=False)
    resp = _call_and_validate(npc, context, config, provider, None, "thought", fallback)
    if resp.llm:
        if cache is not None:
            cache.put(fp, resp)
        return resp.dialogue, None
    return fallback_text, None


def record_conversation_completed(npc, world, partner_name, topic=None) -> None:
    """Explicit deterministic memory integration point for LLM dialogue.

    Called only when LLM dialogue was involved. Stores one concise summary;
    ``Memory.add`` enforces the existing memory cap (50).
    """
    if npc is None or not npc.alive:
        return
    location = world.get_location(npc.location_id)
    place = location.name if location is not None else npc.location_id
    stamp = world.clock.stamp()
    npc.add_memory(
        stamp,
        "talked_with_npc",
        f"{npc.name} talked with {partner_name} at {place}.",
        2.0,
    )


class LLMPlayerBridge:
    """Player-conversation adapter. Purely presentation-side."""

    def __init__(self, config, provider=None, cache=None, executor=None):
        self.config = config
        self.provider = provider
        self.policy = LLMPolicy(config, provider)
        self.cache = cache if cache is not None else LLMCache(enabled=config.get("cache_enabled", True))
        self.executor = executor
        self._pending = {}

    def maybe_reply(self, npc, world, topic, conv) -> Optional[dict]:
        """Return an LLM override dict (dialogue/emotion/topic/follow_up) or
        ``None`` (deterministic reply stands). Applies completed replies to
        ``conv`` immediately."""
        if not self.policy.provider_available():
            return None
        context = build_llm_context(
            npc, world, partner=None, topic=topic, player=True,
            max_memories=self.config.get("max_context_memories", 8),
        )
        fp = fingerprint(context, "player", self.config.get("model", ""))
        cached = self.cache.get(fp)
        if cached is not None and cached.llm:
            self._apply(conv, cached)
            return self._as_dict(cached)
        fallback = deterministic_response(npc, world, topic=topic, player=True)
        if self.executor is not None:
            if fp in self._pending:
                return None
            future = self.executor.submit(
                _background_reply, npc, context, self.config, self.provider,
                self.cache, fp, topic, fallback,
            )
            self._pending[fp] = (conv, future)
            return None
        resp = _call_and_validate(npc, context, self.config, self.provider, topic, "player", fallback)
        if resp.llm:
            self.cache.put(fp, resp)
            self._apply(conv, resp)
            return self._as_dict(resp)
        return None

    def poll(self, wait: float = 0.05) -> None:
        """Apply completed background replies to their conversations.

        ``wait`` is a small bounded grace period so replies that just completed
        (including after a GIL-starved executor) are applied without blocking
        the simulation tick for more than ``wait`` seconds.
        """
        deadline = time.monotonic() + max(0.0, float(wait))
        done = []
        for fp, (conv, future) in list(self._pending.items()):
            if not future.done():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                try:
                    future.result(timeout=remaining)
                except BaseException:
                    pass
            if future.done():
                resp = None
                try:
                    resp = future.result()
                except BaseException:
                    resp = None
                if resp is not None and resp.llm:
                    self._apply(conv, resp)
                done.append(fp)
        for fp in done:
            self._pending.pop(fp, None)

    def on_farewell(self, npc, world, conv) -> None:
        if conv is not None and getattr(conv, "llm", False):
            record_conversation_completed(npc, world, conv.npc_name, topic=getattr(conv, "llm_topic", None))

    @staticmethod
    def _apply(conv, resp) -> None:
        conv.last_text = resp.dialogue
        conv.last_category = resp.topic or conv.last_category
        conv.llm_emotion = resp.emotion
        conv.llm_topic = resp.topic
        conv.llm = True

    @staticmethod
    def _as_dict(resp) -> dict:
        return {
            "dialogue": resp.dialogue,
            "emotion": resp.emotion,
            "topic": resp.topic,
            "follow_up": resp.follow_up,
            "llm": True,
        }


class LLMDialogueStore:
    """Bounded in-memory log of generated NPC-to-NPC exchanges (presentation)."""

    def __init__(self, cap: int = 40):
        self._lock = threading.Lock()
        self._exchanges = []
        self._cap = max(1, int(cap))

    def record(self, entry: dict) -> None:
        with self._lock:
            self._exchanges.append(entry)
            if len(self._exchanges) > self._cap:
                self._exchanges = self._exchanges[-self._cap:]

    def record_exchange(self, conversation_id, tick, entries) -> None:
        for entry in entries:
            self.record({"conversation_id": conversation_id, "tick": tick, **entry})

    def recent(self, limit: int = 5):
        with self._lock:
            return list(self._exchanges[-limit:])

    def __len__(self) -> int:
        with self._lock:
            return len(self._exchanges)


class LLMConversationObserver:
    """Detects NPC-to-NPC conversation exchanges and enqueues LLM dialogue.

    The ConversationSystem remains authoritative; this only observes its
    (stage, topic, turn) progression and produces presentation-only text.
    """

    def __init__(self, config, provider=None, cache=None, executor=None, store=None):
        self.config = config
        self.policy = LLMPolicy(config, provider)
        self.provider = provider
        self.cache = cache if cache is not None else LLMCache(enabled=config.get("cache_enabled", True))
        self.executor = executor
        self.store = store if store is not None else LLMDialogueStore()
        self._seen = set()

    def observe(self, sim) -> None:
        if not self.policy.enabled or not self.config.get("npc_dialogue", True):
            return
        world = sim.world
        if not world.conversations:
            return
        for conv in world.conversations:
            if conv.stage != "exchange":
                continue
            key = (conv.id, conv.stage, conv.topic, conv.turns_left, conv.last_turn_tick)
            if key in self._seen:
                continue
            self._seen.add(key)
            npc_a = world.get_npc(conv.initiator_id)
            npc_b = world.get_npc(conv.responder_id)
            if npc_a is None or npc_b is None or not npc_a.alive or not npc_b.alive:
                continue
            topic = conv.topic or "weather"
            tick = world.clock.tick
            if self.executor is not None:
                self.executor.submit(
                    self._exchange_worker, npc_a, npc_b, world, conv.id, topic, tick
                )
            else:
                try:
                    entries = generate_npc_exchange(
                        npc_a, npc_b, world, topic, self.config, self.provider, self.cache
                    )
                except LLMError:
                    continue
                self.store.record_exchange(conv.id, tick, entries)

    def _exchange_worker(self, npc_a, npc_b, world, conversation_id, topic, tick):
        try:
            entries = generate_npc_exchange(
                npc_a, npc_b, world, topic, self.config, self.provider, self.cache
            )
        except Exception:
            return
        self.store.record_exchange(conversation_id, tick, entries)


class LLMThoughtWriter:
    """Presentation-only, throttled NPC thoughts (async when provider exists)."""

    def __init__(self, config, provider=None, cache=None, executor=None, interval_ticks=48):
        self.config = config
        self.policy = LLMPolicy(config, provider)
        self.provider = provider
        self.cache = cache if cache is not None else LLMCache(enabled=config.get("cache_enabled", True))
        self.executor = executor
        self._interval = max(1, int(interval_ticks))
        self._last = {}
        self._pending = {}

    def observe(self, sim) -> None:
        if not self.policy.enabled or not self.config.get("thoughts_enabled", True):
            return
        world = sim.world
        for npc in world.alive_npcs():
            last = self._last.get(npc.id)
            if last is not None and world.clock.tick - last < self._interval:
                continue
            self._last[npc.id] = world.clock.tick
            text, future = generate_thought(
                npc, world, self.config, self.provider, self.cache, self.executor
            )
            if future is not None:
                self._pending[npc.id] = (npc, future)
                continue
            if text is not None:
                npc.thought = text

    def poll(self, wait: float = 0.05) -> None:
        for npc_id in list(self._pending):
            npc, future = self._pending[npc_id]
            if not future.done():
                try:
                    future.result(timeout=max(0.0, float(wait)))
                except BaseException:
                    pass
            if future.done():
                text = None
                try:
                    text = future.result()
                except BaseException:
                    text = None
                if text is not None:
                    npc.thought = text
                self._pending.pop(npc_id, None)


class LLMLayer:
    """Container wiring the optional LLM layer for a transport runner."""

    def __init__(self, config, provider=None, cache=None, executor=None):
        self.config = config
        self.cache = cache if cache is not None else LLMCache(enabled=config.get("cache_enabled", True))
        self.provider = provider if provider is not None else OpenAICompatibleProvider()
        if executor is None and config.get("enabled"):
            executor = LLMExecutor(self.provider)
        self.executor = executor
        self.player_bridge = LLMPlayerBridge(config, self.provider, self.cache, self.executor)
        self.store = LLMDialogueStore()
        self.observer = LLMConversationObserver(
            config, self.provider, self.cache, self.executor, self.store
        )
        self.thoughts = LLMThoughtWriter(config, self.provider, self.cache, self.executor)

    def observe(self, sim) -> None:
        self.observer.observe(sim)
        self.thoughts.observe(sim)

    def poll(self) -> None:
        self.player_bridge.poll()
        self.thoughts.poll()

    def shutdown(self) -> None:
        if self.executor is not None:
            self.executor.shutdown()


def build_llm_layer(world_config) -> Optional[LLMLayer]:
    """Create the LLM layer from ``world_config['behavior']['llm']`` or None."""
    behavior = world_config.get("behavior", {}) if isinstance(world_config, dict) else {}
    cfg = llm_config(behavior)
    if not cfg["enabled"]:
        return None
    return LLMLayer(cfg)