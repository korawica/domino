from domino.utils.dotdict import DotDict


def test_dotdict():
    d = DotDict(a={"c": 1}, b=2)
    assert d["a.c"] == 1
    assert d["a.e?"] is None
    assert d.get("a.e?.f", "default") == "default"
