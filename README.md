# Info Catalyst

Private Streamlit MVP that turns a YouTube transcript into two AI-generated Markdown reports:

- Summary Report
- Deep Analysis Report

The app uses a transcript-first workflow. It tries public YouTube transcripts and auto-generated captions with `youtube-transcript-api`. If extraction fails, paste a transcript manually and continue.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set:

```text
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4.1-mini
```

Never commit `.env` or API keys.

## Run

```powershell
.\run_app.ps1
```

The launcher uses the project's virtual environment Python:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

This avoids accidentally using the global Python or Streamlit installation.

Open the local Streamlit URL, paste a YouTube URL, review the transcript preview, and generate reports.

Generated reports are saved under:

```text
reports/markdown
```

## Test

```powershell
pytest
```

## Project Structure

```text
app.py
config.py
services/
  analyst.py
  openai_client.py
  prompt_loader.py
  report_writer.py
  summarizer.py
  transcript_provider.py
  url_parser.py
prompts/
  analysis_prompt.md
  summary_prompt.md
tests/
  test_prompt_format.py
  test_url_parser.py
```
