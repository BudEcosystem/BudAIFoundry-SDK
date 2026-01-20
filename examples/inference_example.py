#!/usr/bin/env python3
"""Example script demonstrating the OpenAI-compatible inference API."""

import os

from bud import BudClient

# Configuration - set these environment variables before running
BASE_URL = os.environ.get("BUD_BASE_URL", "https://gateway.bud.studio")
API_KEY = os.environ.get("BUD_API_KEY", "")


def example_chat_completion():
    """Example: Basic chat completion."""
    print("=" * 60)
    print("Example 1: Basic Chat Completion")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    response = client.chat.completions.create(
        model="gpt-4-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "What is 2 + 2?"},
        ],
        temperature=0.3,
        max_tokens=100,
    )

    print(f"Response ID: {response.id}")
    print(f"Model: {response.model}")
    print(f"Content: {response.choices[0].message.content}")
    if response.usage:
        print(f"Tokens: {response.usage.total_tokens}")
    print()

    client.close()


def example_chat_with_tools():
    """Example: Chat completion with tool calling."""
    print("=" * 60)
    print("Example 2: Chat Completion with Tools")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    tools = [
        {
            "type": "function",
            "function": {
                "name": "github-mcp-get-repo-info",
                "description": "Get detailed information about a repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "owner": {"type": "string"},
                        "repo": {"type": "string"},
                    },
                    "required": ["owner", "repo"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
        {
            "type": "function",
            "function": {
                "name": "final_result",
                "description": "The final response which ends this conversation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {"type": "string"},
                        "stars": {"type": "integer"},
                        "forks": {"type": "integer"},
                        "open_issues": {"type": "integer"},
                    },
                    "required": ["repo", "stars", "forks", "open_issues"],
                    "additionalProperties": False,
                },
                "strict": True,
            },
        },
    ]

    response = client.chat.completions.create(
        model="gpt-4-mini",
        messages=[
            {"role": "system", "content": "You must execute github tool first"},
            {
                "role": "user",
                "content": "How many github stars, forks, open issues have in BudEcosystem/bud-runtime?",
            },
        ],
        tools=tools,
        tool_choice="required",
        temperature=0.3,
    )

    print(f"Response ID: {response.id}")
    print(f"Model: {response.model}")
    print(f"Finish Reason: {response.choices[0].finish_reason}")

    message = response.choices[0].message
    if message.tool_calls:
        print(f"Tool Calls: {len(message.tool_calls)}")
        for tc in message.tool_calls:
            print(f"  - Function: {tc.get('function', {}).get('name')}")
            print(f"    Arguments: {tc.get('function', {}).get('arguments')}")
    else:
        print(f"Content: {message.content}")

    print()
    client.close()


def example_streaming():
    """Example: Streaming chat completion."""
    print("=" * 60)
    print("Example 3: Streaming Chat Completion")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    stream = client.chat.completions.create(
        model="gpt-4-mini",
        messages=[
            {"role": "user", "content": "Count from 1 to 5, one number per line."},
        ],
        stream=True,
        temperature=0.3,
        max_tokens=100,
    )

    print("Streaming response: ", end="", flush=True)
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
    print("\n")

    client.close()


def example_list_models():
    """Example: List available models."""
    print("=" * 60)
    print("Example 4: List Models")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    try:
        models = client.models.list()
        print(f"Available models ({len(models.data)}):")
        for model in models.data[:10]:  # Show first 10
            print(f"  - {model.id} (owned by: {model.owned_by})")
    except Exception as e:
        print(f"Error listing models: {e}")

    print()
    client.close()


if __name__ == "__main__":
    print("\n🚀 Bud SDK Inference API Examples\n")

    if not API_KEY:
        print("Error: BUD_API_KEY environment variable is not set.")
        print("Usage: BUD_API_KEY=your-key python examples/inference_example.py")
        exit(1)

    # Run examples
    try:
        example_chat_completion()
    except Exception as e:
        print(f"❌ Example 1 failed: {e}\n")

    try:
        example_chat_with_tools()
    except Exception as e:
        print(f"❌ Example 2 failed: {e}\n")

    try:
        example_streaming()
    except Exception as e:
        print(f"❌ Example 3 failed: {e}\n")

    try:
        example_list_models()
    except Exception as e:
        print(f"❌ Example 4 failed: {e}\n")

    print("✅ Examples complete!")
