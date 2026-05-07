from unittest.mock import MagicMock

from services.skill_selector import select_target_skill, get_session_used_skills


def _make_skill(name: str) -> MagicMock:
    s = MagicMock()
    s.name = name
    return s


# ── select_target_skill ───────────────────────────────────────────────────────

class TestSelectTargetSkill:
    def test_sin_skills_retorna_none(self):
        assert select_target_skill([], []) is None

    def test_skills_sin_nombre_retorna_none(self):
        skill = MagicMock()
        skill.name = None
        assert select_target_skill([skill], []) is None

    def test_primera_skill_cuando_ninguna_usada(self):
        skills = [_make_skill("Python"), _make_skill("SQL"), _make_skill("React")]
        assert select_target_skill(skills, []) == "Python"

    def test_segunda_skill_cuando_primera_ya_usada(self):
        skills = [_make_skill("Python"), _make_skill("SQL"), _make_skill("React")]
        assert select_target_skill(skills, ["Python"]) == "SQL"

    def test_tercera_skill_cuando_dos_usadas(self):
        skills = [_make_skill("Python"), _make_skill("SQL"), _make_skill("React")]
        assert select_target_skill(skills, ["Python", "SQL"]) == "React"

    def test_comparacion_case_insensitive(self):
        skills = [_make_skill("Python"), _make_skill("SQL")]
        assert select_target_skill(skills, ["python"]) == "SQL"

    def test_rotacion_cuando_todas_cubiertas(self):
        skills = [_make_skill("Python"), _make_skill("SQL"), _make_skill("React")]
        # 3 usadas → índice 3 % 3 = 0 → "Python"
        assert select_target_skill(skills, ["Python", "SQL", "React"]) == "Python"

    def test_rotacion_continua_correctamente(self):
        skills = [_make_skill("Python"), _make_skill("SQL")]
        # 4 usadas → índice 4 % 2 = 0 → "Python"
        assert select_target_skill(skills, ["Python", "SQL", "Python", "SQL"]) == "Python"
        # 5 usadas → índice 5 % 2 = 1 → "SQL"
        assert select_target_skill(skills, ["Python", "SQL", "Python", "SQL", "Python"]) == "SQL"

    def test_skills_con_espacios_en_nombre_son_ignorados(self):
        blank = MagicMock()
        blank.name = "   "
        valid = _make_skill("Docker")
        assert select_target_skill([blank, valid], []) == "Docker"

    def test_una_sola_skill_siempre_retorna_esa(self):
        skills = [_make_skill("Python")]
        assert select_target_skill(skills, []) == "Python"
        assert select_target_skill(skills, ["Python"]) == "Python"
        assert select_target_skill(skills, ["Python", "Python"]) == "Python"


# ── get_session_used_skills ───────────────────────────────────────────────────

class TestGetSessionUsedSkills:
    def _make_db(self, categories: list[str | None]) -> MagicMock:
        db = MagicMock()
        rows = [(c,) for c in categories]
        (
            db.query.return_value
            .join.return_value
            .filter.return_value
            .order_by.return_value
            .all.return_value
        ) = rows
        return db

    def test_retorna_skills_usadas_en_sesion(self):
        db = self._make_db(["Python", "SQL"])
        result = get_session_used_skills(db, session_id=1, user_id=1)
        assert result == ["Python", "SQL"]

    def test_filtra_valores_none(self):
        db = self._make_db(["Python", None, "SQL"])
        result = get_session_used_skills(db, session_id=1, user_id=1)
        assert result == ["Python", "SQL"]

    def test_sin_preguntas_retorna_lista_vacia(self):
        db = self._make_db([])
        result = get_session_used_skills(db, session_id=1, user_id=1)
        assert result == []
