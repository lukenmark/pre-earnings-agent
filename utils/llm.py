import asyncio
import os
import time

import anthropic
from dotenv import load_dotenv

from utils.logger import logger

load_dotenv()

DEFAULT_MODEL = "claude-sonnet-4-6"
FALLBACK_MODEL = "claude-haiku-4-5-20251001"

COST_PER_MTok = {
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-haiku-4-5-20251001": {
        "input": 0.80,
        "output": 4.00,
        "cache_write": 1.00,
        "cache_read": 0.08,
    },
}


class LLMClient:
    def __init__(self, model: str = DEFAULT_MODEL, use_cache: bool = True):
        self.client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = model
        self.use_cache = use_cache
        self._session_tokens = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
        self._session_cost = 0.0

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        operation_name: str = "unknown",
        use_haiku: bool = False,
        max_tokens: int = 4096,
    ) -> str:
        """Send a completion request. Returns response text."""
        model = FALLBACK_MODEL if use_haiku else self.model

        if self.use_cache:
            system_param = [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_param = system_prompt

        last_error = None
        for attempt in range(1, 4):
            try:
                response = self.client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    system=system_param,
                    messages=[{"role": "user", "content": user_message}],
                )
                usage = response.usage
                cost = self._calculate_cost(model, usage)

                # Accumulate session stats
                self._session_tokens["input"] += getattr(usage, "input_tokens", 0)
                self._session_tokens["output"] += getattr(usage, "output_tokens", 0)
                self._session_tokens["cache_write"] += getattr(usage, "cache_creation_input_tokens", 0)
                self._session_tokens["cache_read"] += getattr(usage, "cache_read_input_tokens", 0)
                self._session_cost += cost

                logger.debug(
                    f"LLM [{operation_name}] model={model} "
                    f"in={usage.input_tokens} out={usage.output_tokens} "
                    f"cost=${cost:.6f}"
                )
                return response.content[0].text

            except anthropic.RateLimitError as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"LLM rate limit [{operation_name}] attempt {attempt}/3 — waiting {wait}s")
                time.sleep(wait)
            except anthropic.APIError as e:
                last_error = e
                logger.warning(f"LLM API error [{operation_name}] attempt {attempt}/3: {e}")
                if attempt < 3:
                    time.sleep(2 ** attempt)

        raise RuntimeError(f"LLM [{operation_name}] failed after 3 attempts: {last_error}")

    def _calculate_cost(self, model: str, usage) -> float:
        """Calculate cost from usage object."""
        rates = COST_PER_MTok.get(model, COST_PER_MTok[DEFAULT_MODEL])
        return (
            (getattr(usage, "input_tokens", 0) / 1_000_000) * rates["input"]
            + (getattr(usage, "output_tokens", 0) / 1_000_000) * rates["output"]
            + (getattr(usage, "cache_creation_input_tokens", 0) / 1_000_000) * rates["cache_write"]
            + (getattr(usage, "cache_read_input_tokens", 0) / 1_000_000) * rates["cache_read"]
        )

    def get_session_stats(self) -> dict:
        """Returns total tokens used and estimated cost for this session."""
        return {
            "input_tokens": self._session_tokens["input"],
            "output_tokens": self._session_tokens["output"],
            "cache_write_tokens": self._session_tokens["cache_write"],
            "cache_read_tokens": self._session_tokens["cache_read"],
            "total_tokens": sum(self._session_tokens.values()),
            "total_cost": self._session_cost,
        }

    def log_session_summary(self) -> None:
        """Logs a summary of session token usage and cost."""
        stats = self.get_session_stats()
        logger.info(
            f"LLM session summary: "
            f"in={stats['input_tokens']} out={stats['output_tokens']} "
            f"cache_write={stats['cache_write_tokens']} cache_read={stats['cache_read_tokens']} "
            f"total={stats['total_tokens']} cost=${stats['total_cost']:.6f}"
        )


_default_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client


async def complete_async(
    system_prompt: str,
    user_message: str,
    operation_name: str = "unknown",
    use_haiku: bool = False,
    max_tokens: int = 4096,
) -> str:
    """Async wrapper using asyncio.to_thread."""
    client = get_llm_client()
    return await asyncio.to_thread(
        client.complete,
        system_prompt,
        user_message,
        operation_name,
        use_haiku,
        max_tokens,
    )
