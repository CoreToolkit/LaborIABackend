from __future__ import annotations

from datetime import date
from typing import Any, Iterable


DEFAULT_QUESTION_OPTIONS = {
	"temperature": 0.1,
	"num_predict": 120,
}

# ── Tipos de pregunta rotativos para entrevistas grupales ─────────────────────
# Cada elemento define el tipo y la instrucción específica que se inyecta en
# el system prompt. La rotación garantiza variedad entre rondas.
_GROUP_QUESTION_TYPES = [
	{
		"label": "conceptual",
		"instruction": (
			"Genera una pregunta TÉCNICA CONCEPTUAL que evalúe comprensión profunda: "
			"diferencias entre tecnologías, cuándo usar X vs Y, o cómo funciona algo internamente. "
			"Ejemplo de estructura: '¿Cuál es la diferencia entre X e Y y cuándo usarías cada uno?'"
		),
	},
	{
		"label": "situacional_star",
		"instruction": (
			"Genera una pregunta SITUACIONAL que pida al candidato narrar una experiencia real (método STAR). "
			"Debe comenzar con 'Cuéntame de una vez que...' o 'Describe una situación en la que...'. "
			"NO usar '¿Cómo harías?' — pedir algo que YA haya vivido."
		),
	},
	{
		"label": "escenario_crisis",
		"instruction": (
			"Genera una pregunta de ESCENARIO DE CRISIS o fallo en producción. "
			"Plantea un problema concreto y real (error crítico, caída de servicio, bug grave) "
			"y pregunta cómo respondería paso a paso. "
			"Ejemplo: 'Tu aplicación en producción empieza a lanzar X. ¿Cuáles son tus primeros tres pasos?'"
		),
	},
	{
		"label": "trade_off",
		"instruction": (
			"Genera una pregunta de TRADE-OFF o decisión de diseño. "
			"El candidato debe razonar entre dos opciones técnicas válidas con criterios concretos. "
			"Ejemplo: '¿Cuándo elegirías X sobre Y para un nuevo proyecto y qué factores definirían tu decisión?'"
		),
	},
	{
		"label": "aprendizaje_error",
		"instruction": (
			"Genera una pregunta sobre UN ERROR O FRACASO TÉCNICO y qué aprendió el candidato. "
			"Debe invitar a reflexión honesta, no a una respuesta perfecta. "
			"Ejemplo: 'Cuéntame de una decisión técnica que tomaste y que luego tuviste que cambiar o refactorizar. ¿Qué aprendiste?'"
		),
	},
	{
		"label": "basada_en_experiencia",
		"instruction": (
			"Genera una pregunta que ANCLE DIRECTAMENTE en el historial profesional del candidato. "
			"Referencia su cargo más reciente, empresa o una skill específica declarada. "
			"Ejemplo: 'En tu rol como [cargo] en [empresa], ¿cómo abordaste...?'"
		),
	},
]

# Frases de apertura sobreusadas que el modelo debe evitar
_BANNED_OPENERS = [
	"¿Cómo asegurarías",
	"¿Cómo garantizarías",
	"¿Cómo planeas abordar",
	"¿Cómo abordarías",
	"¿Cómo manejarías",
	"¿Cuáles son las mejores prácticas",
]


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
		return "- Ninguna"

	rows = []
	for item in previous_questions:
		text = _safe_text(item, fallback="")
		if text:
			rows.append(f"- {text}")
	return "\n".join(rows) if rows else "- Ninguna"


def _pick_question_type(round_index: int) -> dict:
	"""Rota entre los tipos de pregunta según el índice de ronda."""
	return _GROUP_QUESTION_TYPES[round_index % len(_GROUP_QUESTION_TYPES)]


def _build_experience_anchor(experiences: list) -> str:
	"""
	Extrae la experiencia más reciente del candidato para anclar la pregunta
	en contexto real, en lugar de formular preguntas genéricas.
	"""
	if not experiences:
		return ""
	exp = experiences[0]
	position = _safe_text(getattr(exp, "position", None), fallback="")
	company = _safe_text(getattr(exp, "company", None), fallback="")
	description = _safe_text(getattr(exp, "description", None), fallback="")[:180]
	if not position and not company:
		return ""
	anchor = f"{position}"
	if company and company != "N/A":
		anchor += f" en {company}"
	if description and description != "N/A":
		anchor += f" — {description}"
	return anchor


def _format_banned_openers() -> str:
	return ", ".join(f'"{o}"' for o in _BANNED_OPENERS)


def _build_candidate_context(profile: Any, skills: Iterable[Any], experiences: Iterable[Any]) -> str:
	return (
		f"Candidate profile:\n"
		f"- Full name: {_safe_text(getattr(profile, 'full_name', None))}\n"
		f"- Career: {_safe_text(getattr(profile, 'career', None))}\n"
		f"- University: {_safe_text(getattr(profile, 'university', None))}\n"
		f"- Graduation date: {_date_text(getattr(profile, 'graduation_date', None))}\n"
		f"- English level: {_safe_text(getattr(getattr(profile, 'english_level', None), 'value', None))}\n"
		f"- Profile description: {_safe_text(getattr(profile, 'description', None), fallback='No description')}\n\n"
		f"Skills:\n{_format_skills(skills)}\n\n"
		f"Experiences:\n{_format_experiences(experiences)}"
	)


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
		"Eres un asistente entrevistador especializado en entrevistas técnicas. "
		"Formula exactamente una pregunta técnica en español, en lenguaje claro y directo. "
		"No proporciones respuestas, pistas, explicaciones, markdown, listas ni numeración. "
		"Usa únicamente el contexto del perfil proporcionado. No inventes tecnologías, proyectos, empresas ni experiencias. "
		"Si el contexto es limitado, formula una pregunta fundamental relacionada con las skills conocidas."
	)
	profile_summary = _build_candidate_context(profile, skills, experiences)

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


def build_group_question_generation_prompts(
	profile: Any,
	skills: Iterable[Any],
	experiences: Iterable[Any],
	*,
	role_name: str,
	role_description: str | None = None,
	target_skill: str | None = None,
	difficulty: str | None = None,
	previous_questions: Iterable[str] | None = None,
	round_index: int = 0,
) -> tuple[str, str]:
	"""
	Build prompts for group interview question generation.

	Incorporates:
	- Rotating question types (conceptual, STAR, crisis scenario, trade-off, error/learning, experience-anchored)
	- Explicit anchor in the candidate's most recent real experience
	- Strong anti-repetition: banned openers + list of previous questions
	- round_index drives type rotation for guaranteed variety across rounds
	"""
	# Materializar experiencias una sola vez para poder iterar dos veces
	experiences_list = list(experiences)
	skills_list = list(skills)

	question_type = _pick_question_type(round_index)
	type_label = question_type["label"].upper().replace("_", " ")

	system_prompt = (
		"Eres un entrevistador experto en procesos de selección técnica. "
		f"Formula una sola pregunta de tipo {type_label} en español para una entrevista grupal de la ronda {round_index + 1}. "
		f"{question_type['instruction']} "
		"Ancla la pregunta en el perfil real del candidato. "
		"Responde únicamente con el texto de la pregunta, sin explicaciones, listas ni texto adicional."
	)

	context = _build_candidate_context(profile, skills_list, experiences_list)
	experience_anchor = _build_experience_anchor(experiences_list)

	role_context = (
		f"Contexto de la entrevista grupal:\n"
		f"- Rol objetivo: {_safe_text(role_name)}\n"
		f"- Descripcion del rol: {_safe_text(role_description, fallback='N/A')}\n"
		f"- Dificultad: {_safe_text(difficulty, fallback='adaptive')}\n"
		f"- Habilidad a evaluar: {_safe_text(target_skill, fallback='la más relevante del perfil para este rol')}\n"
		f"- Número de ronda: {round_index + 1}"
	)

	anchor_section = (
		f"\nAncla de experiencia concreta del candidato (úsala si el tipo de pregunta lo permite):\n"
		f"  {experience_anchor}\n"
	) if experience_anchor else ""

	prev_q_text = _format_previous_questions(previous_questions)

	# Sugerencia de variedad redactada en tono natural para no activar filtros de contenido
	openers_hint = (
		"Para esta ronda usa un enfoque diferente al de las preguntas anteriores. "
		"Evita comenzar con frases muy comunes como "
		+ ", ".join(f'"{o}"' for o in _BANNED_OPENERS[:3])
		+ "."
	)

	user_prompt = (
		f"{context}\n\n"
		f"{role_context}\n"
		f"{anchor_section}\n"
		f"Preguntas formuladas en rondas anteriores (no repetir ni parafrasear):\n"
		f"{prev_q_text}\n\n"
		f"{openers_hint}\n\n"
		f"Tipo de pregunta: {type_label} — {question_type['instruction']}\n\n"
		f"Escribe la pregunta:"
	)

	return system_prompt, user_prompt
