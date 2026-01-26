"""API resource modules."""

from bud.resources.actions import Actions, AsyncActions
from bud.resources.audit import AsyncAudit, Audit
from bud.resources.auth import AsyncAuth, Auth
from bud.resources.benchmarks import AsyncBenchmarks, Benchmarks
from bud.resources.clusters import AsyncClusters, Clusters
from bud.resources.events import AsyncEvents, Events
from bud.resources.executions import AsyncExecutions, Executions
from bud.resources.inference import (
    Chat,
    ChatCompletions,
    Classifications,
    Embeddings,
    InferenceModels,
)
from bud.resources.pipelines import AsyncPipelines, Pipelines
from bud.resources.schedules import AsyncSchedules, Schedules
from bud.resources.webhooks import AsyncWebhooks, Webhooks

__all__ = [
    # Core resources
    "Pipelines",
    "AsyncPipelines",
    "Executions",
    "AsyncExecutions",
    "Schedules",
    "AsyncSchedules",
    "Webhooks",
    "AsyncWebhooks",
    "Events",
    "AsyncEvents",
    "Actions",
    "AsyncActions",
    # Additional resources
    "Auth",
    "AsyncAuth",
    "Audit",
    "AsyncAudit",
    "Benchmarks",
    "AsyncBenchmarks",
    "Clusters",
    "AsyncClusters",
    # Inference resources
    "Chat",
    "ChatCompletions",
    "Classifications",
    "Embeddings",
    "InferenceModels",
]
