import asyncio
import sys
import types

from agent_trader.ingestion.sources import baostock_source as mod


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


def main() -> int:
    fake_result = FakeResult()

    # monkeypatch baostock API used by the module
    mod.bs.login = lambda u, p, o: types.SimpleNamespace(error_code="0", error_msg="")
    mod.bs.logout = lambda u: None
    mod.bs.query_stock_basic = lambda: fake_result

    source = mod.BaoStockSource()

    try:
        result = asyncio.run(source.fetch_basic_info())
    except Exception as exc:
        print("TEST FAIL: exception while running fetch_basic_info:", exc)
        return 2

    if not isinstance(result.payload, list) or len(result.payload) != 1:
        print("TEST FAIL: unexpected result payload:", result)
        return 1

    record = result.payload[0]
    ok = result.source == source.name and record.get("symbol") == "600000.SH"
    if ok:
        print("TEST PASS")
        return 0

    print("TEST FAIL: payload mismatch", record)
    return 1


if __name__ == "__main__":
    sys.exit(main())
