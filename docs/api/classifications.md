# Classifications API

Classify text using deployed classifier models.

> **Examples**: See [inference_example.py](../../examples/inference_example.py) for working code examples (Examples 7-8).

## Basic Usage

```python
from bud import BudClient

client = BudClient(api_key="your-api-key")

response = client.classifications.create(
    model="finbert",
    input=["The stock market had a great day with strong gains."]
)

for label_score in response.data[0]:
    print(f"{label_score.label}: {label_score.score:.2%}")
```

## Method Signature

```python
client.classifications.create(
    *,
    input: list[str],
    model: str = "default/not-specified",
    raw_scores: bool | None = None,
    priority: Literal["high", "normal", "low"] | None = None,
) -> ClassifyResponse
```

## Parameters

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `input` | `list[str]` | List of text strings to classify |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model` | `str` | `"default/not-specified"` | Classifier model ID |
| `raw_scores` | `bool` | `False` | Return raw scores instead of normalized |
| `priority` | `str` | `None` | Request priority |

## Parameter Details

### `input`

List of text strings to classify. Each string is classified independently:

```python
# Single text
response = client.classifications.create(
    model="finbert",
    input=["The market is up today."]
)

# Multiple texts (batch)
response = client.classifications.create(
    model="finbert",
    input=[
        "Company reports record profits.",
        "Stock prices plummeted today.",
        "Trading volume was average."
    ]
)
```

### `model`

The classifier model to use. Available models depend on your deployment:

```python
# Sentiment analysis
response = client.classifications.create(
    model="finbert",
    input=["Great product, highly recommend!"]
)

# Default model
response = client.classifications.create(
    model="default/not-specified",
    input=["Some text to classify"]
)
```

### `raw_scores`

Control score normalization:

| Value | Description |
|-------|-------------|
| `False` | Normalized probabilities (sum to 1.0) - default |
| `True` | Raw logits/scores from the model |

```python
# Normalized scores (default)
response = client.classifications.create(
    model="finbert",
    input=["Good news!"],
    raw_scores=False
)
# Scores sum to 1.0: positive=0.85, neutral=0.10, negative=0.05

# Raw scores
response = client.classifications.create(
    model="finbert",
    input=["Good news!"],
    raw_scores=True
)
# Raw logits: positive=2.31, neutral=-0.54, negative=-1.89
```

### `priority`

| Value | Description |
|-------|-------------|
| `"high"` | Higher priority processing |
| `"normal"` | Standard priority (default) |
| `"low"` | Lower priority processing |

```python
response = client.classifications.create(
    model="finbert",
    input=["Urgent classification needed"],
    priority="high"
)
```

## Response Object

### ClassifyResponse

```python
class ClassifyResponse:
    object: str                              # Always "classify"
    data: list[list[ClassifyLabelScore]]     # Classification results
    model: str                               # Model used
    usage: ClassifyUsage                     # Token usage
    id: str | None                           # Response ID
    created: int | None                      # Unix timestamp
```

### ClassifyLabelScore

```python
class ClassifyLabelScore:
    label: str                               # Classification label
    score: float                             # Confidence score (0-1 or raw)
```

### ClassifyUsage

```python
class ClassifyUsage:
    prompt_tokens: int                       # Input tokens
    total_tokens: int                        # Total tokens
```

## Response Structure

The `data` field contains a list of results, one for each input text. Each result is a list of label-score pairs:

```python
response.data = [
    # Results for first input
    [
        ClassifyLabelScore(label="positive", score=0.85),
        ClassifyLabelScore(label="neutral", score=0.10),
        ClassifyLabelScore(label="negative", score=0.05)
    ],
    # Results for second input
    [
        ClassifyLabelScore(label="negative", score=0.72),
        ClassifyLabelScore(label="neutral", score=0.20),
        ClassifyLabelScore(label="positive", score=0.08)
    ]
]
```

## Examples

### Single Text Classification

```python
response = client.classifications.create(
    model="finbert",
    input=["The quarterly earnings exceeded all expectations."]
)

print(f"Model: {response.model}")
print(f"ID: {response.id}")
print()

print("Classification results:")
for label_score in response.data[0]:
    print(f"  {label_score.label}: {label_score.score:.4f}")
```

Output:
```
Model: finbert
ID: infinity-abc123

Classification results:
  positive: 0.9156
  neutral: 0.0623
  negative: 0.0221
```

### Batch Classification

```python
texts = [
    "Company announces major expansion plans.",
    "Layoffs expected as revenue declines.",
    "Stock price remains unchanged today."
]

response = client.classifications.create(
    model="finbert",
    input=texts,
    priority="high"
)

print(f"Classified {len(response.data)} texts\n")

for i, (text, result) in enumerate(zip(texts, response.data, strict=True)):
    # Get the top prediction
    top_label = max(result, key=lambda x: x.score)

    print(f"Text {i + 1}: \"{text}\"")
    print(f"  Prediction: {top_label.label} ({top_label.score:.1%})")
    print()
```

Output:
```
Classified 3 texts

Text 1: "Company announces major expansion plans."
  Prediction: positive (89.2%)

Text 2: "Layoffs expected as revenue declines."
  Prediction: negative (94.1%)

Text 3: "Stock price remains unchanged today."
  Prediction: neutral (81.5%)
```

### Get All Scores

```python
response = client.classifications.create(
    model="finbert",
    input=["Mixed signals in today's trading session."]
)

print("All classification scores:")
for label_score in sorted(response.data[0], key=lambda x: x.score, reverse=True):
    bar = "#" * int(label_score.score * 20)
    print(f"  {label_score.label:10} {label_score.score:6.2%} {bar}")
```

Output:
```
All classification scores:
  neutral    52.34% ##########
  positive   28.41% #####
  negative   19.25% ###
```

### Compare Raw vs Normalized Scores

```python
text = ["The market showed mixed results."]

# Normalized scores
response_norm = client.classifications.create(
    model="finbert",
    input=text,
    raw_scores=False
)

# Raw scores
response_raw = client.classifications.create(
    model="finbert",
    input=text,
    raw_scores=True
)

print("Normalized scores (probabilities):")
for ls in response_norm.data[0]:
    print(f"  {ls.label}: {ls.score:.4f}")

print(f"\nSum: {sum(ls.score for ls in response_norm.data[0]):.4f}")

print("\nRaw scores (logits):")
for ls in response_raw.data[0]:
    print(f"  {ls.label}: {ls.score:.4f}")
```

### Sentiment Analysis Pipeline

```python
def analyze_sentiment(texts: list[str]) -> list[dict]:
    """Analyze sentiment of multiple texts."""
    response = client.classifications.create(
        model="finbert",
        input=texts
    )

    results = []
    for text, scores in zip(texts, response.data, strict=True):
        top = max(scores, key=lambda x: x.score)
        results.append({
            "text": text,
            "sentiment": top.label,
            "confidence": top.score,
            "all_scores": {ls.label: ls.score for ls in scores}
        })
    return results


# Usage
texts = [
    "Excellent customer service!",
    "Product arrived damaged.",
    "It's okay, nothing special."
]

for result in analyze_sentiment(texts):
    print(f"Text: {result['text']}")
    print(f"Sentiment: {result['sentiment']} ({result['confidence']:.1%})")
    print()
```

### Token Usage Tracking

```python
total_tokens = 0

for batch in text_batches:
    response = client.classifications.create(
        model="finbert",
        input=batch
    )
    total_tokens += response.usage.total_tokens
    print(f"Batch tokens: {response.usage.total_tokens}")

print(f"Total tokens used: {total_tokens}")
```

## Common Classifier Models

| Model | Labels | Description |
|-------|--------|-------------|
| `finbert` | positive, neutral, negative | Financial sentiment analysis |
| `distilbert-sentiment` | positive, negative | General sentiment |
| `bert-base-uncased` | Various | General text classification |

Check available models:

```python
models = client.models.list()
for model in models.data:
    print(model.id)
```

## Error Handling

```python
from bud.exceptions import NotFoundError, ValidationError

try:
    response = client.classifications.create(
        model="nonexistent-model",
        input=["Test text"]
    )
except NotFoundError:
    print("Model not found")
except ValidationError as e:
    print(f"Invalid request: {e}")
```

## Best Practices

1. **Batch Processing**: Send multiple texts in one request for efficiency:
   ```python
   # Good - single request
   response = client.classifications.create(
       model="finbert",
       input=["text1", "text2", "text3"]
   )

   # Avoid - multiple requests
   for text in texts:
       response = client.classifications.create(
           model="finbert",
           input=[text]
       )
   ```

2. **Use Priority Wisely**: Reserve `"high"` priority for time-sensitive requests.

3. **Handle All Labels**: Don't assume specific labels exist; iterate over returned scores:
   ```python
   for label_score in response.data[0]:
       # Handle each label dynamically
       process_label(label_score.label, label_score.score)
   ```
