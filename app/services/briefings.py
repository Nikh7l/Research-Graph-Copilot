from __future__ import annotations

from app.models.schemas import Briefing, BriefingRequest
from app.services.agent_client import AgentClientService


class BriefingService:
    def __init__(self, agent_client_service: AgentClientService) -> None:
        self.agent_client_service = agent_client_service

    async def generate(self, request: BriefingRequest) -> Briefing:
        return await self.agent_client_service.generate_briefing(request)
