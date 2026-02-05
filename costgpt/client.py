"""API client for hosted CostGPT service."""

import httpx
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .tracker import UsageEvent


class APIClient:
    """HTTP client for the CostGPT API."""

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self._client = httpx.Client(
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )

    def send_event(self, event: "UsageEvent") -> None:
        """Send a usage event to the API."""
        payload = {
            "id": str(event.id),
            "timestamp": event.timestamp.isoformat(),
            "model": event.model,
            "input_tokens": event.input_tokens,
            "output_tokens": event.output_tokens,
            "input_cost": event.input_cost,
            "output_cost": event.output_cost,
            "total_cost": event.total_cost,
            "duration_ms": event.duration_ms,
            "user_id": event.user_id,
            "feature": event.feature,
            "metadata": event.metadata,
        }

        try:
            response = self._client.post(f"{self.base_url}/v1/events", json=payload)
            response.raise_for_status()
        except httpx.HTTPError:
            # Fail silently - don't break the app if tracking fails
            pass

    def send_events_batch(self, events: list["UsageEvent"]) -> None:
        """Send multiple events in a single request."""
        payload = {
            "events": [
                {
                    "id": str(e.id),
                    "timestamp": e.timestamp.isoformat(),
                    "model": e.model,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "input_cost": e.input_cost,
                    "output_cost": e.output_cost,
                    "total_cost": e.total_cost,
                    "duration_ms": e.duration_ms,
                    "user_id": e.user_id,
                    "feature": e.feature,
                    "metadata": e.metadata,
                }
                for e in events
            ]
        }

        try:
            response = self._client.post(f"{self.base_url}/v1/events/batch", json=payload)
            response.raise_for_status()
        except httpx.HTTPError:
            pass
