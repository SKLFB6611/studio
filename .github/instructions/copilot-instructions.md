---
applyTo: "**"
description: "Studio 工作區專案脈絡與 AI 角色定位。always-on，每次對話自動載入。"
---

# Studio — 個人 Side Project 工作區

## 角色定位

你是此工作區的 **個人 side project 開發助手**。
工作區用途：實驗、學習、工具開發。
非商業專案。決策優先序：**可讀性 > 維護性 > 不過度工程化**。

---

## 工作區結構

此工作區為**單一個人工作區**，以資料夾分類管理（基於安全性與可尋性，非多專案隔離）：

```
studio/
├── .github/            # Copilot 設定、skills、instructions
│   ├── instructions/   # always-on 指令（本檔與 caveman 風格檔）
│   └── skills/         # 按需載入的任務流程
├── AI EXCEL_area/      # Excel 相關任務與產出
├── AI PPT_area/        # PPT 相關任務與產出
├── task_area/          # 一般任務與筆記
├── .env                # 環境變數（本地，不 commit）
└── docs/               # 跨區共用文件與筆記
```

**分區原則**：各 `_area` 資料夾為分類用，非獨立專案；跨區共用邏輯放 `docs/` 或另行約定。

---

## 技術棧

> 以下為主要使用組合；單一任務可依需求偏離，但需在該任務內註明。

- **語言**：Python 3.11+（主力）、TypeScript
- **後端**：FastAPI
- **前端**：Vue
- **套件管理**：pip + venv（Python）、npm（JS/TS）
- **資料庫**：SQLite（本地開發）
- **環境變數**：`.env`，由 `python-dotenv` 載入，**不得 commit**

---

## 編碼風格

- 命名：Python 用 `snake_case`；TS/JS 用 `camelCase`
- 函式單一職責，超過 40 行考慮拆分
- 型別標註優先：Python 用 type hints；TypeScript 禁用 `any`
- 錯誤處理顯式寫出，**不吞 exception**
- 註解用繁體中文，解釋「為什麼」而非「做什麼」
- 不留 dead code，直接刪除

---

## Git 工作流程

遵循 `.github/skills/git-workflow/SKILL.md`，涵蓋 commit message、branch 命名、PR 流程。
本檔不重複細節，以 skill 為單一事實來源。

核心底線：**不在 main branch 直接 commit 功能性變更**。

---

## 工作慣例

- 新功能先寫最小可運作版本，再迭代
- 測試檔放 `tests/`，命名 `test_<模組名>.py`
- 涉及 Excel 產出或暫存檔，限定於對應 `AI EXCEL_area/` 內執行