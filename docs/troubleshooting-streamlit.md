# Streamlit UI 沒更新時怎麼辦

Info Catalyst 是本機 Streamlit app。若 Codex 修改 UI 後，瀏覽器仍顯示舊畫面，通常不是程式碼沒有改到，而是舊的 Streamlit server process 還在背景執行。

## 常見症狀

- Codex 已修改 UI，但瀏覽器仍顯示舊 UI。
- Sidebar 沒有更新。
- Source Library 或新的 controls 沒有出現。
- 瀏覽器仍連到舊的 `localhost:8501` app session。

## 常見原因

- 舊的 Streamlit server process 還在執行。
- 可能有多個 Python 或 Streamlit process 正在 listen。
- 瀏覽器可能仍連在舊的 app session。
- 這不是 `deactivate .venv` 造成的。
- `deactivate .venv` 只會離開目前 PowerShell 的 virtual environment，不會修改程式碼，也不會破壞專案。

## 快速修復流程

```powershell
# 1. 停掉看得到的 Streamlit terminal
# 在執行 Streamlit 的 terminal 按 Ctrl + C

# 2. 檢查 port 8501 是否仍有 listener
netstat -ano | Select-String ":8501"

# 3. 用 PID 停掉殘留 process
Stop-Process -Id <PID> -Force

# 4. 用專案 launcher 重新啟動 app
.\run_app.ps1

# 5. 強制重新整理瀏覽器
# 按 Ctrl + F5，或重新開啟 http://localhost:8501
```

如果有多個 PID，可一次停止：

```powershell
Stop-Process -Id 38452,38696,41808 -Force
```

## 使用專案 launcher

請一律使用：

```powershell
.\run_app.ps1
```

不要直接使用：

```powershell
streamlit run app.py
```

原因是 `run_app.ps1` 會使用專案內的 `.venv`，可避免全域 Python、套件版本、`.env` 載入路徑或工作目錄不一致。

## Codex 驗證方式

不要在 Codex 內執行 `.\run_app.ps1`，因為 Streamlit 是長時間執行的 server，可能阻塞 Codex session。

Codex 應只執行 deterministic checks：

```powershell
.\.venv\Scripts\python.exe -m pytest -q --basetemp tests\.tmp\pytest
.\.venv\Scripts\python.exe -m compileall app.py services ui tests
```

使用者應在一般 PowerShell 手動啟動 Streamlit：

```powershell
.\run_app.ps1
```

## 可選輔助腳本

也可以使用專案提供的 helper script 檢查並停止常見 Streamlit ports 上的 listener：

```powershell
.\scripts\stop_streamlit.ps1
.\run_app.ps1
```

腳本會檢查 ports `8501` 到 `8510`，列出偵測到的 PID，並在確認後才停止 process。
