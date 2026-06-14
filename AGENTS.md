# Info Catalyst Agent Notes

- Keep this MVP small and modular.
- Do not commit `.env`, API keys, generated secrets, or local Streamlit secrets.
- Generated Markdown reports are written to `reports/markdown`.
- Prefer transcript-first extraction before considering any audio or scraping fallback.
- Keep tests focused on URL parsing, prompt formatting, and other low-cost deterministic behavior.
- Do not run `.\run_app.ps1` inside Codex because Streamlit is a long-running server.
- For validation, run deterministic checks:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q --basetemp tests\.tmp\pytest
  .\.venv\Scripts\python.exe -m compileall app.py services ui tests
  ```
- Ask the user to manually test Streamlit from normal PowerShell.
- If UI changes do not appear, check for stale Streamlit processes on port `8501`.
