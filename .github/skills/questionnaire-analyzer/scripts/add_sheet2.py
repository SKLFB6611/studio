# -*- coding: utf-8 -*-
"""
"""
import sys
import re
import os
from collections import Counter, defaultdict
import pandas as pd
import argparse
import tempfile

# ==== keyword synonym mapping (方案 C) ====
SYNONYM_MAP = {
    "保單": "保險",
    "保價金": "保額",
    "回饋金": "返利金",
    "講師": "導師",
    # 可依需求擴充
}

def apply_synonym(text: str) -> str:
    """Replace keywords with their synonyms according to SYNONYM_MAP."""
    for k, v in SYNONYM_MAP.items():
        if k in text:
            text = text.replace(k, v)
    return text

def read_feedback(path):
    with open(path, encoding='utf-8') as f:
        text = f.read()
    sections = re.split(r"^### ", text, flags=re.M)
    data = {}
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        lines = sec.splitlines()
        title = lines[0].strip()
        items = []
        for line in lines[1:]:
            line = line.strip()
            if line.startswith('-'):
                items.append(line.lstrip('-').strip())
        data[title] = items
    return data


def is_blank_response(s: str) -> bool:
    if s is None:
        return True
    s2 = s.strip().lower()
    # 常見表示沒有意見的回覆
    blanks = {'', '無', '無意見', 'n/a', 'na', '沒有', 'none'}
    s2 = s2.strip('。.，,')
    return s2 in blanks

def analyze_section(items, keywords, pos_words, neg_words):
    kw_counts = Counter()
    kw_examples = defaultdict(list)
    sentiments = defaultdict(lambda: Counter({'正':0,'中':0,'負':0}))
    # 用於去重的摘要集合 (方案 B)
    seen_examples = set()

    for it in items:
        # 先做同義詞替換 (方案 C)
        text = apply_synonym(it)
        matched = False
        for kw in keywords:
            if kw in text:
                kw_counts[kw] += 1
                kw_examples[kw].append(text)
                matched = True
                s = '中'
                if any(w in text for w in pos_words):
                    s = '正'
                if any(w in text for w in neg_words):
                    s = '負'
                sentiments[kw][s] += 1
        if not matched:
            kw_counts['其他'] += 1
            kw_examples['其他'].append(text)
            s = '中'
            if any(w in text for w in pos_words):
                s = '正'
            if any(w in text for w in neg_words):
                s = '負'
            sentiments['其他'][s] += 1

    rows = []
    for kw, cnt in kw_counts.most_common():
        # 取第一個範例作為摘要，但先檢查是否重複 (方案 B)
        ex = kw_examples[kw][0] if kw_examples[kw] else ''
        # 去重：若摘要已見過，則嘗試下一個範例
        ex_idx = 0
        while ex in seen_examples and ex_idx < len(kw_examples[kw]):
            ex_idx += 1
            ex = kw_examples[kw][ex_idx] if ex_idx < len(kw_examples[kw]) else ''
        if not ex:
            # 若摘要為空，則跳過此關鍵詞，不產生列
            continue
        seen_examples.add(ex)
        sent = sentiments[kw]
        sent_str = f"正:{sent['正']} / 中:{sent['中']} / 負:{sent['負']}"

        # 新增：簡單規則產生「量化數據關聯」
        quant_link = '對應平均分數高' if cnt >= 5 else '對應平均分數中等或低'

        rows.append({
            '主題': None,
            '子主題/關鍵詞': kw,
            '頻率': cnt,
            '情緒分佈（正/負/中）': sent_str,
            '摘要與摘錄': ex,  # 改欄位名
            '量化數據關聯': quant_link
        })
    return rows

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('excel', help='問卷分析報告.xlsx 路徑')
    parser.add_argument('feedback', help='開放式回饋.txt 路徑')
    parser.add_argument('--overwrite', action='store_true', help='直接覆蓋原檔')
    args = parser.parse_args()

    excel_path = args.excel
    feedback_path = args.feedback

    data = read_feedback(feedback_path)

    # 擴充關鍵字列表
    keywords = ['入金','保單','會計','分錄','結帳','暫收','教材','麥克風','預習','案例','新人','互動','講師','流程','操作','測試','開發','表單','傳輸檔','勾稽','內控']
    pos_words = ['幫助','了解','清楚','不錯','喜歡','好','感謝','棒','明確','進一步','概念','順利','有用','充足','用心','生動','實用']
    neg_words = ['偏小','無法','少用','問題','不清楚','困難','不熟','希望','建議','可增加','注意','初階','新手','聲音']

    all_rows = []
    for section, items in data.items():
        # 過濾掉僅為「無/無意見」等回覆的項目
        filtered = [it for it in items if not is_blank_response(it)]
        if not filtered:
            # 若該欄位沒有實質回覆則跳過
            continue
        rows = analyze_section(filtered, keywords, pos_words, neg_words)
        for r in rows:
            r['主題'] = section
        all_rows.extend(rows)

    if not all_rows:
        print('找不到任何質性回饋。')
        sys.exit(1)

    df = pd.DataFrame(all_rows)

    # 方案 E：去除完全重複的行（基於所有欄位）
    df = df.drop_duplicates()

    # 合併量化統計與質性分析至同一 sheet: '問卷彙整'
    try:
        existing = pd.read_excel(excel_path, sheet_name=None, engine='openpyxl')
    except Exception:
        existing = {}

    # 嘗試取出原有的量化表
    quant_df = existing.get('量化統計') if existing else None

    # 準備將合併結果寫入暫存檔，再原子性替換原檔（避免直接在被鎖定的檔案上寫入）
    dirpath = os.path.dirname(os.path.abspath(excel_path)) or '.'
    fd, tmp_path = tempfile.mkstemp(suffix='.xlsx', dir=dirpath)
    os.close(fd)
    try:
        with pd.ExcelWriter(tmp_path, engine='openpyxl', mode='w') as writer:
            # 第一步：先寫入合併的問卷彙整 sheet（優先順序）
            startrow = 0
            if isinstance(quant_df, pd.DataFrame):
                quant_df.to_excel(writer, sheet_name='問卷彙整', index=False, startrow=startrow)
                startrow = len(quant_df) + 3
            else:
                # 如果沒有量化表，先寫一個標題
                empty = pd.DataFrame({'說明': ['量化統計資料缺失']})
                empty.to_excel(writer, sheet_name='問卷彙整', index=False, startrow=startrow)
                startrow = len(empty) + 3

            # 將質性分析寫入同一 sheet（從 startrow 開始）
            df.to_excel(writer, sheet_name='問卷彙整', index=False, startrow=startrow)

            # 第二步：寫回其他原本的 sheet（保留問卷資料等），但跳過量化統計與質性分析
            for name, sheet in (existing.items() if existing else []):
                if name in ('量化統計', '質性分析'):
                    continue
                try:
                    sheet.to_excel(writer, sheet_name=name, index=False)
                except Exception:
                    pass

        # 以原子方式替換原檔
        os.replace(tmp_path, excel_path)
        print(f'已將量化與質性合併至：{excel_path} 的 sheet "問卷彙整"')
    except PermissionError:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        out_path = excel_path.replace('.xlsx', '_with_問卷彙整.xlsx')
        try:
            with pd.ExcelWriter(out_path, engine='openpyxl', mode='w') as writer:
                # 第一步：先寫入合併的問卷彙整 sheet
                startrow = 0
                if isinstance(quant_df, pd.DataFrame):
                    quant_df.to_excel(writer, sheet_name='問卷彙整', index=False, startrow=startrow)
                    startrow = len(quant_df) + 3
                else:
                    empty = pd.DataFrame({'說明': ['量化統計資料缺失']})
                    empty.to_excel(writer, sheet_name='問卷彙整', index=False, startrow=startrow)
                    startrow = len(empty) + 3

                df.to_excel(writer, sheet_name='問卷彙整', index=False, startrow=startrow)

                # 第二步：寫回其他原本的 sheet（問卷資料等）
                for name, sheet in (existing.items() if existing else []):
                    if name in ('量化統計', '質性分析'):
                        continue
                    try:
                        sheet.to_excel(writer, sheet_name=name, index=False)
                    except Exception:
                        pass
            print(f'原檔被鎖定；已輸出新檔：{out_path}')
        except Exception as e:
            print('無法輸出合併檔案：', e)
            sys.exit(1)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        print('合併寫入時發生錯誤：', e)
        sys.exit(1)

if __name__ == '__main__':
    main()