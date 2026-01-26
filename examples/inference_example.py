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


def example_embeddings():
    """Example: Create text embeddings.

    Note: Update EMBEDDING_MODEL to match your deployment's available models.
    Common embedding models: bge-m3, text-embedding-3-small, BAAI/bge-small-en-v1.5
    """
    print("=" * 60)
    print("Example 5: Text Embeddings")
    print("=" * 60)

    # Update this to your deployment's embedding model
    EMBEDDING_MODEL = os.environ.get("BUD_EMBEDDING_MODEL", "bge-m3")

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    # Single text embedding
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input="Hello, world!",
    )

    print(f"Model: {response.model}")
    print(f"Embedding dimensions: {len(response.data[0].embedding)}")
    print(f"First 5 values: {response.data[0].embedding[:5]}")
    print(f"Tokens used: {response.usage.total_tokens}")
    print()

    # Batch embeddings
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=["First sentence", "Second sentence", "Third sentence"],
    )

    print(f"Batch embeddings: {len(response.data)} vectors")
    for data in response.data:
        print(f"  Index {data.index}: {len(data.embedding)} dimensions")
    print()

    client.close()


def example_embeddings_advanced():
    """Example: Advanced embedding features.

    Note: Update EMBEDDING_MODEL to match your deployment's available models.
    """
    print("=" * 60)
    print("Example 6: Advanced Embeddings (Chunking & Caching)")
    print("=" * 60)

    # Update this to your deployment's embedding model
    EMBEDDING_MODEL = os.environ.get("BUD_EMBEDDING_MODEL", "bge-m3")

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    # Embedding with caching enabled
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input="This text will be cached for faster subsequent requests.",
        cache_options={"enabled": "on", "max_age_s": 3600},
    )

    print("With caching:")
    print(f"  Model: {response.model}")
    print(f"  Dimensions: {len(response.data[0].embedding)}")
    print()

    # Embedding with priority
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input="High priority embedding request.",
        priority="high",
    )

    print("With priority:")
    print(f"  Model: {response.model}")
    print(f"  Tokens: {response.usage.total_tokens}")
    print()

    client.close()


def example_classification():
    """Example: Text classification."""
    print("=" * 60)
    print("Example 7: Text Classification")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    # Single text classification
    response = client.classifications.create(
        model="finbert",
        input=["The stock market had a great day with major gains."],
    )

    print(f"Model: {response.model}")
    print(f"ID: {response.id}")
    print(f"Tokens used: {response.usage.total_tokens}")
    print()
    print("Classification results:")
    for label_score in response.data[0]:
        print(f"  {label_score.label}: {label_score.score:.4f}")
    print()

    client.close()


def example_classification_batch():
    """Example: Batch text classification."""
    print("=" * 60)
    print("Example 8: Batch Classification")
    print("=" * 60)

    client = BudClient(api_key=API_KEY, base_url=BASE_URL)

    texts = [
        "Company reports record profits this quarter.",
        "Market crash leads to significant losses.",
        "Trading volume remains steady today.",
    ]

    response = client.classifications.create(
        model="finbert",
        input=texts,
        priority="high",
    )

    print(f"Model: {response.model}")
    print(f"Classified {len(response.data)} texts")
    print()

    for i, (text, result) in enumerate(zip(texts, response.data, strict=True)):
        # Get top label
        top_label = max(result, key=lambda x: x.score)
        print(f"Text {i + 1}: \"{text[:50]}...\"")
        print(f"  Prediction: {top_label.label} ({top_label.score:.2%})")
        print("  All scores: ", end="")
        print(", ".join(f"{ls.label}={ls.score:.2%}" for ls in result))
        print()

    client.close()


if __name__ == "__main__":
    print("\n Bud SDK Inference API Examples\n")

    if not API_KEY:
        print("Error: BUD_API_KEY environment variable is not set.")
        print("Usage: BUD_API_KEY=your-key python examples/inference_example.py")
        exit(1)

    # Run examples
    try:
        example_chat_completion()
    except Exception as e:
        print(f"Example 1 failed: {e}\n")

    try:
        example_chat_with_tools()
    except Exception as e:
        print(f"Example 2 failed: {e}\n")

    try:
        example_streaming()
    except Exception as e:
        print(f"Example 3 failed: {e}\n")

    try:
        example_list_models()
    except Exception as e:
        print(f"Example 4 failed: {e}\n")

    try:
        example_embeddings()
    except Exception as e:
        print(f"Example 5 failed: {e}\n")

    try:
        example_embeddings_advanced()
    except Exception as e:
        print(f"Example 6 failed: {e}\n")

    try:
        example_classification()
    except Exception as e:
        print(f"Example 7 failed: {e}\n")

    try:
        example_classification_batch()
    except Exception as e:
        print(f"Example 8 failed: {e}\n")

    print("Examples complete!")
