#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_survey.py

Reads a survey CSV, computes Likert 5-point statistics, analyzes open-ended
responses (topic keywords + simple sentiment), and writes an Excel report
with two sheets into `AI EXCEL_area`.

Usage:
  python .github/skills/questionnaire-analyzer/scripts/process_survey.py [--csv PATH] [--keep-csv] [--keep-temp]

This script follows the questionnaire-analyzer skill instructions.
"""

from __future__ import annotations
import argparse
import glob
import os
import sys
import datetime
import re
from collections import Counter, defaultdict
from typing import List, Dict, Tuple

try:
    import pandas as pd
    import numpy as np
except Exception as e:
    print("Missing dependency: pandas/numpy. Install requirements first.")
    raise


def detect_encoding(path: str) -> str:
    # Try chardet if available
    try:
        import chardet
        with open(path, 'rb') as f:
            raw = f.read()
        res = chardet.detect(raw)
        if res and res.get('encoding'):
            return res['encoding']
    except Exception:
        pass

    # Fallback guesses
    for enc in ('utf-8-sig', 'utf-8', 'cp950', 'big5', 'gbk', 'latin1'):
        try:
            with open(path, encoding=enc) as f:
                f.readline()
            return enc
        except Exception:
            continue
    return 'utf-8'


LIKERT_LABELS = ['非常同意', '同意', '普通', '不同意', '非常不同意']
LIKERT_MAP = {k: 5 - i for i, k in enumerate(LIKERT_LABELS)}

EMPTY_TOKENS = set(['無', '無意見', 'n/a', 'na', '沒有', 'none', '-', '無。', '無。', 'NA'])

TOPIC_KEYWORDS = {
    '新契約流程': ['新契約', '流程', '進件', '作業流程', '進件流程', '流程生命週期'],
    '系統／開發': ['系統', '開發', '功能開發', '系統開發', '系統規則', '查找問題'],
    '核保／業務': ['核保', '契變', '業務', '承保', '保單', '核保等級'],
    '教材／簡報': ['簡報', '教材', '講義', '參考'],
    '收音／設備': ['麥克風', '收音', '聲音'],
    '互動／教學': ['互動', '教學', '分享', '講師', '解惑', '授課'],
}

POSITIVE_TOKENS = ['受益', '很棒', '實用', '感謝', '收穫', '解惑', '有幫助', '想再聽', '受益良多']
NEGATIVE_TOKENS = ['希望', '建議', '不清楚', '抱怨', '沒', '差', '麥克風', '收音']


def find_latest_csv(search_dirs: List[str]) -> str:
    candidates = []
    for d in search_dirs:
        if not os.path.exists(d):
            continue
        candidates.extend(glob.glob(os.path.join(d, '*.csv')))
    if not candidates:
        return ''
    return max(candidates, key=os.path.getmtime)


def clean_text(s) -> str:
    if pd.isna(s):
        return ''
    t = str(s).strip()
    # remove common placeholder tokens
    if t in EMPTY_TOKENS:
        return ''
    # unify whitespace
    t = re.sub(r'\s+', ' ', t)
    return t


def classify_sentiment(text: str) -> str:
    t = text.lower()
    pos = any(tok in t for tok in POSITIVE_TOKENS)
    neg = any(tok in t for tok in NEGATIVE_TOKENS)
    if pos and not neg:
        return '正'
    if neg and not pos:
        return '負'
    if pos and neg:
        return '混合'
    return '中'


def match_topics(text: str) -> List[str]:
    hits = []
    t = text.lower()
    for topic, kws in TOPIC_KEYWORDS.items():
        for kw in kws:
            if kw.lower() in t:
                hits.append(topic)
                break
    return hits


def analyze_open_responses(all_texts: List[str]) -> Tuple[Dict[str, int], Dict[str, List[str]], Counter]:
    topic_counts = Counter()
    examples = defaultdict(list)
    sentiment_counts = Counter()
    for t in all_texts:
        if not t:
            continue
        s = clean_text(t)
        if not s:
            continue
        topics = match_topics(s)
        if topics:
            for top in topics:
                topic_counts[top] += 1
                if len(examples[top]) < 5:
                    examples[top].append(s)
        else:
            topic_counts['其他'] += 1
            if len(examples['其他']) < 5:
                examples['其他'].append(s)
        sentiment = classify_sentiment(s)
        sentiment_counts[sentiment] += 1
    return topic_counts, examples, sentiment_counts


def build_summary_rows(df: pd.DataFrame, likert_cols: List[str], topics_summary: Tuple[Counter, Dict[str, List[str]], Counter]) -> List[Dict]:
    topic_counts, examples, sentiment_counts = topics_summary
    top_topic, top_freq = ('', 0)
    if topic_counts:
        top_topic, top_freq = topic_counts.most_common(1)[0]

    rows = []
    for col in likert_cols:
        series = df[col].astype(str).fillna('').str.strip()
        # filter out empty-like entries
        valid = series[series.apply(lambda x: x not in EMPTY_TOKENS and x != '')]
        total = int(valid[valid.isin(LIKERT_LABELS)].shape[0])
        counts = [int((valid == lab).sum()) for lab in LIKERT_LABELS]
        percents = [round((c / total * 100) if total else 0.0, 1) for c in counts]
        numeric = valid.map(LIKERT_MAP).dropna()
        mean = round(float(numeric.mean()) if not numeric.empty else float('nan'), 2)

        row = {
            '類別': '課程方面' if '課程方面' in col else ('講師方面' if '講師方面' in col else '量表'),
            '細項': col,
            '次數（非常同意/同意/普通/不同意/非常不同意）': ' / '.join(map(str, counts)),
            '佔比（%）': ' / '.join([str(p) for p in percents]),
            '平均分數': mean,
            '總回覆數': total,
            '主題': top_topic,
            '子主題/關鍵詞': ', '.join([k for k, _ in topic_counts.most_common(3)]) if topic_counts else '',
            '頻率': top_freq,
            '情緒分佈（正/負/中）': f"{sentiment_counts.get('正',0)}/{sentiment_counts.get('負',0)}/{sentiment_counts.get('中',0)}",
            '摘要與摘錄': '; '.join([examples[top_topic][i] for i in range(min(2, len(examples.get(top_topic, []))))]) if top_topic else '',
            '量化數據關聯': ('高' if top_freq >= 5 else '中' if top_freq >= 2 else '低')
        }
        rows.append(row)
    return rows


def main():
    parser = argparse.ArgumentParser(prog='process_survey')
    parser.add_argument('--csv', help='Path to CSV file (optional)')
    parser.add_argument('--keep-csv', action='store_true', help='Keep original CSV copy in output dir')
    parser.add_argument('--keep-temp', action='store_true', help='Keep temporary files')
    args = parser.parse_args()

    workspace_root = os.getcwd()
    excel_dir = os.path.join(workspace_root, 'AI EXCEL_area')
    os.makedirs(excel_dir, exist_ok=True)

    csv_path = args.csv
    if not csv_path:
        csv_path = find_latest_csv([excel_dir, workspace_root])
    if not csv_path:
        print('No CSV found. Place your survey CSV in AI EXCEL_area or pass --csv path')
        sys.exit(1)

    print(f'Reading CSV: {csv_path}')
    encoding = detect_encoding(csv_path)
    print(f'Detected encoding: {encoding}')
    df = pd.read_csv(csv_path, encoding=encoding)

    # identify Likert columns (按 Skill 規範尋找「課程方面」「講師方面」)
    likert_cols = [c for c in df.columns if ('課程方面' in c) or ('講師方面' in c)]
    if not likert_cols:
        # fallback: pick columns whose values contain likert labels
        for c in df.columns:
            sample = df[c].astype(str).head(30).tolist()
            if any(s in LIKERT_LABELS for s in sample):
                likert_cols.append(c)

    # find open-ended fields
    app_col = next((c for c in df.columns if any(k in c for k in ['運用', '如何運用', '會如何運用', '應用'])), None)
    suggest_col = next((c for c in df.columns if any(k in c for k in ['改進', '建議'])), None)
    feeling_col = next((c for c in df.columns if any(k in c for k in ['心得', '感想'])), None)
    open_cols = [c for c in (app_col, suggest_col, feeling_col) if c]

    # gather all open responses
    all_texts = []
    for c in open_cols:
        all_texts.extend([clean_text(x) for x in df[c].astype(str).fillna('').tolist()])

    topic_counts, examples, sentiment_counts = analyze_open_responses(all_texts)

    summary_rows = build_summary_rows(df, likert_cols, (topic_counts, examples, sentiment_counts))
    sheet1 = pd.DataFrame(summary_rows)

    # write Excel with two sheets
    base = os.path.splitext(os.path.basename(csv_path))[0]
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S')
    out_name = f"{base}_報告.xlsx"
    out_path = os.path.join(excel_dir, out_name)

    # if file exists, append timestamp to avoid lock
    if os.path.exists(out_path):
        out_path = os.path.join(excel_dir, f"{base}_報告_{timestamp}.xlsx")

    with pd.ExcelWriter(out_path, engine='openpyxl') as writer:
        sheet1.to_excel(writer, sheet_name='問卷彙整', index=False)
        # write original raw data
        df.to_excel(writer, sheet_name='原始問卷資料', index=False)

    print('\nReport generated:')
    print(out_path)
    print('\nSummary:')
    # simple markdown-like summary
    print(f"- 樣本數: {len(df)}")
    if topic_counts:
        print(f"- 主要主題: {topic_counts.most_common(3)}")
    print(f"- 情緒分佈: 正 {sentiment_counts.get('正',0)} / 負 {sentiment_counts.get('負',0)} / 中 {sentiment_counts.get('中',0)}")
    print('\nSheets:')
    print('- 問卷彙整 （量化 + 質性摘要）')
    print('- 原始問卷資料（完整 CSV）')


if __name__ == '__main__':
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
問卷分析完整流程驅動程式：自動化問卷彙整
"""

import os
import sys
import glob
import subprocess
import shutil
from pathlib import Path

# Excel 輸出資料夾（所有 Excel 相關作業限定在此）
OUTPUT_DIR = "AI EXCEL工作區"


def find_latest_csv():
    """找出工作區內最新的 CSV 檔案"""
    csv_files = glob.glob('*.csv')
    if not csv_files:
        return None
    return max(csv_files, key=lambda f: os.path.getmtime(f))


def sanitize_filename(csv_path):
    """從 CSV 檔名生成 Excel 報告檔名"""
    return f"{Path(csv_path).stem}_報告.xlsx"


def run_cmd(cmd, desc):
    """執行命令"""
    print(f"\n▶ {desc}")
    try:
        subprocess.run(cmd, check=True, capture_output=False)
        print(f"✓ {desc} 完成")
        return True
    except Exception as e:
        print(f"✗ {desc} 失敗: {e}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="問卷分析完整流程")
    parser.add_argument("--csv", help="指定 CSV 檔案", default=None)
    parser.add_argument("--keep-temp", action="store_true", help="保留臨時檔案")
    parser.add_argument("--keep-csv", action="store_true", help="保留 CSV 檔案")
    args = parser.parse_args()

    # 驗證腳本目錄存在
    scripts_path = ".github/skills/questionnaire-analyzer/scripts"
    if not Path(scripts_path).exists():
        print("錯誤：請在工作區根目錄執行此腳本")
        sys.exit(1)

    # 確定 CSV 檔案
    csv_file = args.csv or find_latest_csv()
    if not csv_file or not os.path.exists(csv_file):
        print(f"錯誤：找不到 CSV 檔案: {csv_file}")
        sys.exit(1)

    # 確保輸出資料夾存在
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    excel_file = os.path.join(OUTPUT_DIR, sanitize_filename(csv_file))
    temp_excel = os.path.join(OUTPUT_DIR, "問卷分析報告.xlsx")
    temp_feedback = os.path.join(OUTPUT_DIR, "開放式回饋.txt")

    print(f"\n{'='*60}")
    print(f"{'='*60}")
    print(f"CSV: {os.path.abspath(csv_file)}")
    print(f"輸出資料夾: {os.path.abspath(OUTPUT_DIR)}")
    print(f"報告檔: {os.path.abspath(excel_file)}")
    print(f"{'='*60}\n")

    # 1. 量化統計
    if not run_cmd(
        ["python", f"{scripts_path}/analyze_questionnaire.py", csv_file, "--output_excel", temp_excel],
        "量化統計與問卷資料抽取"
    ):
        sys.exit(1)

    # 移動開放式回饋檔案到輸出目錄
    generated_feedback = "開放式回饋.txt"
    if os.path.exists(generated_feedback):
        shutil.move(generated_feedback, temp_feedback)
    else:
        print(f"警告：找不到生成的開放式回饋檔案 {generated_feedback}")

    # 2. 質性分析
    if os.path.exists(temp_feedback):
        run_cmd(
            ["python", f"{scripts_path}/add_sheet2.py", temp_excel, temp_feedback, "--overwrite"],
            "質性分析整合"
        )

    # 3. 重命名輸出
    if os.path.exists(temp_excel):
        try:
            if os.path.exists(excel_file):
                os.remove(excel_file)
            os.rename(temp_excel, excel_file)
            print(f"\n✓ 報告已生成：{os.path.abspath(excel_file)}")
        except PermissionError:
            # 既有報告可能被其他程式鎖定（例如 Excel 開啟中），改用備用檔名輸出
            alt = excel_file.replace('.xlsx', '_updated.xlsx')
            try:
                if os.path.exists(alt):
                    os.remove(alt)
                os.rename(temp_excel, alt)
                print(f"\n⚠ 既有報告被鎖定，已輸出為：{os.path.abspath(alt)}")
                excel_file = alt
            except Exception as e:
                print(f"✗ 無法將暫存檔案改名：{e}")
                sys.exit(1)

    # 3.5 在終端印出摘要（不寫檔）以便 Chat 中回報
    try:
        subprocess.run(["python", f"{scripts_path}/generate_md_summary.py", os.path.abspath(excel_file)], check=False)
    except Exception:
        pass

    # 4. 清理臨時檔案
    if not args.keep_temp:
        if os.path.exists(temp_excel):
            os.remove(temp_excel)
        # 保留開放式回饋檔案作為輸出的一部分

    # 5. 刪除原始 CSV
    if not args.keep_csv:
        try:
            os.remove(csv_file)
            print(f"✓ 已刪除原始 CSV: {csv_file}")
        except OSError:
            pass

    print(f"\n{'='*60}")
    print(f"✓ 完成！最終報告: {excel_file}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
