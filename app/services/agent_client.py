from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from contextlib import asynccontextmanager
from typing import Any, cast

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.core.config import Settings
from app.models.schemas import Briefing, BriefingRequest, EvidenceItem, QueryResponse
from app.services.openrouter import OpenRouterClient

TOOL_PLANNER_PROMPT = """You are a research agent planner.
Choose 1 to 4 MCP tools that will answer the user's question with evidence.
Prefer deterministic graph tools. Do not invent tool names.
Return valid JSON with this shape:
{
  "search_mode": "entity|theme|comparative",
  "calls": [
    {"tool_name": "tool_name_here", "arguments": {"arg": "value"}}
  ]
}
"""


ANSWER_PROMPT = """You are an AI research analyst.
Answer the user's question strictly from the supplied MCP tool results.
Use citations from the tool outputs. If evidence is missing, say so.
"""


class AgentClientService:
    def __init__(self, settings: Settings, llm_client: OpenRouterClient | None) -> None:
        self.settings = settings
        self.llm_client = llm_client

    async def answer(
        self,
        question: str,
        search_mode: str = "auto",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> QueryResponse:
        if not self.llm_client:
            return QueryResponse(
                answer="The agent client requires an OpenRouter API key.",
                search_mode="none",
                confidence_note="No OpenRouter client available.",
            )

        async with self._open_session() as session:
            await session.initialize()
            plan = await self._build_plan(session, question, search_mode, start_date, end_date)
            trace = []
            graph_paths: list[list[str]] = []
            related_methods: list[str] = []
            evidence: list[EvidenceItem] = []
            tool_payloads: list[dict[str, Any]] = []
            tool_errors: list[str] = []

            for call in plan["calls"]:
                result = await session.call_tool(call["tool_name"], call["arguments"])
                payload = result.structuredContent or self._content_to_dict(result.content)
                if getattr(result, "isError", False):
                    tool_errors.append(f"{call['tool_name']}: {payload}")
                trace.append(
                    {
                        "tool_name": call["tool_name"],
                        "arguments": call["arguments"],
                        "result": payload,
                    }
                )
                tool_payloads.append({"tool_name": call["tool_name"], "payload": payload})
                evidence.extend(self._extract_evidence(payload))
                related_methods.extend(self._extract_methods(payload))
                graph_paths.extend(payload.get("paths", []))

            answer = await self.llm_client.chat(
                system_prompt=ANSWER_PROMPT,
                user_prompt=self._build_answer_prompt(question, tool_payloads),
                temperature=0.2,
            )
            return QueryResponse(
                answer=answer,
                search_mode=plan["search_mode"],
                evidence=self._dedupe_evidence(evidence),
                related_methods=list(dict.fromkeys(m for m in related_methods if m)),
                graph_paths=graph_paths,
                tool_trace=trace,
                confidence_note=self._build_confidence_note(evidence, tool_errors),
            )

    async def generate_briefing(self, request: BriefingRequest) -> Briefing:
        response = await self.answer(
            question=f"Generate a concise research briefing on {request.topic}.",
            search_mode="theme",
            start_date=request.start_date,
            end_date=request.end_date,
        )
        briefing_id = f"{request.topic}:{request.start_date}:{request.end_date}".encode().hex()[:16]
        return Briefing(
            briefing_id=briefing_id,
            topic=request.topic,
            start_date=request.start_date,
            end_date=request.end_date,
            summary=response.answer,
            citations=[item.citation for item in response.evidence[: request.max_sources]],
        )

    async def _build_plan(
        self,
        session: ClientSession,
        question: str,
        search_mode: str,
        start_date: str | None,
        end_date: str | None,
    ) -> dict[str, Any]:
        llm_client = self.llm_client
        if llm_client is None:
            return self._default_plan(question, search_mode, start_date, end_date)

        tools = await session.list_tools()
        available_tool_names = {tool.name for tool in tools.tools}
        tool_descriptions = [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in tools.tools
        ]
        payload = {
            "question": question,
            "requested_search_mode": search_mode,
            "dates": {"start_date": start_date, "end_date": end_date},
            "tools": tool_descriptions,
        }
        raw_plan = await llm_client.chat_json(
            system_prompt=TOOL_PLANNER_PROMPT,
            user_prompt=json.dumps(payload, indent=2),
            temperature=0.1,
        )
        try:
            parsed = json.loads(raw_plan)
        except json.JSONDecodeError:
            return self._default_plan(question, search_mode, start_date, end_date)

        calls = parsed.get("calls") or []
        filtered_calls = [
            call
            for call in calls
            if isinstance(call, dict)
            and call.get("tool_name") in available_tool_names
            and isinstance(call.get("arguments"), dict)
        ]
        if not filtered_calls:
            return self._default_plan(question, search_mode, start_date, end_date)
        return {
            "search_mode": parsed.get(
                "search_mode",
                search_mode if search_mode != "auto" else "entity",
            ),
            "calls": filtered_calls[:4],
        }

    def _default_plan(
        self,
        question: str,
        search_mode: str,
        start_date: str | None,
        end_date: str | None,
    ) -> dict[str, Any]:
        if search_mode == "comparative":
            return {
                "search_mode": "comparative",
                "calls": [
                    {
                        "tool_name": "search_papers",
                        "arguments": {
                            "query": question,
                            "limit": 8,
                            "start_date": start_date,
                            "end_date": end_date,
                        },
                    },
                    {
                        "tool_name": "get_topic_summary",
                        "arguments": {},
                    },
                ],
            }
        if search_mode == "theme":
            return {
                "search_mode": "theme",
                "calls": [
                    {
                        "tool_name": "get_topic_summary",
                        "arguments": {
                            "topic": self.settings.corpus_topic,
                            "start_date": start_date,
                            "end_date": end_date,
                        },
                    },
                    {
                        "tool_name": "search_papers",
                        "arguments": {
                            "query": question,
                            "limit": 8,
                            "start_date": start_date,
                            "end_date": end_date,
                        },
                    },
                ],
            }
        return {
            "search_mode": "entity",
            "calls": [
                {
                    "tool_name": "search_papers",
                    "arguments": {
                        "query": question,
                        "limit": 8,
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                },
                {
                    "tool_name": "get_relationship_counts",
                    "arguments": {},
                },
            ],
        }

    @asynccontextmanager
    async def _open_session(self):
        env = os.environ.copy()
        env.setdefault("APP_ENV", self.settings.app_env)
        env.setdefault("NEO4J_URI", self.settings.neo4j_uri)
        env.setdefault("NEO4J_USERNAME", self.settings.neo4j_username)
        env.setdefault("NEO4J_PASSWORD", self.settings.neo4j_password)
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", "app.mcp_runner"],
            env=env,
        )
        async with stdio_client(params) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                yield session

    def _build_answer_prompt(self, question: str, tool_payloads: list[dict[str, Any]]) -> str:
        return json.dumps({"question": question, "tool_results": tool_payloads}, indent=2)

    def _content_to_dict(self, content: Sequence[Any]) -> dict[str, Any]:
        text_parts = []
        for item in content:
            maybe_text = getattr(item, "text", None)
            if maybe_text:
                text_parts.append(maybe_text)
        if not text_parts:
            return {}
        try:
            parsed = json.loads("\n".join(text_parts))
            if isinstance(parsed, dict):
                return cast(dict[str, Any], parsed)
            return {"content": parsed}
        except json.JSONDecodeError:
            return {"text": "\n".join(text_parts)}

    def _extract_evidence(self, payload: dict[str, Any]) -> list[EvidenceItem]:
        evidence: list[EvidenceItem] = []
        for paper in payload.get("papers", []):
            evidence.append(
                EvidenceItem(
                    title=paper.get("title", ""),
                    paper_id=paper.get("paper_id", ""),
                    citation=f"{paper.get('title', '')} ({paper.get('publication_date', 'n.d.')})",
                    score=paper.get("score"),
                    metadata={"source": payload.get("query") or payload.get("method_name")},
                )
            )
        for claim in payload.get("claims", []):
            if isinstance(claim, dict):
                evidence.append(
                    EvidenceItem(
                        title=str(
                            claim.get(
                                "title",
                                claim.get("paper_title", claim.get("paper_id", "Claim")),
                            )
                        ),
                        paper_id=claim.get("paper_id", ""),
                        citation=(
                            f"{claim.get('paper_title', claim.get('paper_id', 'Unknown source'))}"
                        ),
                        snippet=claim.get("statement") or claim.get("evidence_span"),
                    )
                )
            elif isinstance(claim, str):
                evidence.append(
                    EvidenceItem(
                        title=payload.get("topic", payload.get("method_name", "Claim")),
                        paper_id="",
                        citation=payload.get("topic", payload.get("method_name", "Unknown source")),
                        snippet=claim,
                    )
                )
        comparison = payload.get("comparison", {})
        for comparison_payload in comparison.values():
            for paper in comparison_payload.get("papers", []):
                evidence.append(
                    EvidenceItem(
                        title=paper.get("title", ""),
                        paper_id=paper.get("paper_id", ""),
                        citation=(
                            f"{paper.get('title', '')} ({paper.get('publication_date', 'n.d.')})"
                        ),
                    )
                )
        return evidence

    def _extract_methods(self, payload: dict[str, Any]) -> list[str]:
        methods = list(payload.get("methods", []))
        method_name = payload.get("method_name")
        if method_name:
            methods.append(method_name)
        comparison = payload.get("comparison", {})
        methods.extend(comparison.keys())
        return methods

    def _dedupe_evidence(self, evidence: list[EvidenceItem]) -> list[EvidenceItem]:
        deduped: dict[tuple[str, str], EvidenceItem] = {}
        for item in evidence:
            key = (item.paper_id, item.citation)
            deduped.setdefault(key, item)
        return list(deduped.values())[:12]

    def _build_confidence_note(
        self,
        evidence: list[EvidenceItem],
        tool_errors: list[str],
    ) -> str | None:
        if tool_errors and not evidence:
            return "Some MCP tool calls failed and returned no usable evidence."
        if tool_errors:
            return "Some MCP tool calls failed, but partial evidence was still returned."
        if not evidence:
            return "Tool calls returned sparse evidence."
        return None
