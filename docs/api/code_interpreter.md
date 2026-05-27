# Code Interpreter API

Build custom sandbox templates and attach them to agents.

> **Examples**: See [code_interpreter_custom_template.py](../../examples/code_interpreter_custom_template.py) for working code examples.

The SDK exposes two namespaces:

- `client.code_interpreter.templates` — create / get / update / delete a
  custom template.
- `client.agents.add_code_interpreter` / `get_code_interpreter` /
  `remove_code_interpreter` — attach a template to an agent (= prompt
  version).

Environments are managed implicitly. When you attach a template to an
agent, the sandbox env is auto-provisioned by the backend; the returned
`AgentToolBinding.env_id` is informational only. Both namespaces are
project-scoped via the standard BudAI API key — see
[configuration.md](../configuration.md).

## Basic Usage

```python
from bud import BudClient

client = BudClient()

# 1. Build a custom template.
tpl = client.code_interpreter.templates.create(
    name="my-py-extra",
    commands=["RUN pip install --no-cache-dir pydantic-ai"],
    cpu_count=2,
    memory_mb=4096,
)
tpl.wait_until_ready(timeout=600)

# 2. Attach it to an agent. The env is created for you.
binding = client.agents.add_code_interpreter(
    "prm_abc",
    template_id=tpl.id,
    network_policy={"type": "filtered", "allow_out": ["pypi.org"], "deny_out": []},
)
```

## Methods

### Create Template

Submit a custom-template build; returns immediately with `status="pending"`.

```python
client.code_interpreter.templates.create(
    *,
    name: str,
    commands: list[str],
    cpu_count: int,
    memory_mb: int,
) -> Template
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | `str` | Slug-safe template id (also the sandbox alias). |
| `commands` | `list[str]` | Raw Dockerfile instructions appended to the base. See [Dockerfile Commands](#dockerfile-commands). |
| `cpu_count` | `int` | vCPU count. |
| `memory_mb` | `int` | Memory in MiB. |

#### Response

Returns a [`Template`](#template) handle with `.refresh()` and
`.wait_until_ready()` bound. Status is `"pending"` until the workflow's
first activity inserts the row.

#### Example

```python
tpl = client.code_interpreter.templates.create(
    name="my-py-extra",
    commands=["RUN pip install --no-cache-dir pydantic-ai"],
    cpu_count=2,
    memory_mb=4096,
)
tpl.wait_until_ready(timeout=600)
```

### Get Template

Fetch a single template row by id.

```python
client.code_interpreter.templates.get(template_id: str) -> Template
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `template_id` | `str` | The template id returned by `create()`. |

#### Response

Returns a [`Template`](#template) handle. Raises `NotFoundError` if the
template doesn't exist or is in another project.

#### Example

```python
tpl = client.code_interpreter.templates.get("my-py-extra")
print(f"status={tpl.status} commands={tpl.commands}")
```

### Update Template

Replace the template's commands and rebuild the same sandbox image.

```python
client.code_interpreter.templates.update(
    template_id: str,
    *,
    commands: list[str],
) -> Template
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `template_id` | `str` | The template id to update. |
| `commands` | `list[str]` | Replacement Dockerfile-instruction list (re-triggers the build). |

#### Response

Returns a [`Template`](#template) handle with `status="pending"`. The
**same sandbox image** is rebuilt; the previous image is overwritten.
Already-running sandboxes keep their old snapshot until they're killed
or idled out — the next sandbox spawn picks up the new image.

#### Example

```python
tpl = client.code_interpreter.templates.update(
    "my-py-extra",
    commands=[
        "RUN pip install --no-cache-dir pydantic-ai",
        "RUN pip install --no-cache-dir httpx",
    ],
)
tpl.wait_until_ready()
```

### Delete Template

Hard-delete the template row and its sandbox image.

```python
client.code_interpreter.templates.delete(template_id: str) -> None
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `template_id` | `str` | The template id to delete. |

#### Response

Returns `None`. Idempotent — a 404 is silently absorbed. Raises if the
template is still bound to an environment.

#### Example

```python
client.code_interpreter.templates.delete("my-py-extra")
```

### Wait Until Ready

Block until the template build completes; raise on failure.

```python
tpl.wait_until_ready(
    *,
    timeout: float = 600.0,
    poll_interval: float = 3.0,
) -> Template
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `timeout` | `float` | `600.0` | Total seconds to wait before raising `TimeoutError`. |
| `poll_interval` | `float` | `3.0` | Seconds between successive `refresh()` calls. |

#### Response

Returns `self` once status reaches `"ready"`. Raises
[`BuildFailedError`](#builderror) if the server reports
`status="failed"` (the captured stderr tail is on `error_message`).
Raises `TimeoutError` if the build is still in progress when `timeout`
elapses.

#### Example

```python
try:
    tpl.wait_until_ready(timeout=600)
except bud.exceptions.BuildFailedError as exc:
    print(f"build failed: {exc.error_message}")
except TimeoutError:
    print("build did not finish in time")
```

### Refresh Template

Re-fetch the row from the server; mutate `self` in place.

```python
tpl.refresh() -> Template
```

#### Response

Returns `self`, so callers can chain (`tpl.refresh().status`). Tolerates
404 for a short grace window after create / update — the row may not
exist yet because the first workflow activity hasn't run. After the
grace elapses, 404 becomes a real `NotFoundError`.

#### Example

```python
while tpl.refresh().status == "building":
    time.sleep(5)
```

### Attach to Agent

Attach (or update) the code-interpreter tool on an agent version.

```python
client.agents.add_code_interpreter(
    agent_id: str,
    *,
    template_id: str,
    version: int = 1,
    lifespan_seconds: int = 1200,
    network_policy: NetworkPolicy | dict | None = None,
) -> AgentToolBinding
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_id` | `str` | — | The agent (prompt) id. |
| `template_id` | `str` | — | A builtin id (e.g. `"python-4g"`) or a custom template id from `create()`. |
| `version` | `int` | `1` | Agent version number. |
| `lifespan_seconds` | `int` | `1200` | Sandbox idle-kill timeout. |
| `network_policy` | `NetworkPolicy \| dict` | `None` | Egress policy. See [`NetworkPolicy`](#networkpolicy). |

Attaching is upsert: calling the method again with different config
replaces the previous binding. The agent (= prompt) must already exist.

#### Response

Returns an [`AgentToolBinding`](#agenttoolbinding). `binding.env_id` is
the auto-provisioned sandbox env id (informational only — the binding
lifecycle goes through these `agents.*` methods, not the env id).

#### Example

```python
binding = client.agents.add_code_interpreter(
    "prm_abc",
    template_id="my-py-extra",
    version=3,
    lifespan_seconds=1200,
    network_policy={
        "type": "filtered",
        "allow_out": ["pypi.org", "*.pythonhosted.org"],
        "deny_out": [],
    },
)
```

### Get Agent Binding

Fetch the agent's current code-interpreter binding.

```python
client.agents.get_code_interpreter(
    agent_id: str,
    version: int = 1,
) -> AgentToolBinding | None
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_id` | `str` | — | The agent (prompt) id. |
| `version` | `int` | `1` | Agent version number. |

#### Response

Returns an [`AgentToolBinding`](#agenttoolbinding), or `None` if no
binding exists for that agent version.

#### Example

```python
binding = client.agents.get_code_interpreter("prm_abc")
if binding is None:
    print("no binding")
else:
    print(f"env_id={binding.env_id}")
```

### Remove from Agent

Detach the code-interpreter tool from an agent version.

```python
client.agents.remove_code_interpreter(
    agent_id: str,
    version: int = 1,
) -> None
```

#### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `agent_id` | `str` | — | The agent (prompt) id. |
| `version` | `int` | `1` | Agent version number. |

#### Response

Returns `None`. Idempotent — a 404 is silently absorbed.

#### Example

```python
client.agents.remove_code_interpreter("prm_abc")
```

## Dockerfile Commands

`commands` is a `list[str]` of raw Dockerfile instructions appended verbatim
to the platform's base Dockerfile. The base ships the systemd + Jupyter
setup that backs the MCP tools.

### Allowed Instructions

`RUN`, `ENV`, `WORKDIR`, `USER`, `ARG`, `LABEL` — plus the rest of the
Docker instruction set that doesn't break our base. Server-side validation
is **deny-list**, not allow-list, so harmless no-ops like `EXPOSE` and
`SHELL` are silently accepted.

### Rejected Instructions

The validator hard-rejects five instructions with explicit per-instruction
error messages:

| Instruction | Why it's rejected |
| --- | --- |
| `FROM` | Replaces the base image → kills the systemd + Jupyter setup. |
| `COPY` / `ADD` | The SDK doesn't ship a build context in v1. Use a heredoc inside `RUN` for small files, or `RUN curl -fsSL …` for already-hosted files. |
| `CMD` / `ENTRYPOINT` | Overrides systemd as PID 1 → the Jupyter + FastAPI shim never starts. |

### Typo Catcher

Each line must start with a recognised Docker instruction keyword. A line
like `"pip install pydantic-ai"` returns a 422 with a `did you forget RUN?`
hint immediately, instead of failing 30 seconds into the sandbox build.

### Structural Limits

- ≤ 64 commands per template.
- ≤ 4 KB per command line.
- No NUL bytes, no bare CRs.

## Response Objects

### Template

```python
class Template:
    id: str                         # Template id (also the sandbox alias)
    type: str                       # "custom" | "builtin"
    status: str                     # "pending" | "building" | "ready" | "failed"
    commands: list[str]             # Dockerfile instructions (empty for builtins)
    languages: list[str]            # Available kernel languages
    cpu_count: int                  # vCPU count
    memory_mb: int                  # Memory in MiB
    error_message: str | None       # Captured stderr tail when status == "failed"
    created_at: datetime | None
    updated_at: datetime | None
    project_id: UUID | None
```

Handles returned by `create()` / `get()` / `update()` carry `.refresh()`
and `.wait_until_ready()` bound to the originating client.

### AgentToolBinding

```python
class AgentToolBinding:
    agent_id: str
    version: int
    tool_name: Literal["code_interpreter"]
    env_id: str                     # Auto-provisioned sandbox env id (informational)
    template_id: str | None
    custom_template_id: str | None
    config: dict | None             # Full backend config blob
```

### NetworkPolicy

```python
class NetworkPolicy:
    type: Literal["disabled", "open", "filtered"] = "disabled"
    allow_out: list[str] = []
    deny_out: list[str] = []
```

- `"disabled"` — block all egress (default).
- `"open"` — unrestricted egress.
- `"filtered"` — caller-defined allow / deny lists.

`allow_out` / `deny_out` accept IP literals, CIDR ranges, domain names,
wildcard domains (`"*.example.com"`), and the case-insensitive sentinel
`"ALL_TRAFFIC"` (which expands to `0.0.0.0/0`). Allow takes precedence
over deny.

### BuildFailedError

```python
class BuildFailedError(BudError):
    message: str                    # Formatted summary including error_message
    template_id: str | None
    error_message: str | None       # Captured stderr tail (≤ 2 KB)
```

Raised by `Template.wait_until_ready()` when the build workflow reports
`status="failed"`.

## Examples

### Full Lifecycle

```python
from bud import BudClient

client = BudClient()

# Build + bind
tpl = client.code_interpreter.templates.create(
    name="my-py-extra",
    commands=["RUN pip install --no-cache-dir pydantic-ai"],
    cpu_count=2,
    memory_mb=4096,
)
tpl.wait_until_ready(timeout=600)

binding = client.agents.add_code_interpreter("prm_abc", template_id=tpl.id)
print(f"bound env_id={binding.env_id}")

# Invoke /v1/responses against the agent here…

# Tear down
client.agents.remove_code_interpreter("prm_abc")
client.code_interpreter.templates.delete(tpl.id)
```

### Custom Network Policy

```python
binding = client.agents.add_code_interpreter(
    "prm_abc",
    template_id="my-py-extra",
    network_policy={
        "type": "filtered",
        "allow_out": ["pypi.org", "*.pythonhosted.org"],
        "deny_out": ["ALL_TRAFFIC"],  # strict allowlist: deny everything else
    },
)
```

### Polling Manually

```python
import time

tpl = client.code_interpreter.templates.create(...)
while tpl.refresh().status == "building":
    time.sleep(5)

if tpl.status == "failed":
    print(f"build failed: {tpl.error_message}")
else:
    print("ready")
```

### Async Client

```python
from bud import AsyncBudClient

async with AsyncBudClient() as client:
    tpl = await client.code_interpreter.templates.create(
        name="my-py-extra",
        commands=["RUN pip install --no-cache-dir pydantic-ai"],
        cpu_count=2,
        memory_mb=4096,
    )
    await tpl.wait_until_ready(timeout=600)
    binding = await client.agents.add_code_interpreter("prm_abc", template_id=tpl.id)
```

## Error Handling

```python
from bud.exceptions import BuildFailedError, NotFoundError, ValidationError

try:
    tpl = client.code_interpreter.templates.create(...)
    tpl.wait_until_ready(timeout=600)
except BuildFailedError as exc:
    print(f"Build failed: {exc.error_message}")
except ValidationError as exc:
    print(f"Invalid commands: {exc.errors}")
except NotFoundError:
    print("Template not found")
except TimeoutError:
    print("Build did not finish in time")
```

## Limits

- No file uploads — `COPY` / `ADD` are rejected. Heredoc in `RUN` or
  `RUN curl` are the documented workarounds.
- No template versioning — edits are destructive. To preserve an old
  recipe, create a new template before editing the old one.
- No template list endpoint in the SDK. Keep the id from `create()`.
- No environment CRUD in the SDK. `agents.add_code_interpreter` does it
  for you; project deletion cascades the cleanup.
- Embedded credentials in `RUN pip install --index-url=…` are baked
  into the image. Treat any image you build as you would any artifact:
  if it contains secrets, do not share it.
