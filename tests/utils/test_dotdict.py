import pytest

from domino.utils.dotdict import DotDict


class TestDotDict:
    def test_dotdict(self):
        data = DotDict({"foo": {"bar": {"baz": 1}}})

        assert dict(data) == {"foo": {"bar": {"baz": 1}}}
        assert data.get(1) is None  # type: ignore
        assert data.get("foo") == {"bar": {"baz": 1}}
        assert data.get("foo.bar.baz") == 1
        assert data.get("foo?.bar.missing", 42) == 42
        assert data.get("foo?.bar.missing") is None

        assert data["baz?.foo.bar"] is None
        assert data["foo.bar"] == {"baz": 1}

        with pytest.raises(KeyError):
            data["baz.foo?.bar"]  # noqa

        assert data.get("foo.bar.missing", 42) == 42

        data.set("foo.bar.baz", 99)
        assert data["foo"]["bar"]["baz"] == 99
        assert data.get("foo.bar.baz") == 99

        # NOTE: strict set -> KeyError if path doesn't exist
        with pytest.raises(KeyError):
            data.set("foo.buz.qux", 10)

        # NOTE: safe set -> creates missing path
        data.set("foo?.buz.qux", 10)
        assert data.get("foo.buz.qux") == 10

        data.set(1, "baz")  # type: ignore
        assert data.get(1) == "baz"  # type: ignore

        data.set("foo", "baz")
        assert data.get("foo") == "baz"

        with pytest.raises(TypeError):
            data.set("foo.baz", "bar")

        data = DotDict({"foo": {}})
        data.set("foo.bar?", None)
        assert data == {"foo": {"bar": None}}

        with pytest.raises(KeyError):
            data.set("foo.baz", None)

        data = DotDict()

        with pytest.raises(KeyError):
            data.set("foo.bar?", None)

        data.set("foo?.bar", None)
        assert data == {"foo": {"bar": None}}


def test_dotdict_get_raise_found():
    """get_raise returns the value when the key exists."""
    d = DotDict({"schedule": "@daily", "nested": {"start_date": "2026-01-01"}})
    assert d.get_raise("schedule") == "@daily"
    assert d.get_raise("nested.start_date") == "2026-01-01"


def test_dotdict_get_raise_missing_no_default():
    """get_raise raises KeyError for a missing key with no default."""
    d = DotDict({"existing": "value"})
    with pytest.raises(KeyError):
        d.get_raise("missing_key")

    with pytest.raises(KeyError):
        d.get_raise("existing.key")

    with pytest.raises(KeyError):
        d.get_raise("nested.also.missing")


def test_dotdict_get_raise_missing_with_default():
    """get_raise returns the default when the key is missing and a default is given."""
    d = DotDict({})
    assert d.get_raise("missing_key", "fallback") == "fallback"
    assert d.get_raise("nested.missing", "null") == "null"


def test_dotdict_get_raise_safe_mode():
    """get_raise with '?' suffix (safe mode) returns None/default without raising."""
    d = DotDict({"schedule": "@daily"})

    # Missing key with safe-mode suffix → None
    assert d.get_raise("missing?") is None

    # Missing key with safe-mode suffix + explicit default → default
    assert d.get_raise("missing?", "safe_fallback") == "safe_fallback"

    # Existing key with safe-mode suffix → value
    assert d.get_raise("schedule?") == "@daily"


def test_dotdict_get_raise_non_string_key():
    """get_raise with a non-string key hits the isinstance branch (lines 533-537)."""
    d = DotDict({1: "one", 2: "two"})

    # Non-string key that exists → return value
    assert d.get_raise(1) == "one"

    # Non-string key that exists + explicit default → still return value
    assert d.get_raise(2, "fallback") == "two"

    # Non-string key missing, explicit default → return default
    assert d.get_raise(99, "default") == "default"

    # Non-string key missing, no default → raise KeyError
    with pytest.raises(KeyError):
        d.get_raise(99)
