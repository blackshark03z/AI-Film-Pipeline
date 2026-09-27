from typing import Literal, Protocol

from pydantic import Field

from ..core import ContractModel, ProviderCapabilities


class ProviderHealth(ContractModel):
    provider_id: str
    state: Literal["READY", "UNAVAILABLE", "AUTH_REQUIRED", "MISCONFIGURED", "INCONCLUSIVE"]
    diagnostic_code: str
    evidence: list[str] = Field(default_factory=list)

    @property
    def routable(self) -> bool:
        return self.state == "READY"


class VideoProvider(Protocol):
    def capabilities(self) -> ProviderCapabilities: ...
    async def preflight(self) -> ProviderHealth: ...
    async def submit(self, request): ...
    async def poll(self, provider_job_id): ...
    async def fetch_outputs(self, provider_job_id): ...
    async def cancel(self, provider_job_id): ...


def routing_availability(health: list[ProviderHealth]) -> dict[str, bool]:
    """Convert normalized health into the core router's availability input."""
    if len({item.provider_id for item in health}) != len(health):
        raise ValueError('duplicate provider health identity')
    return {item.provider_id: item.routable for item in health}
