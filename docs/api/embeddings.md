# Embeddings API

Create embeddings for text, images, or audio using OpenAI-compatible models.

> **Examples**: See [inference_example.py](../../examples/inference_example.py) for working code examples (Examples 5-6).

## Basic Usage

```python
from bud import BudClient

client = BudClient(api_key="your-api-key")

response = client.embeddings.create(
    model="bge-m3",
    input="Hello, world!"
)

embedding = response.data[0].embedding
print(f"Dimensions: {len(embedding)}")
```

## Method Signature

```python
client.embeddings.create(
    *,
    model: str,
    input: str | list[str],
    encoding_format: Literal["float", "base64"] | None = None,
    modality: Literal["text", "image", "audio"] | None = None,
    dimensions: int | None = None,
    priority: Literal["high", "normal", "low"] | None = None,
    user: str | None = None,
    include_input: bool | None = None,
    chunking: dict | None = None,
    cache_options: dict | None = None,
) -> EmbeddingResponse
```

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model` | `str` | ID of the embedding model to use |
| `input` | `str \| list[str]` | Text, URLs, or base64 data to embed |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `encoding_format` | `str` | `"float"` | Output format: `"float"` or `"base64"` |
| `modality` | `str` | `"text"` | Input type: `"text"`, `"image"`, or `"audio"` |
| `dimensions` | `int` | `0` | Output dimensions (0 = full) |
| `priority` | `str` | `None` | Request priority: `"high"`, `"normal"`, or `"low"` |
| `user` | `str` | `None` | Unique user identifier |
| `include_input` | `bool` | `False` | Return original text in response |
| `chunking` | `dict` | `None` | Chunking configuration |
| `cache_options` | `dict` | `None` | Caching configuration |

## Parameter Details

### `encoding_format`

| Value | Description |
|-------|-------------|
| `"float"` | Array of floating point numbers (default) |
| `"base64"` | Base64-encoded binary data |

```python
# Float format (default)
response = client.embeddings.create(
    model="bge-m3",
    input="Hello",
    encoding_format="float"
)
# response.data[0].embedding = [0.123, -0.456, ...]

# Base64 format
response = client.embeddings.create(
    model="bge-m3",
    input="Hello",
    encoding_format="base64"
)
# response.data[0].embedding = "SGVsbG8gV29ybGQ=..."
```

### `modality`

| Value | Description | Input Format |
|-------|-------------|--------------|
| `"text"` | Text embeddings (default) | Plain text strings |
| `"image"` | Image embeddings | URLs or base64-encoded images |
| `"audio"` | Audio embeddings | URLs or base64-encoded audio |

```python
# Text embedding
response = client.embeddings.create(
    model="bge-m3",
    input="Hello, world!",
    modality="text"
)

# Image embedding (URL)
response = client.embeddings.create(
    model="clip-vit-base",
    input="https://example.com/image.jpg",
    modality="image"
)

# Image embedding (base64)
import base64
with open("image.jpg", "rb") as f:
    image_b64 = base64.b64encode(f.read()).decode()

response = client.embeddings.create(
    model="clip-vit-base",
    input=f"data:image/jpeg;base64,{image_b64}",
    modality="image"
)
```

### `dimensions`

Control the output embedding size:

```python
# Full dimensions (model default)
response = client.embeddings.create(
    model="bge-m3",
    input="Hello",
    dimensions=0  # or omit parameter
)

# Reduced dimensions
response = client.embeddings.create(
    model="bge-m3",
    input="Hello",
    dimensions=512  # Model must support this
)
```

### `priority`

| Value | Description |
|-------|-------------|
| `"high"` | Higher priority processing |
| `"normal"` | Standard priority (default) |
| `"low"` | Lower priority processing |

```python
response = client.embeddings.create(
    model="bge-m3",
    input="Urgent request",
    priority="high"
)
```

### `include_input`

Return the original text in the response (text modality only):

```python
response = client.embeddings.create(
    model="bge-m3",
    input="Hello, world!",
    include_input=True
)

print(response.data[0].text)  # "Hello, world!"
```

### `chunking`

Automatically split long text into chunks:

```python
response = client.embeddings.create(
    model="bge-m3",
    input="Very long document text...",
    chunking={
        "strategy": "sentence",      # Chunking strategy
        "chunk_size": 512,           # Max tokens per chunk
        "overlap": 50,               # Token overlap between chunks
    }
)

# Each chunk becomes a separate embedding
for data in response.data:
    print(f"Chunk {data.index}: {data.chunk_text[:50]}...")
```

#### Chunking Strategies

| Strategy | Description |
|----------|-------------|
| `"token"` | Split by token count |
| `"sentence"` | Split at sentence boundaries |
| `"recursive"` | Recursively split at natural boundaries |
| `"semantic"` | Split based on semantic similarity |
| `"code"` | Optimized for code (respects syntax) |
| `"table"` | Optimized for tabular data |

#### Full Chunking Configuration

```python
chunking = {
    "strategy": "recursive",
    "chunk_size": 512,           # 1-8192 tokens
    "overlap": 50,               # Overlap between chunks
    "preprocessing": {
        "normalize_text": True,   # Normalize whitespace
        "strip_markdown": False,  # Remove markdown formatting
        "normalize_tables": True  # Normalize table formatting
    }
}
```

### `cache_options`

Enable response caching:

```python
response = client.embeddings.create(
    model="bge-m3",
    input="Frequently requested text",
    cache_options={
        "enabled": "on",       # "on" or "off"
        "max_age_s": 3600      # Cache TTL in seconds
    }
)
```

## Response Object

### EmbeddingResponse

```python
class EmbeddingResponse:
    object: str                      # Always "list"
    data: list[EmbeddingData]        # Embedding results
    model: str                       # Model used
    usage: EmbeddingUsage            # Token usage
```

### EmbeddingData

```python
class EmbeddingData:
    index: int                       # Position in input list
    embedding: list[float]           # The embedding vector
    object: str                      # Always "embedding"
    text: str | None                 # Original text (if include_input=True)
    chunk_text: str | None           # Chunk text (if chunking enabled)
```

### EmbeddingUsage

```python
class EmbeddingUsage:
    prompt_tokens: int               # Input tokens
    total_tokens: int                # Total tokens processed
```

## Examples

### Single Text Embedding

```python
response = client.embeddings.create(
    model="bge-m3",
    input="Hello, world!"
)

embedding = response.data[0].embedding
print(f"Dimensions: {len(embedding)}")
print(f"First 5 values: {embedding[:5]}")
print(f"Tokens used: {response.usage.total_tokens}")
```

### Batch Embeddings

```python
texts = [
    "First document",
    "Second document",
    "Third document"
]

response = client.embeddings.create(
    model="bge-m3",
    input=texts
)

for data in response.data:
    print(f"Text {data.index}: {len(data.embedding)} dimensions")
```

### Semantic Search

```python
import numpy as np

def cosine_similarity(a, b):
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Create document embeddings
documents = [
    "Python is a programming language",
    "Machine learning uses algorithms",
    "Databases store information"
]

doc_response = client.embeddings.create(
    model="bge-m3",
    input=documents
)
doc_embeddings = [d.embedding for d in doc_response.data]

# Create query embedding
query = "What is Python?"
query_response = client.embeddings.create(
    model="bge-m3",
    input=query
)
query_embedding = query_response.data[0].embedding

# Find most similar
similarities = [
    cosine_similarity(query_embedding, doc_emb)
    for doc_emb in doc_embeddings
]

best_match_idx = np.argmax(similarities)
print(f"Best match: {documents[best_match_idx]}")
print(f"Similarity: {similarities[best_match_idx]:.4f}")
```

### Long Document with Chunking

```python
long_document = """
Your very long document text here...
This could be thousands of words...
"""

response = client.embeddings.create(
    model="bge-m3",
    input=long_document,
    chunking={
        "strategy": "sentence",
        "chunk_size": 256,
        "overlap": 25
    },
    include_input=True
)

print(f"Document split into {len(response.data)} chunks")
for data in response.data:
    print(f"Chunk {data.index}:")
    print(f"  Text: {data.chunk_text[:100]}...")
    print(f"  Embedding dims: {len(data.embedding)}")
```

### With Caching for Repeated Requests

```python
# First request - computed fresh
response = client.embeddings.create(
    model="bge-m3",
    input="Frequently accessed content",
    cache_options={"enabled": "on", "max_age_s": 3600}
)

# Subsequent requests within 1 hour - served from cache
response = client.embeddings.create(
    model="bge-m3",
    input="Frequently accessed content",
    cache_options={"enabled": "on", "max_age_s": 3600}
)
```

### Complete Example with All Options

```python
response = client.embeddings.create(
    model="bge-m3",
    input=["Document 1", "Document 2"],
    encoding_format="float",
    modality="text",
    dimensions=512,
    priority="high",
    user="user-123",
    include_input=True,
    cache_options={"enabled": "on", "max_age_s": 7200}
)

for data in response.data:
    print(f"Index: {data.index}")
    print(f"Original: {data.text}")
    print(f"Dimensions: {len(data.embedding)}")
```

## Common Embedding Models

| Model | Dimensions | Description |
|-------|------------|-------------|
| `bge-m3` | 1024 | Multilingual, high quality |
| `bge-small-en-v1.5` | 384 | English, small and fast |
| `bge-base-en-v1.5` | 768 | English, balanced |
| `bge-large-en-v1.5` | 1024 | English, highest quality |
| `text-embedding-3-small` | 1536 | OpenAI compatible |
| `text-embedding-3-large` | 3072 | OpenAI compatible |
| `clip-vit-base` | 512 | Vision-language |

Check available models with:

```python
models = client.models.list()
for model in models.data:
    print(model.id)
```
