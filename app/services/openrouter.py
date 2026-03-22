from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any, cast

import httpx

logger = logging.getLogger(__name__)

# Default retry settings
MAX_RETRIES = 3
BASE_DELAY = 2.0  # seconds
MAX_DELAY = 10.0  # cap retry delay


class OpenRouterClient:
    """Client for OpenRouter API supporting chat completions and embeddings.

    Includes exponential backoff retry for 429 rate limiting.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        chat_model: str,
        embedding_model: str,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embedding_model = embedding_model

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        payload: dict[str, Any],
        timeout: float = 120.0,
    ) -> dict[str, Any]:
        """Make an HTTP request with exponential backoff on 429."""
        for attempt in range(MAX_RETRIES):
            logger.info(
                "  → Sending %s request (attempt %d/%d)",
                method,
                attempt + 1,
                MAX_RETRIES,
            )
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        headers=self._headers,
                        json=payload,
                    )
            except httpx.TimeoutException:
                logger.warning(
                    "  ✗ %s request timed out after %.0fs (attempt %d/%d)",
                    method,
                    timeout,
                    attempt + 1,
                    MAX_RETRIES,
                )
                continue

            if response.status_code == 429:
                delay = min(BASE_DELAY * (2**attempt), MAX_DELAY)
                retry_after = response.headers.get("retry-after")
                if retry_after:
                    with contextlib.suppress(ValueError):
                        delay = max(delay, float(retry_after))
                logger.warning(
                    "  ✗ Rate limited (429) on %s, retry %d/%d in %.1fs",
                    method,
                    attempt + 1,
                    MAX_RETRIES,
                    delay,
                )
                await asyncio.sleep(delay)
                continue

            response.raise_for_status()
            logger.info("  ✓ %s request succeeded", method)
            return cast(dict[str, Any], response.json())

        # All retries exhausted
        raise httpx.TimeoutException(f"{method} failed after {MAX_RETRIES} attempts")

    async def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, Any] | None = None,
        temperature: float = 0.1,
    ) -> str:
        """Send a chat completion request with retry."""
        payload: dict[str, Any] = {
            "model": self.chat_model,
            "temperature": temperature,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "provider": {
                "order": ["google-vertex"],
            },
        }
        if response_format:
            payload["response_format"] = response_format

        body = await self._request_with_retry(
            "chat",
            f"{self.base_url}/chat/completions",
            payload,
        )
        content = body["choices"][0]["message"]["content"]
        return cast(str, content)

    async def chat_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
    ) -> str:
        """Send a chat request with JSON response format."""
        return await self.chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format={"type": "json_object"},
            temperature=temperature,
        )

    async def embed(self, text: str) -> list[float]:
        """Generate embedding for a single text with retry."""
        payload = {
            "model": self.embedding_model,
            "input": text,
        }
        body = await self._request_with_retry(
            "embed",
            f"{self.base_url}/embeddings",
            payload,
            timeout=30.0,
        )
        embedding = body["data"][0]["embedding"]
        return cast(list[float], embedding)

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 20,
        delay: float = 1.0,
    ) -> list[list[float]]:
        """Generate embeddings with batching and retry.

        OpenAI-compatible APIs accept a list of inputs.
        We batch to stay within request size limits.
        """
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            payload = {
                "model": self.embedding_model,
                "input": batch,
            }

            body = await self._request_with_retry(
                "embed_batch",
                f"{self.base_url}/embeddings",
                payload,
            )

            # Sort by index to maintain order
            sorted_data = sorted(body["data"], key=lambda x: x["index"])
            all_embeddings.extend([item["embedding"] for item in sorted_data])

            if i + batch_size < len(texts):
                await asyncio.sleep(delay)

        return all_embeddings
