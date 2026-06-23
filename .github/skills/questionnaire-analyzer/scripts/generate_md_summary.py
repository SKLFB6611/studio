import sys
from pathlib import Path
import pandas as pd
import re
from collections import Counter
from datetime import datetime

SCORE_MAP = {
    "非常同意": 5,
    "同意": 4,
    "普通": 3,
    "不同意": 2,
    "非常不同意": 1,
    "非常滿意": 5,
    "滿意": 4,
    "不滿意": 2,
    "非常不滿意": 1,
}


def extract_cjk_tokens(text):
    return re.findall(r"[\u4e00-\u9fff]{2,}", text or "")


def summarize_report(xlsx_path: Path, out_md: Path):
    xlsx = pd.read_excel(xlsx_path, sheet_name=None)
    # find sheet with raw responses
    sheet_name = None
    for name in xlsx.keys():
        if "問卷資料" in name or "raw" in name.lower():
            sheet_name = name
            break
    if sheet_name is None:
        # fallback: choose largest sheet by rows
        sheet_name = max(xlsx.items(), key=lambda kv: kv[1].shape[0])[0]
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name)

    # identify candidate Likert columns
    likert_cols = []
    for c in df.columns:
        col = df[c].dropna().astype(str)
        if col.empty:
            continue
        # check percent of values matching known labels
        matches = col.isin(SCORE_MAP.keys()).sum()
        if matches / len(col) > 0.5:
            likert_cols.append(c)
    # compute stats
    stats = []
    for c in likert_cols:
        col = df[c].dropna().astype(str)
        mapped = col.map(SCORE_MAP).dropna().astype(float)
        counts = col.value_counts().to_dict()
        pct = {k: f"{v / len(col) * 100:.1f}%" for k, v in counts.items()}
        mean = mapped.mean() if not mapped.empty else None
        stats.append(
            {"col": c, "mean": mean, "counts": counts, "pct": pct, "n": len(col)}
        )
    stats_sorted = sorted(stats, key=lambda s: (s["mean"] is None, -(s["mean"] or 0)))

    # qualitative tokens from 開放式回饋.txt if present else from textual Open columns
    fb_file = Path("開放式回饋.txt")
    texts = []
    if fb_file.exists():
        texts = [
            line.strip()
            for line in fb_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    else:
        # try common open columns
        candidates = [
            c
            for c in df.columns
            if any(k in c for k in ["心得", "建議", "其他", "應用", "建議"])
        ]
        for c in candidates:
            texts += df[c].dropna().astype(str).tolist()
    # filter trivial
    texts = [t for t in texts if t and t not in ("無", "無意見", "N/A", "NA")]
    tokens = Counter()
    token_examples = {}
    for t in texts:
        for tk in extract_cjk_tokens(t):
            if len(tk) >= 2 and tk not in ("非常", "學習"):
                tokens[tk] += 1
                token_examples.setdefault(tk, t)
    top_tokens = tokens.most_common(6)

    # derive 2-4 recommendations heuristically
    recs = []
    # if any mean < 4.5 suggest examine time/materials
    low_stats = [s for s in stats if s["mean"] is not None and s["mean"] < 4.5]
    if low_stats:
        for s in sorted(low_stats, key=lambda x: x["mean"])[:2]:
            if "時數" in s["col"] or "時數" in s["col"] or "時間" in s["col"]:
                recs.append("視學員回饋檢視課程時數配置，必要時增加實作或練習時間。")
            else:
                recs.append(
                    f"檢視「{s['col']}」的教材或教法，可加入更多實務範例或操作練習。"
                )
    # praise high scoring
    high_stats = [s for s in stats if s["mean"] is not None and s["mean"] >= 4.7]
    if high_stats:
        recs.append("維持講師目前互動與教學方式；可將成功做法納入後續課程標準。")
    # add a generic suggestion from top tokens
    if top_tokens:
        common = ",".join([t for t, _ in top_tokens[:3]])
        recs.append(f"針對常見回饋主題（例如：{common}），安排專門討論或補強模組。")

    # deduplicate and limit to 4
    seen = set()
    final_recs = []
    for r in recs:
        if r in seen:
            continue
        seen.add(r)
        final_recs.append(r)
        if len(final_recs) >= 4:
            break

    # build markdown
    md = []
    md.append(f"# 問卷摘要-{xlsx_path.stem}\n")
    md.append(f"_產生時間-{datetime.now().strftime('%Y-%m-%d %H:%M')}_\n")
    md.append("## 量化重點")
    if stats_sorted:
        md.append("| 指標 | 平均分 (5分制) | 回覆數 |")
        md.append("|---|---:|---:|")
        for s in stats_sorted:
            mean = f"{s['mean']:.2f}" if s["mean"] is not None else "-"
            md.append(f"| {s['col']} | {mean} | {s['n']} |")
        md.append("\n")
        top3 = [s for s in stats_sorted if s["mean"] is not None][:3]
        if top3:
            md.append("**最高三項（平均分）**：")
            for s in top3:
                md.append(f"- {s['col']}：{s['mean']:.2f}")
            md.append("\n")
        low3 = [s for s in reversed(stats_sorted) if s["mean"] is not None][:2]
        if low3:
            md.append("**較低項目（建議檢討）**：")
            for s in low3:
                md.append(f"- {s['col']}：{s['mean']:.2f}")
            md.append("\n")
    else:
        md.append("未找到量化欄位。\n")

    md.append("## 質性重點")
    if top_tokens:
        md.append("**常見主題與代表摘錄**：")
        for tk, count in top_tokens[:6]:
            ex = token_examples.get(tk, "")
            md.append(f"- {tk}（出現 {count} 次） — 範例：{ex}")
    else:
        md.append("- 無顯著開放式回饋。")
    md.append("\n")

    md.append("## 建議（2–4 條）")
    if final_recs:
        for i, r in enumerate(final_recs, 1):
            md.append(f"{i}. {r}")
    else:
        md.append("- 無特定建議。")

    text = "\n".join(md)
    # print to stdout for immediate consumption
    print(text)
    # write to file only if out_md is not None
    if out_md is not None:
        out_md.write_text(text, encoding="utf-8")
        return out_md
    return None


if __name__ == "__main__":
    if len(sys.argv) >= 2:
        xlsx = Path(sys.argv[1])
    else:
        # default guess
        xlsx = Path.cwd() / "保單生命週期課後心得問卷_報告.xlsx"
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("xlsx", nargs="?", default=str(xlsx))
    parser.add_argument("--write", action="store_true", help="同時寫出 markdown 檔")
    args = parser.parse_args()
    xlsx = Path(args.xlsx)
    out = xlsx.with_name(xlsx.stem + "_摘要.md") if args.write else None
    try:
        res = summarize_report(xlsx, out)
        if args.write and res is not None:
            print("已生成：", res)
    except Exception as e:
        print("錯誤：", e)
        raise
