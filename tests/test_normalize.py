"""Tests for _strip_nulls and normalize_input functions."""

import json


class TestStripNulls:
    """Tests for _strip_nulls()."""

    def test_strip_nulls_from_dict(self, optimizer):
        """Null values are removed from flat dicts."""
        result = optimizer._strip_nulls({"a": 1, "b": None, "c": "hello"})
        assert result == {"a": 1, "c": "hello"}

    def test_strip_nulls_nested_dict(self, optimizer):
        """Null values are removed from nested dicts."""
        result = optimizer._strip_nulls({
            "a": 1,
            "b": None,
            "c": {"d": 2, "e": None, "f": {"g": 3, "h": None}},
        })
        assert result == {"a": 1, "c": {"d": 2, "f": {"g": 3}}}

    def test_strip_nulls_from_list(self, optimizer):
        """Null values are removed from lists."""
        result = optimizer._strip_nulls([1, None, 2, None, 3])
        assert result == [1, 2, 3]

    def test_strip_nulls_nested_list(self, optimizer):
        """Null values are stripped from dicts inside lists and vice versa."""
        result = optimizer._strip_nulls([
            1,
            None,
            {"a": 2, "b": None},
            [3, None, 4],
        ])
        assert result == [1, {"a": 2}, [3, 4]]

    def test_strip_nulls_no_nulls(self, optimizer):
        """Input without nulls is returned unchanged."""
        data = {"a": 1, "b": [2, 3], "c": {"d": 4}}
        result = optimizer._strip_nulls(data)
        assert result == data

    def test_strip_nulls_empty_structures(self, optimizer):
        """Empty dicts and lists pass through unchanged."""
        assert optimizer._strip_nulls({}) == {}
        assert optimizer._strip_nulls([]) == []
        assert optimizer._strip_nulls("hello") == "hello"
        assert optimizer._strip_nulls(42) == 42
        assert optimizer._strip_nulls(None) is None


class TestNormalizeInput:
    """Tests for normalize_input()."""

    def test_sorts_keys(self, optimizer):
        """Keys are sorted alphabetically."""
        result = optimizer.normalize_input({"z": 1, "a": 2, "m": 3})
        assert result == '{"a":2,"m":3,"z":1}'

    def test_strips_nulls_before_serializing(self, optimizer):
        """Null values are stripped before JSON serialization."""
        result = optimizer.normalize_input({"a": 1, "b": None})
        assert result == '{"a":1}'
        assert "null" not in result

    def test_compact_format(self, optimizer):
        """Output uses compact separators (no spaces)."""
        result = optimizer.normalize_input({"key": "value"})
        assert " " not in result

    def test_nested_keys_sorted(self, optimizer):
        """Nested dict keys are also sorted."""
        result = optimizer.normalize_input({
            "z": {"b": 1, "a": 2},
            "a": 3,
        })
        assert result == '{"a":3,"z":{"a":2,"b":1}}'

    def test_identical_with_and_without_nulls(self, optimizer):
        """Input with nulls produces same output as input without."""
        with_nulls = optimizer.normalize_input({"a": 1, "b": None, "c": 2})
        without_nulls = optimizer.normalize_input({"a": 1, "c": 2})
        assert with_nulls == without_nulls
