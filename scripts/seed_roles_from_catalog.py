import argparse
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import models  # noqa: F401 - ensures model metadata is loaded
from core.database import SessionLocal
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.role_skill import RoleSkill
from models.technology import Technology

CATEGORY_MAP = {
    "software": JobRoleCategory.TECH,
    "clouddevops": JobRoleCategory.TECH,
    "infra": JobRoleCategory.TECH,
    "ops": JobRoleCategory.TECH,
    "security": JobRoleCategory.TECH,
    "erp": JobRoleCategory.TECH,
    "qa": JobRoleCategory.TECH,
    "dataai": JobRoleCategory.DATA,
    "digital": JobRoleCategory.DESIGN,
    "productux": JobRoleCategory.DESIGN,
}

SENIORITY_MAP = {
    "junior": SeniorityLevel.JUNIOR,
    "semi senior": SeniorityLevel.MID,
    "semisenior": SeniorityLevel.MID,
    "mid": SeniorityLevel.MID,
    "senior": SeniorityLevel.SENIOR,
}

ENGLISH_ORDER = ["A1", "A2", "B1", "B2", "C1", "C2"]
ENGLISH_RANK = {level: idx for idx, level in enumerate(ENGLISH_ORDER)}


@dataclass
class RoleNormalized:
    name: str
    description: str | None
    category: JobRoleCategory
    seniority: SeniorityLevel
    min_english_level: RoleEnglishLevel
    salary_min: Decimal | None
    salary_max: Decimal | None
    technologies: list[str]


def _normalize_key(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _parse_currency_number(text: str) -> Decimal | None:
    cleaned = re.sub(r"[^0-9]", "", text)
    if not cleaned:
        return None
    return Decimal(cleaned)


def _parse_salary_range(raw: str | None) -> tuple[Decimal | None, Decimal | None]:
    if not raw:
        return None, None

    tokens = re.findall(r"\d[\d\.,]*", raw)
    values: list[Decimal] = []
    for token in tokens:
        parsed = _parse_currency_number(token)
        if parsed is not None:
            values.append(parsed)

    if not values:
        return None, None

    if len(values) == 1:
        if "+" in raw:
            return values[0], None
        return values[0], values[0]

    minimum, maximum = values[0], values[1]
    if "+" in raw:
        return minimum, None
    return minimum, maximum


def _map_category(raw: str | None) -> JobRoleCategory:
    key = _normalize_key(raw)
    mapped = CATEGORY_MAP.get(key)
    if mapped:
        return mapped

    # Conservative fallback: unknown categories are treated as TECH to avoid enum errors.
    return JobRoleCategory.TECH


def _map_seniority(raw: str | None) -> SeniorityLevel:
    key = _normalize_key(raw)
    mapped = SENIORITY_MAP.get(key)
    if mapped:
        return mapped
    return SeniorityLevel.MID


def _map_english_level(raw: str | None) -> RoleEnglishLevel:
    if not raw:
        return RoleEnglishLevel.B1

    found_levels = re.findall(r"A1|A2|B1|B2|C1|C2", raw.upper())
    if not found_levels:
        return RoleEnglishLevel.B1

    min_level = min(found_levels, key=lambda level: ENGLISH_RANK[level])
    return RoleEnglishLevel[min_level]


def _extract_technologies(role: dict[str, Any]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []

    for source_key in ("technical_stack", "technological_tools"):
        raw_items = role.get(source_key, [])
        if not isinstance(raw_items, list):
            continue

        for item in raw_items:
            if not isinstance(item, str):
                continue
            cleaned = item.strip()
            if not cleaned:
                continue

            normalized = cleaned.lower()
            if normalized in seen:
                continue

            seen.add(normalized)
            ordered.append(cleaned)

    return ordered


def _pick_salary_for_seniority(role: dict[str, Any], seniority: SeniorityLevel) -> tuple[Decimal | None, Decimal | None]:
    salary_block = role.get("salary_range_reference_cop_month")
    if not isinstance(salary_block, dict):
        return None, None

    if seniority == SeniorityLevel.JUNIOR:
        raw = salary_block.get("junior")
    elif seniority == SeniorityLevel.SENIOR:
        raw = salary_block.get("senior")
    else:
        raw = salary_block.get("semi_senior")

    if not isinstance(raw, str):
        return None, None

    return _parse_salary_range(raw)


def normalize_role(raw_role: dict[str, Any]) -> RoleNormalized:
    name = str(raw_role.get("role_name", "")).strip()
    description = raw_role.get("description")
    description = description.strip() if isinstance(description, str) else None

    seniority = _map_seniority(raw_role.get("seniority"))
    salary_min, salary_max = _pick_salary_for_seniority(raw_role, seniority)

    return RoleNormalized(
        name=name,
        description=description,
        category=_map_category(raw_role.get("category")),
        seniority=seniority,
        min_english_level=_map_english_level(raw_role.get("english_level_recommended")),
        salary_min=salary_min,
        salary_max=salary_max,
        technologies=_extract_technologies(raw_role),
    )


def load_catalog(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))

    if isinstance(data, dict) and isinstance(data.get("roles"), list):
        return data["roles"]

    if isinstance(data, list):
        return data

    raise ValueError("El archivo JSON no tiene una estructura valida. Se esperaba {'roles': [...]} o una lista.")


def _get_or_create_role(session: Session, normalized: RoleNormalized) -> tuple[JobRole, bool]:
    role = session.query(JobRole).filter(JobRole.name == normalized.name).first()
    created = False

    if role is None:
        role = JobRole(name=normalized.name)
        session.add(role)
        created = True

    role.description = normalized.description
    role.category = normalized.category
    role.seniority_level = normalized.seniority
    role.min_english_level = normalized.min_english_level
    role.estimated_salary_min_cop = normalized.salary_min
    role.estimated_salary_max_cop = normalized.salary_max
    role.active = True

    session.flush()
    return role, created


def _get_or_create_technology(session: Session, name: str, cache: dict[str, Technology]) -> tuple[Technology, bool]:
    key = name.lower()
    technology = cache.get(key)
    if technology is not None:
        return technology, False

    technology = session.query(Technology).filter(Technology.name == name).first()
    created = False

    if technology is None:
        technology = Technology(name=name)
        session.add(technology)
        session.flush()
        created = True

    cache[key] = technology
    return technology, created


def seed_roles(catalog_path: Path, dry_run: bool = False) -> None:
    raw_roles = load_catalog(catalog_path)

    session = SessionLocal()
    created_roles = 0
    updated_roles = 0
    created_technologies = 0
    replaced_role_skills = 0

    try:
        tech_cache: dict[str, Technology] = {}

        for raw_role in raw_roles:
            normalized = normalize_role(raw_role)
            if not normalized.name:
                continue

            role, created = _get_or_create_role(session, normalized)
            if created:
                created_roles += 1
            else:
                updated_roles += 1

            session.query(RoleSkill).filter(RoleSkill.role_id == role.id).delete(synchronize_session=False)

            for index, technology_name in enumerate(normalized.technologies):
                technology, tech_created = _get_or_create_technology(session, technology_name, tech_cache)
                if tech_created:
                    created_technologies += 1

                weight = max(1, 10 - index)
                session.add(
                    RoleSkill(
                        role_id=role.id,
                        technology_id=technology.id,
                        importance_weight=weight,
                        is_required=index < 3,
                    )
                )
                replaced_role_skills += 1

        if dry_run:
            session.rollback()
            print("[DRY-RUN] No se escribieron cambios en la base de datos.")
        else:
            session.commit()

        print("Seed finalizado.")
        print(f"Roles creados: {created_roles}")
        print(f"Roles actualizados: {updated_roles}")
        print(f"Tecnologias creadas: {created_technologies}")
        print(f"Role skills insertados: {replaced_role_skills}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def resolve_catalog_path(user_path: str | None) -> Path:
    if user_path:
        return Path(user_path)

    candidates = [Path("roles_dialog.json"), Path("roles_catalog.json")]
    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        "No se encontro roles_dialog.json ni roles_catalog.json en la raiz del proyecto."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pobla job_roles, technologies y role_skills desde un archivo de catalogo JSON.",
    )
    parser.add_argument(
        "--file",
        dest="file_path",
        default=None,
        help="Ruta al archivo JSON. Si se omite, intenta roles_dialog.json y luego roles_catalog.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Procesa el archivo y valida inserciones sin confirmar cambios.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    catalog_path = resolve_catalog_path(args.file_path)

    if not catalog_path.exists():
        raise FileNotFoundError(f"No existe el archivo: {catalog_path}")

    seed_roles(catalog_path=catalog_path, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
