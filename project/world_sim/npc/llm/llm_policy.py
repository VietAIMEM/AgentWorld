"""Configuration and policy for the optional LLM layer.

The LLM layer is strictly additive and presentation-only. It lives under
``world_sim/npc/llm`` so it can read NPC/world state, but no simulation/AI
system ever imports it. Its config block lives under ``behavior.llm`` and
defaults to ``enabled: false``; when disabled the system behaves exactly as
before (deterministic conversation remains the fallback).
"""

from __future__ import annotations

DEFAULT_LLM_CONFIG = {
    "enabled": False,
    "provider": "",
    "model": "",
    "temperature": 0.7,
    "max_tokens": 150,
    "timeout_seconds": 10.0,
    "max_context_memories": 8,
    "cache_enabled": True,
    "thoughts_enabled": True,
    "npc_dialogue": True,
}


def llm_config(behavior_cfg) -> dict:
    """Parse the ``behavior.llm`` block with safe defaults (no key required)."""
    if not isinstance(behavior_cfg, dict):
        behavior_cfg = {}
    llm = behavior_cfg.get("llm", {})
    if not isinstance(llm, dict):
        llm = {}
    merged = dict(DEFAULT_LLM_CONFIG)
    for key in DEFAULT_LLM_CONFIG:
        if key in llm:
            merged[key] = llm[key]
    merged["enabled"] = bool(merged["enabled"])
    merged["cache_enabled"] = bool(merged["cache_enabled"])
    merged["thoughts_enabled"] = bool(merged["thoughts_enabled"])
    merged["npc_dialogue"] = bool(merged["npc_dialogue"])
    merged["temperature"] = float(merged["temperature"])
    merged["max_tokens"] = int(merged["max_tokens"])
    merged["timeout_seconds"] = float(merged["timeout_seconds"])
    merged["max_context_memories"] = int(merged["max_context_memories"])
    return merged


def personality_instructions(personality) -> list:
    """Map the existing personality traits to behavioral instructions.

    Uses only the existing Personality dataclass (no second personality
    system is invented).
    """
    instructions = []
    if personality.sociability >= 0.66:
        instructions.append(
            "high sociability: be chatty, ask the listener questions, warm and friendly"
        )
    elif personality.sociability <= 0.33:
        instructions.append(
            "low sociability: give short answers and do not prolong the conversation"
        )
    if personality.ambition >= 0.66:
        instructions.append("high ambition: likes to discuss work, goals and achievements")
    if personality.risk_tolerance >= 0.66:
        instructions.append("high risk tolerance: express adventurous, bold opinions")
    elif personality.risk_tolerance <= 0.33:
        instructions.append("low risk tolerance: cautious, conservative opinions")
    if personality.work_ethic >= 0.66:
        instructions.append("strong work ethic: values hard work and diligence")
    if personality.generosity >= 0.66:
        instructions.append("high generosity: offer help and be giving")
    elif personality.generosity <= 0.33:
        instructions.append("low generosity: guarded about giving and sharing")
    return instructions


class LLMPolicy:
    """Decides whether/how the LLM layer may engage for a request."""

    def __init__(self, config: dict, provider=None):
        self.config = config
        self.provider = provider

    @property
    def enabled(self) -> bool:
        return bool(self.config.get("enabled", False))

    def provider_available(self) -> bool:
        return bool(
            self.enabled
            and self.provider is not None
            and self.provider.available()
        )

    def should_generate(self, kind: str) -> bool:
        """kind in {'player', 'npc', 'thought'}."""
        if not self.enabled:
            return False
        if kind == "thought" and not self.config.get("thoughts_enabled", True):
            return False
        if kind == "npc" and not self.config.get("npc_dialogue", True):
            return False
        return True