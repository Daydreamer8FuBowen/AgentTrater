import baostock as bs
import pandas as pd

lg = bs.login()
print("login:", lg.error_code, lg.error_msg)

rs = bs.query_history_k_data_plus(
    "sh.600000",
    "date,time,code,open,high,low,close,volume,amount,adjustflag",
    start_date="2024-01-02",
    end_date="2024-01-05",
    frequency="5",
    adjustflag="3",  # 先用不复权，便于排查
)

print("query:", rs.error_code, rs.error_msg)
print("fields:", rs.fields)

rows = []
while rs.error_code == "0" and rs.next():
    rows.append(rs.get_row_data())

df = pd.DataFrame(rows, columns=rs.fields)

print("原始行数:", len(df))
print(df.head(10))
print(df.tail(10))

bs.logout()
