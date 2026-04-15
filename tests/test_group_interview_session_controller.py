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
from core.database import Base
from core.jwt import create_token
from models.group_interview_session import GroupInterviewSession
from models.job_role import JobRole, JobRoleCategory, RoleEnglishLevel, SeniorityLevel
from models.user import User


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
