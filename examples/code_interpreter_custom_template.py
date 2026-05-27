#!/usr/bin/env python3
"""Code-interpreter custom-template examples using the BudAI SDK.

Walks through the SDK-facing flow for building a custom code-interpreter
template and binding it to an agent (= prompt version).

Examples covered:

* **Create + Build** — submit a Dockerfile-extension build and block
  until the sandbox image is ready.
* **Update** — append another command to the template; same alias is
  rebuilt.
* **Get Template** — fetch the current template row.
* **Attach to Agent** — bind the template to an agent version with a
  filtered network policy.
* **Get Binding** — read the agent's current code-interpreter binding.
* **Detach** — remove the binding from the agent.
* **Delete Template** — final cleanup.

SDK methods used::

    client.code_interpreter.templates.create(name=..., commands=..., cpu_count=..., memory_mb=...)
    client.code_interpreter.templates.update(template_id, commands=...)
    client.code_interpreter.templates.get(template_id)
    client.code_interpreter.templates.delete(template_id)
    client.agents.add_code_interpreter(agent_id, template_id=..., version=..., network_policy=...)
    client.agents.get_code_interpreter(agent_id, version=...)
    client.agents.remove_code_interpreter(agent_id, version=...)

Usage:
    BUD_API_KEY=your-key BUD_AGENT_ID=prm_abc python examples/code_interpreter_custom_template.py

Environment variables:
    BUD_API_KEY        API key (required)
    BUD_BASE_URL       budapp URL (default: http://localhost:9081)
    BUD_AGENT_ID       Existing prompt id to attach the tool to (required)
    BUD_AGENT_VERSION  Agent version number (default: 1)
    BUD_TEMPLATE_NAME  Template name to create (default: sdk-example-pydantic-ai)
"""

from __future__ import annotations

import os

from bud import BudClient

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = os.environ.get("BUD_BASE_URL", "http://localhost:9081")
API_KEY = os.environ.get("BUD_API_KEY", "")
AGENT_ID = os.environ.get("BUD_AGENT_ID", "")
AGENT_VERSION = int(os.environ.get("BUD_AGENT_VERSION", "1"))
TEMPLATE_NAME = os.environ.get("BUD_TEMPLATE_NAME", "sdk-example-pydantic-ai")


# ---------------------------------------------------------------------------
# Example 1: Create + Build a custom template
# ---------------------------------------------------------------------------


def example_create_template():
    """Example 1: Submit a build and block until ready."""
    print("=" * 60)
    print("Example 1: Create + Build Custom Template")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    print(f"Creating template {TEMPLATE_NAME!r}...")
    tpl = client.code_interpreter.templates.create(
        name=TEMPLATE_NAME,
        commands=["RUN pip install --no-cache-dir pydantic-ai"],
        cpu_count=2,
        memory_mb=4096,
    )
    print(f"  → id={tpl.id} status={tpl.status}")

    print("Waiting for build to finish (up to 10 min)...")
    tpl.wait_until_ready(timeout=600)
    print(f"  → status={tpl.status}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 2: Update template commands (rebuild same alias)
# ---------------------------------------------------------------------------


def example_update_template():
    """Example 2: Append another command; the same alias is rebuilt."""
    print("=" * 60)
    print("Example 2: Update Template")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    print(f"Updating template {TEMPLATE_NAME!r} (adds httpx)...")
    tpl = client.code_interpreter.templates.update(
        TEMPLATE_NAME,
        commands=[
            "RUN pip install --no-cache-dir pydantic-ai",
            "RUN pip install --no-cache-dir httpx",
        ],
    )
    tpl.wait_until_ready(timeout=600)
    print(f"  → status={tpl.status}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 3: Get template details
# ---------------------------------------------------------------------------


def example_get_template():
    """Example 3: Fetch the current template row."""
    print("=" * 60)
    print("Example 3: Get Template")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    tpl = client.code_interpreter.templates.get(TEMPLATE_NAME)
    print(
        f"  → id={tpl.id} status={tpl.status} "
        f"cpu={tpl.cpu_count} memory_mb={tpl.memory_mb}"
    )
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 4: Attach code-interpreter to an agent
# ---------------------------------------------------------------------------


def example_attach_agent():
    """Example 4: Bind the template to an agent version (filtered egress)."""
    print("=" * 60)
    print("Example 4: Attach to Agent")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    print(f"Attaching code-interpreter to agent {AGENT_ID!r} (version={AGENT_VERSION})...")
    binding = client.agents.add_code_interpreter(
        AGENT_ID,
        template_id=TEMPLATE_NAME,
        version=AGENT_VERSION,
        lifespan_seconds=1200,
        network_policy={
            "type": "filtered",
            "allow_out": ["pypi.org", "*.pythonhosted.org"],
            "deny_out": [],
        },
    )
    print(f"  → agent={binding.agent_id} version={binding.version} env_id={binding.env_id}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 5: Get the agent's code-interpreter binding
# ---------------------------------------------------------------------------


def example_get_binding():
    """Example 5: Read the agent's current code-interpreter binding."""
    print("=" * 60)
    print("Example 5: Get Binding")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    fetched = client.agents.get_code_interpreter(AGENT_ID, version=AGENT_VERSION)
    print(f"  → fetched binding env_id={fetched.env_id if fetched else None}")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 6: Detach code-interpreter from the agent
# ---------------------------------------------------------------------------


def example_detach_agent():
    """Example 6: Remove the binding from the agent version."""
    print("=" * 60)
    print("Example 6: Detach from Agent")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    print(f"Removing code-interpreter from agent {AGENT_ID!r}...")
    client.agents.remove_code_interpreter(AGENT_ID, version=AGENT_VERSION)
    print("  → detached")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Example 7: Delete the custom template
# ---------------------------------------------------------------------------


def example_delete_template():
    """Example 7: Final cleanup — drop the template row + sandbox image."""
    print("=" * 60)
    print("Example 7: Delete Template")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    print(f"Deleting template {TEMPLATE_NAME!r}...")
    client.code_interpreter.templates.delete(TEMPLATE_NAME)
    print("  → deleted")
    print()

    client.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("\n Bud SDK Code-Interpreter Custom-Template Examples\n")

    if not API_KEY:
        print("Error: BUD_API_KEY environment variable is not set.")
        print(
            "Usage: BUD_API_KEY=your-key BUD_AGENT_ID=prm_abc "
            "python examples/code_interpreter_custom_template.py"
        )
        exit(1)
    if not AGENT_ID:
        print("Error: BUD_AGENT_ID environment variable is not set.")
        exit(1)

    try:
        example_create_template()
    except Exception as e:
        print(f"Example 1 failed: {e}\n")

    try:
        example_update_template()
    except Exception as e:
        print(f"Example 2 failed: {e}\n")

    try:
        example_get_template()
    except Exception as e:
        print(f"Example 3 failed: {e}\n")

    try:
        example_attach_agent()
    except Exception as e:
        print(f"Example 4 failed: {e}\n")

    try:
        example_get_binding()
    except Exception as e:
        print(f"Example 5 failed: {e}\n")

    try:
        example_detach_agent()
    except Exception as e:
        print(f"Example 6 failed: {e}\n")

    try:
        example_delete_template()
    except Exception as e:
        print(f"Example 7 failed: {e}\n")

    print("Examples complete!")


if __name__ == "__main__":
    main()
