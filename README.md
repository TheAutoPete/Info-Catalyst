# Info Catalyst

Info Catalyst 是一個 Windows / PowerShell 友善的 Streamlit MVP，用來從 YouTube 影片取得逐字稿，並透過 OpenAI 產生 Summary Report 與 Deep Analysis Report。產出的 Markdown 報告會寫入 `reports/markdown`。

## 快速開始

```powershell
# 進入你 clone 下來的專案根目錄
cd path\to\info-catalyst

# 使用啟動器啟動 Info Catalyst
.\run_app.ps1
```

請把 `path\to\info-catalyst` 換成你自己電腦上的專案路徑。

「專案根目錄」是包含 `app.py`、`README.md`、`requirements.txt`、`run_app.ps1` 的資料夾。請在這個資料夾執行安裝、設定與啟動指令。

`run_app.ps1` 會使用專案自己的虛擬環境 Python 啟動 Streamlit。目前啟動器內容是：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

私人使用時，建議讓 App 只在本機開啟，也就是使用 `localhost`。若未來要調整啟動器，可以使用這種形式：

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address localhost
```

## Windows 第一次設定

第一次在新電腦或新資料夾使用時，請在 PowerShell 執行：

```powershell
git clone <REPO_URL>
cd info-catalyst
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
.\run_app.ps1
```

請把 `<REPO_URL>` 換成實際的 Git repository URL。開啟 `.env` 後，填入你自己的 OpenAI API key。

## 日常使用

平常已經設定好之後，只需要：

```powershell
cd path\to\info-catalyst
.\run_app.ps1
```

不需要每次都重新安裝 `requirements.txt`。只有在專案依賴套件更新，或重新建立 `.venv` 時，才需要再次執行安裝指令。

啟動後，Streamlit 通常會顯示本機網址，例如：

```text
http://localhost:8501
```

使用完畢後，回到 PowerShell 視窗按 `Ctrl + C` 停止 App。

## 重要提醒：不要直接執行 streamlit

請優先使用：

```powershell
.\run_app.ps1
```

不建議直接執行：

```powershell
streamlit run app.py
```

因為這樣可能會用到全域 Python 或全域 Streamlit，而不是專案 `.venv` 裡的環境。這可能造成套件版本不同、找不到 API key，或在 Codex 協助開發時出現難以追蹤的環境問題。

## 環境變數與 API Key

`.env` 是放在你自己電腦上的本機設定檔，裡面存放真正的 OpenAI API key。`.env` 不可以 commit 到 Git，也不應該分享給其他人。

`.env.example` 是安全的範本，可以放在 Git 裡，讓其他使用者知道需要哪些設定欄位。

請自行到 OpenAI 建立 API key，然後填入 `.env`。範例格式：

```env
OPENAI_API_KEY=
SUMMARY_MODEL=
ANALYSIS_MODEL=
```

請不要把真實 API key 寫進 `README.md`、程式碼、commit 訊息或任何公開文件。

## 本機安全建議

一般私人使用請使用 `localhost`。這表示 App 只給你目前這台電腦使用。

Streamlit 有時也會顯示 Network URL。除非你明確想讓同一個區域網路內的其他裝置連進來，否則不要分享 Network URL。

使用完畢請在 PowerShell 按 `Ctrl + C` 關閉 App。

## 專案功能

- 接收 YouTube URL。
- 解析 YouTube 影片 ID。
- 優先使用逐字稿擷取內容。
- 產生 Summary Report。
- 產生 Deep Analysis Report。
- 將 Markdown 報告輸出到 `reports/markdown`。

這個 MVP 以 transcript-first 為優先：先嘗試取得 YouTube 逐字稿，再考慮其他備援方式。這樣比較快，也比較適合保持專案簡潔。

## 專案結構

以下是目前 repository 中主要檔案與資料夾：

```text
app.py
  Streamlit App 入口。

config.py
  讀取 .env 設定，例如 OpenAI API key 與模型名稱。

run_app.ps1
  Windows PowerShell 啟動器，使用 .venv 裡的 Python 啟動 Streamlit。

requirements.txt
  Python 套件清單。

.env.example
  環境變數範本，不包含真實 API key。

prompts/
  analysis_prompt.md
  summary_prompt.md
  AI 報告產生用的 prompt 範本。

services/
  analyst.py
  openai_client.py
  prompt_loader.py
  report_writer.py
  summarizer.py
  transcript_provider.py
  url_parser.py
  __init__.py
  App 的主要服務模組，例如逐字稿取得、URL 解析、prompt 載入、OpenAI 呼叫與報告寫入。

reports/
  markdown/
  產出的 Markdown 報告位置。

tests/
  test_prompt_format.py
  test_transcript_provider.py
  test_url_parser.py
  低成本、可重複執行的測試。

check_transcript.py
  檢查 YouTube 逐字稿擷取狀況的輔助腳本。

AGENTS.md
  Codex / agent 協作時的專案注意事項。

.gitignore
  Git 忽略規則。
```

本機產生或私人使用的檔案，例如 `.env`、`.venv`、`__pycache__`、pytest cache，不應該作為一般專案文件要求其他使用者手動修改或 commit。

## Troubleshooting

### PowerShell 封鎖 run_app.ps1

如果 PowerShell 不讓你執行腳本，可以只針對目前 PowerShell 視窗暫時放行：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\run_app.ps1
```

### 找不到 .env

請先從範本建立自己的 `.env`：

```powershell
copy .env.example .env
notepad .env
```

### 找不到 OpenAI API key

請確認 `.env` 裡有設定：

```env
OPENAI_API_KEY=你的 OpenAI API key
```

不要把 `你的 OpenAI API key` 這幾個字原樣留下來，請換成你自己建立的真實 key。

### Transcript extraction fails

有些 YouTube 影片沒有可用逐字稿、關閉字幕，或受到地區與權限限制。遇到這種情況時，可以換一支有字幕或逐字稿的影片測試。這個 MVP 目前以逐字稿優先，不以音訊下載或網頁爬取作為主要流程。

### Streamlit 不小心用到全域 Python

請確認你是用啟動器：

```powershell
.\run_app.ps1
```

不要直接用：

```powershell
streamlit run app.py
```

### 如何確認 Python 路徑

如果你已經啟用 `.venv`，可以用：

```powershell
python -c "import sys; print(sys.executable)"
```

正常情況下，輸出路徑應該指向你的專案資料夾底下的 `.venv\Scripts\python.exe`，而不是系統全域 Python。

## Git 工作流程

更新 README 後，可以用：

```powershell
git status
git add README.md
git commit -m "Update README quick start guide"
git push
```

commit 前請再次確認沒有加入 `.env`、API key、`.venv` 或其他本機產生的私人檔案。
