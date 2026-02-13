"""Semantic attribute constants for bud.* baggage and span attributes.

These constants MUST match the gateway's baggage.rs keys exactly.
Source of truth: services/budgateway/tensorzero-internal/src/baggage.rs
"""

from __future__ import annotations

# W3C Baggage keys (set by gateway auth middleware)
PROJECT_ID = "bud.project_id"
PROMPT_ID = "bud.prompt_id"
PROMPT_VERSION_ID = "bud.prompt_version_id"
ENDPOINT_ID = "bud.endpoint_id"
MODEL_ID = "bud.model_id"
API_KEY_ID = "bud.api_key_id"
API_KEY_PROJECT_ID = "bud.api_key_project_id"
USER_ID = "bud.user_id"
AUTH_PROCESSED = "bud.auth_processed"

# Ordered list of baggage keys for BaggageSpanProcessor
BAGGAGE_KEYS: list[str] = [
    PROJECT_ID,
    PROMPT_ID,
    PROMPT_VERSION_ID,
    ENDPOINT_ID,
    MODEL_ID,
    API_KEY_ID,
    API_KEY_PROJECT_ID,
    USER_ID,
]

# SDK-specific attributes
SDK_VERSION = "bud.sdk.version"
SDK_LANGUAGE = "bud.sdk.language"
SDK_LANGUAGE_VALUE = "python"
