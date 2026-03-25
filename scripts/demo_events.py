import baostock as bs
import pandas as pd

bs.login()
# 获取当天所有股票快照
rs = bs.query_real_time_data(code="sh.600000,sz.000001,sh.600036")
df = rs.get_data()
print(df)
bs.logout()