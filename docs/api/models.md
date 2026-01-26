# Models API

List and retrieve information about available models.

> **Examples**: See [inference_example.py](../../examples/inference_example.py) for working code examples (Example 4).

## Basic Usage

```python
from bud import BudClient

client = BudClient(api_key="your-api-key")

# List all models
models = client.models.list()
for model in models.data:
    print(f"{model.id} - {model.owned_by}")

# Get specific model
model = client.models.retrieve("gpt-4")
print(f"Model: {model.id}, Created: {model.created}")
```

## Methods

### List Models

List all available models in your deployment.

```python
client.models.list() -> ModelList
```

#### Response

```python
class ModelList:
    object: str          # Always "list"
    data: list[Model]    # Available models
```

#### Example

```python
models = client.models.list()

print(f"Available models: {len(models.data)}")
for model in models.data:
    print(f"  - {model.id}")
```

### Retrieve Model

Get information about a specific model.

```python
client.models.retrieve(model_id: str) -> Model
```

#### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `model_id` | `str` | The ID of the model to retrieve |

#### Response

```python
class Model:
    id: str              # Model identifier
    object: str          # Always "model"
    created: int         # Unix timestamp of creation
    owned_by: str        # Model owner/provider
```

#### Example

```python
model = client.models.retrieve("gpt-4")

print(f"ID: {model.id}")
print(f"Created: {model.created}")
print(f"Owned by: {model.owned_by}")
```

## Response Objects

### Model

```python
class Model:
    id: str              # Unique model identifier
    object: str          # Always "model"
    created: int         # Unix timestamp when model was created
    owned_by: str        # Organization that owns/provides the model
```

### ModelList

```python
class ModelList:
    object: str          # Always "list"
    data: list[Model]    # List of Model objects
```

## Examples

### List All Models

```python
models = client.models.list()

print(f"Total models: {len(models.data)}\n")

for model in models.data:
    print(f"ID: {model.id}")
    print(f"  Owner: {model.owned_by}")
    print(f"  Created: {model.created}")
    print()
```

### Filter Models by Owner

```python
models = client.models.list()

# Get models owned by specific provider
openai_models = [m for m in models.data if m.owned_by == "openai"]
bud_models = [m for m in models.data if m.owned_by == "bud"]

print(f"OpenAI models: {len(openai_models)}")
for m in openai_models:
    print(f"  - {m.id}")

print(f"\nBud models: {len(bud_models)}")
for m in bud_models:
    print(f"  - {m.id}")
```

### Check Model Availability

```python
def is_model_available(client, model_id: str) -> bool:
    """Check if a model is available."""
    try:
        client.models.retrieve(model_id)
        return True
    except Exception:
        return False


# Usage
if is_model_available(client, "gpt-4"):
    print("GPT-4 is available")
else:
    print("GPT-4 is not available")
```

### Get Model Details

```python
from datetime import datetime

model = client.models.retrieve("finbert")

print(f"Model: {model.id}")
print(f"Owner: {model.owned_by}")
print(f"Created: {datetime.fromtimestamp(model.created)}")
```

### List Models for Specific Use Case

```python
models = client.models.list()

# Categorize models (example - actual categories depend on your deployment)
chat_models = []
embedding_models = []
classifier_models = []

for model in models.data:
    model_id = model.id.lower()
    if any(x in model_id for x in ["gpt", "llama", "claude", "qwen"]):
        chat_models.append(model.id)
    elif any(x in model_id for x in ["embed", "bge", "clip"]):
        embedding_models.append(model.id)
    elif any(x in model_id for x in ["bert", "classifier"]):
        classifier_models.append(model.id)

print("Chat/Completion Models:")
for m in chat_models:
    print(f"  - {m}")

print("\nEmbedding Models:")
for m in embedding_models:
    print(f"  - {m}")

print("\nClassifier Models:")
for m in classifier_models:
    print(f"  - {m}")
```

### Model Information Cache

```python
class ModelCache:
    """Cache model information to reduce API calls."""

    def __init__(self, client):
        self.client = client
        self._models = None

    def list(self, refresh: bool = False) -> list:
        """Get cached model list."""
        if self._models is None or refresh:
            self._models = self.client.models.list().data
        return self._models

    def get(self, model_id: str) -> dict | None:
        """Get model by ID from cache."""
        for model in self.list():
            if model.id == model_id:
                return model
        return None

    def exists(self, model_id: str) -> bool:
        """Check if model exists."""
        return self.get(model_id) is not None


# Usage
cache = ModelCache(client)

# First call fetches from API
print(f"Models: {len(cache.list())}")

# Subsequent calls use cache
if cache.exists("gpt-4"):
    model = cache.get("gpt-4")
    print(f"Found: {model.id}")
```

## Error Handling

```python
from bud.exceptions import NotFoundError

try:
    model = client.models.retrieve("nonexistent-model")
except NotFoundError:
    print("Model not found")
```

## Model Types

Models in your deployment may include:

### Chat/Completion Models
Used with `client.chat.completions.create()`:
- `gpt-4`, `gpt-3.5-turbo`
- `llama-2-70b`, `llama-3-8b`
- `claude-3-opus`, `claude-3-sonnet`
- `qwen-72b`, `qwen-7b`

### Embedding Models
Used with `client.embeddings.create()`:
- `bge-m3`, `bge-large-en-v1.5`
- `text-embedding-3-small`, `text-embedding-3-large`
- `clip-vit-base` (vision-language)

### Classifier Models
Used with `client.classifications.create()`:
- `finbert` (financial sentiment)
- `distilbert-sentiment`
- `bert-base-uncased`

The actual available models depend on your BudAI deployment configuration.
