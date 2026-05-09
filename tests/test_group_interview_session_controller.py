import os
import json
import uuid
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["JWT_SECRET"] = "test-secret"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import api.group_interview_sessions as group_sessions_module
import services.group_interview_orchestrator_service as orchestrator_module
from core.database import Base
from core.jwt import create_token
from models.group_interview_session import GroupInterviewSession
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.profile import EnglishLevel, Profile
from models.user import User


# ---------------------------------------------------------------------------
# Helpers para mockear TTSResult en tests de audio (AB#326, AB#325)
# ---------------------------------------------------------------------------

import base64 as _base64
import asyncio as _asyncio


def _tts_ok_result(text: str):
    """Coroutine que devuelve un TTSResult con audio simulado."""
    from services.group_interview_orchestrator_service import TTSResult

    async def _inner():
        return TTSResult(
            audio_b64=_base64.b64encode(b"fake-audio").decode(),
            tts_status="ok",
            tts_elapsed_ms=50,
        )
    return _inner()


def _tts_fallback_result():
    """Coroutine que devuelve un TTSResult de fallback."""
    from services.group_interview_orchestrator_service import TTSResult

    async def _inner():
        return TTSResult(
            audio_b64=None,
            tts_status="fallback",
            tts_error="El audio no está disponible en este momento. La pregunta se muestra en texto.",
            tts_elapsed_ms=100,
        )
    return _inner()


TEST_DB_PATH = Path("test.db")
test_engine = create_engine(f"sqlite:///{TEST_DB_PATH}")
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
app = FastAPI()
app.include_router(group_sessions_module.router, prefix="/api")
client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_test_database():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    def override_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[group_sessions_module.get_db] = override_db
    yield
    app.dependency_overrides.clear()


def _create_user(email: str | None = None) -> User:
    db = TestSessionLocal()
    try:
        unique_email = email or f"group-session-{uuid.uuid4().hex}@example.com"
        user = User(
            email=unique_email,
            name="Group Session User",
            profile_picture=None,
            oauth_provider="google",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _create_role(
    name: str = "Senior Python Developer",
    *,
    salary_min: int = 3000000,
    salary_max: int = 6000000,
    active: bool = True,
) -> JobRole:
    db = TestSessionLocal()
    try:
        role = JobRole(
            id=uuid.uuid4(),
            name=name,
            description=f"{name} description",
            category=JobRoleCategory.TECH,
            seniority_level=SeniorityLevel.MID,
            min_english_level=RoleEnglishLevel.B2,
            estimated_salary_min_cop=salary_min,
            estimated_salary_max_cop=salary_max,
            active=active,
        )
        db.add(role)
        db.commit()
        db.refresh(role)
        return role
    finally:
        db.close()


def _create_profile(user: User) -> Profile:
    db = TestSessionLocal()
    try:
        profile = Profile(
            user_id=user.id,
            full_name=user.name,
            career="Software Engineer",
            university="Example University",
            description="Backend engineer focused on APIs and Python.",
            english_level=EnglishLevel.ADVANCED,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile
    finally:
        db.close()


def _auth_headers_for_user(user: User) -> dict:
    token = create_token(
        {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "picture": user.profile_picture,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def test_create_group_session_authenticated():
    """Test crear una sesión grupal con usuario autenticado."""
    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["session_code"] is not None
    assert len(data["session_code"]) == 8  # 4 letters + 4 numbers
    assert data["host_id"] == user.id
    assert data["role_id"] == str(role.id)
    assert data["difficulty"] == "intermediate"
    assert data["status"] == "waiting"


def test_create_group_session_generates_unique_codes():
    """Test que cada sesión obtiene un código único."""
    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    # Crear 3 sesiones
    codes = []
    for _ in range(3):
        response = client.post(
            "/api/group-sessions",
            json={
                "role_id": str(role.id),
                "difficulty": "beginner",
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        codes.append(response.json()["session_code"])

    # Verificar que todos los códigos son únicos
    assert len(codes) == len(set(codes)), "Los códigos deben ser únicos"


def test_create_group_session_requires_authentication():
    """Test que crear sesión requiere autenticación."""
    role = _create_role()

    response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
    )

    assert response.status_code == 401


def test_get_group_session_by_code():
    """Test obtener sesión por código único."""
    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    # Crear sesión
    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "advanced",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]

    # Obtener por código
    get_response = client.get(
        f"/api/group-sessions/{session_code}",
        headers=auth_headers,
    )

    assert get_response.status_code == 200
    data = get_response.json()
    assert data["session_code"] == session_code
    assert data["host_id"] == user.id
    assert data["host"]["email"] == user.email
    assert data["role"]["id"] == str(role.id)
    assert data["status"] == "waiting"


def test_get_group_session_invalid_code():
    """Test obtener sesión con código que no existe."""
    user = _create_user()
    auth_headers = _auth_headers_for_user(user)

    response = client.get(
        "/api/group-sessions/INVALID1",
        headers=auth_headers,
    )

    assert response.status_code == 404
    assert "No se encontró" in response.json()["detail"]


def test_list_my_group_sessions():
    """Test listar mis sesiones como host."""
    user1 = _create_user()
    user2 = _create_user()
    role = _create_role()
    auth_headers_user1 = _auth_headers_for_user(user1)
    auth_headers_user2 = _auth_headers_for_user(user2)

    # User1 crea 2 sesiones
    for i in range(2):
        client.post(
            "/api/group-sessions",
            json={
                "role_id": str(role.id),
                "difficulty": "beginner" if i == 0 else "intermediate",
            },
            headers=auth_headers_user1,
        )

    # User2 crea 1 sesión
    client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "advanced",
        },
        headers=auth_headers_user2,
    )

    # User1 obtiene sus sesiones
    response = client.get(
        "/api/group-sessions",
        headers=auth_headers_user1,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Todas deben tener host_id = user1.id
    assert all(session["host_id"] == user1.id for session in data)

    # User2 obtiene sus sesiones
    response = client.get(
        "/api/group-sessions",
        headers=auth_headers_user2,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["host_id"] == user2.id


def test_list_active_sessions():
    """Test listar sesiones activas públicas."""
    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    # Crear 2 sesiones
    for i in range(2):
        client.post(
            "/api/group-sessions",
            json={
                "role_id": str(role.id),
                "difficulty": "beginner",
            },
            headers=auth_headers,
        )

    # Listar sesiones activas
    response = client.get(
        "/api/group-sessions/discover?limit=50",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2


def test_delete_group_session_as_host():
    """Test eliminar sesión como host (propietario)."""
    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    # Crear sesión
    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_id = create_response.json()["id"]

    # Eliminar sesión
    delete_response = client.delete(
        f"/api/group-sessions/{session_id}",
        headers=auth_headers,
    )

    assert delete_response.status_code == 204

    # Verificar que la sesión fue eliminada
    verify_response = client.get(
        f"/api/group-sessions/{create_response.json()['session_code']}",
        headers=auth_headers,
    )
    assert verify_response.status_code == 404


def test_delete_group_session_not_host():
    """Test que no puedes eliminar sesión de otro host."""
    user1 = _create_user()
    user2 = _create_user()
    role = _create_role()
    auth_headers_user1 = _auth_headers_for_user(user1)
    auth_headers_user2 = _auth_headers_for_user(user2)

    # User1 crea sesión
    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers_user1,
    )
    session_id = create_response.json()["id"]

    # User2 intenta eliminar
    delete_response = client.delete(
        f"/api/group-sessions/{session_id}",
        headers=auth_headers_user2,
    )

    assert delete_response.status_code == 403
    assert "Solo el host" in delete_response.json()["detail"]


def test_start_group_session_as_host():
    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]

    start_response = client.post(
        f"/api/group-sessions/{session_code}/start",
        headers=auth_headers,
    )

    assert start_response.status_code == 200
    assert start_response.json()["status"] == "in_progress"


def test_start_group_session_emits_interview_started_event(monkeypatch):
    emitted: list[tuple[str, str]] = []

    async def _fake_broadcast_text(message: str, room_id: str, sender_id: str = ""):
        emitted.append((message, room_id))

    monkeypatch.setattr(group_sessions_module.manager, "broadcast_text", _fake_broadcast_text)

    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]

    start_response = client.post(
        f"/api/group-sessions/{session_code}/start",
        headers=auth_headers,
    )

    assert start_response.status_code == 200
    assert len(emitted) == 1
    message, room_id = emitted[0]
    payload = json.loads(message)
    assert room_id == session_code
    assert payload["event"] == "interview_started"
    assert payload["session_code"] == session_code
    assert payload["status"] == "in_progress"


def test_start_group_session_not_host_returns_403():
    host = _create_user()
    other_user = _create_user()
    role = _create_role()
    host_headers = _auth_headers_for_user(host)
    other_headers = _auth_headers_for_user(other_user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=host_headers,
    )
    session_code = create_response.json()["session_code"]

    start_response = client.post(
        f"/api/group-sessions/{session_code}/start",
        headers=other_headers,
    )

    assert start_response.status_code == 403
    assert "Solo el host" in start_response.json()["detail"]


def test_start_group_session_already_started_returns_409():
    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]

    first_start = client.post(
        f"/api/group-sessions/{session_code}/start",
        headers=auth_headers,
    )
    assert first_start.status_code == 200

    second_start = client.post(
        f"/api/group-sessions/{session_code}/start",
        headers=auth_headers,
    )
    assert second_start.status_code == 409


def test_close_group_session_as_host():
    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]

    client.post(
        f"/api/group-sessions/{session_code}/start",
        headers=auth_headers,
    )

    close_response = client.post(
        f"/api/group-sessions/{session_code}/close",
        headers=auth_headers,
    )

    assert close_response.status_code == 200
    assert close_response.json()["status"] == "closed"


def test_close_group_session_emits_interview_closed_event(monkeypatch):
    emitted: list[tuple[str, str]] = []

    async def _fake_broadcast_text(message: str, room_id: str, sender_id: str = ""):
        emitted.append((message, room_id))

    monkeypatch.setattr(group_sessions_module.manager, "broadcast_text", _fake_broadcast_text)

    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]

    start_response = client.post(
        f"/api/group-sessions/{session_code}/start",
        headers=auth_headers,
    )
    assert start_response.status_code == 200

    close_response = client.post(
        f"/api/group-sessions/{session_code}/close",
        headers=auth_headers,
    )

    assert close_response.status_code == 200
    assert len(emitted) == 2
    message, room_id = emitted[1]
    payload = json.loads(message)
    assert room_id == session_code
    assert payload["event"] == "interview_closed"
    assert payload["session_code"] == session_code
    assert payload["status"] == "closed"


def test_close_group_session_not_host_returns_403():
    host = _create_user()
    other_user = _create_user()
    role = _create_role()
    host_headers = _auth_headers_for_user(host)
    other_headers = _auth_headers_for_user(other_user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=host_headers,
    )
    session_code = create_response.json()["session_code"]

    client.post(
        f"/api/group-sessions/{session_code}/start",
        headers=host_headers,
    )

    close_response = client.post(
        f"/api/group-sessions/{session_code}/close",
        headers=other_headers,
    )

    assert close_response.status_code == 403
    assert "Solo el host" in close_response.json()["detail"]


def test_close_group_session_when_waiting_returns_409():
    user = _create_user()
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]

    close_response = client.post(
        f"/api/group-sessions/{session_code}/close",
        headers=auth_headers,
    )

    assert close_response.status_code == 409


def test_create_next_round_creates_round_and_returns_200():
    user = _create_user()
    _create_profile(user)
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]

    client.post(
        f"/api/group-sessions/{session_code}/start",
        headers=auth_headers,
    )

    async def _fake_ask(self, question: str, system_prompt: str = None, temperature: float = None, max_tokens: int = 256, top_p: float = None):
        _ = (question, system_prompt, temperature, max_tokens, top_p)
        return "Explica como funciona la inyeccion de dependencias en FastAPI."

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(orchestrator_module.AzureOpenAIClient, "ask", _fake_ask)
    monkeypatch.setattr(
        orchestrator_module.GroupInterviewOrchestratorService,
        "_generate_tts_with_fallback",
        lambda self, text: _tts_fallback_result(),
    )

    try:
        next_round_response = client.post(
            f"/api/group-sessions/{session_code}/rounds/next",
            json={
                "target_skill": "Python",
                "difficulty": "intermediate",
            },
            headers=auth_headers,
        )
    finally:
        monkeypatch.undo()

    assert next_round_response.status_code == 200
    payload = next_round_response.json()
    assert payload["round_index"] == 1
    assert payload["difficulty"] == "intermediate"
    assert payload["target_skill"] == "Python"
    assert payload["question_text"]


def test_create_next_round_emits_round_started_and_question_generated(monkeypatch):
    emitted: list[tuple[str, str]] = []

    async def _fake_broadcast_text(message: str, room_id: str, sender_id: str = ""):
        _ = sender_id
        emitted.append((message, room_id))

    async def _fake_ask(self, question: str, system_prompt: str = None, temperature: float = None, max_tokens: int = 256, top_p: float = None):
        _ = (question, system_prompt, temperature, max_tokens, top_p)
        return "Cual es la diferencia entre concurrencia y paralelismo en Python?"

    monkeypatch.setattr(group_sessions_module.manager, "broadcast_text", _fake_broadcast_text)
    monkeypatch.setattr(orchestrator_module.AzureOpenAIClient, "ask", _fake_ask)
    monkeypatch.setattr(
        orchestrator_module.GroupInterviewOrchestratorService,
        "_generate_tts_with_fallback",
        lambda self, text: _tts_fallback_result(),
    )

    user = _create_user()
    _create_profile(user)
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]
    client.post(f"/api/group-sessions/{session_code}/start", headers=auth_headers)
    emitted.clear()

    response = client.post(
        f"/api/group-sessions/{session_code}/rounds/next",
        json={"target_skill": "Python"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    # Siempre se emiten 3 eventos: round_started, question_generated, y
    # question_audio_ready o tts_error (AB#326)
    assert len(emitted) == 3
    events = [json.loads(msg) for msg, _ in emitted]
    event_names = [e["event"] for e in events]
    assert event_names[0] == "round_started"
    assert event_names[1] == "question_generated"
    assert event_names[2] in ("question_audio_ready", "tts_error")


def test_create_next_round_emits_question_audio_ready_on_tts_success(monkeypatch):
    """AB#326: cuando TTS tiene éxito se emite question_audio_ready con audio_b64."""
    emitted: list[dict] = []

    async def _fake_broadcast_text(message: str, room_id: str, sender_id: str = ""):
        emitted.append(json.loads(message))

    async def _fake_ask(self, question, system_prompt=None, temperature=None, max_tokens=256, top_p=None):
        return "Explica el patron de diseño Observer."

    async def _fake_tts(self, text: str) -> bytes:
        return b"fake-audio-bytes"

    monkeypatch.setattr(group_sessions_module.manager, "broadcast_text", _fake_broadcast_text)
    monkeypatch.setattr(orchestrator_module.AzureOpenAIClient, "ask", _fake_ask)
    monkeypatch.setattr(
        orchestrator_module.GroupInterviewOrchestratorService,
        "_generate_tts_with_fallback",
        lambda self, text: _tts_ok_result(text),
    )

    user = _create_user()
    _create_profile(user)
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={"role_id": str(role.id), "difficulty": "intermediate"},
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]
    client.post(f"/api/group-sessions/{session_code}/start", headers=auth_headers)
    emitted.clear()

    response = client.post(
        f"/api/group-sessions/{session_code}/rounds/next",
        json={"target_skill": "Python"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    audio_event = next((e for e in emitted if e["event"] == "question_audio_ready"), None)
    assert audio_event is not None, "Debe emitirse question_audio_ready cuando TTS tiene éxito"
    assert audio_event["audio_b64"] is not None
    assert audio_event["question_text"]
    assert audio_event["round_id"]
    assert audio_event["round_index"] == 1


def test_create_next_round_emits_tts_error_on_tts_failure(monkeypatch):
    """AB#325 + AB#326: cuando TTS falla se emite tts_error con mensaje seguro."""
    emitted: list[dict] = []

    async def _fake_broadcast_text(message: str, room_id: str, sender_id: str = ""):
        emitted.append(json.loads(message))

    async def _fake_ask(self, question, system_prompt=None, temperature=None, max_tokens=256, top_p=None):
        return "Que es un deadlock?"

    monkeypatch.setattr(group_sessions_module.manager, "broadcast_text", _fake_broadcast_text)
    monkeypatch.setattr(orchestrator_module.AzureOpenAIClient, "ask", _fake_ask)
    monkeypatch.setattr(
        orchestrator_module.GroupInterviewOrchestratorService,
        "_generate_tts_with_fallback",
        lambda self, text: _tts_fallback_result(),
    )

    user = _create_user()
    _create_profile(user)
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={"role_id": str(role.id), "difficulty": "intermediate"},
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]
    client.post(f"/api/group-sessions/{session_code}/start", headers=auth_headers)
    emitted.clear()

    response = client.post(
        f"/api/group-sessions/{session_code}/rounds/next",
        json={"target_skill": "Python"},
        headers=auth_headers,
    )

    assert response.status_code == 200
    tts_error_event = next((e for e in emitted if e["event"] == "tts_error"), None)
    assert tts_error_event is not None, "Debe emitirse tts_error cuando TTS falla"
    assert tts_error_event["question_text"], "El texto de la pregunta debe estar presente en fallback"
    # AB#325: el mensaje expuesto al cliente debe ser seguro, no detalle crudo del proveedor
    assert "ElevenLabs" not in tts_error_event.get("tts_error", "")
    assert "xi-api-key" not in tts_error_event.get("tts_error", "")


def test_broadcast_reaches_all_participants_in_room(monkeypatch):
    """AB#327: el evento llega a todos los participantes de la sala."""
    import asyncio
    from services.websocket_service import ConnectionManager

    received: dict[str, list[str]] = {"user1": [], "user2": [], "user3": []}

    class _FakeWS:
        def __init__(self, user_id: str):
            self._user_id = user_id

        async def send_text(self, message: str):
            received[self._user_id].append(message)

    mgr = ConnectionManager()
    mgr.rooms["ROOM1"] = [
        ("user1", _FakeWS("user1")),
        ("user2", _FakeWS("user2")),
        ("user3", _FakeWS("user3")),
    ]

    asyncio.run(mgr.broadcast_text('{"event":"test"}', "ROOM1", sender_id=""))

    assert len(received["user1"]) == 1
    assert len(received["user2"]) == 1
    assert len(received["user3"]) == 1


def test_broadcast_continues_after_one_connection_fails(monkeypatch):
    """AB#327: si una conexión falla, las demás siguen recibiendo el evento."""
    import asyncio
    from services.websocket_service import ConnectionManager

    received: dict[str, list[str]] = {"user1": [], "user2": [], "user3": []}

    class _GoodWS:
        def __init__(self, user_id: str):
            self._user_id = user_id

        async def send_text(self, message: str):
            received[self._user_id].append(message)

    class _BrokenWS:
        async def send_text(self, message: str):
            raise RuntimeError("conexión rota")

    mgr = ConnectionManager()
    mgr.rooms["ROOM2"] = [
        ("user1", _GoodWS("user1")),
        ("user2", _BrokenWS()),       # esta falla
        ("user3", _GoodWS("user3")),
    ]

    # No debe lanzar excepción
    asyncio.run(mgr.broadcast_text('{"event":"test"}', "ROOM2", sender_id=""))

    # user1 y user3 deben haber recibido el mensaje a pesar del fallo de user2
    assert len(received["user1"]) == 1
    assert len(received["user3"]) == 1


def test_broadcast_isolation_between_rooms(monkeypatch):
    """AB#327: el broadcast de una sala no llega a otra sala."""
    import asyncio
    from services.websocket_service import ConnectionManager

    received: dict[str, list[str]] = {"roomA_user": [], "roomB_user": []}

    class _FakeWS:
        def __init__(self, user_id: str):
            self._user_id = user_id

        async def send_text(self, message: str):
            received[self._user_id].append(message)

    mgr = ConnectionManager()
    mgr.rooms["ROOMA"] = [("roomA_user", _FakeWS("roomA_user"))]
    mgr.rooms["ROOMB"] = [("roomB_user", _FakeWS("roomB_user"))]

    asyncio.run(mgr.broadcast_text('{"event":"only_for_A"}', "ROOMA", sender_id=""))

    assert len(received["roomA_user"]) == 1
    assert len(received["roomB_user"]) == 0, "El evento de ROOMA no debe llegar a ROOMB"


def test_create_next_round_returns_409_when_session_not_started():
    user = _create_user()
    _create_profile(user)
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]

    response = client.post(
        f"/api/group-sessions/{session_code}/rounds/next",
        json={"target_skill": "Python"},
        headers=auth_headers,
    )

    assert response.status_code == 409


def test_create_next_round_returns_403_for_non_host(monkeypatch):
    async def _fake_ask(self, question: str, system_prompt: str = None, temperature: float = None, max_tokens: int = 256, top_p: float = None):
        _ = (question, system_prompt, temperature, max_tokens, top_p)
        return "Pregunta cualquiera"

    monkeypatch.setattr(orchestrator_module.AzureOpenAIClient, "ask", _fake_ask)
    monkeypatch.setattr(
        orchestrator_module.GroupInterviewOrchestratorService,
        "_generate_tts_with_fallback",
        lambda self, text: _tts_fallback_result(),
    )

    host = _create_user()
    _create_profile(host)
    other_user = _create_user()
    _create_profile(other_user)
    role = _create_role()
    host_headers = _auth_headers_for_user(host)
    other_headers = _auth_headers_for_user(other_user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=host_headers,
    )
    session_code = create_response.json()["session_code"]
    client.post(f"/api/group-sessions/{session_code}/start", headers=host_headers)

    response = client.post(
        f"/api/group-sessions/{session_code}/rounds/next",
        json={"target_skill": "Python"},
        headers=other_headers,
    )

    assert response.status_code == 403


def test_create_next_round_returns_502_when_ai_fails(monkeypatch):
    async def _fake_ask(self, question: str, system_prompt: str = None, temperature: float = None, max_tokens: int = 256, top_p: float = None):
        _ = (question, system_prompt, temperature, max_tokens, top_p)
        raise Exception("azure down")

    monkeypatch.setattr(orchestrator_module.AzureOpenAIClient, "ask", _fake_ask)

    user = _create_user()
    _create_profile(user)
    role = _create_role()
    auth_headers = _auth_headers_for_user(user)

    create_response = client.post(
        "/api/group-sessions",
        json={
            "role_id": str(role.id),
            "difficulty": "intermediate",
        },
        headers=auth_headers,
    )
    session_code = create_response.json()["session_code"]
    client.post(f"/api/group-sessions/{session_code}/start", headers=auth_headers)

    response = client.post(
        f"/api/group-sessions/{session_code}/rounds/next",
        json={"target_skill": "Python"},
        headers=auth_headers,
    )

    assert response.status_code == 502


def test_create_next_round_contract_requires_authentication():
    response = client.post(
        "/api/group-sessions/ABCD1234/rounds/next",
        json={
            "target_skill": "Python",
        },
    )

    assert response.status_code == 401
