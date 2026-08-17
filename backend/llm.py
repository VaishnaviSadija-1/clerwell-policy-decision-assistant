"""LLM clients for the decision engine.

``AnthropicClient`` (default) talks to the Claude API through the official
``anthropic`` SDK. ``OpenAICompatClient`` remains available for any
OpenAI-compatible ``/chat/completions`` endpoint. Configuration falls back
to environment variables loaded from a ``.env`` file when constructor
arguments are not supplied.
"""
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

DEFAULT_ANTHROPIC_MODEL = "claude-haiku-4-5"


class LLMError(Exception):
    """Raised for any network error, timeout, or non-2xx response from the
    configured LLM provider. Carries a short, human-readable message —
    never a raw traceback."""


class AnthropicClient:
    """Claude API client via the official ``anthropic`` SDK."""

    def __init__(self, api_key=None, model=None, timeout=None):
        import anthropic

        timeout_env = os.getenv("LLM_TIMEOUT_SECONDS")
        self.model = model or os.getenv("LLM_MODEL") or DEFAULT_ANTHROPIC_MODEL
        self.timeout = (
            timeout if timeout is not None
            else float(timeout_env) if timeout_env else 45.0
        )
        self._client = anthropic.Anthropic(
            api_key=api_key or os.getenv("ANTHROPIC_API_KEY"),
            timeout=self.timeout,
            max_retries=1,
        )

    def complete(self, system: str, user: str) -> str:
        import anthropic

        try:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=2048,
                temperature=0,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AuthenticationError:
            raise LLMError("Language model authentication failed — check ANTHROPIC_API_KEY.")
        except anthropic.RateLimitError:
            raise LLMError("Language model rate limit reached — try again shortly.")
        except anthropic.APIConnectionError:
            raise LLMError("Language model unreachable — check your network connection.")
        except anthropic.APIStatusError as exc:
            raise LLMError(f"Language model request failed with status {exc.status_code}.")
        except anthropic.APIError:
            raise LLMError("Language model request failed.")

        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        if not text:
            raise LLMError("Language model returned an empty response.")
        return text


def default_client():
    """Build the default LLM client from the environment (Claude API)."""
    return AnthropicClient()


class OpenAICompatClient:
    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or "").rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.model = model or os.getenv("LLM_MODEL")
        timeout_env = os.getenv("LLM_TIMEOUT_SECONDS")
        if timeout is not None:
            self.timeout = timeout
        elif timeout_env is not None:
            self.timeout = float(timeout_env)
        else:
            self.timeout = 30

    def complete(self, system: str, user: str) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        last_error = "Language model request failed."
        attempts = 2
        for attempt in range(attempts):
            try:
                response = requests.post(
                    url, json=payload, headers=headers, timeout=self.timeout
                )
            except requests.exceptions.RequestException as exc:
                last_error = f"Language model request failed: {type(exc).__name__}."
            else:
                if 200 <= response.status_code < 300:
                    try:
                        data = response.json()
                        return data["choices"][0]["message"]["content"]
                    except (ValueError, KeyError, IndexError, TypeError):
                        last_error = "Language model returned an unexpected response shape."
                else:
                    last_error = (
                        f"Language model request failed with status "
                        f"{response.status_code}."
                    )

            if attempt < attempts - 1:
                time.sleep(0.05)

        raise LLMError(last_error)
