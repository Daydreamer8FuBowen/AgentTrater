import tushare as ts

# tushare版本 1.4.24
token = "6588e45307d18e78fc1725898b2ec1dfdad28cb085145d1c47e9f4ee6d12"

pro = ts.pro_api(token)

pro._DataApi__token = token  # 保证有这个代码，不然不可以获取
pro._DataApi__http_url = "http://lianghua.nanyangqiankun.top"  # 保证有这个代码，不然不可以获取

stock_code = "600519.SH"

# df = pro.daily(ts_code='000001.SZ', start_date='20240101', end_date='20240131')


# print(df)

# ===================== 3. 获取股票实时市盈率PE等估值指标 =====================
def get_stock_pe(ts_code):
    """获取股票市盈率、市净率等估值数据"""
    df = pro.daily_basic(ts_code=ts_code, trade_date="", fields="ts_code,trade_date,pe,pe_ttm,pb")
    # pe：静态市盈率   pe_ttm：滚动市盈率（最常用、最准确）
    if not df.empty:
        latest = df.iloc[0]  # 取最新一条数据
        print("=" * 50)
        print(f"【股票估值指标】{ts_code}")
        print(f"最新日期：{latest['trade_date']}")
        print(f"滚动市盈率(PE-TTM)：{latest['pe_ttm']:.2f}")
        print(f"静态市盈率(PE)：{latest['pe']:.2f}")
        print(f"市净率(PB)：{latest['pb']:.2f}")
        print("=" * 50)
    return df


# ===================== 4. 获取财务指标（已修复错误字段）=====================
def get_financial_indicators(ts_code):
    """获取公司核心财务指标（修复版）"""
    df = pro.fina_indicator(ts_code=ts_code, start_date="20230101", end_date="20251231")
    if not df.empty:
        latest = df.iloc[0]
        print("\n【公司核心财务指标（最新财报）】")
        print(f"报告期：{latest['end_date']}")
        print(f"毛利率(%)：{latest['grossprofit_margin']:.2f}")
        print(f"净利率(%)：{latest['netprofit_margin']:.2f}")
        print(f"净资产收益率ROE(%)：{latest['roe']:.2f}")
        print(f"资产负债率(%)：{latest['debt_to_assets']:.2f}")
    return df


# ===================== 5. 获取利润表（含净利润）=====================
def get_income_statement(ts_code):
    """从利润表获取准确净利润"""
    df = pro.income(
        ts_code=ts_code,
        start_date="20230101",
        end_date="20251231",
        fields="ts_code,end_date,report_type,total_revenue,n_income",
    )
    if not df.empty:
        latest = df.iloc[0]
        print("\n【利润表关键数据】")
        print(f"报告期：{latest['end_date']}")
        print(f"营业收入(亿元)：{latest['total_revenue'] / 10000:.2f}")
        print(f"净利润(亿元)：{latest['n_income'] / 10000:.2f}")
    return df


# ===================== 执行函数 =====================
if __name__ == "__main__":
    # 1. 获取市盈率
    get_stock_pe(stock_code)

    # 2. 获取核心财务指标
    get_financial_indicators(stock_code)

    # 3. 获取利润表
    get_income_statement(stock_code)
