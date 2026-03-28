import asyncio
import types


def _make_fake_result():
    class FakeResult:
        def __init__(self):
            self.error_code = "0"
            self.fields = ["code", "code_name"]
            self._rows = [["sh.600000", "TestCo"]]
            self._i = -1

        def next(self):
            self._i += 1
            return self._i < len(self._rows)

        def get_row_data(self):
            return self._rows[self._i]

        @property
        def error_msg(self):
            return ""

    return FakeResult()


def test_fetch_basic_info(monkeypatch):
    import agent_trader.ingestion.sources.baostock_source as mod

    fake_result = _make_fake_result()

    # patch baostock methods used by the source
    monkeypatch.setattr(
        mod.bs, "login", lambda u, p, o: types.SimpleNamespace(error_code="0", error_msg="")
    )
    monkeypatch.setattr(mod.bs, "logout", lambda u: None)
    monkeypatch.setattr(mod.bs, "query_stock_basic", lambda: fake_result)

    source = mod.BaoStockSource()

    result = asyncio.run(source.fetch_basic_info())

    assert result.source == source.name
    assert isinstance(result.payload, list)
    assert len(result.payload) == 1
    record = result.payload[0]
    assert record.symbol == "600000.SH"
    assert record.name == "TestCo"
