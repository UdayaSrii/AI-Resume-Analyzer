import json
import os
import re
import requests
import shutil
import uuid

from datetime import datetime

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException,
    Depends,
    Header
)

from fastapi.responses import FileResponse

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from xml.sax.saxutils import escape

from sqlalchemy.orm import Session

from dotenv import load_dotenv

from .database import (
    Base,
    engine,
    get_db
)

from .models import (
    User,
    Resume,
    Analysis,
    JobApplication
)

from .auth import (
    hash_password,
    verify_password,
    create_access_token,
    decode_token
)

from .resume_parser import extract_text

from .ai_agent import (
    analyze_resume,
    rewrite_resume,
    generate_professional_resume,
    generate_cover_letter,
    optimize_linkedin,
    recommend_roles,
    generate_interview_question,
    evaluate_interview_answer,
    generate_coding_question,
    evaluate_code,
    career_roadmap
)

from .report_generator import create_report


load_dotenv()


# ==================================================
# DATABASE
# ==================================================

Base.metadata.create_all(
    bind=engine
)


# ==================================================
# DIRECTORIES
# ==================================================

UPLOAD_DIR = "uploads"
REPORT_DIR = "reports"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)

os.makedirs(
    REPORT_DIR,
    exist_ok=True
)


# ==================================================
# HELPERS
# ==================================================

def _extract_resume_skills(text: str):
    catalog = [
        "python", "java", "javascript", "typescript", "c", "c++", "c#",
        "sql", "mysql", "postgresql", "mongodb", "html", "css", "react",
        "node.js", "node", "fastapi", "flask", "django", "streamlit",
        "git", "github", "docker", "aws", "azure", "gcp", "power bi",
        "tableau", "excel", "pandas", "numpy", "scikit-learn", "tensorflow",
        "pytorch", "machine learning", "deep learning", "nlp", "generative ai",
        "langchain", "rest api", "api", "figma", "ui/ux", "testing", "selenium",
        "playwright", "pytest", "postman", "linux", "firebase"
    ]
    low = (text or "").lower()
    found = []
    for skill in catalog:
        if skill in low:
            found.append(skill)
    return found


def _job_suitability(job: dict, skills: list, fresher_only: bool):
    title = str(job.get("title", ""))
    description = str(job.get("description", ""))
    blob = f"{title} {description}".lower()
    score = 50
    matched = []
    for skill in skills:
        if skill.lower() in blob:
            matched.append(skill)
            score += 4
    if any(x in blob for x in ["fresher", "graduate", "entry level", "junior", "trainee", "apprentice", "intern"]):
        score += 12
    if fresher_only and not any(x in blob for x in ["fresher", "graduate", "entry level", "junior", "trainee", "apprentice", "intern", "0-1 year", "0-2 years"]):
        score -= 18
    return max(0, min(100, score)), matched


def search_live_jobs(role: str, location: str, resume_text: str, fresher_only: bool = True, limit: int = 15):
    app_id = os.getenv("ADZUNA_APP_ID", "").strip()
    app_key = os.getenv("ADZUNA_APP_KEY", "").strip()
    if not app_id or not app_key:
        return {
            "configured": False,
            "message": "Live job search is not configured. Add ADZUNA_APP_ID and ADZUNA_APP_KEY to the backend environment.",
            "jobs": [],
            "source": "Adzuna"
        }

    role = (role or "Software Engineer").strip()
    location = (location or "India").strip()
    skills = _extract_resume_skills(resume_text)
    query_parts = [role]
    if fresher_only:
        query_parts.append("graduate entry level junior fresher")
    if skills:
        query_parts.append(" ".join(skills[:5]))

    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": min(max(limit * 2, 20), 50),
        "what": " ".join(query_parts),
        "where": location,
        "sort_by": "relevance",
        "max_days_old": 30,
        "content-type": "application/json",
    }
    try:
        r = requests.get(
            "https://api.adzuna.com/v1/api/jobs/in/search/1",
            params=params,
            headers={"Accept": "application/json"},
            timeout=30,
        )
        if not r.ok:
            return {"configured": True, "message": f"Job provider returned HTTP {r.status_code}.", "jobs": [], "source": "Adzuna"}
        data = r.json()
    except Exception as exc:
        return {"configured": True, "message": f"Unable to reach live job provider: {exc}", "jobs": [], "source": "Adzuna"}

    jobs = []
    seen = set()
    for raw in data.get("results", []):
        company = ((raw.get("company") or {}).get("display_name") or "Company")
        title = raw.get("title") or "Job Opening"
        url = raw.get("redirect_url") or ""
        key = f"{company}|{title}|{url}"
        if key in seen:
            continue
        seen.add(key)
        score, matched = _job_suitability(raw, skills, fresher_only)
        jobs.append({
            "id": str(raw.get("id", "")),
            "title": title,
            "company": company,
            "location": ((raw.get("location") or {}).get("display_name") or location),
            "description": raw.get("description") or "",
            "url": url,
            "created": raw.get("created") or "",
            "salary_min": raw.get("salary_min"),
            "salary_max": raw.get("salary_max"),
            "contract_type": raw.get("contract_type") or "",
            "contract_time": raw.get("contract_time") or "",
            "suitability_score": score,
            "matched_skills": matched,
        })

    jobs.sort(key=lambda x: (x["suitability_score"], x["created"]), reverse=True)
    return {
        "configured": True,
        "source": "Adzuna",
        "location": location,
        "role": role,
        "fresher_friendly_filter": fresher_only,
        "jobs": jobs[:limit]
    }


def create_resume_pdf(content: str, path: str, title: str = "ATS-Friendly Resume"):
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ResumeTitle", parent=styles["Title"], fontSize=18, leading=22,
        alignment=TA_CENTER, spaceAfter=16, textColor=colors.HexColor("#0f172a")
    )
    body_style = ParagraphStyle(
        "ResumeBody", parent=styles["BodyText"], fontSize=9.5, leading=13,
        spaceAfter=5, textColor=colors.HexColor("#111827")
    )
    heading_style = ParagraphStyle(
        "ResumeHeading", parent=styles["Heading2"], fontSize=11.5, leading=14,
        spaceBefore=8, spaceAfter=5, textColor=colors.HexColor("#1d4ed8")
    )
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    story = [Paragraph(escape(title), title_style), Spacer(1, 4)]
    for raw_line in (content or "").splitlines():
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 5))
            continue
        clean = re.sub(r"^[#*\-•\d.\s]+", "", line).strip()
        upper = clean.upper()
        if (len(clean) < 60 and upper == clean and any(k in upper for k in [
            "SUMMARY", "PROFILE", "SKILLS", "EXPERIENCE", "INTERNSHIP", "PROJECTS",
            "EDUCATION", "CERTIFICATIONS", "ACHIEVEMENTS", "LANGUAGES", "COURSEWORK"
        ])):
            story.append(Paragraph(escape(clean), heading_style))
        else:
            story.append(Paragraph(escape(line).replace("  ", "&nbsp; "), body_style))
    doc.build(story)


# ==================================================
# APP
# ==================================================

app = FastAPI(
    title="AI Resume Analyzer & Career Coach",
    version="4.0.0"
)


# ==================================================
# AUTHENTICATION
# ==================================================

def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
):

    if not authorization:

        raise HTTPException(
            status_code=401,
            detail="Authorization header required."
        )

    if not authorization.startswith(
        "Bearer "
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header."
        )

    token = authorization.split(
        " ",
        1
    )[1]

    user_id = decode_token(
        token
    )

    if not user_id:

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token."
        )

    user = (
        db.query(User)
        .filter(
            User.id == user_id
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="User not found."
        )

    return user


# ==================================================
# ROOT
# ==================================================

@app.get("/")
def root():

    return {
        "message":
            "AI Resume Analyzer API is running",
        "version":
            "4.0.0"
    }


@app.get("/config/status")
def config_status():
    """Safely report whether backend secrets are configured. Never returns secret values."""
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    adzuna_id = os.getenv("ADZUNA_APP_ID", "").strip()
    adzuna_key = os.getenv("ADZUNA_APP_KEY", "").strip()
    return {
        "groq_configured": bool(groq_key),
        "openai_configured": bool(openai_key),
        "adzuna_configured": bool(adzuna_id and adzuna_key),
        "message": "Backend environment configuration checked successfully."
    }


@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# ==================================================
# REGISTER
# ==================================================

@app.post("/auth/register")
def register(

    name: str = Form(...),

    email: str = Form(...),

    password: str = Form(...),

    db: Session = Depends(get_db)
):

    email = email.lower().strip()

    existing = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    if existing:

        raise HTTPException(
            status_code=400,
            detail="Email already registered."
        )

    if len(password) < 6:

        raise HTTPException(
            status_code=400,
            detail=(
                "Password must contain "
                "at least 6 characters."
            )
        )

    user = User(

        name=name.strip(),

        email=email,

        password_hash=hash_password(
            password
        )
    )

    db.add(user)

    db.commit()

    db.refresh(user)

    token = create_access_token(
        user.id
    )

    return {

        "success": True,

        "token": token,

        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }


# ==================================================
# LOGIN
# ==================================================

@app.post("/auth/login")
def login(

    email: str = Form(...),

    password: str = Form(...),

    db: Session = Depends(get_db)
):

    email = email.lower().strip()

    user = (
        db.query(User)
        .filter(
            User.email == email
        )
        .first()
    )

    if not user:

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    if not verify_password(
        password,
        user.password_hash
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid email or password."
        )

    token = create_access_token(
        user.id
    )

    return {

        "success": True,

        "token": token,

        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email
        }
    }


# ==================================================
# PROFILE
# ==================================================

@app.get("/profile")
def profile(
    user: User = Depends(get_current_user)
):

    return {

        "id": user.id,

        "name": user.name,

        "email": user.email
    }


# ==================================================
# RESUME UPLOAD
# ==================================================

@app.post("/resumes")
async def upload_resume(

    resume: UploadFile = File(...),

    user: User = Depends(get_current_user),

    db: Session = Depends(get_db)
):

    filename = resume.filename or ""

    extension = os.path.splitext(
        filename
    )[1].lower()

    if extension not in [
        ".pdf",
        ".docx"
    ]:

        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX files are allowed."
        )

    unique_name = (
        f"{uuid.uuid4()}{extension}"
    )

    file_path = os.path.join(
        UPLOAD_DIR,
        unique_name
    )

    try:

        with open(
            file_path,
            "wb"
        ) as buffer:

            shutil.copyfileobj(
                resume.file,
                buffer
            )

        text = extract_text(
            file_path
        )

        if not text.strip():

            raise HTTPException(
                status_code=400,
                detail="Unable to extract resume text."
            )

        resume_record = Resume(

            user_id=user.id,

            filename=filename,

            file_path=file_path,

            extracted_text=text
        )

        db.add(
            resume_record
        )

        db.commit()

        db.refresh(
            resume_record
        )

        return {

            "success": True,

            "resume_id":
                resume_record.id,

            "filename":
                filename
        }

    except HTTPException:

        raise

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ==================================================
# GET RESUMES
# ==================================================

@app.get("/resumes")
def get_resumes(

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resumes = (
        db.query(Resume)
        .filter(
            Resume.user_id == user.id
        )
        .order_by(
            Resume.created_at.desc()
        )
        .all()
    )

    return {

        "resumes": [

            {
                "id": r.id,
                "filename": r.filename,
                "created_at":
                    r.created_at.isoformat()
            }

            for r in resumes
        ]
    }


# ==================================================
# ANALYZE RESUME
# ==================================================

@app.post("/analyze")
def analyze(

    resume_id: int = Form(...),

    job_title: str = Form(""),

    company: str = Form(""),

    job_description: str = Form(...),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    ),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id
        )
        .first()
    )

    if not resume:

        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    try:

        result = analyze_resume(

            resume_text=
                resume.extracted_text,

            job_description=
                job_description,

            provider=
                provider,

            model_name=
                model_name
        )

        score = (
            result
            .get(
                "ats_analysis",
                {}
            )
            .get(
                "score",
                0
            )
        )

        analysis = Analysis(

            user_id=user.id,

            resume_id=resume.id,

            job_title=job_title,

            company=company,

            job_description=
                job_description,

            ats_score=score,

            result=json.dumps(
                result
            )
        )

        db.add(
            analysis
        )

        db.commit()

        db.refresh(
            analysis
        )

        return {

            "success": True,

            "analysis_id":
                analysis.id,

            "result":
                result
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ==================================================
# GET ANALYSIS
# ==================================================

@app.get("/analysis/{analysis_id}")
def get_analysis(

    analysis_id: int,

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    analysis = (
        db.query(Analysis)
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user.id
        )
        .first()
    )

    if not analysis:

        raise HTTPException(
            status_code=404,
            detail="Analysis not found."
        )

    return {

        "id":
            analysis.id,

        "job_title":
            analysis.job_title,

        "company":
            analysis.company,

        "ats_score":
            analysis.ats_score,

        "result":
            json.loads(
                analysis.result
            ),

        "created_at":
            analysis.created_at.isoformat()
    }


# ==================================================
# ANALYSIS HISTORY
# ==================================================

@app.get("/analyses")
def analyses(

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    records = (
        db.query(Analysis)
        .filter(
            Analysis.user_id == user.id
        )
        .order_by(
            Analysis.created_at.desc()
        )
        .all()
    )

    return {

        "analyses": [

            {
                "id": r.id,
                "resume_id": r.resume_id,
                "job_title": r.job_title,
                "company": r.company,
                "ats_score": r.ats_score,
                "created_at":
                    r.created_at.isoformat()
            }

            for r in records
        ]
    }


# ==================================================
# RESUME REWRITE
# ==================================================

@app.post("/resume/rewrite")
def resume_rewrite(

    resume_id: int = Form(...),

    job_description: str = Form(...),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    ),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id
        )
        .first()
    )

    if not resume:

        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    try:

        result = rewrite_resume(

            resume.extracted_text,

            job_description,

            provider,

            model_name
        )

        return {
            "success": True,
            "result": result
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ==================================================
# PROFESSIONAL RESUME
# ==================================================

@app.post("/resume/generate")
def generate_resume(

    resume_id: int = Form(...),

    job_description: str = Form(""),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    ),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id
        )
        .first()
    )

    if not resume:

        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    result = generate_professional_resume(

        resume.extracted_text,

        job_description,

        provider,

        model_name
    )

    return {
        "success": True,
        "result": result
    }


# ==================================================
# COVER LETTER
# ==================================================

@app.post("/cover-letter")
def cover_letter(

    resume_id: int = Form(...),

    company: str = Form(...),

    role: str = Form(...),

    job_description: str = Form(...),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    ),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id
        )
        .first()
    )

    if not resume:

        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    letter = generate_cover_letter(

        resume.extracted_text,

        job_description,

        company,

        role,

        provider,

        model_name
    )

    return {

        "success": True,

        "cover_letter": letter
    }


# ==================================================
# LINKEDIN
# ==================================================

@app.post("/linkedin")
def linkedin(

    resume_id: int = Form(...),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    ),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id
        )
        .first()
    )

    if not resume:

        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    result = optimize_linkedin(

        resume.extracted_text,

        provider,

        model_name
    )

    return {

        "success": True,

        "result": result
    }


# ==================================================
# JOB ROLES
# ==================================================

@app.post("/job-roles")
def job_roles(

    resume_id: int = Form(...),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    ),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id
        )
        .first()
    )

    if not resume:

        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    result = recommend_roles(

        resume.extracted_text,

        provider,

        model_name
    )

    return {

        "success": True,

        "result": result
    }


# ==================================================
# CAREER ROADMAP
# ==================================================

@app.post("/career-roadmap")
def roadmap(

    resume_id: int = Form(...),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    ),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id
        )
        .first()
    )

    if not resume:

        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    result = career_roadmap(

        resume.extracted_text,

        provider,

        model_name
    )

    return {

        "success": True,

        "result": result
    }


# ==================================================
# INTERVIEW QUESTION
# ==================================================

@app.post("/interview/question")
def interview_question(

    resume_id: int = Form(...),

    role: str = Form(...),

    interview_type: str = Form(
        "Technical"
    ),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    ),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id
        )
        .first()
    )

    if not resume:

        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    result = generate_interview_question(

        resume.extracted_text,

        role,

        interview_type,

        provider,

        model_name
    )

    return {

        "success": True,

        "result": result
    }


# ==================================================
# INTERVIEW EVALUATION
# ==================================================

@app.post("/interview/evaluate")
def interview_evaluate(

    question: str = Form(...),

    answer: str = Form(...),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    )
):

    result = evaluate_interview_answer(

        question,

        answer,

        provider,

        model_name
    )

    return {

        "success": True,

        "result": result
    }


# ==================================================
# CODING QUESTION
# ==================================================

@app.post("/coding/question")
def coding_question(

    resume_id: int = Form(...),

    role: str = Form(...),

    difficulty: str = Form(
        "Medium"
    ),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    ),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    resume = (
        db.query(Resume)
        .filter(
            Resume.id == resume_id,
            Resume.user_id == user.id
        )
        .first()
    )

    if not resume:

        raise HTTPException(
            status_code=404,
            detail="Resume not found."
        )

    result = generate_coding_question(

        resume.extracted_text,

        role,

        difficulty,

        provider,

        model_name
    )

    return {

        "success": True,

        "result": result
    }


# ==================================================
# CODE EVALUATION
# ==================================================

@app.post("/coding/evaluate")
def coding_evaluate(

    question: str = Form(...),

    code: str = Form(...),

    provider: str = Form("Groq"),

    model_name: str = Form(
        "llama-3.3-70b-versatile"
    )
):

    result = evaluate_code(

        question,

        code,

        provider,

        model_name
    )

    return {

        "success": True,

        "result": result
    }


# ==================================================
# APPLICATION TRACKER
# ==================================================

@app.post("/applications")
def create_application(

    company: str = Form(...),

    role: str = Form(...),

    location: str = Form(""),

    status: str = Form("Applied"),

    job_url: str = Form(""),

    notes: str = Form(""),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    application = JobApplication(

        user_id=user.id,

        company=company,

        role=role,

        location=location,

        status=status,

        job_url=job_url,

        notes=notes
    )

    db.add(
        application
    )

    db.commit()

    db.refresh(
        application
    )

    return {

        "success": True,

        "application": {

            "id":
                application.id,

            "company":
                application.company,

            "role":
                application.role,

            "status":
                application.status
        }
    }


@app.get("/applications")
def get_applications(

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    applications = (
        db.query(
            JobApplication
        )
        .filter(
            JobApplication.user_id ==
            user.id
        )
        .order_by(
            JobApplication.applied_date.desc()
        )
        .all()
    )

    return {

        "applications": [

            {

                "id": a.id,

                "company": a.company,

                "role": a.role,

                "location": a.location,

                "status": a.status,

                "job_url": a.job_url,

                "notes": a.notes,

                "applied_date":
                    a.applied_date.isoformat()

            }

            for a in applications
        ]
    }


@app.put("/applications/{application_id}")
def update_application(

    application_id: int,

    status: str = Form(...),

    notes: str = Form(""),

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    application = (
        db.query(
            JobApplication
        )
        .filter(
            JobApplication.id ==
                application_id,

            JobApplication.user_id ==
                user.id
        )
        .first()
    )

    if not application:

        raise HTTPException(
            status_code=404,
            detail="Application not found."
        )

    application.status = status

    application.notes = notes

    db.commit()

    return {
        "success": True
    }


# ==================================================
# PDF REPORT
# ==================================================

@app.get("/report/{analysis_id}")
def report(

    analysis_id: int,

    user: User = Depends(
        get_current_user
    ),

    db: Session = Depends(
        get_db
    )
):

    analysis = (
        db.query(Analysis)
        .filter(
            Analysis.id == analysis_id,
            Analysis.user_id == user.id
        )
        .first()
    )

    if not analysis:

        raise HTTPException(
            status_code=404,
            detail="Analysis not found."
        )

    result = json.loads(
        analysis.result
    )

    filename = (
        f"resume_report_"
        f"{analysis.id}.pdf"
    )

    path = os.path.join(
        REPORT_DIR,
        filename
    )

    create_report(
        result,
        path
    )

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=filename
    )


# ==================================================
# DOWNLOADABLE REWRITTEN / GENERATED RESUME PDF
# ==================================================

@app.post("/resume/pdf")
def resume_pdf(
    resume_content: str = Form(...),
    filename: str = Form("AI_Resume"),
    target_role: str = Form("ATS-Friendly Resume"),
    user: User = Depends(get_current_user),
):
    safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", filename).strip("_") or "AI_Resume"
    pdf_filename = f"{safe_name}.pdf"
    path = os.path.join(REPORT_DIR, f"{uuid.uuid4()}_{pdf_filename}")
    try:
        create_resume_pdf(resume_content, path, target_role or "ATS-Friendly Resume")
        return FileResponse(path, media_type="application/pdf", filename=pdf_filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not create resume PDF: {exc}")


# ==================================================
# LIVE JOB OPENINGS FOR FRESHERS
# ==================================================

@app.post("/jobs/recommend")
def recommend_jobs(
    resume_id: int = Form(...),
    role: str = Form(...),
    location: str = Form("India"),
    fresher_only: bool = Form(True),
    limit: int = Form(15),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    resume = db.query(Resume).filter(Resume.id == resume_id, Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return search_live_jobs(role, location, resume.extracted_text, fresher_only, max(1, min(limit, 25)))


@app.get("/jobs/status")
def jobs_status(user: User = Depends(get_current_user)):
    return {
        "provider": "Adzuna",
        "configured": bool(os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY")),
        "message": "Live job openings are enabled." if (os.getenv("ADZUNA_APP_ID") and os.getenv("ADZUNA_APP_KEY")) else "Add ADZUNA_APP_ID and ADZUNA_APP_KEY to enable live openings."
    }


# ==================================================
# RUN
# ==================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
