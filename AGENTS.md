# Info Catalyst Agent Notes

- Keep this MVP small and modular.
- Do not commit `.env`, API keys, generated secrets, or local Streamlit secrets.
- Generated Markdown reports are written to `reports/markdown`.
- Prefer transcript-first extraction before considering any audio or scraping fallback.
- Keep tests focused on URL parsing, prompt formatting, and other low-cost deterministic behavior.

