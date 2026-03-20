from __future__ import annotations

from datetime import date
from typing import Any, Iterable


DEFAULT_QUESTION_OPTIONS = {
	"temperature": 0.1,
	"num_predict": 120,
}


def _safe_text(value: Any, fallback: str = "N/A") -> str:
	if value is None:
		return fallback
	text = str(value).strip()
	return text if text else fallback


def _date_text(value: date | None) -> str:
	if value is None:
		return "N/A"
	return value.isoformat()


def _format_skills(skills: Iterable[Any]) -> str:
	rows = []
	for skill in skills:
		name = _safe_text(getattr(skill, "name", None))
		level = _safe_text(getattr(skill, "level", None))
		category = _safe_text(getattr(skill, "category", None))
		rows.append(f"- {name} | level={level} | category={category}")

	if not rows:
		return "- No explicit skills in profile"
	return "\n".join(rows)


def _format_experiences(experiences: Iterable[Any]) -> str:
	rows = []
	for exp in experiences:
		position = _safe_text(getattr(exp, "position", None))
		company = _safe_text(getattr(exp, "company", None))
		start_date = _date_text(getattr(exp, "start_date", None))
		end_date = _date_text(getattr(exp, "end_date", None))
		current = "yes" if bool(getattr(exp, "currently_working", False)) else "no"
		description = _safe_text(getattr(exp, "description", None), fallback="")
		description = description[:220]
		rows.append(
			f"- {position} @ {company} | {start_date} -> {end_date} | current={current} | desc={description}"
		)

	if not rows:
		return "- No prior experiences in profile"
	return "\n".join(rows)


def _format_previous_questions(previous_questions: Iterable[str] | None) -> str:
	if not previous_questions:
		return "- None"

	rows = []
	for item in previous_questions:
		text = _safe_text(item, fallback="")
		if text:
			rows.append(f"- {text}")
	return "\n".join(rows) if rows else "- None"


def get_question_generation_options(overrides: dict | None = None) -> dict:
	options = dict(DEFAULT_QUESTION_OPTIONS)
	if not overrides:
		return options

	for key in ("temperature", "num_predict"):
		if key in overrides and overrides[key] is not None:
			options[key] = overrides[key]
	return options


def build_question_generation_prompts(
	profile: Any,
	skills: Iterable[Any],
	experiences: Iterable[Any],
	*,
	target_skill: str | None = None,
	difficulty: str | None = None,
	previous_questions: Iterable[str] | None = None,
) -> tuple[str, str]:
	"""
	Build system and user prompts focused on generating one interview question.
	"""
	system_prompt = (
		"You are an interviewer assistant focused on technical interviews. "
		"Generate exactly one technical question in plain language. "
		"Do not provide answers, hints, explanations, markdown, bullets, or numbering. "
		"Use only provided profile context. Do not invent technologies, projects, companies, or experience. "
		"If context is limited, ask a fundamental question tied to known skills."
	)

	profile_summary = (
		f"Candidate profile:\n"
		f"- Full name: {_safe_text(getattr(profile, 'full_name', None))}\n"
		f"- Career: {_safe_text(getattr(profile, 'career', None))}\n"
		f"- University: {_safe_text(getattr(profile, 'university', None))}\n"
		f"- Graduation date: {_date_text(getattr(profile, 'graduation_date', None))}\n"
		f"- English level: {_safe_text(getattr(getattr(profile, 'english_level', None), 'value', None))}\n"
		f"- Profile description: {_safe_text(getattr(profile, 'description', None), fallback='No description')}"
	)

	focus = _safe_text(target_skill, fallback="Auto-select best-fit skill from profile")
	difficulty_value = _safe_text(difficulty, fallback="adaptive")

	user_prompt = (
		f"{profile_summary}\n\n"
		f"Skills:\n{_format_skills(skills)}\n\n"
		f"Experiences:\n{_format_experiences(experiences)}\n\n"
		f"Previous questions to avoid repeating:\n{_format_previous_questions(previous_questions)}\n\n"
		f"Question generation constraints:\n"
		f"- Focus skill: {focus}\n"
		f"- Difficulty: {difficulty_value}\n"
		f"- Keep wording simple, direct, and technical\n"
		f"- Ask only one question\n"
		f"- Return only the question text"
	)

	return system_prompt, user_prompt
