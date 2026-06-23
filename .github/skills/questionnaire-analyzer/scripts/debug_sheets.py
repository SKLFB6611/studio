import pandas as pd
p='商品與精算課後心得問卷_報告.xlsx'
try:
    wb=pd.read_excel(p, sheet_name=None, engine='openpyxl')
except Exception as e:
    print('讀取錯誤', e)
    raise
for name,df in wb.items():
    print('Sheet:', name)
    print('Shape:', df.shape)
    print(df.head(5).to_string(index=False))
    print('---')
