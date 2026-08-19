"""Optional LLM-powered dialogue/personality layer.

Strictly additive and presentation-side. No simulation/AI system imports this
package; it is consumed by the presentation/transport layer. See
``llm_dialogue.SYSTEM_PROMPT`` and ``llm_policy.llm_config``.
"""

from .llm_cache import LLMCache
from .llm_client import (
    LLMError,
    LLMExecutor,
    LLMProvider,
    LLMRequest,
    OpenAICompatibleProvider,
    StaticProvider,
)
from .llm_context import build_llm_context
from .llm_dialogue import (
    KNOWN_EMOTIONS,
    KNOWN_FOLLOW_UPS,
    KNOWN_TOPICS,
    LLMConversationObserver,
    LLMDialogueStore,
    LLMLayer,
    LLMPlayerBridge,
    LLMResponse,
    LLMThoughtWriter,
    MAX_DIALOGUE_LENGTH,
    SYSTEM_PROMPT,
    SYSTEM_PROMPT_VERSION,
    build_llm_layer,
    deterministic_response,
    fingerprint,
    generate_npc_exchange,
    generate_player_reply,
    generate_thought,
    record_conversation_completed,
    validate_llm_response,
)
from .llm_policy import LLMPolicy, llm_config, personality_instructions

__all__ = [
    "LLMCache",
    "LLMError",
    "LLMExecutor",
    "LLMProvider",
    "LLMRequest",
    "OpenAICompatibleProvider",
    "StaticProvider",
    "build_llm_context",
    "KNOWN_EMOTIONS",
    "KNOWN_FOLLOW_UPS",
    "KNOWN_TOPICS",
    "LLMConversationObserver",
    "LLMDialogueStore",
    "LLMLayer",
    "LLMPlayerBridge",
    "LLMResponse",
    "LLMThoughtWriter",
    "MAX_DIALOGUE_LENGTH",
    "SYSTEM_PROMPT",
    "SYSTEM_PROMPT_VERSION",
    "build_llm_layer",
    "deterministic_response",
    "fingerprint",
    "generate_npc_exchange",
    "generate_player_reply",
    "generate_thought",
    "record_conversation_completed",
    "validate_llm_response",
    "LLMPolicy",
    "llm_config",
    "personality_instructions",
]