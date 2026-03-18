from typing import Protocol, List
from app.models.schemas import BoceResultResponse

class DetectionProvider(Protocol):
    async def create_task(self, url: str) -> str:
        """Create a detection task and return the provider's task ID."""
        ...

    async def poll_result(self, provider_task_id: str) -> BoceResultResponse:
        """Poll and return normalized results."""
        ...

    async def get_balance(self) -> dict:
        """Return provider-specific balance information."""
        ...
