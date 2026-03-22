from __future__ import annotations

import re
from collections.abc import Iterable

# Expanded alias map for method normalization
ALIAS_MAP: dict[str, str] = {
    "function calling": "tool calling",
    "tool call": "tool calling",
    "tool calls": "tool calling",
    "tool use": "tool calling",
    "tool usage": "tool calling",
    "tool invocation": "tool calling",
    "structured json": "structured outputs",
    "json schema": "structured outputs",
    "json mode": "structured outputs",
    "structured generation": "structured outputs",
    "constrained decoding": "structured outputs",
    "guided generation": "structured outputs",
    "automatic retry": "retry strategies",
    "retry mechanism": "retry strategies",
    "retry logic": "retry strategies",
    "retry based": "retry strategies",
    "exponential backoff": "retry strategies",
    "output validation": "verification",
    "output verification": "verification",
    "result checking": "verification",
    "self verification": "verification",
    "self correction": "verification",
    "tool routing": "tool selection",
    "tool selection": "tool selection",
    "tool dispatch": "tool selection",
    "tool choice": "tool selection",
    "chain of thought": "planning",
    "cot": "planning",
    "step by step": "planning",
    "task planning": "planning",
    "action planning": "planning",
    "react": "reasoning and acting",
    "reason and act": "reasoning and acting",
    "reflection": "reflection",
    "self reflection": "reflection",
    "reflexion": "reflection",
}

# Category mapping for methods
CATEGORY_MAP: dict[str, str] = {
    "tool calling": "core-mechanism",
    "structured outputs": "output-format",
    "retry strategies": "retry-based",
    "verification": "verification-based",
    "tool selection": "routing",
    "planning": "planning-based",
    "reasoning and acting": "planning-based",
    "reflection": "verification-based",
}


def canonicalize_method(name: str) -> str:
    """Normalize method name to a canonical form."""
    normalized = re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
    return ALIAS_MAP.get(normalized, normalized)


def get_method_category(canonical_name: str) -> str | None:
    """Get the category for a canonical method name."""
    return CATEGORY_MAP.get(canonical_name)


def dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    """Deduplicate a sequence while preserving insertion order."""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def normalize_author_name(name: str) -> str:
    """Normalize author name for deduplication."""
    # Strip extra whitespace, normalize unicode
    name = " ".join(name.strip().split())
    # Remove any trailing numbers (common in some APIs)
    name = re.sub(r"\s+\d+$", "", name)
    return name


def merge_authors(
    authors_a: list[dict[str, str | None]],
    authors_b: list[dict[str, str | None]],
) -> list[dict[str, str | None]]:
    """Merge two author lists, deduplicating by normalized name."""
    seen: dict[str, dict[str, str | None]] = {}
    for author in [*authors_a, *authors_b]:
        raw_name = author.get("name") or ""
        key = normalize_author_name(raw_name).lower()
        if key and key not in seen:
            seen[key] = author
        elif key in seen and author.get("affiliation") and not seen[key].get("affiliation"):
            seen[key]["affiliation"] = author["affiliation"]
    return list(seen.values())


def normalize_title(title: str) -> str:
    """Normalize a paper title for dedup comparison."""
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def dedupe_papers_by_title(papers: list[dict]) -> list[dict]:
    """Deduplicate papers by normalized title, keeping the first occurrence."""
    seen_titles: set[str] = set()
    unique: list[dict] = []
    for paper in papers:
        key = normalize_title(paper.get("title", "") or "")
        if key and key not in seen_titles:
            seen_titles.add(key)
            unique.append(paper)
    return unique
