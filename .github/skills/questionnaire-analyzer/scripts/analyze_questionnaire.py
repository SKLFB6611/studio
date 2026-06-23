#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
問卷分析腳本：處理滿意度調查 CSV，產生量化統計與 Excel 報告
"""

import argparse
import pandas as pd
from pathlib import Path
import subprocess

# 評分對應字典
SCORE_MAP = {
    '非常同意': 5,
    '同意': 4,
    '普通': 3,
    '不同意': 2,
    '非常不同意': 1,
    # 容錯
    '非常同意 ': 5, ' 同意': 4, '同意 ': 4,
}

# 從 description 定義開放式欄位名稱（未來可從 SKILL.md 或外部檔案讀取）
OPEN_QUESTION_DESC = {
    '應用': '此課程實施後，會如何運用在您的工作上？',
    '建議': '其他的改進事項及建議',
    '心得': '心得'
}

def main():
    parser = argparse.ArgumentParser(description="分析問卷 CSV 並產生 Excel 報告")
    parser.add_argument("input_csv", help="輸入的 CSV 檔案路徑")
    parser.add_argument("--output_excel", default="問卷分析報告.xlsx", help="輸出的 Excel 檔案名稱")
    parser.add_argument("--auto_add_sheet2", action="store_true", help="自動呼叫 add_sheet2.py 補充質性分析")
    args = parser.parse_args()

    input_path = Path(args.input_csv)
    if not input_path.exists():
        print(f"錯誤：檔案 {input_path} 不存在")
        return

    # 自動偵測編碼
    encodings = ['utf-8-sig', 'big5', 'cp950', 'gbk']
    df = None
    for enc in encodings:
        try:
            df = pd.read_csv(input_path, encoding=enc)
            print(f"成功使用 {enc} 編碼讀取 CSV")
            break
        except UnicodeDecodeError:
            continue
    if df is None:
        raise UnicodeDecodeError("無法讀取 CSV，請確認編碼或檔案是否損壞")

    print("CSV 欄位：", df.columns.tolist())
    print(f"已讀取 {len(df)} 筆資料")

    # 找出量表欄位
    likert_columns = [col for col in df.columns if any(kw in col for kw in ['課程方面', '講師方面'])]

    results = []
    for col in likert_columns:
        df[col] = df[col].map(SCORE_MAP).fillna(3)

        value_counts = df[col].value_counts().sort_index()
        total = len(df[col].dropna())
        if total == 0:
            continue

        counts = [value_counts.get(i, 0) for i in range(5, 0, -1)]
        count_str = ' / '.join(map(str, counts))

        percentages = [(c / total * 100) for c in counts]
        perc_str = ' / '.join(f"{p:.1f}%" for p in percentages)

        mean_score = df[col].mean().round(2)

        # 改進類別判斷：更精準匹配「課程方面」「講師方面」
        category = '課程內容方面' if '課程方面' in col else '講師方面' if '講師方面' in col else '其他'

        results.append({
            '類別': category,
            '細項': col.strip(),
            '次數（非常同意/同意/普通/不同意/非常不同意）': count_str,
            '佔比（非常同意/同意/普通/不同意/非常不同意）': perc_str,
            '平均分數（5分制）': mean_score,
            '總回覆數': total
        })

    quant_df = pd.DataFrame(results)
    print("量化統計完成：")
    print(quant_df.to_string(index=False))

    # 提取開放式欄位（從 OPEN_QUESTION_DESC 取名稱）
    qualitative_texts = {}
    for key, col_name in OPEN_QUESTION_DESC.items():
        if col_name in df.columns:
            texts = df[col_name].dropna().str.strip().tolist()
            qualitative_texts[key] = texts
            print(f"\n開放式欄位：{key} ({col_name})")
            print(f"共有 {len(texts)} 筆有效回覆")
            for i, text in enumerate(texts[:3], 1):
                print(f"  {i}. {text[:100]}{'...' if len(text) > 100 else ''}")

    # 存成文字檔
    qual_path = Path("開放式回饋.txt")
    with open(qual_path, 'w', encoding='utf-8') as f:
        for key, texts in qualitative_texts.items():
            f.write(f"### {OPEN_QUESTION_DESC[key]}\n")
            for text in texts:
                f.write(f"- {text}\n")
            f.write("\n\n")
    print(f"開放式回饋已存成：{qual_path.absolute()}")

    # 匯出 Excel
    output_path = Path(args.output_excel)
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        quant_df.to_excel(writer, sheet_name='量化統計', index=False)

        # Sheet2 佔位
        qualitative_data = {
            '主題': ['質性分析佔位（待 Claude 處理）'],
            '子主題/關鍵詞': ['-'],
            '頻率': ['-'],
            '情緒分佈（正/負/中）': ['-'],
            '摘要與摘錄': ['請將開放式回饋.txt 內容提供給我，我會進行主題歸納、情緒分類與建議連結'],
            '量化數據關聯': ['-']
        }
        qual_df = pd.DataFrame(qualitative_data)
        qual_df.to_excel(writer, sheet_name='質性分析', index=False)

        # 新增：問卷資料 sheet（原始 CSV 完整資料）

        df_original = pd.read_csv(input_path, encoding=enc)
        df_original.to_excel(writer, sheet_name='問卷資料', index=False)


    print(f"Excel 報告已產生：{output_path.absolute()}")
    print(f"開放式回饋文字檔已產生：{qual_path.absolute()}")

    # 新增：自動呼叫 add_sheet2.py（如果啟用 --auto_add_sheet2）
    if args.auto_add_sheet2:
        print("\n自動呼叫 add_sheet2.py 補充質性分析...")
        try:
            subprocess.run([
                "python", "add_sheet2.py",
                str(output_path),
                str(qual_path),
                "--overwrite"
            ], check=True)
            print("add_sheet2.py 執行完成")
        except Exception as e:
            print(f"自動呼叫失敗：{e}")
            print("請手動執行：python add_sheet2.py 問卷分析報告.xlsx 開放式回饋.txt --overwrite")

if __name__ == "__main__":
    main()