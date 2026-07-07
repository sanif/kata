"""Shared fuzzy-matching helpers for the TUI."""

from __future__ import annotations


def fuzzy_match(query: str, target: str) -> bool:
    """Return True if every character of ``query`` appears, in order, in ``target``.

    A subsequence match (the same behaviour the search modal, recents panel and
    project tree each used to implement independently). ``query`` and ``target``
    are compared as-is, so callers should lower-case both for case-insensitive
    matching.

    Args:
        query: The (already lower-cased) search string.
        target: The (already lower-cased) candidate string.

    Returns:
        True if ``query`` is a subsequence of ``target``.
    """
    if not query:
        return True
    query_idx = 0
    for char in target:
        if query_idx < len(query) and char == query[query_idx]:
            query_idx += 1
    return query_idx == len(query)
