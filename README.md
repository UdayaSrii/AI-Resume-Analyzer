# CareerPilot AI — AI Resume Analyzer & Career Coach

## Features
- Secure registration/login with JWT
- PDF/DOCX resume upload and text extraction
- ATS scoring and job-description matching
- AI resume rewriting and generation
- Cover letters
- LinkedIn optimization
- Job-role recommendations
- Interview question generation and answer evaluation
- Coding problem generation and code review
- Job application tracker
- 90-day career roadmap
- PDF ATS reports
- Local SQLite database; PostgreSQL on Render
- Professional Streamlit UI

## 1. Install
```powershell
cd "C:\Users\NELLURI UDAYASRI\OneDrive\Documents\AI-Resume-Analyzer"
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 2. Configure
Copy `.env.example` to `.env` and add at least one AI key:
```env
DATABASE_URL=
JWT_SECRET_KEY=replace-with-a-long-random-value
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=
```

Leave `DATABASE_URL` empty for local SQLite. No PostgreSQL installation is required for local development.

## 3. Start backend
From the project ROOT (not inside `backend`):
```powershell
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```
Open http://127.0.0.1:8000/docs

Keep this terminal running.

## 4. Start frontend
Open a SECOND PowerShell terminal:
```powershell
cd "C:\Users\NELLURI UDAYASRI\OneDrive\Documents\AI-Resume-Analyzer"
.\.venv\Scripts\Activate.ps1
streamlit run frontend/app.py
```

The Streamlit sidebar defaults to `http://127.0.0.1:8000`.

## Important
Do not run `--port $PORT` locally in PowerShell. `$PORT` is a Render/server environment variable. Use `--port 8000` locally.

## Render
Deploy `render.yaml`. Render supplies `DATABASE_URL` and `PORT`. Add your AI API key(s) in the service Environment settings.
