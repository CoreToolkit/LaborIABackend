from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from core.config import settings
from utils.string_normalization import normalize_skill_name

_EDUCATION_DOMAIN_KEYWORDS = {
    "tech": {
        "ingenieria de sistemas",
        "ingenieria de software",
        "software",
        "sistemas",
        "informatica",
        "computacion",
        "computer science",
        "desarrollo de software",
        "programacion",
    },
    "data": {
        "ciencia de datos",
        "data science",
        "datos",
        "estadistica",
        "statistics",
        "matematicas",
        "mathematics",
        "analitica",
        "analytics",
        "econometria",
    },
    "design": {
        "diseno",
        "diseño",
        "ux",
        "ui",
        "producto",
        "multimedia",
        "grafico",
        "gráfico",
        "visual",
    },
}

_EDUCATION_DOMAIN_AFFINITY = {
    "tech":   {"tech": 100.0, "data": 60.0, "design":  0.0},
    "data":   {"data": 100.0, "tech": 60.0, "design":  0.0},
    "design": {"design": 100.0, "tech": 0.0, "data":   0.0},
}


@dataclass(frozen=True)
class _RoleRequirement:
    name: str
    normalized_name: str
    importance_weight: int
    is_required: bool


def normalize_skills(skills) -> set[str]:
    if not skills:
        return set()
    result: set[str] = set()
    for skill in skills:
        normalized = normalize_skill_name(skill.name)
        if normalized:
            result.add(normalized)
    return result


def normalize_decimal(value) -> Decimal | None:
    if value is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def detect_education_domains(value: str | None) -> set[str]:
    normalized = normalize_skill_name(value)
    if not normalized:
        return set()
    return {
        domain
        for domain, keywords in _EDUCATION_DOMAIN_KEYWORDS.items()
        if any(kw in normalized for kw in keywords)
    }


def get_role_education_domains(role) -> set[str]:
    domains: set[str] = set()
    if role.category is not None:
        domains.add(role.category.value)
    domains.update(detect_education_domains(role.name))
    return domains


def get_required_experience_months(role) -> int:
    from models.job_role import SeniorityLevel
    minimum_by_seniority = {
        SeniorityLevel.JUNIOR: 12,
        SeniorityLevel.MID:    24,
        SeniorityLevel.SENIOR: 48,
    }
    return minimum_by_seniority.get(role.seniority_level, 24)


def calculate_experience_months(start_date: date, end_date: date) -> int:
    if end_date <= start_date:
        return 0
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day < start_date.day:
        months -= 1
    return max(months, 0)


def get_total_experience_months(experiences, reference_date: date | None = None) -> int:
    if not experiences:
        return 0
    reference_date = reference_date or date.today()
    total = 0
    for exp in experiences:
        if not exp.start_date:
            continue
        end = reference_date if exp.currently_working else (exp.end_date or exp.start_date)
        total += calculate_experience_months(exp.start_date, end)
    return total


def get_unique_role_requirements(role) -> list[_RoleRequirement]:
    if not role.role_skills:
        return []
    seen: set[str] = set()
    result: list[_RoleRequirement] = []
    for rs in sorted(role.role_skills, key=lambda rs: rs.importance_weight, reverse=True):
        tech = rs.technology
        if not tech:
            continue
        normalized = normalize_skill_name(tech.name)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(_RoleRequirement(
            name=tech.name.strip(),
            normalized_name=normalized,
            importance_weight=rs.importance_weight,
            is_required=rs.is_required,
        ))
    return result


def get_role_location(role) -> str | None:
    for attr in ("location", "preferred_location", "job_location", "work_location"):
        loc = getattr(role, attr, None)
        if loc:
            return str(loc)
    return None


def calculate_location_preference_score(profile, role) -> float | None:
    p_loc = normalize_skill_name(getattr(profile, "preferred_location", None))
    r_loc = normalize_skill_name(get_role_location(role))
    if not p_loc or not r_loc:
        return None
    return 100.0 if p_loc == r_loc else 0.0


def calculate_salary_preference_score(profile, role) -> float | None:
    expectation = normalize_decimal(getattr(profile, "salary_expectation", None))
    salary_min  = normalize_decimal(getattr(role, "estimated_salary_min_cop", None))
    salary_max  = normalize_decimal(getattr(role, "estimated_salary_max_cop", None))

    if expectation is None or (salary_min is None and salary_max is None):
        return None
    guaranteed = salary_max or salary_min
    if guaranteed is None or guaranteed <= 0:
        return None
    if salary_min is not None and expectation < salary_min:
        return 100.0
    if salary_max is not None and expectation <= salary_max:
        return 100.0
    return round(min(max(float((guaranteed / expectation) * Decimal("100")), 0.0), 100.0), 2)


def calculate_weighted_match_score(breakdown: dict[str, float]) -> float:
    total = (
        breakdown["skill_match"]       * settings.SKILL_MATCH_WEIGHT
        + breakdown["experience_match"]  * settings.EXPERIENCE_MATCH_WEIGHT
        + breakdown["education_match"]   * settings.EDUCATION_MATCH_WEIGHT
        + breakdown["preferences_match"] * settings.PREFERENCES_MATCH_WEIGHT
    )
    return round(min(max(total, 0.0), 100.0), 2)


def calculate_skill_match_for_role(normalized_user_skills: set[str], role) -> float:
    if not normalized_user_skills:
        return 0.0
    requirements = get_unique_role_requirements(role)
    if not requirements:
        return 0.0
    total_weight = sum(r.importance_weight for r in requirements)
    if total_weight <= 0:
        return 0.0
    matched = sum(r.importance_weight for r in requirements if r.normalized_name in normalized_user_skills)
    return round(min(max((matched / total_weight) * 100, 0.0), 100.0), 2)


def detect_skill_gaps_for_role(normalized_user_skills: set[str], role) -> list[dict]:
    requirements = get_unique_role_requirements(role)
    return [
        {"name": r.name, "importance_weight": r.importance_weight, "is_required": r.is_required}
        for r in requirements
        if r.normalized_name not in normalized_user_skills
    ]


def calculate_experience_match_for_role(profile, experiences, role) -> float:
    if not profile or not experiences:
        return 0.0
    required = get_required_experience_months(role)
    if required <= 0:
        return 100.0
    actual = get_total_experience_months(experiences)
    if actual <= 0:
        return 0.0
    return round(min(max((actual / required) * 100, 0.0), 100.0), 2)


def calculate_education_match_for_role(profile, role) -> float:
    if not profile or not profile.career:
        return 0.0
    if normalize_skill_name(profile.career) == normalize_skill_name(role.name):
        return 100.0
    career_domains = detect_education_domains(profile.career)
    if not career_domains:
        return 0.0
    role_domains = get_role_education_domains(role)
    if not role_domains:
        return 0.0
    best = 0.0
    for cd in career_domains:
        affinity = _EDUCATION_DOMAIN_AFFINITY.get(cd, {})
        for rd in role_domains:
            best = max(best, affinity.get(rd, 0.0))
    return round(min(max(best, 0.0), 100.0), 2)


def calculate_preferences_match_for_role(profile, role) -> float:
    if not profile:
        return 0.0
    scores = [
        s for s in (
            calculate_location_preference_score(profile, role),
            calculate_salary_preference_score(profile, role),
        )
        if s is not None
    ]
    if not scores:
        return 0.0
    return round(min(max(sum(scores) / len(scores), 0.0), 100.0), 2)
