"""AI services for AI Resume Analyzer & Career Coach.

Uses direct REST calls so the backend does not depend on provider SDK versions.
Supports Groq's OpenAI-compatible endpoint and OpenAI's chat completions endpoint.
"""
import json
import os
import re
from typing import Any, Dict

import requests
from dotenv import load_dotenv

load_dotenv()

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

LEGACY_MODELS = {
    "llama-3.3-70b-versatile": "openai/gpt-oss-120b",
    "llama-3.1-8b-instant": "openai/gpt-oss-20b",
}


def normalize_model(provider: str, model_name: str) -> str:
    model = (model_name or "").strip()
    if model in LEGACY_MODELS:
        model = LEGACY_MODELS[model]
    if not model:
        return "openai/gpt-oss-120b" if provider.lower() == "groq" else "gpt-4o-mini"
    return model


def _call_llm(system: str, prompt: str, provider: str = "Groq", model_name: str = "", temperature: float = 0.2, max_tokens: int = 5000) -> str:
    provider = (provider or "Groq").strip().lower()
    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "").strip()
        url = OPENAI_URL
    else:
        key = os.getenv("GROQ_API_KEY", "").strip()
        url = GROQ_URL
        provider = "groq"

    if not key:
        raise RuntimeError(f"{provider.upper()}_API_KEY is not configured on the backend.")

    payload = {
        "model": normalize_model(provider, model_name),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=120,
    )
    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text[:1000]
        raise RuntimeError(f"AI provider error ({response.status_code}): {detail}")
    data = response.json()
    return data["choices"][0]["message"]["content"]


def _json_from_text(text: str, fallback: Dict[str, Any] | None = None) -> Dict[str, Any]:
    text = (text or "").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            pass
    if fallback is not None:
        fallback["raw_response"] = text
        return fallback
    return {"raw_response": text}


def _safe_list(value):
    return value if isinstance(value, list) else []


def analyze_resume(resume_text: str, job_description: str, provider: str = "Groq", model_name: str = ""):
    system = """You are an expert ATS resume reviewer and career coach. Be accurate and honest. Never invent candidate experience. Return valid JSON only."""
    prompt = f"""Analyze this resume against the job description.

RESUME:\n{resume_text[:18000]}

JOB DESCRIPTION:\n{job_description[:14000]}

Return JSON with:
{{"ats_analysis":{{"score":0,"summary":"","matched_keywords":[],"missing_keywords":[],"formatting_notes":[]}},"skills":{{"matched":[],"missing":[],"strengths":[],"weaknesses":[]}},"recommendations":[],"fresher_guidance":[],"priority_actions":[]}}
Score must be an integer 0-100 and is an AI guidance metric, not a proprietary ATS score."""
    return _json_from_text(_call_llm(system, prompt, provider, model_name), {"ats_analysis": {"score": 0}})


def rewrite_resume(resume_text: str, job_description: str, provider: str = "Groq", model_name: str = ""):
    system = "You are a professional resume editor. Preserve facts. Do not invent jobs, degrees, dates, awards, metrics or skills. Return JSON only."
    prompt = f"""Rewrite this resume for the target job description. Make it ATS-friendly and suitable for a fresher when experience is limited.
RESUME:\n{resume_text[:18000]}
JOB DESCRIPTION:\n{job_description[:12000]}
Return {{"rewritten_resume":"...","changes":[],"keywords_added":[],"truthfulness_note":""}}."""
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=6500), {"rewritten_resume": resume_text, "changes": []})


def generate_professional_resume(resume_text: str, job_description: str = "", provider: str = "Groq", model_name: str = ""):
    system = "You are a professional CV writer for students and freshers. Use only facts present in the source. Return JSON only."
    prompt = f"""Create a complete professional ATS-friendly resume from the source.
SOURCE RESUME:\n{resume_text[:18000]}
TARGET JOB DESCRIPTION (optional):\n{job_description[:12000]}
Return {{"resume":"...","summary":"...","sections":["..."],"keywords_used":[],"improvements":[]}}. Use clean plain text headings."""
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=7000), {"resume": resume_text, "summary": "", "improvements": []})


def generate_cover_letter(resume_text: str, job_description: str, company: str, role: str, provider: str = "Groq", model_name: str = "") -> str:
    system = "You write concise, truthful professional cover letters. Never invent candidate facts."
    prompt = f"Write a tailored cover letter for {role} at {company}. Resume:\n{resume_text[:12000]}\nJob description:\n{job_description[:10000]}"
    return _call_llm(system, prompt, provider, model_name, temperature=0.3, max_tokens=2500).strip()


def optimize_linkedin(resume_text: str, provider: str = "Groq", model_name: str = ""):
    system = "You are a LinkedIn profile coach. Preserve factual accuracy. Return JSON only."
    prompt = f"Improve this candidate's LinkedIn positioning:\n{resume_text[:15000]}\nReturn {{\"headline\":\"\",\"about\":\"\",\"skills\":[],\"project_descriptions\":[],\"improvement_tips\":[]}}."
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=4500))


def recommend_roles(resume_text: str, provider: str = "Groq", model_name: str = ""):
    system = "You are a fresher career advisor. Recommend realistic entry-level roles based only on demonstrated skills. Return JSON only."
    prompt = f"Resume:\n{resume_text[:15000]}\nReturn {{\"roles\":[{{\"role\":\"\",\"match_score\":0,\"why\":\"\",\"skills_to_improve\":[]}}],\"general_advice\":[]}} with 5-8 roles."
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=4000))


def career_roadmap(resume_text: str, provider: str = "Groq", model_name: str = ""):
    system = "You are a practical career mentor for a fresher. Return JSON only."
    prompt = f"Create a 90-day career roadmap from this resume:\n{resume_text[:15000]}\nReturn {{\"current_level\":\"\",\"days_1_30\":[],\"days_31_60\":[],\"days_61_90\":[],\"portfolio_actions\":[],\"application_strategy\":[]}}."
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=4500))


def generate_interview_question(resume_text: str, role: str, interview_type: str = "Technical", provider: str = "Groq", model_name: str = ""):
    system = "You are an interview coach. Generate teachable questions for freshers. Return JSON only."
    prompt = f"Create one {interview_type} interview question for role {role}. Candidate resume:\n{resume_text[:12000]}\nReturn {{\"question\":\"\",\"topic\":\"\",\"difficulty\":\"\",\"why_this_is_asked\":\"\",\"model_answer\":\"\",\"explanation\":\"\",\"key_points_to_remember\":[],\"common_mistakes\":[],\"follow_up_question\":\"\"}}."
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=3500))


def evaluate_interview_answer(question: str, answer: str, provider: str = "Groq", model_name: str = ""):
    system = "You are a supportive interview teacher. Give specific corrections and a model answer. Return JSON only."
    prompt = f"Question:\n{question}\nCandidate answer:\n{answer}\nReturn {{\"score\":0,\"verdict\":\"\",\"strengths\":[],\"improvements\":[],\"better_answer\":\"\",\"teaching_feedback\":\"\",\"what_to_learn\":[]}}."
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=3500))


def generate_coding_question(resume_text: str, role: str, difficulty: str = "Medium", provider: str = "Groq", model_name: str = ""):
    system = "You are a coding interview instructor. Generate one practical problem and teach the solution. Return JSON only."
    prompt = f"Create a {difficulty} coding problem for a fresher applying for {role}. Resume:\n{resume_text[:10000]}\nReturn {{\"title\":\"\",\"topic\":\"\",\"question\":\"\",\"input_output\":\"\",\"examples\":[],\"hints\":[],\"reference_solution\":\"\",\"explanation\":\"\",\"complexity\":\"\",\"common_mistakes\":[],\"follow_up\":\"\"}}."
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=5000))


def evaluate_code(question: str, code: str, provider: str = "Groq", model_name: str = ""):
    system = "You are a coding mentor. Evaluate correctness and teach the candidate. Return JSON only."
    prompt = f"Problem:\n{question}\nCandidate code:\n{code}\nReturn {{\"score\":0,\"correct\":false,\"strengths\":[],\"bugs\":[],\"improved_solution\":\"\",\"explanation\":\"\",\"complexity\":\"\",\"what_to_learn\":[]}}."
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=4500))


def write_cv(resume_text: str, target_role: str, job_description: str = "", provider: str = "Groq", model_name: str = ""):
    system = "You are a professional CV writer for students and freshers. Never invent facts. Return JSON only."
    prompt = f"""Create a polished CV for target role: {target_role}.
SOURCE RESUME:\n{resume_text[:18000]}
JOB DESCRIPTION:\n{job_description[:12000]}
Use ATS-friendly headings and concise bullet points. Preserve all facts. Do not invent experience, education, dates, awards, metrics or skills.
Return {{"cv":"...","profile_summary":"...","improvements":[],"keywords_used":[]}}."""
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=7500), {"cv": resume_text, "profile_summary": "", "improvements": [], "keywords_used": []})


def generate_english_test(level: str, focus: str, provider: str = "Groq", model_name: str = ""):
    system = "You are an English assessment designer. Create fair, unambiguous questions. Return JSON only."
    prompt = f"""Create a 5-question English and workplace communication assessment for level {level}, focus {focus}.
Use a mix of grammar, vocabulary, workplace communication, interview English and sentence correction. Prefer 4-option MCQs so automatic scoring is reliable.
Return {{"title":"English & Communication Assessment","instructions":"...","questions":[{{"id":1,"question":"","options":["A","B","C","D"],"correct_answer":"exact option text","explanation":"","learning_point":""}}]}}."""
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=4500), {"title": "English & Communication Assessment", "questions": []})


def evaluate_english_test(questions_json: str, answers_json: str, provider: str = "Groq", model_name: str = ""):
    try:
        questions = json.loads(questions_json)
    except Exception:
        questions = []
    try:
        answers = json.loads(answers_json)
    except Exception:
        answers = {}
    total = len(questions)
    correct = 0
    mistakes = []
    strengths = []
    for q in questions:
        qid = str(q.get("id"))
        expected = str(q.get("correct_answer", "")).strip()
        actual = str(answers.get(qid, "")).strip()
        ok = actual.lower() == expected.lower()
        if ok:
            correct += 1
        else:
            mistakes.append({"question_id": q.get("id"), "your_answer": actual, "correct_answer": expected, "explanation": q.get("explanation", "")})
    score = round((correct / total) * 100) if total else 0
    level = "Advanced" if score >= 90 else "Upper-Intermediate" if score >= 75 else "Intermediate" if score >= 55 else "Elementary" if score >= 35 else "Beginner"
    prompt = f"Review an English test result. Score {score}%. Mistakes: {json.dumps(mistakes)[:6000]}. Give concise personalized communication feedback, strengths, what to learn, and a 7-day practice plan. Return JSON {{\"communication_feedback\":\"\",\"strengths\":[],\"what_to_learn\":[],\"practice_plan\":[]}}."
    try:
        extra = _json_from_text(_call_llm("You are a supportive English teacher. Return JSON only.", prompt, provider, model_name, max_tokens=2500))
    except Exception:
        extra = {}
    return {
        "score": score, "correct": correct, "total": total, "level_estimate": level,
        "mistakes": mistakes, "strengths": extra.get("strengths", ["You completed the assessment."] if correct else []),
        "communication_feedback": extra.get("communication_feedback", "Review the explanations and practice speaking your answers aloud."),
        "what_to_learn": extra.get("what_to_learn", []), "practice_plan": extra.get("practice_plan", [])
    }


def english_lesson(topic: str, level: str, goal: str, provider: str = "Groq", model_name: str = ""):
    system = "You are a patient English teacher for job-seeking students. Return JSON only."
    prompt = f"Teach {topic} to a {level} learner whose goal is: {goal}. Include simple explanation, rules, examples, common mistakes, workplace phrases and 5 practice questions. Return {{\"topic\":\"\",\"explanation\":\"\",\"rules\":[],\"good_examples\":[],\"common_mistakes\":[],\"workplace_phrases\":[],\"practice_questions\":[]}}."
    return _json_from_text(_call_llm(system, prompt, provider, model_name, max_tokens=4500))
