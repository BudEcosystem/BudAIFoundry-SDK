# Agent Discovery

Discover agent capabilities and metadata using agent cards.

> **Examples**: See [a2a_example.py](../../examples/a2a_example.py) for working code examples.

## get_agent_card()

Fetch an agent's public metadata via HTTP GET to `.well-known/agent-card.json`. This does not require JSON-RPC and is typically unauthenticated.

### Function Signature

```python
client.a2a.get_agent_card(
    agent_name: str,
    *,
    version: int | None = None,
) -> AgentCard
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_name` | `str` | required | Name of the agent |
| `version` | `int \| None` | `None` | Agent deployment version (`None` = latest) |

### Example

```python
card = client.a2a.get_agent_card("my-agent")

print(f"Name: {card.name}")
print(f"Description: {card.description}")
print(f"Version: {card.version}")

if card.capabilities:
    print(f"Streaming: {card.capabilities.streaming}")
    print(f"Push notifications: {card.capabilities.push_notifications}")

if card.skills:
    for skill in card.skills:
        print(f"  Skill: {skill.name} — {skill.description}")
```

### Specific Agent Version

```python
# Get card for deployment version 2
card = client.a2a.get_agent_card("my-agent", version=2)
```

## get_extended_agent_card()

Fetch the extended (authenticated) agent card via JSON-RPC POST. The extended card may include additional skills, capabilities, and configuration not visible in the public card.

### Function Signature

```python
client.a2a.get_extended_agent_card(
    agent_name: str,
    *,
    version: int | None = None,
    tenant: str | None = None,
) -> AgentCard
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_name` | `str` | required | Name of the agent |
| `version` | `int \| None` | `None` | Agent deployment version |
| `tenant` | `str \| None` | `None` | Tenant identifier (v1.0 only) |

### Difference from get_agent_card()

| | `get_agent_card()` | `get_extended_agent_card()` |
|-|-------|---------|
| **HTTP method** | GET | POST (JSON-RPC) |
| **Authentication** | Optional (public) | Required |
| **Content** | Public metadata | Full metadata (may include extra skills) |
| **Endpoint** | `.well-known/agent-card.json` | Agent's JSON-RPC endpoint |
| **v0.3 method** | N/A (plain HTTP) | `agent/getAuthenticatedExtendedCard` |
| **v1.0 method** | N/A (plain HTTP) | `GetExtendedAgentCard` |

### Example

```python
from bud.exceptions import A2AError

try:
    card = client.a2a.get_extended_agent_card("my-agent")
    print(f"Name: {card.name}")
    print(f"Skills: {len(card.skills or [])}")
except A2AError as e:
    if e.code == -32004:
        print("Agent doesn't support extended cards")
    elif e.code == -32007:
        print("Extended card not configured")
    else:
        print(f"Error: {e}")
```

## AgentCard Model

The `AgentCard` model accepts both v0.3 and v1.0 response formats.

### Core Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `str` | Agent name |
| `description` | `str \| None` | What the agent does |
| `version` | `str \| None` | Agent version string |
| `capabilities` | `AgentCapabilities \| None` | Capability flags |
| `skills` | `list[AgentSkill] \| None` | Advertised skills |
| `default_input_modes` | `list[str] \| None` | Accepted input media types |
| `default_output_modes` | `list[str] \| None` | Output media types |
| `security_schemes` | `dict \| None` | Authentication schemes |
| `provider` | `AgentProvider \| None` | Organization info |
| `icon_url` | `str \| None` | Agent icon URL |
| `documentation_url` | `str \| None` | Documentation URL |

### v0.3-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `url` | `str \| None` | Agent base endpoint URL |
| `protocol_version` | `str \| None` | Protocol version (e.g. `"0.3"`) |

### v1.0-Specific Fields

| Field | Type | Description |
|-------|------|-------------|
| `supported_interfaces` | `list[AgentInterface] \| None` | Protocol interfaces |

### AgentCapabilities

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `streaming` | `bool` | `False` | Supports SSE streaming |
| `push_notifications` | `bool` | `False` | Supports webhook notifications |
| `state_transition_history` | `bool` | `False` | Tracks state history |
| `extended_agent_card` | `bool` | `False` | Extended card available |

### AgentSkill

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique skill identifier |
| `name` | `str` | Human-readable name |
| `description` | `str \| None` | What the skill does |
| `tags` | `list[str] \| None` | Discovery keywords |
| `examples` | `list[str] \| None` | Sample prompts |
| `input_modes` | `list[str] \| None` | Accepted input types |
| `output_modes` | `list[str] \| None` | Output types |

### AgentInterface (v1.0)

| Field | Type | Description |
|-------|------|-------------|
| `url` | `str` | Interface endpoint URL |
| `protocol_binding` | `str \| None` | Transport (`JSONRPC`, `GRPC`, `HTTP+JSON`) |
| `protocol_version` | `str \| None` | Protocol version |
| `tenant` | `str \| None` | Default tenant |

### AgentProvider

| Field | Type | Description |
|-------|------|-------------|
| `organization` | `str` | Organization name |
| `url` | `str` | Organization URL |

## Best Practices

- Use `get_agent_card()` first to check if the agent supports streaming before using `send_message(stream=True)`
- Check `capabilities.extended_agent_card` before calling `get_extended_agent_card()`
- Cache agent cards locally — they change infrequently
- The card's `skills` list helps determine what the agent can do before sending messages
- The `AgentCard` model uses `extra="allow"` — unknown fields from newer protocol versions are preserved
