"""JSON-RPC 2.0 envelope helpers for A2A protocol."""

from __future__ import annotations

import uuid
from typing import Any

from bud.exceptions import A2AError


def build_request(
    method: str,
    params: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 request envelope.

    Args:
        method: JSON-RPC method name (e.g. "SendMessage", "message/send").
        params: Method parameters.
        request_id: Optional request ID. Auto-generated UUID if not provided.

    Returns:
        JSON-RPC 2.0 request dict ready for serialization.
    """
    return {
        "jsonrpc": "2.0",
        "id": request_id or uuid.uuid4().hex,
        "method": method,
        "params": params,
    }


def unwrap_response(data: Any) -> Any:
    """Extract the result from a JSON-RPC 2.0 response.

    Args:
        data: Parsed JSON response dict.

    Returns:
        The ``result`` value from the response.

    Raises:
        A2AError: If the response contains an error or is malformed.
    """
    if not isinstance(data, dict):
        raise A2AError(f"Expected JSON-RPC response dict, got {type(data).__name__}")

    if "error" in data and data["error"] is not None:
        err = data["error"]
        raise A2AError(
            message=err.get("message", "Unknown JSON-RPC error"),
            code=err.get("code"),
            data=err.get("data"),
        )

    if "result" not in data:
        raise A2AError("JSON-RPC response missing both 'result' and 'error'")

    return data["result"]


def unwrap_sse_event(rpc_response: dict[str, Any]) -> Any:
    """Extract the result from a JSON-RPC 2.0 SSE event.

    Same logic as ``unwrap_response`` but used for individual streaming events
    where each SSE ``data:`` line contains a full JSON-RPC envelope.

    Args:
        rpc_response: Parsed JSON-RPC response from an SSE data line.

    Returns:
        The ``result`` value from the event.

    Raises:
        A2AError: If the event contains an error or is malformed.
    """
    return unwrap_response(rpc_response)
