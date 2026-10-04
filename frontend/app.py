import requests
import streamlit as st

st.set_page_config(page_title="CareerPilot AI", page_icon="🚀", layout="wide", initial_sidebar_state="expanded")

# ---------------- THEME ----------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
[data-testid="stAppViewContainer"] { background: #f6f8fc; }
[data-testid="stSidebar"] { background: #111827; }
[data-testid="stSidebar"] * { color: #f9fafb !important; }
.hero { padding: 2.2rem 2.4rem; border-radius: 24px; background: linear-gradient(135deg,#111827,#1f3a5f); color:white; margin-bottom:1.2rem; box-shadow:0 15px 35px rgba(17,24,39,.15); }
.hero h1 { font-size:2.3rem; margin:0 0 .5rem 0; }
.hero p { color:#dbeafe; margin:0; font-size:1rem; }
.card { background:white; padding:1.2rem; border-radius:18px; border:1px solid #e5e7eb; box-shadow:0 6px 18px rgba(15,23,42,.05); margin-bottom:1rem; }
.small { color:#64748b; font-size:.88rem; }
div.stButton > button { border-radius:12px; font-weight:600; min-height:2.6rem; }
div[data-testid="stMetric"] { background:white; border:1px solid #e5e7eb; padding:1rem; border-radius:16px; }
</style>
""", unsafe_allow_html=True)

API_URL = st.sidebar.text_input(
    "Backend URL",
    value=st.secrets.get("API_URL", "http://127.0.0.1:8000https://your-backend-name.onrender.com")
).rstrip("/")

for k,v in {"token":None,"user":None,"resume_id":None,"question":None,"coding":None}.items():
    if k not in st.session_state: st.session_state[k]=v

def api_error(resp):
    try: return resp.json().get("detail", resp.text)
    except Exception: return resp.text or f"HTTP {resp.status_code}"

def headers():
    return {"Authorization":f"Bearer {st.session_state.token}"} if st.session_state.token else {}

def post(endpoint, data=None, files=None, timeout=180):
    return requests.post(API_URL+endpoint, headers=headers(), data=data, files=files, timeout=timeout)

def get(endpoint, timeout=60):
    return requests.get(API_URL+endpoint, headers=headers(), timeout=timeout)

def put(endpoint, data=None):
    return requests.put(API_URL+endpoint, headers=headers(), data=data, timeout=60)

def delete(endpoint):
    return requests.delete(API_URL+endpoint, headers=headers(), timeout=60)

# ---------------- AUTH ----------------
if not st.session_state.token:
    st.markdown("""<div class="hero"><h1>🚀 CareerPilot AI</h1><p>AI Resume Analyzer • Career Coach • Interview Simulator</p></div>""", unsafe_allow_html=True)
    a,b=st.columns([1.1,1])
    with a:
        st.markdown('<div class="card"><h3>Build a stronger career profile</h3><p class="small">Upload your resume, compare it with jobs, improve your content and practice interviews with AI.</p></div>', unsafe_allow_html=True)
    with b:
        login,register=st.tabs(["Sign in","Create account"])
        with login:
            email=st.text_input("Email", key="login_email")
            password=st.text_input("Password", type="password", key="login_password")
            if st.button("Sign in", use_container_width=True):
                try:
                    r=requests.post(API_URL+"/auth/login",data={"email":email,"password":password},timeout=30)
                    if r.ok:
                        d=r.json(); st.session_state.token=d["token"]; st.session_state.user=d["user"]; st.rerun()
                    else: st.error(api_error(r))
                except requests.RequestException as e: st.error(f"Cannot reach backend: {e}")
        with register:
            name=st.text_input("Full name", key="reg_name")
            email=st.text_input("Email", key="reg_email")
            password=st.text_input("Password (6+ characters)", type="password", key="reg_password")
            if st.button("Create account", use_container_width=True):
                try:
                    r=requests.post(API_URL+"/auth/register",data={"name":name,"email":email,"password":password},timeout=30)
                    if r.ok:
                        d=r.json(); st.session_state.token=d["token"]; st.session_state.user=d["user"]; st.rerun()
                    else: st.error(api_error(r))
                except requests.RequestException as e: st.error(f"Cannot reach backend: {e}")
    st.stop()

# ---------------- SIDEBAR ----------------
st.sidebar.markdown("## 🚀 CareerPilot AI")
st.sidebar.success(f"Hi, {st.session_state.user['name']}")
provider=st.sidebar.selectbox("AI Provider",["Groq","OpenAI"])
if provider=="Groq":
    model=st.sidebar.selectbox("Model",["openai/gpt-oss-120b","llama-3.1-8b-instant"])
else:
    model=st.sidebar.selectbox("Model",["gpt-4o-mini","gpt-4.1-mini"])
if st.sidebar.button("Log out", use_container_width=True):
    for k in ["token","user","resume_id","question","coding"]: st.session_state[k]=None
    st.rerun()

# ---------------- HEADER ----------------
st.markdown(f"""<div class="hero"><h1>Welcome back, {st.session_state.user['name']} 👋</h1>
<p>Your AI-powered workspace for resumes, job applications and interview preparation.</p></div>""", unsafe_allow_html=True)

tabs=st.tabs(["📊 Dashboard","📄 Resumes","🎯 ATS","✍️ Writer","📧 Cover Letter","💼 LinkedIn","🎯 Roles","🎤 Interview","💻 Coding","📋 Applications","🗺️ Roadmap"])

# ---------------- DASHBOARD ----------------
with tabs[0]:
    try:
        rr=get("/resumes"); ar=get("/analyses"); jr=get("/applications")
        resumes=rr.json().get("resumes",[]) if rr.ok else []
        analyses=ar.json().get("analyses",[]) if ar.ok else []
        apps=jr.json().get("applications",[]) if jr.ok else []
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Resumes",len(resumes)); c2.metric("Analyses",len(analyses)); c3.metric("Applications",len(apps))
        avg=sum(float(x["ats_score"]) for x in analyses)/len(analyses) if analyses else 0
        c4.metric("Avg ATS Score",f"{avg:.0f}/100")
        st.subheader("Recent activity")
        if analyses:
            st.dataframe(analyses[:8],use_container_width=True,hide_index=True)
        else: st.info("Upload a resume and run your first ATS analysis.")
    except requests.RequestException as e: st.error(f"Backend unavailable: {e}")

# ---------------- RESUMES ----------------
with tabs[1]:
    st.header("📄 Resume Library")
    f=st.file_uploader("Upload PDF or DOCX",type=["pdf","docx"])
    if st.button("Upload resume",use_container_width=True):
        if not f: st.warning("Choose a PDF or DOCX first.")
        else:
            try:
                r=post("/resumes",files={"resume":(f.name,f.getvalue(),f.type)})
                if r.ok: st.success("Resume uploaded."); st.rerun()
                else: st.error(api_error(r))
            except requests.RequestException as e: st.error(str(e))
    try:
        data=get("/resumes").json().get("resumes",[])
        if data:
            for x in data:
                c1,c2=st.columns([5,1])
                c1.write(f"**{x['filename']}**  ·  ID {x['id']}  ·  {x['created_at'][:10]}")
                if c2.button("Select",key=f"sel{x['id']}"): st.session_state.resume_id=x["id"]; st.rerun()
            if st.session_state.resume_id: st.success(f"Selected Resume ID: {st.session_state.resume_id}")
        else: st.info("No resumes yet.")
    except Exception as e: st.error(str(e))

def resume_selector(key):
    default=st.session_state.resume_id or 1
    return st.number_input("Resume ID",min_value=1,value=default,key=key)

# ---------------- ATS ----------------
with tabs[2]:
    st.header("🎯 ATS Resume Analyzer")
    rid=resume_selector("ats_rid")
    job=st.text_input("Target job title")
    company=st.text_input("Company")
    jd=st.text_area("Paste job description",height=240)
    if st.button("Analyze resume",use_container_width=True):
        try:
            r=post("/analyze",{"resume_id":rid,"job_title":job,"company":company,"job_description":jd,"provider":provider,"model_name":model})
            if r.ok:
                d=r.json(); result=d["result"]; ats=result.get("ats_analysis",{}); score=float(ats.get("score",0))
                c1,c2,c3=st.columns(3); c1.metric("ATS Score",f"{score:.0f}/100"); c2.metric("Matched",len(ats.get("matched_skills",[]))); c3.metric("Missing",len(ats.get("missing_skills",[])))
                st.progress(max(0,min(100,score))/100)
                x,y=st.columns(2)
                with x:
                    st.subheader("Matched skills")
                    for v in ats.get("matched_skills",[]): st.success(str(v))
                with y:
                    st.subheader("Missing skills")
                    for v in ats.get("missing_skills",[]): st.error(str(v))
                st.subheader("Strengths"); [st.write("✅ "+str(v)) for v in result.get("strengths",[])]
                st.subheader("Recommendations"); [st.write("💡 "+str(v)) for v in ats.get("recommendations",[])]
                report=requests.get(API_URL+f"/report/{d['analysis_id']}",headers=headers(),timeout=60)
                if report.ok: st.download_button("📥 Download PDF report",report.content,"ATS_Report.pdf","application/pdf")
            else: st.error(api_error(r))
        except requests.RequestException as e: st.error(str(e))

# ---------------- WRITER ----------------
with tabs[3]:
    st.header("✍️ AI Resume Writer")
    rid=resume_selector("writer_rid"); jd=st.text_area("Target job description",height=220,key="writer_jd")
    c1,c2=st.columns(2)
    with c1:
        if st.button("Rewrite resume",use_container_width=True):
            try:
                r=post("/resume/rewrite",{"resume_id":rid,"job_description":jd,"provider":provider,"model_name":model})
                if r.ok:
                    d=r.json()["result"]; st.subheader("Professional summary"); st.write(d.get("summary","")); st.subheader("Rewritten resume"); st.text_area("Copy",d.get("rewritten_resume",""),height=520)
                    st.subheader("Improvements"); [st.write("✓ "+str(x)) for x in d.get("improvements",[])]
                else: st.error(api_error(r))
            except Exception as e: st.error(str(e))
    with c2:
        if st.button("Generate ATS-friendly resume",use_container_width=True):
            try:
                r=post("/resume/generate",{"resume_id":rid,"job_description":jd,"provider":provider,"model_name":model})
                if r.ok: st.text_area("Generated resume",r.json()["result"].get("resume",""),height=620)
                else: st.error(api_error(r))
            except Exception as e: st.error(str(e))

# ---------------- COVER ----------------
with tabs[4]:
    st.header("📧 Cover Letter")
    rid=resume_selector("cover_rid"); company=st.text_input("Company",key="cover_company"); role=st.text_input("Role",key="cover_role"); jd=st.text_area("Job description",height=220,key="cover_jd")
    if st.button("Generate cover letter",use_container_width=True):
        try:
            r=post("/cover-letter",{"resume_id":rid,"company":company,"role":role,"job_description":jd,"provider":provider,"model_name":model})
            if r.ok: st.text_area("Cover letter",r.json()["cover_letter"],height=600)
            else: st.error(api_error(r))
        except Exception as e: st.error(str(e))

# ---------------- LINKEDIN ----------------
with tabs[5]:
    st.header("💼 LinkedIn Optimizer")
    rid=resume_selector("li_rid")
    if st.button("Optimize profile",use_container_width=True):
        try:
            r=post("/linkedin",{"resume_id":rid,"provider":provider,"model_name":model})
            if r.ok:
                d=r.json()["result"]; st.subheader("Headline"); st.code(d.get("headline","")); st.subheader("About"); st.text_area("About",d.get("about",""),height=320); st.subheader("Keywords"); st.write(", ".join(d.get("keywords",[])))
            else: st.error(api_error(r))
        except Exception as e: st.error(str(e))

# ---------------- ROLES ----------------
with tabs[6]:
    st.header("🎯 Best-fit Job Roles")
    rid=resume_selector("roles_rid")
    if st.button("Find roles",use_container_width=True):
        try:
            r=post("/job-roles",{"resume_id":rid,"provider":provider,"model_name":model})
            if r.ok:
                for x in r.json()["result"].get("roles",[]):
                    st.markdown(f"### {x.get('role','Role')}")
                    st.progress(max(0,min(100,float(x.get('match_score',0))))/100)
                    st.write(f"**Match:** {x.get('match_score',0)}% — {x.get('reason','')}")
                    st.write("Skills: "+", ".join(x.get("required_skills",[])))
            else: st.error(api_error(r))
        except Exception as e: st.error(str(e))

# ---------------- INTERVIEW ----------------
with tabs[7]:
    st.header("🎤 Interview Simulator")
    rid=resume_selector("int_rid"); role=st.text_input("Target role",value="Software Engineer"); typ=st.selectbox("Interview type",["Technical","HR","Behavioral"])
    if st.button("Generate question",use_container_width=True):
        try:
            r=post("/interview/question",{"resume_id":rid,"role":role,"interview_type":typ,"provider":provider,"model_name":model})
            if r.ok: st.session_state.question=r.json()["result"]
            else: st.error(api_error(r))
        except Exception as e: st.error(str(e))
    if st.session_state.question:
        q=st.session_state.question; st.subheader(q.get("question","")); st.caption(q.get("why_it_is_asked",""))
        answer=st.text_area("Your answer",height=230)
        if st.button("Evaluate answer",use_container_width=True):
            try:
                r=post("/interview/evaluate",{"question":q.get("question",""),"answer":answer,"provider":provider,"model_name":model})
                if r.ok:
                    d=r.json()["result"]; a,b,c=st.columns(3); a.metric("Score",f"{d.get('score',0)}/100"); b.metric("Communication",f"{d.get('communication',0)}/100"); c.metric("Technical",f"{d.get('technical_accuracy',0)}/100")
                    st.subheader("Strengths"); [st.write("✅ "+str(x)) for x in d.get("strengths",[])]
                    st.subheader("Improve"); [st.write("⚠️ "+str(x)) for x in d.get("weaknesses",[])]
                    st.subheader("Better answer"); st.write(d.get("better_answer",""))
                else: st.error(api_error(r))
            except Exception as e: st.error(str(e))

# ---------------- CODING ----------------
with tabs[8]:
    st.header("💻 Coding Interview")
    rid=resume_selector("code_rid"); role=st.text_input("Coding role",value="Python Developer"); diff=st.selectbox("Difficulty",["Easy","Medium","Hard"])
    if st.button("Generate problem",use_container_width=True):
        try:
            r=post("/coding/question",{"resume_id":rid,"role":role,"difficulty":diff,"provider":provider,"model_name":model})
            if r.ok: st.session_state.coding=r.json()["result"]
            else: st.error(api_error(r))
        except Exception as e: st.error(str(e))
    if st.session_state.coding:
        p=st.session_state.coding; st.subheader(p.get("title","Coding Problem")); st.write(p.get("question","")); st.write("**Constraints**"); [st.write("• "+str(x)) for x in p.get("constraints",[])]
        code=st.text_area("Your solution",value=p.get("starter_code",""),height=400)
        if st.button("Evaluate code",use_container_width=True):
            try:
                r=post("/coding/evaluate",{"question":p.get("question",""),"code":code,"provider":provider,"model_name":model})
                if r.ok:
                    d=r.json()["result"]; a,b,c=st.columns(3); a.metric("Score",f"{d.get('score',0)}/100"); b.metric("Correctness",f"{d.get('correctness',0)}/100"); c.metric("Quality",f"{d.get('code_quality',0)}/100")
                    st.subheader("Bugs"); [st.error(str(x)) for x in d.get("bugs",[])]
                    st.subheader("Improvements"); [st.write("💡 "+str(x)) for x in d.get("improvements",[])]
                else: st.error(api_error(r))
            except Exception as e: st.error(str(e))

# ---------------- APPLICATIONS ----------------
with tabs[9]:
    st.header("📋 Application Tracker")
    with st.form("app_form"):
        a,b=st.columns(2); company=a.text_input("Company"); role=b.text_input("Role")
        a,b=st.columns(2); location=a.text_input("Location"); status=b.selectbox("Status",["Saved","Applied","Assessment","Interview","Offer","Rejected"])
        url=st.text_input("Job URL"); notes=st.text_area("Notes"); submit=st.form_submit_button("Add application",use_container_width=True)
        if submit:
            try:
                r=post("/applications",{"company":company,"role":role,"location":location,"status":status,"job_url":url,"notes":notes})
                if r.ok: st.success("Application added."); st.rerun()
                else: st.error(api_error(r))
            except Exception as e: st.error(str(e))
    try:
        apps=get("/applications").json().get("applications",[])
        for a in apps:
            with st.expander(f"{a['company']} · {a['role']} · {a['status']}"):
                st.write(f"**Location:** {a['location']}")
                st.write(f"**Applied:** {a['applied_date'][:10]}")
                st.write(f"**Notes:** {a['notes']}")
                if a["job_url"]: st.link_button("Open job posting",a["job_url"])
                new=st.selectbox("Update status",["Saved","Applied","Assessment","Interview","Offer","Rejected"],index=["Saved","Applied","Assessment","Interview","Offer","Rejected"].index(a["status"]) if a["status"] in ["Saved","Applied","Assessment","Interview","Offer","Rejected"] else 0,key=f"s{a['id']}")
                if st.button("Save status",key=f"u{a['id']}"):
                    r=put(f"/applications/{a['id']}",{"status":new,"notes":a["notes"]})
                    if r.ok: st.success("Updated."); st.rerun()
                if st.button("Delete",key=f"d{a['id']}"):
                    r=delete(f"/applications/{a['id']}")
                    if r.ok: st.rerun()
    except Exception as e: st.error(str(e))

# ---------------- ROADMAP ----------------
with tabs[10]:
    st.header("🗺️ 90-Day Career Roadmap")
    rid=resume_selector("road_rid")
    if st.button("Generate roadmap",use_container_width=True):
        try:
            r=post("/career-roadmap",{"resume_id":rid,"provider":provider,"model_name":model})
            if r.ok:
                d=r.json()["result"]; st.info("Current level: "+d.get("current_level",""))
                st.subheader("Target roles"); [st.write("🎯 "+str(x)) for x in d.get("target_roles",[])]
                st.subheader("Skills to learn"); [st.write("📚 "+str(x)) for x in d.get("skills_to_learn",[])]
                a,b,c=st.columns(3)
                for col,title,key in [(a,"Days 1–30","days_30"),(b,"Days 31–60","days_60"),(c,"Days 61–90","days_90")]:
                    with col:
                        st.markdown(f"### {title}")
                        [st.write("• "+str(x)) for x in d.get(key,[])]
                st.subheader("Weekly habits"); [st.write("✓ "+str(x)) for x in d.get("weekly_habits",[])]
            else: st.error(api_error(r))
        except Exception as e: st.error(str(e))
