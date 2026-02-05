"""Auto-instrumentation for OpenAI SDK."""

import functools
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..tracker import CostTracker

_original_create = None
_tracker = None


def instrument(tracker: "CostTracker") -> None:
    """Monkey-patch OpenAI SDK to track costs."""
    global _original_create, _tracker

    try:
        import openai
    except ImportError:
        raise ImportError("openai package not installed. Run: pip install openai")

    if _original_create is not None:
        return  # Already instrumented

    _tracker = tracker
    _original_create = openai.resources.chat.completions.Completions.create

    @functools.wraps(_original_create)
    def tracked_create(self, *args, **kwargs):
        start = time.perf_counter()
        result = _original_create(self, *args, **kwargs)
        duration_ms = int((time.perf_counter() - start) * 1000)

        if result.usage:
            _tracker.track(
                model=result.model,
                input_tokens=result.usage.prompt_tokens,
                output_tokens=result.usage.completion_tokens,
                duration_ms=duration_ms,
            )

        return result

    openai.resources.chat.completions.Completions.create = tracked_create


def uninstrument() -> None:
    """Remove instrumentation."""
    global _original_create, _tracker

    if _original_create is None:
        return

    try:
        import openai
        openai.resources.chat.completions.Completions.create = _original_create
        _original_create = None
        _tracker = None
    except ImportError:
        pass
