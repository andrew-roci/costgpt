"""Cost tracking SDK."""

import functools
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable
from uuid import UUID, uuid4

from .pricing import get_cost


@dataclass
class UsageEvent:
    """A single LLM usage event."""
    id: UUID
    timestamp: datetime
    model: str
    input_tokens: int
    output_tokens: int
    input_cost: float
    output_cost: float
    total_cost: float
    duration_ms: int | None = None
    user_id: str | None = None
    feature: str | None = None
    metadata: dict = field(default_factory=dict)


class CostTracker:
    """Track LLM costs with attribution."""

    def __init__(
        self,
        api_key: str | None = None,
        api_url: str = "https://api.cost-gpt.com",
        default_user_id: str | None = None,
        default_feature: str | None = None,
    ):
        """
        Initialize the cost tracker.

        Args:
            api_key: API key for hosted service
            api_url: Base URL for API
            default_user_id: Default user ID for all events
            default_feature: Default feature tag for all events
        """
        self.api_key = api_key
        self.api_url = api_url
        self.default_user_id = default_user_id
        self.default_feature = default_feature
        self._client = None

        if api_key:
            from .client import APIClient
            self._client = APIClient(api_key, api_url)

    def track(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        user_id: str | None = None,
        feature: str | None = None,
        duration_ms: int | None = None,
        metadata: dict | None = None,
    ) -> UsageEvent:
        """
        Track a single LLM usage event.

        Args:
            model: Model name (e.g., "claude-sonnet-4-20250514")
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            user_id: User who triggered this call
            feature: Feature/endpoint that triggered this call
            duration_ms: Call duration in milliseconds
            metadata: Additional metadata

        Returns:
            UsageEvent with calculated costs
        """
        input_cost, output_cost, total_cost = get_cost(model, input_tokens, output_tokens)

        event = UsageEvent(
            id=uuid4(),
            timestamp=datetime.now(timezone.utc),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
            duration_ms=duration_ms,
            user_id=user_id or self.default_user_id,
            feature=feature or self.default_feature,
            metadata=metadata or {},
        )

        # Send to API if configured
        if self._client:
            self._client.send_event(event)

        return event

    def instrument_anthropic(self) -> None:
        """Auto-instrument the Anthropic SDK."""
        from .instruments import anthropic as anthropic_instrument
        anthropic_instrument.instrument(self)

    def instrument_openai(self) -> None:
        """Auto-instrument the OpenAI SDK."""
        from .instruments import openai as openai_instrument
        openai_instrument.instrument(self)


def track_usage(
    tracker: CostTracker,
    model: str,
    user_id: str | None = None,
    feature: str | None = None,
):
    """
    Decorator to track LLM usage from a function that returns a response object.

    The decorated function must return an object with:
    - usage.input_tokens
    - usage.output_tokens

    Example:
        @track_usage(tracker, model="claude-sonnet-4-20250514", feature="chat")
        def call_llm(prompt):
            return client.messages.create(...)
    """
    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = fn(*args, **kwargs)
            duration_ms = int((time.perf_counter() - start) * 1000)

            # Extract token usage from response
            input_tokens = getattr(getattr(result, 'usage', None), 'input_tokens', 0)
            output_tokens = getattr(getattr(result, 'usage', None), 'output_tokens', 0)

            tracker.track(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                user_id=user_id,
                feature=feature,
                duration_ms=duration_ms,
            )

            return result
        return wrapper
    return decorator
