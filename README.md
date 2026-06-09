# Info Catalyst

標準啟動方式是使用專案內建的啟動器 `run_app.ps1`：

```powershell
cd "C:\Users\Peter\Desktop\Tech Project\2026 - Project Titan\Info Catalyst\Info-Catalyst"
.\run_app.ps1
```

`run_app.ps1` 會使用本專案虛擬環境裡的 Python 啟動 Streamlit：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

請不要直接使用：

```powershell
streamlit run app.py
```

因為這樣可能會不小心用到電腦全域安裝的 Python 或 Streamlit，而不是本專案 `.venv` 裡的環境，導致套件版本、API key 讀取或執行結果不一致。

## 快速啟動

1. 開啟 PowerShell。
2. 切換到專案根目錄：

```powershell
cd "C:\Users\Peter\Desktop\Tech Project\2026 - Project Titan\Info Catalyst\Info-Catalyst"
```

3. 執行啟動器：

```powershell
.\run_app.ps1
```

4. 如果瀏覽器沒有自動開啟，請手動打開：

```text
http://localhost:8501
```

5. 要停止 App，回到 PowerShell 視窗按 `Ctrl + C`。

## 專案用途

Info Catalyst 是一個 Streamlit MVP，用來把 YouTube 影片逐字稿轉成 AI 產出的研究報告。它目前的用途是：

- 接受 YouTube 連結。
- 擷取影片逐字稿或字幕。
- 產生 Summary Report。
- 產生 Deep Analysis Report。
- 以台灣用語的繁體中文輸出報告。
- 支援來源逐字稿為繁體中文、簡體中文或英文。

這個專案是給非工程背景的專案擁有者使用，日常開發可由 Codex 協助修改與除錯；實際啟動與測試 App，建議在一般 PowerShell 內執行。

## 目前 MVP 功能

- YouTube URL 輸入。
- YouTube 影片 ID 解析。
- 公開逐字稿與自動字幕擷取。
- 顯示可用字幕語言與目前選用的字幕。
- 逐字稿預覽。
- 自動擷取失敗時，可手動貼上逐字稿作為備援。
- Summary Report 產生。
- Deep Analysis Report 產生。
- Markdown 報告儲存到 `reports/markdown`。

## 環境設定

`.env` 用來在本機保存真正的 OpenAI API key。這個檔案只能留在自己的電腦上，絕對不要 commit 到 Git。

`.env.example` 是安全的範本，可以放在 Git 裡，因為裡面不應包含任何真實 API key。

OpenAI API key 建議在 OpenAI 專案 `Info Catalyst` 底下建立，方便之後管理權限、費用與使用紀錄。

安全範例：

```env
OPENAI_API_KEY=
SUMMARY_MODEL=
ANALYSIS_MODEL=
```

注意：目前程式碼實際讀取的是 `OPENAI_API_KEY` 與 `OPENAI_MODEL`。如果目前版本還沒有支援 Summary / Analysis 分別指定模型，請依照 `.env.example` 使用：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

請不要把真實 key 貼到 README、Git commit、聊天紀錄或任何公開位置。

## 安裝流程

第一次設定專案，或重新建立 `.venv` 時，使用以下指令：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

安裝完成後，請建立自己的 `.env`：

```powershell
Copy-Item .env.example .env
```

然後用文字編輯器打開 `.env`，填入自己的 OpenAI API key。

日常使用通常不需要重新安裝 requirements；只有在 `requirements.txt` 有變更、套件遺失，或重新建立 `.venv` 時，才需要再執行安裝流程。

## 標準日常使用流程

每天要啟動 App 時，使用：

```powershell
cd "C:\Users\Peter\Desktop\Tech Project\2026 - Project Titan\Info Catalyst\Info-Catalyst"
.\run_app.ps1
```

啟動後，在瀏覽器打開 `http://localhost:8501`，貼上 YouTube 連結，確認逐字稿預覽，再產生報告。

## 重要注意事項

- 不要 commit `.env`。
- 不要 commit `.venv`。
- 不要把 API key、密碼、generated secrets 或 Streamlit 本機 secrets 放進 Git。
- 請使用 `.\run_app.ps1`，不要直接使用 `streamlit run app.py`。
- App 請從一般 PowerShell 啟動，不要從 Codex 裡面啟動。
- Codex 適合用來協助編輯、解釋與除錯程式碼；PowerShell 適合用來啟動與測試 App。
- 產生的 Markdown 報告會寫到 `reports/markdown`。
- 這個 MVP 採用 transcript-first 流程：先嘗試取得 YouTube 逐字稿或字幕，不優先做音訊下載、音訊轉錄或網頁爬取。

## 專案結構

目前主要檔案與資料夾如下：

```text
app.py
  Streamlit App 主程式。

config.py
  讀取 .env 設定，包含 OpenAI API key、模型名稱、prompt 路徑與報告輸出路徑。

run_app.ps1
  標準啟動器，使用 .venv 裡的 Python 執行 Streamlit。

requirements.txt
  Python 套件清單。

.env.example
  安全的環境變數範本，不包含真實 API key。

prompts/
  analysis_prompt.md
  summary_prompt.md
  AI 報告產生時使用的 prompt 範本。

services/
  analyst.py
  openai_client.py
  prompt_loader.py
  report_writer.py
  summarizer.py
  transcript_provider.py
  url_parser.py
  App 的主要功能模組，包含逐字稿取得、prompt 組合、OpenAI 呼叫與報告儲存。

reports/markdown/
  產生的 Markdown 報告輸出位置。

tests/
  test_prompt_format.py
  test_transcript_provider.py
  test_url_parser.py
  低成本、可重複的自動化測試。

check_transcript.py
  開發與除錯用的小工具，用來檢查 YouTube 影片可用的逐字稿。

AGENTS.md
  Codex / agent 使用此專案時的協作注意事項。
```

本機產生的 `.venv`、`.env`、`__pycache__`、pytest cache 與其他暫存資料不應視為需要手動維護的專案內容。

## Troubleshooting

PowerShell 擋下 `run_app.ps1`：

如果看到執行原則相關錯誤，可以在目前這次 PowerShell 工作階段允許本機 script：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_app.ps1
```

缺少 `.env`：

如果還沒有 `.env`，請先複製範本：

```powershell
Copy-Item .env.example .env
```

然後打開 `.env`，填入 OpenAI API key。

找不到 OpenAI API key：

請確認 `.env` 裡有設定：

```env
OPENAI_API_KEY=你的真實 API key
```

也請確認是用 `.\run_app.ps1` 啟動，而不是從其他資料夾或其他 Python 環境啟動。

逐字稿擷取失敗：

可能原因包含影片沒有公開逐字稿、字幕被關閉、影片限制、YouTube 暫時阻擋請求，或該字幕語言不可用。此時可以把逐字稿手動貼到 App 的 manual transcript fallback 欄位，繼續產生報告。

Streamlit 不小心用到全域 Python：

請停止 App，改用：

```powershell
cd "C:\Users\Peter\Desktop\Tech Project\2026 - Project Titan\Info Catalyst\Info-Catalyst"
.\run_app.ps1
```

確認 Python 路徑：

在啟用 `.venv` 後，可以執行：

```powershell
python -c "import sys; print(sys.executable)"
```

如果是專案虛擬環境，路徑應該會指向：

```text
C:\Users\Peter\Desktop\Tech Project\2026 - Project Titan\Info Catalyst\Info-Catalyst\.venv\Scripts\python.exe
```

## Git 工作流

查看目前有哪些檔案變更：

```powershell
git status
```

提交 README 更新：

```powershell
git add .
git commit -m "Update README"
git push
```

提交前請再次確認沒有把 `.env`、`.venv`、API key 或其他秘密資訊加入 Git。
