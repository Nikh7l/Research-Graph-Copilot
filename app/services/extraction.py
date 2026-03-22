from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from hashlib import sha1

from app.models.schemas import Claim, ExtractedClaim, ExtractedMethod, Method, Paper, Provenance
from app.services.normalization import (
    canonicalize_method,
    dedupe_preserve_order,
    get_method_category,
)
from app.services.openrouter import OpenRouterClient

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are a research extraction agent specialized "
    "in agent tool-call reliability.\n\n"
    "Given a paper title and abstract, extract:\n"
    "1. **Methods** — techniques, approaches, or strategies "
    "discussed (e.g., structured outputs, retry mechanisms, "
    "tool routing)\n"
    "2. **Claims** — specific factual assertions or findings "
    "made by the paper\n\n"
    "Return a JSON object with this exact structure:\n"
    "{\n"
    '  "methods": [\n'
    "    {\n"
    '      "name": "method name",\n'
    '      "category": "one of: retry-based, '
    "verification-based, planning-based, output-format, "
    'routing, core-mechanism, evaluation, other",\n'
    '      "description": "brief one-sentence description"\n'
    "    }\n"
    "  ],\n"
    '  "claims": [\n'
    "    {\n"
    '      "statement": "a specific factual claim",\n'
    '      "method_name": "related method, or null",\n'
    '      "confidence": "high|medium|low",\n'
    '      "evidence_span": "supporting phrase from abstract"\n'
    "    }\n"
    "  ]\n"
    "}\n\n"
    "Rules:\n"
    "- Extract ONLY methods and claims related to agent "
    "tool-call reliability, structured outputs, retries, "
    "verification, planning, or tool routing.\n"
    "- Be precise: each claim should be a single factual "
    "statement, not a summary.\n"
    "- If the abstract has no relevant methods or claims, "
    "return empty arrays.\n"
    "- Return valid JSON only, no markdown or extra text."
)


FEW_SHOT_EXAMPLE = (
    "Example input:\n"
    'Title: "Improving Tool-Call Reliability Through '
    'Structured Output Validation"\n'
    'Abstract: "We propose a two-stage validation pipeline '
    "that checks LLM tool calls against JSON Schema before "
    "execution. Our approach reduces tool-call errors by 43% "
    "on the ToolBench benchmark. We also find that combining "
    "schema validation with automatic retry on failure yields "
    'an additional 12% improvement."\n\n'
    "Example output:\n"
    "{\n"
    '  "methods": [\n'
    '    {"name": "structured output validation", '
    '"category": "verification-based", '
    '"description": "Two-stage pipeline checking tool calls '
    'against JSON Schema before execution"},\n'
    '    {"name": "automatic retry", '
    '"category": "retry-based", '
    '"description": "Retrying failed tool calls after '
    'validation failure"}\n'
    "  ],\n"
    '  "claims": [\n'
    '    {"statement": "Structured output validation reduces '
    'tool-call errors by 43% on ToolBench", '
    '"method_name": "structured output validation", '
    '"confidence": "high", '
    '"evidence_span": "reduces tool-call errors by 43% '
    'on the ToolBench benchmark"},\n'
    '    {"statement": "Combining schema validation with '
    'automatic retry yields additional 12% improvement", '
    '"method_name": "automatic retry", '
    '"confidence": "high", '
    '"evidence_span": "combining schema validation with '
    "automatic retry on failure yields an additional "
    '12% improvement"}\n'
    "  ]\n"
    "}"
)


class ExtractionService:
    """Extracts methods and claims from paper abstracts using structured LLM output."""

    EXTRACT_RETRIES = 3

    def __init__(self, llm_client: OpenRouterClient | None) -> None:
        self.llm_client = llm_client
        self.successes = 0
        self.failures = 0

    async def extract(self, paper: Paper) -> tuple[list[Method], list[Claim]]:
        """Extract methods and claims with retry logic."""
        if not self.llm_client or not paper.abstract:
            return [], []

        user_prompt = (
            f"{FEW_SHOT_EXAMPLE}\n\n"
            f"Now extract from this paper:\n"
            f'Title: "{paper.title}"\n'
            f'Abstract: "{paper.abstract}"'
        )

        for attempt in range(1, self.EXTRACT_RETRIES + 1):
            try:
                response = await self.llm_client.chat_json(SYSTEM_PROMPT, user_prompt)
                result = self._parse_json_response(paper, response)
                self.successes += 1
                return result
            except Exception:
                logger.warning(
                    "Extraction attempt %d/%d failed for paper %s",
                    attempt,
                    self.EXTRACT_RETRIES,
                    paper.paper_id,
                )
                if attempt == self.EXTRACT_RETRIES:
                    logger.error(
                        "SKIPPING paper %s after %d failed attempts",
                        paper.paper_id,
                        self.EXTRACT_RETRIES,
                    )
                    self.failures += 1
                    return [], []

        return [], []

    def _parse_json_response(self, paper: Paper, response: str) -> tuple[list[Method], list[Claim]]:
        """Parse structured JSON extraction response into Method and Claim objects."""
        timestamp = datetime.now(UTC).isoformat()

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON from extraction for paper %s", paper.paper_id)
            return [], []

        # Parse methods
        raw_methods: list[ExtractedMethod] = []
        for item in data.get("methods", []):
            if isinstance(item, dict) and item.get("name"):
                raw_methods.append(
                    ExtractedMethod(
                        name=item["name"],
                        category=item.get("category"),
                        description=item.get("description"),
                    )
                )

        # Parse claims
        raw_claims: list[ExtractedClaim] = []
        for item in data.get("claims", []):
            if isinstance(item, dict) and item.get("statement"):
                raw_claims.append(
                    ExtractedClaim(
                        statement=item["statement"],
                        method_name=item.get("method_name"),
                        confidence=item.get("confidence", "medium"),
                        evidence_span=item.get("evidence_span"),
                    )
                )

        # Convert to domain models with normalization
        methods: list[Method] = []
        for raw in raw_methods:
            canonical = canonicalize_method(raw.name)
            category = raw.category or get_method_category(canonical)
            methods.append(
                Method(
                    name=raw.name,
                    canonical_name=canonical,
                    category=category,
                    description=raw.description,
                    aliases=[raw.name],
                    provenance=Provenance(
                        source_type="openrouter",
                        source_id=paper.paper_id,
                        extracted_at=timestamp,
                        extraction_method="llm_few_shot",
                        confidence="medium",
                        text_span=paper.abstract,
                    ),
                )
            )

        claims: list[Claim] = []
        for raw_claim in raw_claims:
            claim_id = sha1(f"{paper.paper_id}:{raw_claim.statement}".encode()).hexdigest()[:16]
            method_name = (
                canonicalize_method(raw_claim.method_name) if raw_claim.method_name else None
            )
            claims.append(
                Claim(
                    claim_id=claim_id,
                    statement=raw_claim.statement,
                    evidence_span=raw_claim.evidence_span,
                    confidence=raw_claim.confidence,
                    method_name=method_name,
                    paper_id=paper.paper_id,
                    provenance=Provenance(
                        source_type="openrouter",
                        source_id=paper.paper_id,
                        extracted_at=timestamp,
                        extraction_method="llm_few_shot",
                        confidence=raw_claim.confidence,
                        text_span=raw_claim.evidence_span,
                    ),
                )
            )

        # Deduplicate methods by canonical name
        deduped_methods: list[Method] = []
        for canonical in dedupe_preserve_order([m.canonical_name for m in methods]):
            original = next(m for m in methods if m.canonical_name == canonical)
            deduped_methods.append(original)

        return deduped_methods, claims
