import os
import requests
import streamlit as st


# ============================================================
# CONFIGURATION
# ============================================================

def get_default_api_url():
    env_url = os.getenv("API_URL", "").strip()
    if env_url:
        return env_url.rstrip("/")
    try:
        secret_url = st.secrets["API_URL"]
        if secret_url:
            return str(secret_url).rstrip("/")
    except Exception:
        pass
    return "http://127.0.0.1:8000"


st.set_page_config(
    page_title="AI Resume Analyzer & Career Coach",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_URL = get_default_api_url()


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "token": None,
    "user": None,
    "resume_id": None,
    "last_analysis": None,
    "rewritten_resume": "",
    "generated_resume": "",
    "interview_question": None,
    "coding_question": None,
    "cv_content": "",
    "english_test": None,
    "english_result": None,
    "english_lesson": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# API HELPERS
# ============================================================

def auth_headers():
    if not st.session_state.token:
        return {}
    return {"Authorization": f"Bearer {st.session_state.token}"}


def api_request(method, endpoint, data=None, files=None, timeout=180):
    try:
        return requests.request(
            method,
            f"{API_URL}{endpoint}",
            headers=auth_headers(),
            data=data,
            files=files,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        st.error(f"Cannot reach backend: {exc}")
        return None


def api_error(response, fallback="Something went wrong."):
    if response is None:
        return fallback
    try:
        payload = response.json()
        return payload.get("detail", fallback)
    except Exception:
        return response.text[:1000] or fallback


def safe_number(value, default=0):
    try:
        return float(value)
    except Exception:
        return default


# ============================================================
# LOGIN / REGISTER
# ============================================================

if not st.session_state.token:
    st.markdown("# 🚀 AI Resume Analyzer & Career Coach")
    st.caption("A fresher-friendly AI platform for resumes, skills, interviews and job discovery.")

    login_tab, register_tab = st.tabs(["🔐 Sign in", "📝 Create account"])

    with login_tab:
        st.subheader("Welcome back")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")

        if st.button("Sign in", type="primary", use_container_width=True):
            response = api_request("POST", "/auth/login", data={"email": email, "password": password}, timeout=30)
            if response is not None and response.ok:
                data = response.json()
                st.session_state.token = data["token"]
                st.session_state.user = data["user"]
                st.rerun()
            elif response is not None:
                st.error(api_error(response, "Login failed."))

    with register_tab:
        st.subheader("Create your free account")
        name = st.text_input("Full Name", key="register_name")
        email = st.text_input("Email", key="register_email")
        password = st.text_input("Password", type="password", key="register_password")
        st.caption("Use at least 6 characters.")

        if st.button("Create account", type="primary", use_container_width=True):
            response = api_request(
                "POST",
                "/auth/register",
                data={"name": name, "email": email, "password": password},
                timeout=30,
            )
            if response is not None and response.ok:
                data = response.json()
                st.session_state.token = data["token"]
                st.session_state.user = data["user"]
                st.success("Account created successfully.")
                st.rerun()
            elif response is not None:
                st.error(api_error(response, "Registration failed."))

    st.stop()


# ============================================================
# SIDEBAR
# ============================================================

user = st.session_state.user or {}

st.sidebar.title("🚀 AI Career Coach")
st.sidebar.success(f"Welcome, {user.get('name', 'Candidate')}")

st.sidebar.subheader("⚙️ Settings")
backend_url = st.sidebar.text_input("Backend URL", value=API_URL).strip().rstrip("/")
if backend_url != API_URL:
    API_URL = backend_url

provider = st.sidebar.selectbox("AI Provider", ["Groq", "OpenAI"])

if provider == "Groq":
    model_name = st.sidebar.selectbox(
        "Model",
        ["openai/gpt-oss-120b", "openai/gpt-oss-20b"],
    )
else:
    model_name = st.sidebar.selectbox(
        "Model",
        ["gpt-4o-mini", "gpt-4.1-mini"],
    )

fresher_mode = st.sidebar.checkbox(
    "🎓 Fresher-friendly mode",
    value=True,
    help="Prioritizes beginner-friendly explanations, entry-level roles and learning guidance.",
)

if st.sidebar.button("Logout", use_container_width=True):
    st.session_state.token = None
    st.session_state.user = None
    st.rerun()


# ============================================================
# HEADER
# ============================================================

st.title("AI Resume Analyzer & Career Coach")
st.caption("Analyze → Improve → Learn → Find Jobs → Apply → Grow")


# ============================================================
# NAVIGATION
# ============================================================

tabs = st.tabs([
    "📄 Resumes",
    "🎯 ATS Analyzer",
    "✍️ Resume Writer",
    "📧 Cover Letter",
    "💼 LinkedIn",
    "🎯 Job Roles",
    "🔎 Job Openings",
    "🎤 Interview",
    "💻 Coding",
    "📋 Applications",
    "🗺️ Career Roadmap",
    "📝 CV Writer",
    "🗣️ English & Communication",
])


# ============================================================
# TAB 1 — RESUMES
# ============================================================

with tabs[0]:
    st.header("📄 My Resumes")
    st.write("Upload your current resume. PDF and DOCX are supported.")

    uploaded = st.file_uploader("Upload Resume", type=["pdf", "docx"], key="resume_upload")
    if st.button("Upload Resume", type="primary", use_container_width=True):
        if uploaded is None:
            st.warning("Please select a PDF or DOCX resume first.")
        else:
            response = api_request(
                "POST",
                "/resumes",
                files={"resume": (uploaded.name, uploaded.getvalue(), uploaded.type)},
            )
            if response is not None and response.ok:
                data = response.json()
                st.session_state.resume_id = data["resume_id"]
                st.success(f"Uploaded successfully. Resume ID: {data['resume_id']}")
                st.rerun()
            elif response is not None:
                st.error(api_error(response, "Resume upload failed."))

    response = api_request("GET", "/resumes", timeout=60)
    if response is not None and response.ok:
        resumes = response.json().get("resumes", [])
        if not resumes:
            st.info("No resumes uploaded yet.")
        else:
            st.subheader("Uploaded versions")
            for resume in resumes:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.write(f"📄 **{resume['filename']}** — ID {resume['id']}")
                    st.caption(resume.get("created_at", ""))
                with col2:
                    if st.button("Select", key=f"select_resume_{resume['id']}"):
                        st.session_state.resume_id = resume["id"]
                        st.rerun()

    if st.session_state.resume_id:
        st.success(f"Selected Resume ID: {st.session_state.resume_id}")

    st.info("💡 Tip for freshers: projects, internships, certifications, coursework and measurable project results are valuable when you do not have full-time experience.")


# ============================================================
# TAB 2 — ATS ANALYZER
# ============================================================

with tabs[1]:
    st.header("🎯 ATS & Skill-Gap Analyzer")

    resume_id = st.number_input(
        "Resume ID",
        min_value=1,
        value=int(st.session_state.resume_id or 1),
        key="ats_resume_id",
    )
    job_title = st.text_input("Target Job Title", key="ats_job_title")
    company = st.text_input("Company (optional)", key="ats_company")
    jd = st.text_area("Paste Job Description", height=280, key="ats_jd")

    if st.button("🚀 Analyze Resume", type="primary", use_container_width=True):
        if not jd.strip():
            st.warning("Paste the job description so the system can compare your resume with it.")
        else:
            with st.spinner("Analyzing your resume..."):
                response = api_request(
                    "POST",
                    "/analyze",
                    data={
                        "resume_id": resume_id,
                        "job_title": job_title,
                        "company": company,
                        "job_description": jd,
                        "provider": provider,
                        "model_name": model_name,
                    },
                )
            if response is not None and response.ok:
                payload = response.json()
                result = payload.get("result", {})
                st.session_state.last_analysis = result

                ats = result.get("ats_analysis", {})
                score = safe_number(ats.get("score"))
                st.metric("AI-Assisted ATS Guidance Score", f"{score:.0f}/100")
                st.progress(max(0.0, min(score, 100.0)) / 100.0)
                st.caption("This is a guidance score, not a guaranteed score from a company's proprietary ATS.")

                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("✅ Matching Skills")
                    for item in ats.get("matched_skills", []):
                        st.success(str(item))
                with c2:
                    st.subheader("❌ Missing Skills")
                    for item in ats.get("missing_skills", []):
                        st.error(str(item))

                st.subheader("💪 Strengths")
                for item in result.get("strengths", []):
                    st.write(f"• {item}")

                st.subheader("⚠️ Improvement Areas")
                for item in result.get("weaknesses", []):
                    st.write(f"• {item}")

                st.subheader("💡 Recommendations")
                for item in ats.get("recommendations", []):
                    st.write(f"• {item}")

                st.subheader("🎓 Fresher Advice")
                for item in result.get("fresher_advice", []):
                    st.info(item)

                analysis_id = payload.get("analysis_id")
                if analysis_id:
                    report = api_request("GET", f"/report/{analysis_id}", timeout=60)
                    if report is not None and report.ok:
                        st.download_button(
                            "📥 Download ATS Analysis PDF",
                            report.content,
                            file_name="ATS_Resume_Report.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
            elif response is not None:
                st.error(api_error(response, "Analysis failed."))


# ============================================================
# TAB 3 — RESUME WRITER
# ============================================================

with tabs[2]:
    st.header("✍️ AI Resume Writer")
    st.write("Rewrite your resume for a specific role without inventing experience.")

    resume_id = st.number_input(
        "Resume ID",
        min_value=1,
        value=int(st.session_state.resume_id or 1),
        key="writer_resume_id",
    )
    writer_jd = st.text_area("Target Job Description", height=240, key="writer_jd")

    if st.button("✨ Rewrite My Resume", type="primary", use_container_width=True):
        if not writer_jd.strip():
            st.warning("Add a target job description for better tailoring.")
        else:
            with st.spinner("Rewriting your resume..."):
                response = api_request(
                    "POST",
                    "/resume/rewrite",
                    data={
                        "resume_id": resume_id,
                        "job_description": writer_jd,
                        "provider": provider,
                        "model_name": model_name,
                    },
                )
            if response is not None and response.ok:
                result = response.json().get("result", {})
                rewritten = result.get("rewritten_resume", "")
                st.session_state.rewritten_resume = rewritten

                st.subheader("Professional Summary")
                st.write(result.get("summary", ""))
                st.subheader("Rewritten Resume")
                st.text_area("Editable Resume", rewritten, height=650, key="rewritten_editor")

                st.subheader("What Changed")
                for item in result.get("improvements", []):
                    st.write(f"✅ {item}")

                st.subheader("ATS Keywords Used")
                st.write(", ".join(result.get("ats_keywords_used", [])) or "None")
            elif response is not None:
                st.error(api_error(response, "Resume rewrite failed."))

    # Always use the latest editable text for PDF generation.
    current_rewritten = st.session_state.get("rewritten_resume", "")
    if current_rewritten:
        edited = st.text_area("Edit before downloading (optional)", current_rewritten, height=500, key="rewrite_pdf_editor")
        if st.button("📄 Create Downloadable Rewritten Resume PDF", use_container_width=True):
            pdf_response = api_request(
                "POST",
                "/resume/pdf",
                data={
                    "resume_content": edited,
                    "filename": "Rewritten_Resume",
                    "target_role": job_title if 'job_title' in locals() else "ATS-Friendly Resume",
                },
                timeout=60,
            )
            if pdf_response is not None and pdf_response.ok:
                st.download_button(
                    "⬇️ Download Rewritten Resume PDF",
                    pdf_response.content,
                    file_name="Rewritten_Resume.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            elif pdf_response is not None:
                st.error(api_error(pdf_response, "Could not create PDF."))

    st.divider()
    st.subheader("📄 Generate a Fresh ATS-Friendly Resume")
    if st.button("Generate Professional Resume", use_container_width=True):
        response = api_request(
            "POST",
            "/resume/generate",
            data={
                "resume_id": resume_id,
                "job_description": writer_jd,
                "provider": provider,
                "model_name": model_name,
            },
        )
        if response is not None and response.ok:
            result = response.json().get("result", {})
            generated = result.get("rewritten_resume", result.get("resume", ""))
            st.session_state.generated_resume = generated
        elif response is not None:
            st.error(api_error(response, "Resume generation failed."))

    if st.session_state.generated_resume:
        generated_edit = st.text_area(
            "Generated Resume",
            st.session_state.generated_resume,
            height=650,
            key="generated_editor",
        )
        if st.button("📄 Create Generated Resume PDF", use_container_width=True):
            pdf_response = api_request(
                "POST",
                "/resume/pdf",
                data={
                    "resume_content": generated_edit,
                    "filename": "Generated_ATS_Resume",
                    "target_role": "ATS-Friendly Resume",
                },
                timeout=60,
            )
            if pdf_response is not None and pdf_response.ok:
                st.download_button(
                    "⬇️ Download Generated Resume PDF",
                    pdf_response.content,
                    file_name="Generated_ATS_Resume.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            elif pdf_response is not None:
                st.error(api_error(pdf_response, "Could not create PDF."))


# ============================================================
# TAB 4 — COVER LETTER
# ============================================================

with tabs[3]:
    st.header("📧 AI Cover Letter")
    resume_id = st.number_input("Resume ID", min_value=1, value=int(st.session_state.resume_id or 1), key="cover_resume_id")
    cover_company = st.text_input("Company", key="cover_company")
    cover_role = st.text_input("Job Role", key="cover_role")
    cover_jd = st.text_area("Job Description", height=260, key="cover_jd")

    if st.button("Generate Cover Letter", type="primary", use_container_width=True):
        response = api_request(
            "POST",
            "/cover-letter",
            data={
                "resume_id": resume_id,
                "company": cover_company,
                "role": cover_role,
                "job_description": cover_jd,
                "provider": provider,
                "model_name": model_name,
            },
        )
        if response is not None and response.ok:
            st.text_area("Generated Cover Letter", response.json().get("cover_letter", ""), height=650)
        elif response is not None:
            st.error(api_error(response, "Cover letter generation failed."))


# ============================================================
# TAB 5 — LINKEDIN
# ============================================================

with tabs[4]:
    st.header("💼 LinkedIn Optimizer")
    resume_id = st.number_input("Resume ID", min_value=1, value=int(st.session_state.resume_id or 1), key="linkedin_resume_id")

    if st.button("Optimize LinkedIn Profile", type="primary", use_container_width=True):
        response = api_request(
            "POST",
            "/linkedin",
            data={"resume_id": resume_id, "provider": provider, "model_name": model_name},
        )
        if response is not None and response.ok:
            result = response.json().get("result", {})
            st.subheader("Headline")
            st.code(result.get("headline", ""))
            st.subheader("About")
            st.text_area("LinkedIn About", result.get("about", ""), height=350)
            st.subheader("Keywords")
            st.write(", ".join(result.get("keywords", [])))
            st.subheader("Improvements")
            for item in result.get("improvements", []):
                st.write(f"• {item}")
        elif response is not None:
            st.error(api_error(response, "LinkedIn optimization failed."))


# ============================================================
# TAB 6 — JOB ROLES
# ============================================================

with tabs[5]:
    st.header("🎯 Suitable Job Roles")
    resume_id = st.number_input("Resume ID", min_value=1, value=int(st.session_state.resume_id or 1), key="roles_resume_id")

    if st.button("Find Suitable Roles", type="primary", use_container_width=True):
        response = api_request(
            "POST",
            "/job-roles",
            data={"resume_id": resume_id, "provider": provider, "model_name": model_name},
        )
        if response is not None and response.ok:
            roles = response.json().get("result", {}).get("roles", [])
            if not roles:
                st.info("No roles were returned. Try a more detailed resume.")
            for item in roles:
                with st.container(border=True):
                    st.subheader(f"🎯 {item.get('role', 'Role')}")
                    st.metric("Estimated Match", f"{item.get('match_score', 0)}%")
                    st.write(item.get("reason", ""))
                    st.write("**Required skills:** " + ", ".join(item.get("required_skills", [])))
                    if fresher_mode and item.get("starter_projects"):
                        st.write("**Good starter projects:** " + ", ".join(item.get("starter_projects", [])))
        elif response is not None:
            st.error(api_error(response, "Could not recommend roles."))


# ============================================================
# TAB 7 — LIVE JOB OPENINGS
# ============================================================

with tabs[6]:
    st.header("🔎 Live Job Openings for Your Profile")
    st.write("Find current openings that match your target role and resume skills.")
    st.caption("Live openings are provided through the configured job-search provider; availability can change at any time.")

    resume_id = st.number_input("Resume ID", min_value=1, value=int(st.session_state.resume_id or 1), key="jobs_resume_id")
    job_role = st.text_input("Role to search", value="Software Engineer", key="jobs_role")
    job_location = st.text_input("Location", value="India", key="jobs_location")
    fresher_only = st.checkbox("🎓 Show fresher / entry-level friendly openings first", value=fresher_mode)
    limit = st.slider("Number of openings", 5, 25, 15)

    status_response = api_request("GET", "/jobs/status", timeout=30)
    if status_response is not None and status_response.ok:
        status = status_response.json()
        if status.get("configured"):
            st.success("Live job search is enabled.")
        else:
            st.warning(status.get("message", "Live job search is not configured."))
            st.code("ADZUNA_APP_ID=your_app_id\nADZUNA_APP_KEY=your_app_key")

    if st.button("🔍 Find Matching Openings", type="primary", use_container_width=True):
        response = api_request(
            "POST",
            "/jobs/recommend",
            data={
                "resume_id": resume_id,
                "role": job_role,
                "location": job_location,
                "fresher_only": str(fresher_only).lower(),
                "limit": limit,
            },
            timeout=60,
        )
        if response is not None and response.ok:
            data = response.json()
            jobs = data.get("jobs", [])
            if not jobs:
                st.info(data.get("message", "No matching openings were found."))
            else:
                st.success(f"Found {len(jobs)} matching openings from {data.get('source', 'job provider')}.")
                for job in jobs:
                    with st.container(border=True):
                        c1, c2 = st.columns([4, 1])
                        with c1:
                            st.subheader(job.get("title", "Job Opening"))
                            st.write(f"🏢 **{job.get('company', 'Company')}**")
                            st.write(f"📍 {job.get('location', job_location)}")
                            if job.get("contract_type") or job.get("contract_time"):
                                st.caption(f"{job.get('contract_type', '')} {job.get('contract_time', '')}".strip())
                        with c2:
                            st.metric("Fit", f"{job.get('suitability_score', 0)}%")
                        if job.get("matched_skills"):
                            st.write("**Your matching skills:** " + ", ".join(job["matched_skills"]))
                        desc = job.get("description", "")
                        if desc:
                            st.write(desc[:700] + ("…" if len(desc) > 700 else ""))
                        if job.get("url"):
                            st.link_button("Apply / View Opening ↗", job["url"], use_container_width=False)
        elif response is not None:
            st.error(api_error(response, "Live job search failed."))


# ============================================================
# TAB 8 — INTERVIEW
# ============================================================

with tabs[7]:
    st.header("🎤 Mock Interview + Learning Answers")
    st.write("Practice first, then reveal the model answer and explanation so you can learn topics you do not know.")

    resume_id = st.number_input("Resume ID", min_value=1, value=int(st.session_state.resume_id or 1), key="interview_resume_id")
    interview_role = st.text_input("Target Role", value="Software Engineer", key="interview_role")
    interview_type = st.selectbox("Interview Type", ["HR", "Technical", "Behavioral"], key="interview_type")

    if st.button("🎤 Generate Mock Question", type="primary", use_container_width=True):
        response = api_request(
            "POST",
            "/interview/question",
            data={
                "resume_id": resume_id,
                "role": interview_role,
                "interview_type": interview_type,
                "provider": provider,
                "model_name": model_name,
            },
        )
        if response is not None and response.ok:
            st.session_state.interview_question = response.json().get("result", {})
        elif response is not None:
            st.error(api_error(response, "Could not generate interview question."))

    question = st.session_state.get("interview_question")
    if question:
        st.subheader(question.get("question", "Interview question"))
        st.caption(f"Topic: {question.get('topic', 'General')} · Difficulty: {question.get('difficulty', 'Medium')}")
        st.write("**Why this is asked:**", question.get("why_this_is_asked", ""))

        answer = st.text_area("Your answer", height=220, key="mock_interview_answer")
        if st.button("Evaluate My Answer", use_container_width=True):
            response = api_request(
                "POST",
                "/interview/evaluate",
                data={
                    "question": question.get("question", ""),
                    "answer": answer,
                    "provider": provider,
                    "model_name": model_name,
                },
            )
            if response is not None and response.ok:
                result = response.json().get("result", {})
                c1, c2, c3 = st.columns(3)
                c1.metric("Overall", f"{result.get('score', 0)}/100")
                c2.metric("Communication", f"{result.get('communication', 0)}/100")
                c3.metric("Technical", f"{result.get('technical_accuracy', 0)}/100")
                st.subheader("Strengths")
                for item in result.get("strengths", []):
                    st.write(f"✅ {item}")
                st.subheader("How to improve")
                for item in result.get("weaknesses", []):
                    st.write(f"⚠️ {item}")
                st.subheader("Better answer")
                st.write(result.get("better_answer", ""))
                st.subheader("📚 What to learn")
                for item in result.get("what_to_learn", []):
                    st.info(item)
                st.write("**Teaching explanation:**", result.get("teaching_explanation", ""))
            elif response is not None:
                st.error(api_error(response, "Answer evaluation failed."))

        with st.expander("📖 Show model answer and learn the concept"):
            st.write("**Model answer:**")
            st.write(question.get("model_answer", ""))
            st.write("**Explanation:**")
            st.write(question.get("explanation", ""))
            st.write("**Key points to remember:**")
            for item in question.get("key_points_to_remember", []):
                st.write(f"• {item}")
            st.write("**Common mistakes:**")
            for item in question.get("common_mistakes", []):
                st.write(f"• {item}")
            if question.get("follow_up_question"):
                st.write("**Follow-up:**", question["follow_up_question"])


# ============================================================
# TAB 9 — CODING
# ============================================================

with tabs[8]:
    st.header("💻 Coding Interview + Learning Solution")
    st.write("Try the problem yourself. The correct reference solution is also provided for learning.")

    resume_id = st.number_input("Resume ID", min_value=1, value=int(st.session_state.resume_id or 1), key="coding_resume_id")
    coding_role = st.text_input("Coding Role", value="Python Developer", key="coding_role")
    difficulty = st.selectbox("Difficulty", ["Easy", "Medium", "Hard"], key="coding_difficulty")

    if st.button("💻 Generate Coding Problem", type="primary", use_container_width=True):
        response = api_request(
            "POST",
            "/coding/question",
            data={
                "resume_id": resume_id,
                "role": coding_role,
                "difficulty": difficulty,
                "provider": provider,
                "model_name": model_name,
            },
        )
        if response is not None and response.ok:
            st.session_state.coding_question = response.json().get("result", {})
        elif response is not None:
            st.error(api_error(response, "Could not generate coding question."))

    problem = st.session_state.get("coding_question")
    if problem:
        st.subheader(problem.get("title", "Coding Problem"))
        st.caption(f"Topic: {problem.get('topic', 'Programming')} · Difficulty: {difficulty}")
        st.write(problem.get("question", ""))
        if problem.get("input_format"):
            st.write("**Input:**", problem["input_format"])
        if problem.get("output_format"):
            st.write("**Output:**", problem["output_format"])
        if problem.get("examples"):
            st.write("**Examples:**")
            for ex in problem["examples"]:
                st.code(str(ex))
        for hint in problem.get("hints", []):
            st.info(f"Hint: {hint}")

        code = st.text_area("Your solution", height=350, placeholder="def solution(...):", key="candidate_code")
        if st.button("Evaluate Code", use_container_width=True):
            response = api_request(
                "POST",
                "/coding/evaluate",
                data={
                    "question": problem.get("question", ""),
                    "code": code,
                    "provider": provider,
                    "model_name": model_name,
                },
            )
            if response is not None and response.ok:
                result = response.json().get("result", {})
                c1, c2, c3 = st.columns(3)
                c1.metric("Score", f"{result.get('score', 0)}/100")
                c2.metric("Correctness", f"{result.get('correctness', 0)}/100")
                c3.metric("Code Quality", f"{result.get('code_quality', 0)}/100")
                for bug in result.get("bugs", []):
                    st.error(str(bug))
                for item in result.get("improvements", []):
                    st.write(f"💡 {item}")
                with st.expander("📚 Learn the correct solution"):
                    st.code(result.get("reference_solution", ""), language="python")
                    st.write(result.get("solution_explanation", ""))
                    st.write("**Time complexity:**", result.get("time_complexity", ""))
                    st.write("**Space complexity:**", result.get("space_complexity", ""))
                    for item in result.get("what_to_learn", []):
                        st.info(item)
            elif response is not None:
                st.error(api_error(response, "Code evaluation failed."))

        with st.expander("📖 Show reference solution before submitting"):
            st.code(problem.get("reference_solution", ""), language="python")
            st.write(problem.get("solution_explanation", ""))
            st.write("**Complexity:**", problem.get("time_complexity", ""), "/", problem.get("space_complexity", ""))
            for item in problem.get("common_mistakes", []):
                st.write(f"• {item}")


# ============================================================
# TAB 10 — APPLICATION TRACKER
# ============================================================

with tabs[9]:
    st.header("📋 Job Application Tracker")

    with st.form("application_form"):
        app_company = st.text_input("Company")
        app_role = st.text_input("Role")
        app_location = st.text_input("Location")
        app_status = st.selectbox("Status", ["Saved", "Applied", "Assessment", "Interview", "Offer", "Rejected"])
        app_url = st.text_input("Job URL")
        app_notes = st.text_area("Notes")
        submitted = st.form_submit_button("Add Application", use_container_width=True)

        if submitted:
            response = api_request(
                "POST",
                "/applications",
                data={
                    "company": app_company,
                    "role": app_role,
                    "location": app_location,
                    "status": app_status,
                    "job_url": app_url,
                    "notes": app_notes,
                },
            )
            if response is not None and response.ok:
                st.success("Application added.")
                st.rerun()
            elif response is not None:
                st.error(api_error(response, "Could not add application."))

    response = api_request("GET", "/applications", timeout=60)
    if response is not None and response.ok:
        applications = response.json().get("applications", [])
        if not applications:
            st.info("No applications tracked yet. Add jobs from the Live Job Openings tab.")
        for item in applications:
            with st.container(border=True):
                st.subheader(f"🏢 {item['company']} — {item['role']}")
                st.write(f"📍 {item.get('location', '')}")
                st.write(f"Current status: **{item.get('status', '')}**")
                if item.get("job_url"):
                    st.link_button("Open Job", item["job_url"])
                st.caption(f"Added: {item.get('applied_date', '')}")
                st.write(item.get("notes", ""))

                new_status = st.selectbox(
                    "Update status",
                    ["Saved", "Applied", "Assessment", "Interview", "Offer", "Rejected"],
                    index=["Saved", "Applied", "Assessment", "Interview", "Offer", "Rejected"].index(item.get("status", "Saved")) if item.get("status") in ["Saved", "Applied", "Assessment", "Interview", "Offer", "Rejected"] else 0,
                    key=f"status_{item['id']}",
                )
                if st.button("Update", key=f"update_{item['id']}"):
                    update = api_request(
                        "PUT",
                        f"/applications/{item['id']}",
                        data={"status": new_status, "notes": item.get("notes", "")},
                    )
                    if update is not None and update.ok:
                        st.success("Updated.")
                        st.rerun()
                    elif update is not None:
                        st.error(api_error(update, "Update failed."))


# ============================================================
# TAB 11 — CAREER ROADMAP
# ============================================================

with tabs[10]:
    st.header("🗺️ Personalized 90-Day Career Roadmap")
    resume_id = st.number_input("Resume ID", min_value=1, value=int(st.session_state.resume_id or 1), key="roadmap_resume_id")

    if st.button("Generate Career Roadmap", type="primary", use_container_width=True):
        response = api_request(
            "POST",
            "/career-roadmap",
            data={"resume_id": resume_id, "provider": provider, "model_name": model_name},
        )
        if response is not None and response.ok:
            result = response.json().get("result", {})
            st.subheader("Current Level")
            st.info(result.get("current_level", ""))
            st.subheader("Target Roles")
            for item in result.get("target_roles", []):
                st.write(f"🎯 {item}")
            st.subheader("Skills to Learn")
            for item in result.get("skills_to_learn", []):
                st.write(f"📚 {item}")

            c1, c2, c3 = st.columns(3)
            with c1:
                st.subheader("Days 1–30")
                for item in result.get("days_30", []):
                    st.write(f"• {item}")
            with c2:
                st.subheader("Days 31–60")
                for item in result.get("days_60", []):
                    st.write(f"• {item}")
            with c3:
                st.subheader("Days 61–90")
                for item in result.get("days_90", []):
                    st.write(f"• {item}")

            if result.get("portfolio_actions"):
                st.subheader("Portfolio Actions")
                for item in result["portfolio_actions"]:
                    st.write(f"🚀 {item}")

            if result.get("application_strategy"):
                st.subheader("Application Strategy")
                for item in result["application_strategy"]:
                    st.write(f"📌 {item}")
        elif response is not None:
            st.error(api_error(response, "Could not generate roadmap."))


# ============================================================
# TAB 12 — CV WRITER
# ============================================================

with tabs[11]:
    st.header("📝 Professional CV Writer")
    st.write("Create a polished CV from your uploaded resume, tailor it to a target role, edit it and download it as a PDF.")
    st.caption("Designed for students and freshers. The AI is instructed not to invent experience, qualifications or achievements.")

    cv_resume_id = st.number_input(
        "Resume ID", min_value=1, value=int(st.session_state.resume_id or 1), key="cv_resume_id"
    )
    cv_role = st.text_input("Target Role", value="Software Engineer", key="cv_role")
    cv_jd = st.text_area("Job Description (optional but recommended)", height=220, key="cv_jd")

    if st.button("✨ Write My Professional CV", type="primary", use_container_width=True):
        response = api_request(
            "POST",
            "/cv/write",
            data={
                "resume_id": cv_resume_id,
                "target_role": cv_role,
                "job_description": cv_jd,
                "provider": provider,
                "model_name": model_name,
            },
            timeout=180,
        )
        if response is not None and response.ok:
            result = response.json().get("result", {})
            st.session_state.cv_content = result.get("cv", "")
            st.subheader("Profile Summary")
            st.write(result.get("profile_summary", ""))
            if result.get("improvements"):
                st.subheader("What the CV improved")
                for item in result["improvements"]:
                    st.write(f"✅ {item}")
            if result.get("keywords_used"):
                st.write("**Keywords used:** " + ", ".join(result["keywords_used"]))
        elif response is not None:
            st.error(api_error(response, "CV generation failed."))

    cv_content = st.session_state.get("cv_content", "")
    if cv_content:
        edited_cv = st.text_area("Edit your CV before downloading", cv_content, height=700, key="cv_editor")
        if st.button("📄 Create CV PDF", type="primary", use_container_width=True):
            response = api_request(
                "POST",
                "/cv/pdf",
                data={
                    "cv_content": edited_cv,
                    "filename": "Professional_CV",
                    "target_role": cv_role or "Professional CV",
                },
                timeout=60,
            )
            if response is not None and response.ok:
                st.download_button(
                    "⬇️ Download Professional CV PDF",
                    response.content,
                    file_name="Professional_CV.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            elif response is not None:
                st.error(api_error(response, "Could not create CV PDF."))

        st.info("💡 Tip: Keep the final CV truthful. Add measurable results only when you can support them.")


# ============================================================
# TAB 13 — ENGLISH & COMMUNICATION
# ============================================================

with tabs[12]:
    st.header("🗣️ English & Communication Test + Learning")
    st.write("Practice English, workplace communication and interview language. Take a short test, review mistakes and study targeted lessons.")

    test_tab, lesson_tab = st.tabs(["📝 Take Test", "📚 Learn & Practice"])

    with test_tab:
        level = st.selectbox("Your current level", ["Beginner", "Elementary", "Intermediate", "Upper-Intermediate", "Advanced"], index=2, key="english_level")
        focus = st.selectbox(
            "Test focus",
            [
                "Grammar and workplace communication",
                "Vocabulary and professional English",
                "Interview communication",
                "Email and business communication",
                "Mixed English assessment",
            ],
            key="english_focus",
        )

        if st.button("📝 Start English Test", type="primary", use_container_width=True):
            response = api_request(
                "POST",
                "/english/test",
                data={
                    "level": level,
                    "focus": focus,
                    "provider": provider,
                    "model_name": model_name,
                },
                timeout=180,
            )
            if response is not None and response.ok:
                st.session_state.english_test = response.json().get("result", {})
                st.session_state.english_result = None
            elif response is not None:
                st.error(api_error(response, "Could not generate the English test."))

        test = st.session_state.get("english_test")
        if test:
            st.subheader(test.get("title", "English & Communication Assessment"))
            questions = test.get("questions", [])
            answers = {}
            for q in questions:
                qid = str(q.get("id"))
                st.markdown(f"### Q{q.get('id')}. {q.get('question', '')}")
                options = q.get("options") or []
                if options:
                    answers[qid] = st.radio("Choose an answer", options, key=f"english_answer_{qid}")
                else:
                    answers[qid] = st.text_input("Your answer", key=f"english_answer_{qid}")

            if st.button("✅ Submit English Test", use_container_width=True):
                response = api_request(
                    "POST",
                    "/english/evaluate",
                    data={
                        "questions_json": __import__("json").dumps(questions),
                        "answers_json": __import__("json").dumps(answers),
                        "provider": provider,
                        "model_name": model_name,
                    },
                    timeout=180,
                )
                if response is not None and response.ok:
                    st.session_state.english_result = response.json().get("result", {})
                elif response is not None:
                    st.error(api_error(response, "English test evaluation failed."))

            result = st.session_state.get("english_result")
            if result:
                c1, c2, c3 = st.columns(3)
                c1.metric("Score", f"{result.get('score', 0)}%")
                c2.metric("Correct", f"{result.get('correct', 0)}/{result.get('total', len(questions))}")
                c3.metric("Estimated Level", result.get("level_estimate", "-"))

                st.subheader("💪 Your Strengths")
                for item in result.get("strengths", []):
                    st.success(str(item))

                st.subheader("📌 Mistakes & Explanations")
                for item in result.get("mistakes", []):
                    st.error(f"Q{item.get('question_id')}: Your answer — {item.get('your_answer', '')}")
                    st.write(f"**Correct:** {item.get('correct_answer', '')}")
                    st.write(item.get("explanation", ""))

                st.subheader("🗣️ Communication Feedback")
                st.write(result.get("communication_feedback", ""))
                st.subheader("📚 What to Learn Next")
                for item in result.get("what_to_learn", []):
                    st.info(str(item))
                st.subheader("📅 Practice Plan")
                for item in result.get("practice_plan", []):
                    st.write(f"• {item}")

            with st.expander("🔍 Reveal correct answers and learning points"):
                for q in questions:
                    st.write(f"**Q{q.get('id')}:** {q.get('correct_answer', '')}")
                    st.write(q.get("explanation", ""))
                    if q.get("learning_point"):
                        st.info(q["learning_point"])

    with lesson_tab:
        lesson_topic = st.selectbox(
            "Choose a learning topic",
            [
                "Grammar basics",
                "Tenses",
                "Articles and prepositions",
                "Vocabulary for interviews",
                "Professional email writing",
                "Speaking confidently in interviews",
                "Group discussion communication",
                "Workplace conversations",
                "Common English mistakes",
            ],
            key="lesson_topic",
        )
        lesson_level = st.selectbox("Learning level", ["Beginner", "Elementary", "Intermediate", "Upper-Intermediate", "Advanced"], index=2, key="lesson_level")
        lesson_goal = st.text_input("Your goal", value="Speak confidently in job interviews and workplace conversations", key="lesson_goal")

        if st.button("📚 Teach Me This Topic", type="primary", use_container_width=True):
            response = api_request(
                "POST",
                "/english/lesson",
                data={
                    "topic": lesson_topic,
                    "level": lesson_level,
                    "goal": lesson_goal,
                    "provider": provider,
                    "model_name": model_name,
                },
                timeout=180,
            )
            if response is not None and response.ok:
                st.session_state.english_lesson = response.json().get("result", {})
            elif response is not None:
                st.error(api_error(response, "Could not generate the lesson."))

        lesson = st.session_state.get("english_lesson")
        if lesson:
            st.subheader(lesson.get("topic", lesson_topic))
            st.write(lesson.get("explanation", ""))
            if lesson.get("rules"):
                st.subheader("📌 Rules")
                for item in lesson["rules"]:
                    st.write(f"• {item}")
            if lesson.get("good_examples"):
                st.subheader("✅ Good Examples")
                for item in lesson["good_examples"]:
                    st.success(str(item))
            if lesson.get("common_mistakes"):
                st.subheader("⚠️ Common Mistakes")
                for item in lesson["common_mistakes"]:
                    st.warning(str(item))
            if lesson.get("workplace_phrases"):
                st.subheader("💼 Workplace Phrases")
                for item in lesson["workplace_phrases"]:
                    st.info(str(item))
            if lesson.get("practice_questions"):
                st.subheader("✏️ Practice")
                for i, item in enumerate(lesson["practice_questions"], 1):
                    st.write(f"{i}. {item}")
            if lesson.get("answers"):
                with st.expander("Show practice answers"):
                    for item in lesson["answers"]:
                        st.write(f"• {item}")
            st.subheader("⏱️ Daily Practice")
            st.write(lesson.get("daily_practice", ""))
