"""Auto-instrumentation for Anthropic SDK."""

import functools
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..tracker import CostTracker

_original_create = None
_tracker = None


def instrument(tracker: "CostTracker") -> None:
    """Monkey-patch Anthropic SDK to track costs."""
    global _original_create, _tracker

    try:
        import anthropic
    except ImportError:
        raise ImportError("anthropic package not installed. Run: pip install anthropic")

    if _original_create is not None:
        return  # Already instrumented

    _tracker = tracker
    _original_create = anthropic.resources.messages.Messages.create

    @functools.wraps(_original_create)
    def tracked_create(self, *args, **kwargs):
        start = time.perf_counter()
        result = _original_create(self, *args, **kwargs)
        duration_ms = int((time.perf_counter() - start) * 1000)

        _tracker.track(
            model=result.model,
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            duration_ms=duration_ms,
        )

        return result

    anthropic.resources.messages.Messages.create = tracked_create


def uninstrument() -> None:
    """Remove instrumentation."""
    global _original_create, _tracker

    if _original_create is None:
        return

    try:
        import anthropic
        anthropic.resources.messages.Messages.create = _original_create
        _original_create = None
        _tracker = None
    except ImportError:
        pass
