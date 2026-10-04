import json, os, re
import requests
from dotenv import load_dotenv

load_dotenv()

SYSTEM = """You are an expert resume strategist, recruiter, career coach and technical interviewer.
Return ONLY valid JSON when the task requests JSON. Do not use markdown fences.
Use the candidate data provided; never invent employers, degrees, certifications or experience.
Keep advice practical and ATS-friendly."""

def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise ValueError("AI returned invalid JSON.")

def _call(provider, model, prompt, temperature=0.2):
    provider = (provider or "Groq").strip()
    model = model or ("openai/gpt-oss-120b" if provider.lower() == "groq" else "gpt-4o-mini")
    if provider.lower() == "groq":
        key, url = os.getenv("GROQ_API_KEY"), "https://api.groq.com/openai/v1/chat/completions"
    else:
        key, url = os.getenv("OPENAI_API_KEY"), "https://api.openai.com/v1/chat/completions"
    if not key:
        raise ValueError(f"{provider} API key is missing. Add it to .env.")
    r = requests.post(url, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"model": model, "messages":[{"role":"system","content":SYSTEM},{"role":"user","content":prompt}],
              "temperature": temperature}, timeout=120)
    if not r.ok:
        try: detail = r.json()
        except Exception: detail = r.text
        raise RuntimeError(f"{provider} API error: {detail}")
    return r.json()["choices"][0]["message"]["content"]

def _json_task(instruction, provider, model):
    return _extract_json(_call(provider, model, instruction))

def analyze_resume(resume_text, job_description, provider, model_name):
    return _json_task(f"""Analyze this resume against the job description.
Return exactly: {{"ats_analysis":{{"score":0,"matched_skills":[],"missing_skills":[],"recommendations":[]}},
"strengths":[],"weaknesses":[],"keyword_gaps":[],"summary":""}}
Score 0-100 using skills, experience relevance, keywords, education and clarity.
RESUME:
{resume_text[:18000]}
JOB DESCRIPTION:
{job_description[:14000]}""", provider, model_name)

def rewrite_resume(resume_text, job_description, provider, model_name):
    return _json_task(f"""Rewrite the resume for the target job without fabricating facts.
Return exactly: {{"summary":"","rewritten_resume":"","improvements":[]}}
Use clean plain text sections and strong measurable wording only where supported.
RESUME:
{resume_text[:18000]}
JOB:
{job_description[:12000]}""", provider, model_name)

def generate_professional_resume(resume_text, job_description, provider, model_name):
    return _json_task(f"""Create an ATS-friendly professional resume from the source resume and optional target job.
Do not invent facts. Return exactly: {{"resume":"","highlights":[]}}
Use concise sections: Summary, Skills, Experience, Projects, Education, Certifications if present.
SOURCE:
{resume_text[:18000]}
TARGET JOB:
{job_description[:10000]}""", provider, model_name)

def generate_cover_letter(resume_text, job_description, company, role, provider, model_name):
    out = _call(provider, model_name, f"""Write a tailored one-page cover letter for {role} at {company}.
Do not invent facts. Return plain text only.
RESUME:
{resume_text[:15000]}
JOB:
{job_description[:10000]}""")
    return out.strip()

def optimize_linkedin(resume_text, provider, model_name):
    return _json_task(f"""Optimize a LinkedIn profile from this resume without inventing facts.
Return exactly: {{"headline":"","about":"","keywords":[],"featured_projects":[]}}
RESUME:
{resume_text[:18000]}""", provider, model_name)

def recommend_roles(resume_text, provider, model_name):
    return _json_task(f"""Recommend the best roles for this candidate based only on the resume.
Return exactly: {{"roles":[{{"role":"","match_score":0,"reason":"","required_skills":[]}}]}}
Give 6 roles, score 0-100.
RESUME:
{resume_text[:18000]}""", provider, model_name)

def career_roadmap(resume_text, provider, model_name):
    return _json_task(f"""Create a realistic 90-day career roadmap based on this resume.
Return exactly: {{"current_level":"","target_roles":[],"skills_to_learn":[],"days_30":[],"days_60":[],"days_90":[],"weekly_habits":[]}}
RESUME:
{resume_text[:18000]}""", provider, model_name)

def generate_interview_question(resume_text, role, interview_type, provider, model_name):
    return _json_task(f"""Generate one {interview_type} interview question for a {role} candidate, personalized to the resume.
Return exactly: {{"question":"","why_it_is_asked":"","tips":[],"ideal_answer_points":[]}}
RESUME:
{resume_text[:16000]}""", provider, model_name)

def evaluate_interview_answer(question, answer, provider, model_name):
    return _json_task(f"""Evaluate the interview answer.
Return exactly: {{"score":0,"communication":0,"technical_accuracy":0,"relevance":0,"strengths":[],"weaknesses":[],"better_answer":""}}
Score each 0-100.
QUESTION: {question}
ANSWER: {answer}""", provider, model_name)

def generate_coding_question(resume_text, role, difficulty, provider, model_name):
    return _json_task(f"""Create one {difficulty} coding interview problem for a {role} candidate.
Return exactly: {{"title":"","question":"","constraints":[],"examples":[],"starter_code":"","expected_concepts":[]}}
RESUME:
{resume_text[:12000]}""", provider, model_name)

def evaluate_code(question, code, provider, model_name):
    return _json_task(f"""Review this coding solution without executing it.
Return exactly: {{"score":0,"correctness":0,"code_quality":0,"complexity":0,"bugs":[],"improvements":[],"ideal_approach":""}}
QUESTION:
{question}
CODE:
{code[:16000]}""", provider, model_name)
