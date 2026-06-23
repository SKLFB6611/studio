import pandas as pd
p='商品與精算課後心得問卷_報告.xlsx'
try:
    df=pd.read_excel(p, sheet_name='問卷彙整', engine='openpyxl')
except Exception as e:
    print('讀取 Excel 失敗：', e)
    raise
cols=[c for c in df.columns]
print('問卷彙整 欄位：', cols)
# 嘗試找到質性相關欄位
qual_cols=[c for c in cols if '子主題' in c or '關鍵詞' in c or '摘要' in c or '情緒' in c]
if not qual_cols:
    print('找不到質性分析欄位')
else:
    key=qual_cols[0]
    rows=df[df[key].notna()]
    out_cols=['主題', key]
    for c in ['頻率', '情緒', '情緒分佈（正/負/中）', '情緒分佈', '摘要與摘錄', '摘要']:
        if c in df.columns:
            out_cols.append(c)
    # 保證唯一
    out_cols=[x for i,x in enumerate(out_cols) if x not in out_cols[:i]]
    print(rows[out_cols].to_string(index=False))
