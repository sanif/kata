"""Tests for the shared fuzzy_match helper."""

from kata.utils.matching import fuzzy_match


def test_empty_query_matches_anything():
    assert fuzzy_match("", "anything") is True


def test_subsequence_matches():
    assert fuzzy_match("kw", "kata-workspace") is True
    assert fuzzy_match("nxt", "next.js") is True


def test_non_subsequence_does_not_match():
    assert fuzzy_match("zzz", "kata") is False
    assert fuzzy_match("ba", "abc") is False


def test_order_matters():
    assert fuzzy_match("ac", "abc") is True
    assert fuzzy_match("ca", "abc") is False
