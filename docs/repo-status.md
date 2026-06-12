# Info Catalyst Repo 狀態與架構

本文記錄目前 Info Catalyst MVP 的實際架構，供未來維護者與 AI agent 快速理解專案狀態。這份文件只描述現況與低風險維護邊界，不代表新增產品功能。

## 1. 專案概覽

Info Catalyst 是本機 Streamlit MVP，用來把 YouTube 逐字稿或使用者手動提供的 transcript 轉成研究型 Markdown 報告。專案目前以「transcript-first」為核心假設：優先使用 YouTube 公開字幕或本地 transcript cache，只有在使用者明確選擇時才使用音訊轉錄 fallback。

目前 MVP 範圍包含：

- YouTube URL 解析與 video ID 擷取。
- 本地 transcript cache 讀取與寫入。
- YouTube transcript 擷取。
- 手動 transcript fallback。
- 明確 opt-in 的 audio transcription fallback。
- 分析模式與模型 profile 選擇。
- 報告生成前的成本與 token 粗估。
- OpenAI 生成 Markdown 報告。
- 報告與 metadata 歸檔。
- 可選的 Report Q&A Context Pack 產生。

此專案預設為本機、私人使用；產出的 reports、transcripts、metadata、context packs 和 logs 都可能包含敏感內容，不應預設提交到版本控制。

## 2. 目前 App Flow

1. 使用者在 Streamlit UI 輸入 YouTube URL。
2. App 透過 `services/url_parser.py` 解析 video ID。
3. App 先查詢 `reports/transcripts/{video_id}.json` 是否已有本地 transcript cache。
4. 如果有 cache，優先載入本地 transcript，避免重複打 YouTube。
5. 使用者明確按下 `Fetch transcript from YouTube` 或 `Refresh transcript from YouTube` 時，才呼叫 YouTube transcript 擷取。
6. 如果 YouTube transcript 擷取失敗，使用者可以貼上 manual transcript 並存入 cache。
7. 如果 transcript 不可用，使用者也可以明確確認後啟用 audio transcription fallback。
8. 使用者選擇 analysis mode；系統套用預設 model profile，或使用手動 override。
9. App 根據 transcript 長度、模式、模型和 reasoning effort 顯示成本與 token 粗估。
10. 使用者確認後，App 呼叫 OpenAI 產生 Markdown report。
11. Report 寫入 `reports/markdown`。
12. Metadata 寫入 `reports/metadata`，包含來源、模式、模型、usage 與 transcript 來源資訊。
13. 使用者可從側邊欄開啟近期報告。
14. 使用者可選擇產生 Report Q&A Context Pack，寫入 `reports/context`。

## 3. Module Map

- `app.py`：Streamlit 主入口。處理 UI、session state、URL 輸入、transcript 準備、fallback、成本估算、報告生成、歷史報告與 context pack 顯示。
- `config.py`：讀取 `.env`，定義 prompts、reports、transcripts、metadata、logs 等路徑與 OpenAI 設定。
- `services/url_parser.py`：解析 YouTube URL，擷取並驗證 video ID。
- `services/transcript_provider.py`：處理 YouTube transcript 擷取、語言選擇、proxy debug、yt-dlp audio download，以及 OpenAI audio transcription fallback。
- `services/transcript_cache.py`：讀寫 transcript JSON cache，並處理安全檔名。
- `services/openai_client.py`：封裝 OpenAI Responses API 呼叫、usage metadata 擷取與使用者可理解的錯誤訊息。
- `services/mode_prompts.py`：集中管理 analysis mode 對應的報告架構與 mode prompt 組裝。
- `services/prompt_loader.py`：讀取 prompt template 並填入 transcript、source URL 與其他欄位。
- `services/model_profiles.py`：定義 analysis modes、model options、reasoning effort options 與預設 model profile。
- `services/cost_estimator.py`：以本地 deterministic 規則估算 transcript token、成本等級與確認需求。
- `services/report_writer.py`：提供報告儲存入口，目前主要委派給 report archive。
- `services/report_archive.py`：寫入 Markdown report 與 metadata，列出近期報告，查找重複 video ID，並相容 legacy markdown。
- `services/context_pack.py`：根據 report 與 metadata 產生可複製給外部 AI 的 Report Q&A Context Pack。
- `services/summarizer.py`：legacy summary prompt wrapper；目前主 UI 主要使用 mode-based prompt flow。
- `services/analyst.py`：legacy deep analysis prompt wrapper；目前主 UI 主要使用 mode-based prompt flow。
- `prompts/`：Markdown prompt templates，包含 mode report、summary、analysis 等模板。
- `tests/`：低成本 deterministic 測試，涵蓋 URL parsing、prompt formatting、transcript cache/provider、cost estimator、model profiles、report archive、context pack 等。
- `reports/`：本機產出資料夾。內容通常是使用者資料，不應提交真實產物。

## 4. Data Directories

- `reports/markdown`：產生的 Markdown 報告。
- `reports/metadata`：每份報告對應的 JSON metadata。
- `reports/transcripts`：YouTube 或 manual transcript cache。
- `reports/context`：Report Q&A Context Pack。
- `logs/`：本機執行 log，例如 `logs/app.log`。

若需要可公開的範例，建議建立獨立的 `sample_reports/`，不要提交真實 generated reports、transcripts 或 context packs。

## 5. Testing Policy

- 測試應保持 deterministic。
- 測試不應呼叫真實 YouTube。
- 測試不應呼叫真實 OpenAI API。
- 外部服務需使用 mock、fake object 或本地 fixture。
- 優先測 URL parsing、prompt formatting、cache read/write、metadata serialization、成本估算與模式對應等低成本行為。

## 6. Operational Notes

- `.env` 必須永遠不要 commit。
- `.venv/` 必須永遠不要 commit。
- 建議用 `run_app.ps1` 啟動 app。
- 不要用全域 Python 直接跑 Streamlit，避免套件版本、`.env` 與工作目錄不一致。
- 保持 transcript-first approach；產生報告前應先使用已準備好的 transcript。
- Audio fallback 必須維持 opt-in，且要清楚提醒可能花較久時間與增加 API 成本。
- YouTube transcript extraction 可能因 IP、proxy、頻率或 YouTube policy 被阻擋。
- 有 transcript cache 時，應先使用 cache，再考慮打 YouTube。
- 如果 PowerShell 或 Windows Terminal 顯示中文亂碼，請確認終端與檔案讀取使用 UTF-8，例如 PowerShell 可先執行 `chcp 65001`，並用支援 UTF-8 的字型。

## 7. Known Risks

- `app.py` 目前偏大，聚合 UI、state、fallback、report generation 與 archive 顯示，後續應逐步拆分。
- `services/transcript_provider.py` 同時處理 YouTube transcript、proxy 設定、yt-dlp audio download 與 OpenAI transcription，責任較多。
- Generated reports、transcripts、metadata、context packs 與 logs 可能包含敏感內容。
- Model availability 取決於執行時 OpenAI 帳號權限，不保證每個 profile 在所有環境都可用。
- Windows / PowerShell 編碼設定不一致時，可能讓繁體中文顯示錯誤；修改中文文件前需確認 UTF-8。
- 已被 Git 追蹤的 generated files 不會因新增 `.gitignore` 規則自動解除追蹤，需另行審慎處理。

## 8. 建議的下一步 Refactor Boundaries

- 先從 `app.py` 抽出 Streamlit UI helper functions，例如 transcript status、manual fallback、cost estimate、report display 與 context pack controls。
- 如果 audio transcription fallback 繼續成長，再從 `services/transcript_provider.py` 拆到獨立 module。
- 保持 report archive 與 metadata 邏輯隔離在 `services/report_archive.py`。
- 保持 prompt、analysis mode 與 model profile 邏輯集中在 `services/mode_prompts.py` 與 `services/model_profiles.py`。
- 每次 refactor 都應搭配 deterministic tests，避免引入 YouTube 或 OpenAI API 依賴。
