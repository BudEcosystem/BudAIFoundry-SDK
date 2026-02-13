"""OpenAI-compatible inference API resources."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from bud._streaming import Stream
from bud.models.inference import (
    ChatCompletion,
    ChatCompletionChunk,
    ClassifyResponse,
    EmbeddingResponse,
    Model,
    ModelList,
)
from bud.resources._base import AsyncResource, SyncResource

if TYPE_CHECKING:
    from bud._http import HttpClient
    from bud._response_streaming import AsyncResponseStream, ResponseStream


class ChatCompletions(SyncResource):
    """Chat completion operations.

    Create chat completions using OpenAI-compatible models.
    """

    @overload
    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: Literal[False] = False,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        stop: str | list[str] | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        user: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> ChatCompletion: ...

    @overload
    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: Literal[True],
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        stop: str | list[str] | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        user: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> Stream[ChatCompletionChunk]: ...

    def create(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        stream: bool = False,
        temperature: float | None = None,
        top_p: float | None = None,
        max_tokens: int | None = None,
        stop: str | list[str] | None = None,
        presence_penalty: float | None = None,
        frequency_penalty: float | None = None,
        user: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> ChatCompletion | Stream[ChatCompletionChunk]:
        """Create a chat completion.

        Args:
            model: ID of the model to use.
            messages: List of messages in the conversation.
            stream: If True, returns a streaming iterator.
            temperature: Sampling temperature (0-2).
            top_p: Nucleus sampling probability.
            max_tokens: Maximum tokens to generate.
            stop: Stop sequences.
            presence_penalty: Presence penalty (-2.0 to 2.0).
            frequency_penalty: Frequency penalty (-2.0 to 2.0).
            user: Unique user identifier.
            tools: List of tools the model may call.
            tool_choice: Controls which tool is called.

        Returns:
            ChatCompletion or Stream[ChatCompletionChunk] if streaming.

        Example:
            # Non-streaming
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello!"}]
            )
            print(response.choices[0].message.content)

            # Streaming
            stream = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello!"}],
                stream=True
            )
            for chunk in stream:
                if chunk.choices[0].delta.content:
                    print(chunk.choices[0].delta.content, end="")
        """
        # Validate message count to prevent DoS
        max_messages = 1000
        if len(messages) > max_messages:
            raise ValueError(f"messages list exceeds maximum of {max_messages} messages")

        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        # Add optional parameters (filter out None values)
        optional_params = {
            "temperature": temperature,
            "top_p": top_p,
            "max_tokens": max_tokens,
            "stop": stop,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "user": user,
            "tools": tools,
            "tool_choice": tool_choice,
        }
        payload.update({k: v for k, v in optional_params.items() if v is not None})

        if stream:
            response_ctx = self._http.stream("POST", "/v1/chat/completions", json=payload)
            response = response_ctx.__enter__()
            # Pass the context manager so Stream can clean it up properly
            return Stream(response, ChatCompletionChunk, response_context=response_ctx)
        else:
            data = self._http.post("/v1/chat/completions", json=payload)
            return ChatCompletion.model_validate(data)


class Chat(SyncResource):
    """Chat resource wrapper providing access to completions.

    Example:
        client.chat.completions.create(...)
    """

    def __init__(self, http: HttpClient) -> None:
        super().__init__(http)
        self.completions = ChatCompletions(http)


class Embeddings(SyncResource):
    """Text embedding operations.

    Create embeddings for text, images, or audio using OpenAI-compatible models.
    """

    def create(
        self,
        *,
        model: str,
        input: str | list[str],
        encoding_format: Literal["float", "base64"] | None = None,
        modality: Literal["text", "image", "audio"] | None = None,
        dimensions: int | None = None,
        priority: Literal["high", "normal", "low"] | None = None,
        user: str | None = None,
        include_input: bool | None = None,
        chunking: dict[str, Any] | None = None,
        cache_options: dict[str, Any] | None = None,
    ) -> EmbeddingResponse:
        """Create embeddings for the given input.

        Args:
            model: ID of the model to use.
            input: Text strings, URLs, or base64 data to embed.
            encoding_format: Format for the embeddings ("float" or "base64").
            modality: Input modality ("text", "image", or "audio").
            dimensions: Number of dimensions for the output (0 for full).
            priority: Request priority ("high", "normal", or "low").
            user: Unique user identifier.
            include_input: Return original text in response (text modality only).
            chunking: Chunking configuration for automatic text chunking.
            cache_options: Cache options with "enabled" ("on"/"off") and "max_age_s".

        Returns:
            EmbeddingResponse containing the embeddings.

        Example:
            # Basic text embedding
            response = client.embeddings.create(
                model="BAAI/bge-small-en-v1.5",
                input="Hello, world!"
            )
            print(len(response.data[0].embedding))

            # With chunking
            response = client.embeddings.create(
                model="BAAI/bge-small-en-v1.5",
                input="Long text to chunk...",
                chunking={"strategy": "sentence", "chunk_size": 512}
            )

            # With caching
            response = client.embeddings.create(
                model="BAAI/bge-small-en-v1.5",
                input="Hello, world!",
                cache_options={"enabled": "on", "max_age_s": 3600}
            )
        """
        payload: dict[str, Any] = {
            "model": model,
            "input": input,
        }

        # Add optional parameters (filter out None values)
        optional_params = {
            "encoding_format": encoding_format,
            "modality": modality,
            "dimensions": dimensions,
            "priority": priority,
            "user": user,
            "include_input": include_input,
            "chunking": chunking,
        }
        payload.update({k: v for k, v in optional_params.items() if v is not None})

        # Add cache options with special key
        if cache_options is not None:
            payload["tensorzero::cache_options"] = cache_options

        data = self._http.post("/v1/embeddings", json=payload)
        return EmbeddingResponse.model_validate(data)


class Classifications(SyncResource):
    """Text classification operations.

    Classify text using deployed classifier models.
    """

    def create(
        self,
        *,
        input: list[str],
        model: str = "default/not-specified",
        raw_scores: bool | None = None,
        priority: Literal["high", "normal", "low"] | None = None,
    ) -> ClassifyResponse:
        """Classify the given input texts.

        Args:
            input: List of text strings to classify.
            model: ID of the classifier model to use.
            raw_scores: If True, return raw scores instead of normalized probabilities.
            priority: Request priority ("high", "normal", or "low").

        Returns:
            ClassifyResponse containing classification results with label-score pairs.

        Example:
            response = client.classifications.create(
                model="ProsusAI/finbert",
                input=["The stock market is performing well today"]
            )
            for result in response.data:
                for label_score in result:
                    print(f"{label_score.label}: {label_score.score}")
        """
        payload: dict[str, Any] = {
            "model": model,
            "input": input,
        }

        # Add optional parameters (filter out None values)
        optional_params = {
            "raw_scores": raw_scores,
            "priority": priority,
        }
        payload.update({k: v for k, v in optional_params.items() if v is not None})

        data = self._http.post("/v1/classify", json=payload)
        return ClassifyResponse.model_validate(data)


class InferenceModels(SyncResource):
    """Model listing operations.

    List and retrieve available models.
    """

    def list(self) -> ModelList:
        """List all available models.

        Returns:
            ModelList containing available models.

        Example:
            models = client.models.list()
            for model in models.data:
                print(f"{model.id} - {model.owned_by}")
        """
        data = self._http.get("/v1/models")
        return ModelList.model_validate(data)

    def retrieve(self, model_id: str) -> Model:
        """Retrieve a specific model by ID.

        Args:
            model_id: The ID of the model to retrieve.

        Returns:
            Model information.

        Example:
            model = client.models.retrieve("gpt-4")
            print(f"Model: {model.id}, Created: {model.created}")
        """
        data = self._http.get(f"/v1/models/{model_id}")
        return Model.model_validate(data)


class Responses(SyncResource):
    """OpenAI Responses API operations.

    Create responses using the /v1/responses endpoint with support for
    multi-turn conversations, tool use, and streaming.
    """

    @overload
    def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: Literal[False] = False,
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> Any: ...  # openai.types.responses.Response

    @overload
    def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: Literal[True],
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> ResponseStream: ...

    def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: bool = False,
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> Any:
        """Create a response using the Responses API.

        Args:
            model: Model ID. Required unless ``prompt`` is provided.
            input: Text string or list of input messages.
            stream: If True, returns a ResponseStream.
            instructions: System instructions for the model.
            previous_response_id: ID of a previous response for multi-turn.
            temperature: Sampling temperature (0-2).
            top_p: Nucleus sampling probability.
            max_output_tokens: Maximum tokens to generate.
            tools: List of tools the model may call.
            tool_choice: Controls which tool is called.
            parallel_tool_calls: Allow parallel tool calls.
            reasoning: Reasoning configuration.
            metadata: Key-value metadata.
            user: Unique user identifier.
            prompt: Stored prompt configuration (alternative to model+input).
            store: Whether to store the response.
            background: Whether to run in the background.
            service_tier: Service tier for the request.
            text: Text generation configuration.
            truncation: Truncation strategy.
            include: Additional fields to include in response.

        Returns:
            openai.types.responses.Response or ResponseStream if streaming.

        Raises:
            ValueError: If neither ``model`` nor ``prompt`` is provided.
        """
        if model is None and prompt is None:
            raise ValueError("At least one of 'model' or 'prompt' must be provided")

        payload: dict[str, Any] = {}
        if stream:
            payload["stream"] = True

        # Add all non-None parameters
        optional_params = {
            "model": model,
            "input": input,
            "instructions": instructions,
            "previous_response_id": previous_response_id,
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": parallel_tool_calls,
            "reasoning": reasoning,
            "metadata": metadata,
            "user": user,
            "prompt": prompt,
            "store": store,
            "background": background,
            "service_tier": service_tier,
            "text": text,
            "truncation": truncation,
            "include": include,
        }
        payload.update({k: v for k, v in optional_params.items() if v is not None})

        if stream:
            from bud._response_streaming import ResponseStream

            response_ctx = self._http.stream("POST", "/v1/responses", json=payload)
            response = response_ctx.__enter__()
            return ResponseStream(response, response_context=response_ctx)
        else:
            from openai.types.responses import Response

            data = self._http.post("/v1/responses", json=payload)
            return Response.model_validate(data)


class AsyncResponses(AsyncResource):
    """Async OpenAI Responses API operations.

    Async version of Responses resource.
    """

    @overload
    async def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: Literal[False] = False,
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> Any: ...  # openai.types.responses.Response

    @overload
    async def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: Literal[True],
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> AsyncResponseStream: ...

    async def create(
        self,
        *,
        model: str | None = None,
        input: str | list[dict[str, Any]] | None = None,
        stream: bool = False,
        instructions: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        max_output_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
        parallel_tool_calls: bool | None = None,
        reasoning: dict[str, Any] | None = None,
        metadata: dict[str, str] | None = None,
        user: str | None = None,
        prompt: dict[str, Any] | None = None,
        store: bool | None = None,
        background: bool | None = None,
        service_tier: str | None = None,
        text: dict[str, Any] | None = None,
        truncation: str | None = None,
        include: list[str] | None = None,
    ) -> Any:
        """Create a response using the Responses API (async).

        Same parameters as Responses.create(). See that method for full docs.
        """
        if model is None and prompt is None:
            raise ValueError("At least one of 'model' or 'prompt' must be provided")

        payload: dict[str, Any] = {}
        if stream:
            payload["stream"] = True

        optional_params = {
            "model": model,
            "input": input,
            "instructions": instructions,
            "previous_response_id": previous_response_id,
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
            "tools": tools,
            "tool_choice": tool_choice,
            "parallel_tool_calls": parallel_tool_calls,
            "reasoning": reasoning,
            "metadata": metadata,
            "user": user,
            "prompt": prompt,
            "store": store,
            "background": background,
            "service_tier": service_tier,
            "text": text,
            "truncation": truncation,
            "include": include,
        }
        payload.update({k: v for k, v in optional_params.items() if v is not None})

        if stream:
            from bud._response_streaming import AsyncResponseStream

            response_ctx = self._http.async_stream("POST", "/v1/responses", json=payload)
            response = await response_ctx.__aenter__()
            return AsyncResponseStream(response, response_context=response_ctx)
        else:
            from openai.types.responses import Response

            data = await self._http.post("/v1/responses", json=payload)
            return Response.model_validate(data)
