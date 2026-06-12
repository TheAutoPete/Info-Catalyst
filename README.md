# Info Catalyst

Info Catalyst 是本機 Streamlit MVP，用來把 YouTube 逐字稿或使用者提供的文字轉成研究型 Markdown 報告。專案優先採用 transcript-first 流程，並用本地 cache 降低重複向 YouTube 索取字幕的機率。

## 啟動方式

請優先使用專案啟動器：

```powershell
cd path\to\Info-Catalyst
.\run_app.ps1
```

不要直接用全域 Python 執行 `streamlit run app.py`，避免套件版本、`.env`、API key 讀取路徑不一致。

第一次設定：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
copy .env.example .env
notepad .env
.\run_app.ps1
```

`.env` 範例：

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.4-mini
OPENAI_TRANSCRIPTION_MODEL=whisper-1
OPENAI_USE_SYSTEM_PROXY=false
```

不要 commit `.env`、API keys、generated secrets、local Streamlit secrets 或 `.venv`。

## Current Architecture

目前 repo 架構、app flow、資料目錄、測試政策與下一步安全重構邊界，請見 [`docs/repo-status.md`](docs/repo-status.md)。

## Transcript Flow

YouTube 可能會對過度頻繁的自動字幕請求做流量限制，常見錯誤是 `RequestBlocked` 或 `IpBlocked`。Info Catalyst 現在採用 cache-first 與明確按鈕觸發：

1. 貼上 YouTube URL。
2. App 解析 video ID。
3. App 先檢查 `reports/transcripts/{video_id}.json`。
4. 如果有 cache，預設載入本地 transcript，並顯示 `Loaded transcript from local cache.`。
5. 只有使用者明確點擊 `Fetch transcript from YouTube` 或 `Refresh transcript from YouTube` 時，才會呼叫 YouTube。
6. Refresh 有冷卻時間，避免 Streamlit rerun 或連續點擊造成重複請求。
7. Report generation 只使用已準備好的 transcript，不會再呼叫 YouTube。

Transcript cache 存在：

```text
reports/transcripts/
```

cache 內容包含來源、video ID、URL、語言、逐字稿全文、provider、建立/擷取時間與可用字幕 metadata。

## Fallback Options

如果 YouTube transcript extraction 失敗，請不要一直 refresh。可以改用：

- 載入本地 cached transcript
- 手動貼上 transcript，並按 `Save manual transcript to cache`
- 明確勾選確認後使用 `Use audio transcription fallback`

Audio transcription fallback 是 opt-in。它可能下載音訊並呼叫 OpenAI transcription，會比 YouTube 字幕擷取慢，也可能產生額外 API 成本。只有在使用者明確確認並按下按鈕後才會執行。

## Analysis Modes

- `Quick Summary`
- `Deep Analysis`
- `Investment Lens`
- `Bias Check`
- `Titan Input / Structured Research`

輸出報告維持台灣慣用繁體中文。可使用預設 model profile，也可以勾選 `Override model settings` 覆寫 model 與 reasoning effort。

## Reports And Metadata

Markdown 報告：

```text
reports/markdown
```

Metadata：

```text
reports/metadata
```

Context Pack：

```text
reports/context
```

metadata 會記錄 video ID、source URL、analysis mode、model profile、usage，以及 transcript 來源資訊：

- `transcript_source`
- `transcript_provider`
- `transcript_cache_path`
- `transcript_language`
- `transcript_created_at`

舊 metadata 仍可相容讀取。

## Cost & Token Estimate

產生報告前會顯示：

- transcript 字元數
- approximate transcript token count
- analysis mode
- report model
- reasoning effort
- qualitative cost level：Low / Medium / High / Very High

若成本等級是 High 或 Very High，必須勾選確認後才能產生報告。Audio transcription fallback 會另外顯示成本與耗時提醒。

## Debugging

預設不顯示 traceback。勾選 `Show debug info` 後可看到：

- parsed video ID
- transcript source
- cache path
- available transcript languages
- cache 是否使用
- YouTube 是否被呼叫
- exception type/message
- full traceback

錯誤會寫入 `logs/app.log`。不要在 log、README 或 commit 中放 API key。

## Tests

執行全部測試：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp tests\.tmp\pytest
```

常用局部測試：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_transcript_cache.py tests\test_transcript_provider.py -q --basetemp tests\.tmp\pytest
```

單元測試不需要真實 YouTube 或 OpenAI API call。
