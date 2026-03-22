from app.services.normalization import (
    canonicalize_method,
    dedupe_preserve_order,
    get_method_category,
    normalize_author_name,
    normalize_title,
)


def test_canonicalize_method_maps_known_aliases() -> None:
    assert canonicalize_method("Function Calling") == "tool calling"
    assert canonicalize_method("JSON Schema") == "structured outputs"
    assert canonicalize_method("tool calls") == "tool calling"
    assert canonicalize_method("Tool Use") == "tool calling"
    assert canonicalize_method("structured json") == "structured outputs"
    assert canonicalize_method("automatic retry") == "retry strategies"
    assert canonicalize_method("chain of thought") == "planning"
    assert canonicalize_method("self correction") == "verification"


def test_canonicalize_method_passthrough_unknown() -> None:
    assert canonicalize_method("some novel technique") == "some novel technique"


def test_get_method_category() -> None:
    assert get_method_category("tool calling") == "core-mechanism"
    assert get_method_category("retry strategies") == "retry-based"
    assert get_method_category("verification") == "verification-based"
    assert get_method_category("unknown method") is None


def test_dedupe_preserve_order_keeps_first_occurrence() -> None:
    assert dedupe_preserve_order(["a", "b", "a", "c"]) == ["a", "b", "c"]


def test_dedupe_preserve_order_empty() -> None:
    assert dedupe_preserve_order([]) == []


def test_normalize_author_name() -> None:
    assert normalize_author_name("  John   Doe  ") == "John Doe"
    assert normalize_author_name("Jane Smith 1") == "Jane Smith"


def test_normalize_title() -> None:
    assert normalize_title("Hello, World!") == "hello world"
    assert normalize_title("  Foo -- Bar  ") == "foo bar"
