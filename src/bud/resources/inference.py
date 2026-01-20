"""OpenAI-compatible inference API resources."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal, overload

from bud._streaming import Stream
from bud.models.inference import (
    ChatCompletion,
    ChatCompletionChunk,
    EmbeddingResponse,
    Model,
    ModelList,
)
from bud.resources._base import SyncResource

if TYPE_CHECKING:
    from bud._http import HttpClient


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

    Create embeddings for text using OpenAI-compatible models.
    """

    def create(
        self,
        *,
        model: str,
        input: str | list[str],
        encoding_format: Literal["float", "base64"] | None = None,
        dimensions: int | None = None,
        user: str | None = None,
    ) -> EmbeddingResponse:
        """Create embeddings for the given input.

        Args:
            model: ID of the model to use.
            input: Text to embed (string or list of strings).
            encoding_format: Format for the embeddings.
            dimensions: Number of dimensions for the output.
            user: Unique user identifier.

        Returns:
            EmbeddingResponse containing the embeddings.

        Example:
            response = client.embeddings.create(
                model="text-embedding-3-small",
                input="Hello, world!"
            )
            print(len(response.data[0].embedding))  # e.g., 1536
        """
        payload: dict[str, Any] = {
            "model": model,
            "input": input,
        }

        # Add optional parameters (filter out None values)
        optional_params = {
            "encoding_format": encoding_format,
            "dimensions": dimensions,
            "user": user,
        }
        payload.update({k: v for k, v in optional_params.items() if v is not None})

        data = self._http.post("/v1/embeddings", json=payload)
        return EmbeddingResponse.model_validate(data)


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
