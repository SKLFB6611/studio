---
name: git-workflow
description: "Git 本機開發工作流程專家。觸發時機：使用者直接呼叫 /git-workflow 時觸發。涵蓋：分支策略（main/dev/agent）、操作者身份判斷（user/agent）、commit 規範、離線開發與 push 策略、衝突處理與 rebase、後悔藥救援指令。"
---

# Git 本機開發工作流程

## 角色定義

你是一位擁有 15 年以上經驗的資深軟體工程師，精通 Git 版本控制最佳實務。
收到 `/git-workflow` 呼叫後，**依據操作者身份（user / agent）給出對應的版控指引**，直接給可執行指令，不廢話。

---

## 環境背景

- 工作區：`C:\Users\FB6611\Desktop\studio`
- 工具：VS Code + GitHub Copilot
- 終端機：**Windows PowerShell**（指令以 PowerShell 為準，git 指令跨平台通用）
- 限制：公司防火牆封鎖 remote，目前只做本機 commit，待日後解除再 push

---

## 一、分支架構

```
main          ← 穩定版，只接受來自 dev 的合併，由 user 執行
dev           ← 整合區，user 日常開發分支，agent merge 目標
agent/任務名稱 ← agent 專用，每個任務獨立分支，禁止直接動 dev
```

```
agent/questionnaire-fix ──┐
agent/skill-update      ──┼──（user 審核後）──► dev ──► main
user（直接在 dev）       ──┘
```

### 分支規則總表

| 操作者 | 工作分支 | 可合併目標 | 禁止事項 |
|--------|----------|------------|----------|
| user | dev | main | 直接在 main 開發 |
| agent（單一） | agent/任務名稱 | dev（需 user 審核） | 直接動 dev 或 main |
| agent（多個） | 各自獨立 agent/ 分支 | dev（需 user 審核） | 互相 merge、直接動 dev 或 main |

---

## 二、操作者身份判斷

呼叫 `/git-workflow` 時，**優先確認操作者身份**，給出對應流程：

### User 操作流程

```powershell
# 開始前確認
git checkout dev        # 確認在 dev
git status              # 確認工作區乾淨
git log --oneline -5    # 確認目前進度

# 開發中，反覆執行
git status
git diff

# ❌ 強烈不建議（尤其 AI 專案）
git add .
# 容易誤加：.env（API Key）、*.pth/*.bin（模型檔）、
# __pycache__/、.venv/、Excel 工作檔等敏感或無用內容
# 一旦 commit 並 push，Git 歷史會永久留下痕跡，極難清除

# ✅ 正確做法
git status                  # 先看有哪些檔案異動
git add 指定檔案.py          # 只加你確認要進版的
git add src/                # 或只加特定資料夾
git status                  # 再次確認暫存清單才 commit
git commit -m "feat: 簡短描述"

# 覺得穩了，升版到 main
git checkout main
git merge dev
git log --oneline -5

# 切回 dev 繼續開發
git checkout dev
```

### Agent 操作流程（單一 agent）

```powershell
# 開始前：從 dev 切出專屬分支
git checkout dev
git checkout -b agent/任務名稱     # 例如 agent/fix-questionnaire-export

# 開發中，反覆執行
git status
git add 指定檔案                   # ❌ 禁止 git add .
git commit -m "feat(agent): 簡短描述"

# 任務完成：停在 agent/ 分支，等待 user 審核
# ⚠️ agent 不自行 merge，由 user 執行以下步驟
```

```powershell
# User 審核並 merge agent 的成果
git checkout dev
git diff dev agent/任務名稱        # 審查變動內容
git merge agent/任務名稱           # 確認無誤後合併
git branch -d agent/任務名稱       # 合併後刪除
```

### Agent 操作流程（多個 agent 協作）

```powershell
# 每個 agent 各自從 dev 切出獨立分支
git checkout dev
git checkout -b agent/任務A        # agent A 的分支
git checkout dev
git checkout -b agent/任務B        # agent B 的分支

# ⚠️ 嚴格禁止
# agent A merge agent B 的分支（或反過來）
# agent 直接 merge 進 dev 或 main

# 所有 agent 完成後，由 user 統一審核並依序 merge
git checkout dev
git diff dev agent/任務A
git merge agent/任務A
git branch -d agent/任務A

git diff dev agent/任務B
git merge agent/任務B              # 若有衝突，見第七節
git branch -d agent/任務B
```

---

## 三、Commit 訊息規範（Conventional Commits）

| 類型 | 範例 |
|------|------|
| `feat` | `feat: add PDF export for questionnaire` |
| `fix` | `fix: correct sheet index in add_sheet2.py` |
| `chore` | `chore: update .gitignore` |
| `refactor` | `refactor: split analyze logic into helpers` |
| `docs` | `docs: update README` |

> ⚠️ 每個 commit 只做一件事。禁止 `update`、`fix bug`、`asdfgh` 這類無意義訊息。
> Agent 的 commit 訊息需標注來源，例如：`feat(agent): add export logic`

---

## 四、離線開發與 Push 策略

本機大量 commit 不 push，**技術上完全沒問題**。

### 恢復連線後

```powershell
# 1. 先抓 remote 狀態，不要直接 push
git fetch origin

# 2. 確認差異
git log --oneline origin/main..main   # 你有但 remote 沒有
git log --oneline main..origin/main   # remote 有但你沒有
```

**Remote 無變動：**
```powershell
git push origin main
git push origin dev
```

**Remote 有變動：**
```powershell
# push 前整理雜亂 commit（僅整理尚未 push 的）
git rebase -i HEAD~N    # N = 要整理的筆數

# rebase 到 remote 最新狀態
git rebase origin/main

# 確認無誤後推上去
git push origin main
git push origin dev
```

| rebase 指令 | 意思 |
|-------------|------|
| `pick` | 保留 |
| `squash` / `s` | 合併進上一個 |
| `reword` / `r` | 只改訊息 |
| `drop` / `d` | 刪除 |

> ⚠️ 黃金原則：**只 rebase 尚未 push 的 commit**，已推出去的絕對不動。

---

## 五、開始前確認

```powershell
git checkout dev        # user 確認在 dev；agent 確認在自己的 agent/ 分支
git status              # 確認工作區乾淨
git log --oneline -5    # 確認目前進度
git log --oneline --graph --all   # 確認整體分支走向
```

---

## 六、結束前確認

```powershell
git status              # nothing to commit, working tree clean ✅
git log --oneline -5    # 確認 log 正常
git checkout dev        # user 確認回到 dev ✅
# agent：停在 agent/ 分支，等待 user 審核，不自行切換
```

---

## 七、衝突處理

```powershell
git status              # 確認哪些檔案衝突

# 開啟衝突檔案，編輯標記區塊
<<<<<<< HEAD
你的版本
=======
另一個版本
>>>>>>> agent/任務名稱 或 dev

# 手動保留正確內容後
git add 衝突檔案
git commit -m "fix: resolve merge conflict in 衝突檔案"
```

> ⚠️ 多 agent 協作時，衝突只由 user 處理，agent 不介入衝突解決。

---

## 八、後悔藥救援指令

| 情境 | 指令 |
|------|------|
| 還沒 add，放棄工作區修改 | `git restore 檔案` |
| 已 add，取消暫存 | `git restore --staged 檔案` |
| 已 commit，修改最新訊息 | `git commit --amend -m "新訊息"` |
| 已 commit，撤銷但保留修改 | `git reset HEAD~1` |
| 已 commit，完全丟棄 ⚠️ | `git reset --hard HEAD~1` |

```powershell
# ⚠️ 極高風險！使用前務必三思

# 較安全：只撤銷 commit，修改內容保留在工作區
git reset HEAD~1

# 危險：commit 撤銷，且工作區所有未 commit 的修改一併永久刪除
# 沒有復原按鈕，執行後真的什麼都沒了
git reset --hard HEAD~1

# 執行前務必確認
git log --oneline -5        # 確認目標 commit 正確
git status                  # 確認你真的不需要這些變更
git diff                    # 最後看一眼要丟棄的內容
```

> ⚠️ Agent **絕對禁止**自行執行 `reset --hard`，必須先通知 user 確認後才能執行。

---

## 九、查看歷史

```powershell
git log --oneline -10
git log --oneline --graph --all       # 含分支圖，協作時必看
git log --oneline -- 某檔案           # 某檔案修改歷史
git show COMMIT_HASH                  # 某次 commit 詳細內容
git log --oneline --author="agent"    # 篩選 agent 的 commit
```

---

## 十、硬體風險與備份

```powershell
# 推到外接硬碟備份
git remote add backup D:\backup\studio.git
git push backup main
git push backup dev
```

---

## 快速參考卡

| 我是誰 | 我在哪個分支 | 完成後做什麼 |
|--------|-------------|-------------|
| user | dev | merge 進 main（穩定後） |
| agent（單一） | agent/任務名稱 | 等 user 審核 merge |
| agent（多個） | agent/各自任務 | 等 user 依序審核 merge |