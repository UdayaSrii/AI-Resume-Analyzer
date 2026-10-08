import json
import os
import re
from typing import Any, Dict

import requests


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

LEGACY_MODELS = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
}


def normalize_model(provider: str, model_name: str) -> str:
    if not model_name:
        return "openai/gpt-oss-120b" if provider.lower() == "groq" else "gpt-4o-mini"
    return LEGACY_MODELS.get(model_name, model_name)


def _provider_config(provider: str, model_name: str):
    provider = (provider or "Groq").strip().lower()
    model = normalize_model(provider, model_name)

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        return key, OPENAI_URL, model

    key = os.getenv("GROQ_API_KEY", "").strip()
    return key, GROQ_URL, model


def _chat(provider: str, model_name: str, system: str, user: str, temperature: float = 0.2) -> str:
    key, url, model = _provider_config(provider, model_name)
    if not key:
        name = "OPENAI_API_KEY" if provider.lower() == "openai" else "GROQ_API_KEY"
        raise RuntimeError(f"{name} is not configured on the backend.")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }

    response = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=180,
    )

    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:1000]
        raise RuntimeError(f"AI provider error ({response.status_code}): {detail}")

    data = response.json()
    return data["choices"][0]["message"]["content"]


def _parse_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                pass
    raise ValueError("AI returned invalid JSON.")


def _safe_list(value):
    return value if isinstance(value, list) else []


def analyze_resume(resume_text, job_description, provider, model_name):
    system = """You are an expert ATS resume analyst and career coach. Return ONLY valid JSON. Be honest and fresher-friendly. Never invent experience, projects, employers, degrees, certifications, or skills that are not supported by the resume."""
    prompt = f"""
Analyze this resume against the target job description.

RESUME:
{resume_text[:18000]}

JOB DESCRIPTION:
{job_description[:12000]}

Return exactly this JSON structure:
{{
  "ats_analysis": {{
    "score": 0,
    "matched_skills": [],
    "missing_skills": [],
    "keywords_found": [],
    "keywords_to_add": [],
    "recommendations": []
  }},
  "strengths": [],
  "weaknesses": [],
  "summary": "",
  "fresher_advice": []
}}
Score 0-100 as a guidance metric, not as a real proprietary ATS score.
"""
    result = _parse_json(_chat(provider, model_name, system, prompt))
    result.setdefault("ats_analysis", {})
    result["ats_analysis"]["score"] = max(0, min(100, float(result["ats_analysis"].get("score", 0))))
    return result


def rewrite_resume(resume_text, job_description, provider, model_name):
    system = """You are a professional resume writer. Return ONLY valid JSON. Preserve factual accuracy. For freshers, emphasize projects, internships, coursework, certifications and measurable project outcomes instead of inventing work experience."""
    prompt = f"""
Rewrite the resume for this target job.

RESUME:
{resume_text[:18000]}

TARGET JOB:
{job_description[:12000]}

Return:
{{
  "summary": "",
  "rewritten_resume": "",
  "improvements": [],
  "ats_keywords_used": [],
  "fresher_notes": []
}}
The rewritten_resume should be a complete, clean, ATS-friendly plain-text resume with sections such as SUMMARY, SKILLS, EXPERIENCE/INTERNSHIPS, PROJECTS, EDUCATION and CERTIFICATIONS when applicable. Do not invent facts.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.15))


def generate_professional_resume(resume_text, job_description, provider, model_name):
    return rewrite_resume(resume_text, job_description, provider, model_name)


def generate_cover_letter(resume_text, job_description, company, role, provider, model_name):
    system = "You are a professional career writer. Do not invent facts. Return a concise, human-sounding cover letter."
    prompt = f"""
Write a tailored cover letter for {role} at {company}.

RESUME:
{resume_text[:16000]}

JOB DESCRIPTION:
{job_description[:10000]}
"""
    return _chat(provider, model_name, system, prompt, 0.35)


def optimize_linkedin(resume_text, provider, model_name):
    system = "You are a LinkedIn profile coach. Return ONLY valid JSON and do not invent experience."
    prompt = f"""
Optimize this profile for a fresher/job seeker.
RESUME:
{resume_text[:16000]}
Return:
{{"headline":"", "about":"", "keywords":[], "improvements":[]}}
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.25))


def recommend_roles(resume_text, provider, model_name):
    system = "You are a fresher-friendly career advisor. Return ONLY valid JSON. Recommend realistic entry-level roles based only on evidence in the resume."
    prompt = f"""
Resume:
{resume_text[:16000]}
Return:
{{"roles":[{{"role":"","match_score":0,"reason":"","required_skills":[],"starter_projects":[]}}]}}
Give 6-8 realistic roles. Match score is a guidance estimate.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.25))


def generate_interview_question(resume_text, role, interview_type, provider, model_name):
    system = "You are a patient interview trainer for students and freshers. Return ONLY valid JSON. The answer must teach the concept, not merely grade it."
    prompt = f"""
Create ONE {interview_type} interview question for a fresher targeting {role}.
Resume:
{resume_text[:14000]}

Return:
{{
  "question":"",
  "topic":"",
  "difficulty":"Easy|Medium|Hard",
  "why_this_is_asked":"",
  "model_answer":"",
  "explanation":"",
  "key_points_to_remember":[],
  "common_mistakes":[],
  "follow_up_question":""
}}
Make the model_answer suitable for a fresher and clearly explain unfamiliar concepts.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.3))


def evaluate_interview_answer(question, answer, provider, model_name):
    system = "You are a supportive interview evaluator and teacher. Return ONLY valid JSON."
    prompt = f"""
Question:
{question}

Candidate answer:
{answer}

Return:
{{
  "score":0,
  "communication":0,
  "technical_accuracy":0,
  "strengths":[],
  "weaknesses":[],
  "better_answer":"",
  "teaching_explanation":"",
  "what_to_learn":[],
  "next_question":""
}}
If the candidate does not know the answer, explain the concept simply and provide a strong fresher-level answer.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.25))


def generate_coding_question(resume_text, role, difficulty, provider, model_name):
    system = "You are a coding interview instructor for freshers. Return ONLY valid JSON. Always include a correct reference solution and explanation so the learner can study even when they cannot solve it."
    prompt = f"""
Create ONE {difficulty} coding interview problem for {role}.
Resume context:
{resume_text[:12000]}

Return:
{{
  "title":"",
  "topic":"",
  "question":"",
  "input_format":"",
  "output_format":"",
  "examples":[],
  "hints":[],
  "reference_solution":"",
  "solution_explanation":"",
  "time_complexity":"",
  "space_complexity":"",
  "common_mistakes":[],
  "follow_up": ""
}}
Use Python unless the role strongly suggests another language.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.25))


def evaluate_code(question, code, provider, model_name):
    system = "You are a coding mentor. Return ONLY valid JSON. Be constructive and teach the candidate."
    prompt = f"""
Problem:
{question}

Candidate code:
{code}

Return:
{{
  "score":0,
  "correctness":0,
  "code_quality":0,
  "bugs":[],
  "improvements":[],
  "reference_solution":"",
  "solution_explanation":"",
  "time_complexity":"",
  "space_complexity":"",
  "what_to_learn":[]
}}
If the code is empty or incorrect, still provide a correct reference solution and explain it.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.2))



def generate_cv(resume_text, target_role, job_description, provider, model_name):
    system = """You are an expert CV writer for students and freshers. Return ONLY valid JSON. Preserve factual accuracy and never invent employers, degrees, certifications, dates, skills, achievements, or experience. Optimize the CV for clarity, ATS readability and the target role."""
    prompt = f"""
Create a professional CV for the target role: {target_role}.

CURRENT RESUME / PROFILE:
{resume_text[:18000]}

JOB DESCRIPTION (optional):
{job_description[:12000]}

Return exactly:
{{
  "cv": "",
  "profile_summary": "",
  "sections_used": [],
  "improvements": [],
  "keywords_used": [],
  "fresher_tips": []
}}
The cv field must contain a complete, clean, editable plain-text CV. Use sections such as NAME/CONTACT, PROFILE, EDUCATION, SKILLS, PROJECTS, EXPERIENCE/INTERNSHIPS, CERTIFICATIONS, ACHIEVEMENTS and LANGUAGES only when supported by the source information. Keep it suitable for a fresher and do not add false claims.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.15))


def generate_english_test(level, focus, provider, model_name):
    system = "You are an English communication teacher for college students and freshers. Return ONLY valid JSON. Make questions practical for workplace communication and explain every answer so the learner can study."
    prompt = f"""
Create a 5-question English and communication assessment for a {level} learner. Focus: {focus}.
Include a balanced mix of grammar, vocabulary, sentence correction, workplace communication and reading/comprehension.

Return exactly:
{{
  "title":"",
  "level":"",
  "questions":[
    {{
      "id":1,
      "type":"MCQ|Correction|Communication|Vocabulary|Reading",
      "question":"",
      "options":[],
      "correct_answer":"",
      "explanation":"",
      "learning_point":""
    }}
  ]
}}
For non-MCQ questions, options may be an empty list. Keep the test appropriate for freshers and make the answer explanations useful for learning.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.25))


def evaluate_english_test(questions, answers, provider, model_name):
    system = "You are a supportive English communication evaluator. Return ONLY valid JSON. Grade fairly, explain mistakes simply, and give actionable learning advice."
    prompt = f"""
Questions and answer key:
{json.dumps(questions, ensure_ascii=False)[:18000]}

Candidate answers:
{json.dumps(answers, ensure_ascii=False)[:8000]}

Return exactly:
{{
  "score":0,
  "correct":0,
  "total":0,
  "level_estimate":"Beginner|Elementary|Intermediate|Upper-Intermediate|Advanced",
  "strengths":[],
  "mistakes":[{{"question_id":1,"your_answer":"","correct_answer":"","explanation":""}}],
  "communication_feedback":"",
  "what_to_learn":[],
  "practice_plan":[]
}}
Score as a percentage. For unanswered questions, treat them as incorrect and explain the concept.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.2))


def generate_english_lesson(topic, level, goal, provider, model_name):
    system = "You are a patient English and workplace communication tutor for students and freshers. Return ONLY valid JSON. Teach with simple examples and practical exercises."
    prompt = f"""
Create a short self-study lesson for a {level} learner.
Topic: {topic}
Career/workplace goal: {goal}

Return exactly:
{{
  "topic":"",
  "level":"",
  "explanation":"",
  "rules":[],
  "good_examples":[],
  "common_mistakes":[],
  "workplace_phrases":[],
  "practice_questions":[],
  "answers":[],
  "daily_practice":""
}}
Keep the lesson practical, beginner-friendly and useful for interviews, emails, meetings and workplace conversations.
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.2))

def career_roadmap(resume_text, provider, model_name):
    system = "You are a practical career coach for students and freshers. Return ONLY valid JSON."
    prompt = f"""
Create a realistic 90-day roadmap based on this resume:
{resume_text[:16000]}

Return:
{{
  "current_level":"",
  "target_roles":[],
  "skills_to_learn":[],
  "days_30":[],
  "days_60":[],
  "days_90":[],
  "portfolio_actions":[],
  "application_strategy":[]
}}
"""
    return _parse_json(_chat(provider, model_name, system, prompt, 0.25))
