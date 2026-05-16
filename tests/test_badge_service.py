from unittest.mock import MagicMock, patch

from models.badge import Badge
from services.badge_service import BadgeService


def _make_badge(id, condition_type, condition_value, name="Badge") -> Badge:
    b = MagicMock(spec=Badge)
    b.id = id
    b.name = name
    b.condition_type = condition_type
    b.condition_value = condition_value
    return b


def _service(badges=None, unlocked_ids=None) -> BadgeService:
    db = MagicMock()
    service = BadgeService(db)
    service.repo = MagicMock()
    service.repo.list_all.return_value = badges or []
    service.repo.list_by_user.return_value = [
        MagicMock(badge_id=bid) for bid in (unlocked_ids or [])
    ]
    service._count_completed_sessions = MagicMock(return_value=3)
    service._get_previous_session_score = MagicMock(return_value=50.0)
    return service


# ── _meets_condition ──────────────────────────────────────────────────────────

class TestMeetsCondition:
    def test_total_interviews_cumple(self):
        s = _service()
        badge = _make_badge(1, "total_interviews", "3")
        assert s._meets_condition(badge, {"total_interviews": 3, "session_score": None, "previous_score": None, "avg_score": 0})

    def test_total_interviews_no_cumple(self):
        s = _service()
        badge = _make_badge(1, "total_interviews", "5")
        assert not s._meets_condition(badge, {"total_interviews": 3, "session_score": None, "previous_score": None, "avg_score": 0})

    def test_session_score_gte_cumple(self):
        s = _service()
        badge = _make_badge(1, "session_score_gte", "80")
        assert s._meets_condition(badge, {"total_interviews": 1, "session_score": 85.0, "previous_score": None, "avg_score": 0})

    def test_session_score_gte_sin_score_no_cumple(self):
        s = _service()
        badge = _make_badge(1, "session_score_gte", "80")
        assert not s._meets_condition(badge, {"total_interviews": 1, "session_score": None, "previous_score": None, "avg_score": 0})

    def test_score_improvement_comeback_kid(self):
        s = _service()
        badge = _make_badge(1, "score_improvement_gte", "30")
        assert s._meets_condition(badge, {"total_interviews": 2, "session_score": 85.0, "previous_score": 50.0, "avg_score": 0})

    def test_score_improvement_no_cumple(self):
        s = _service()
        badge = _make_badge(1, "score_improvement_gte", "30")
        assert not s._meets_condition(badge, {"total_interviews": 2, "session_score": 70.0, "previous_score": 55.0, "avg_score": 0})

    def test_score_improvement_sin_sesion_previa_no_cumple(self):
        s = _service()
        badge = _make_badge(1, "score_improvement_gte", "30")
        assert not s._meets_condition(badge, {"total_interviews": 1, "session_score": 90.0, "previous_score": None, "avg_score": 0})

    def test_avg_score_gte_cumple(self):
        s = _service()
        badge = _make_badge(1, "avg_score_gte", "70")
        assert s._meets_condition(badge, {"total_interviews": 3, "session_score": 80.0, "previous_score": 60.0, "avg_score": 75.0})

    def test_condicion_desconocida_retorna_false(self):
        s = _service()
        badge = _make_badge(1, "unknown_type", "99")
        assert not s._meets_condition(badge, {"total_interviews": 100, "session_score": 100, "previous_score": 0, "avg_score": 100})

    def test_condition_type_none_retorna_false(self):
        s = _service()
        badge = _make_badge(1, None, None)
        assert not s._meets_condition(badge, {})


# ── check_and_unlock_badges ───────────────────────────────────────────────────

class TestCheckAndUnlockBadges:
    def test_desbloquea_badge_cumplido(self):
        badge = _make_badge(1, "total_interviews", "1", "Primera Entrevista")
        s = _service(badges=[badge], unlocked_ids=[])
        s._count_completed_sessions = MagicMock(return_value=1)
        s._get_previous_session_score = MagicMock(return_value=None)

        with patch("services.badge_service.UserMetricsService") as MockMetrics:
            MockMetrics.return_value.calculate_average_score.return_value = 80.0
            result = s.check_and_unlock_badges(user_id=1, session_id=1, session_score=80.0)

        assert len(result) == 1
        assert result[0].name == "Primera Entrevista"

    def test_no_desbloquea_badge_ya_obtenido(self):
        badge = _make_badge(1, "total_interviews", "1")
        s = _service(badges=[badge], unlocked_ids=[1])

        with patch("services.badge_service.UserMetricsService") as MockMetrics:
            MockMetrics.return_value.calculate_average_score.return_value = 80.0
            result = s.check_and_unlock_badges(user_id=1, session_id=1, session_score=80.0)

        assert result == []

    def test_no_desbloquea_badge_sin_cumplir_condicion(self):
        badge = _make_badge(1, "session_score_gte", "95", "Perfeccionista")
        s = _service(badges=[badge], unlocked_ids=[])

        with patch("services.badge_service.UserMetricsService") as MockMetrics:
            MockMetrics.return_value.calculate_average_score.return_value = 70.0
            result = s.check_and_unlock_badges(user_id=1, session_id=1, session_score=80.0)

        assert result == []

    def test_comeback_kid_con_mejora_suficiente(self):
        badge = _make_badge(1, "score_improvement_gte", "30", "Comeback Kid")
        s = _service(badges=[badge], unlocked_ids=[])
        s._count_completed_sessions = MagicMock(return_value=2)
        s._get_previous_session_score = MagicMock(return_value=50.0)

        with patch("services.badge_service.UserMetricsService") as MockMetrics:
            MockMetrics.return_value.calculate_average_score.return_value = 65.0
            result = s.check_and_unlock_badges(user_id=1, session_id=2, session_score=82.0)

        assert len(result) == 1
        assert result[0].name == "Comeback Kid"

    def test_sin_badges_en_db_retorna_vacio(self):
        s = _service(badges=[], unlocked_ids=[])

        with patch("services.badge_service.UserMetricsService") as MockMetrics:
            MockMetrics.return_value.calculate_average_score.return_value = 0.0
            result = s.check_and_unlock_badges(user_id=1, session_id=1, session_score=None)

        assert result == []
