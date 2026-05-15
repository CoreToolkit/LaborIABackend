"""
Pruebas de carga LaborIA Backend — Locust
==========================================
Escenarios:
  1. HealthUser        (weight=5)  — endpoints públicos sin auth
  2. DashboardUser     (weight=40) — usuario leyendo su dashboard, read-heavy
  3. InterviewUser     (weight=30) — usuario creando sesiones y preguntas
  4. AIEvaluationUser  (weight=15) — flujo completo con Azure OpenAI
  5. WebSocketUser     (weight=10) — sala grupal con WebSocket

Arranque rápido:
  locust -f locustfile.py --host http://localhost:8000 --users 50 --spawn-rate 5 --run-time 5m
"""

import json
import logging
import random
import time

import requests as _requests
from websocket import create_connection, WebSocketException

from locust import HttpUser, User, between, events, task
from locust.exception import RescheduleTask

from auth_helper import generate_token, auth_headers
from config import (
    AI_POLL_INTERVAL_SECONDS,
    AI_POLL_MAX_RETRIES,
    ROLE_IDS,
    SAMPLE_ANSWERS,
    SAMPLE_QUESTIONS,
    TEST_USERS,
)

logger = logging.getLogger(__name__)


# ── Utilidades ────────────────────────────────────────────────────────────────

def _pick_user() -> dict:
    return random.choice(TEST_USERS)


def _fire_ws_event(name: str, elapsed_ms: float, length: int = 0, exc=None):
    events.request.fire(
        request_type="WS",
        name=name,
        response_time=elapsed_ms,
        response_length=length,
        exception=exc,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. HealthUser — endpoints públicos
# ─────────────────────────────────────────────────────────────────────────────

class HealthUser(HttpUser):
    """
    Simula monitoreo continuo de salud. Sin auth. Peso bajo.
    Endpoints: /health/live, /health/ready
    """
    weight = 5
    wait_time = between(1, 2)

    @task(2)
    def health_live(self):
        self.client.get("/health/live", name="GET /health/live")

    @task(1)
    def health_ready(self):
        self.client.get("/health/ready", name="GET /health/ready")


# ─────────────────────────────────────────────────────────────────────────────
# 2. DashboardUser — usuario leyendo su dashboard
# ─────────────────────────────────────────────────────────────────────────────

class DashboardUser(HttpUser):
    """
    Simula un usuario navegando su dashboard: perfil, métricas, recomendaciones,
    historial de entrevistas y plan de mejora. Solo lectura — alto peso.
    """
    weight = 40
    wait_time = between(1, 3)

    def on_start(self):
        user = _pick_user()
        self._headers = auth_headers(user)

    # Perfil — más frecuente, es la primera pantalla
    @task(5)
    def get_profile(self):
        self.client.get("/api/profiles/me", headers=self._headers, name="GET /api/profiles/me")

    # Recomendaciones de roles — segunda pantalla más visitada
    @task(4)
    def get_recommendations(self):
        self.client.get(
            "/api/matching/recommendations",
            headers=self._headers,
            name="GET /api/matching/recommendations",
        )

    # Lista de sesiones de entrevista
    @task(3)
    def get_sessions(self):
        self.client.get(
            "/api/sessions?limit=10&include_meta=true",
            headers=self._headers,
            name="GET /api/sessions",
        )

    # Métricas de rendimiento
    @task(3)
    def get_metrics_user(self):
        self.client.get("/api/metrics/user", headers=self._headers, name="GET /api/metrics/user")

    # Score de empleabilidad
    @task(2)
    def get_employability(self):
        self.client.get(
            "/api/metrics/employability",
            headers=self._headers,
            name="GET /api/metrics/employability",
        )

    # Badges
    @task(2)
    def get_badges(self):
        self.client.get("/api/badges/me", headers=self._headers, name="GET /api/badges/me")

    # Resumen de reportes de entrevistas (dashboard card)
    @task(2)
    def get_reports_summary(self):
        self.client.get(
            "/api/interviews/reports/summary",
            headers=self._headers,
            name="GET /api/interviews/reports/summary",
        )

    # Plan de mejora
    @task(1)
    def get_improvement_plan(self):
        self.client.get(
            "/api/improvement-plan/me",
            headers=self._headers,
            name="GET /api/improvement-plan/me",
        )

    # Timeline de métricas
    @task(1)
    def get_timeline(self):
        self.client.get(
            "/api/metrics/timeline/summary?granularity=week",
            headers=self._headers,
            name="GET /api/metrics/timeline/summary",
        )

    # Salas grupales disponibles
    @task(1)
    def discover_group_sessions(self):
        self.client.get(
            "/api/group-sessions/discover",
            headers=self._headers,
            name="GET /api/group-sessions/discover",
        )

    # Listado de roles disponibles en la plataforma
    @task(2)
    def list_roles(self):
        self.client.get(
            "/api/roles?page=1&size=10&active=true",
            headers=self._headers,
            name="GET /api/roles",
        )

    # Recomendaciones personalizadas con LLM (endpoint separado de matching)
    @task(2)
    def get_recommendations_llm(self):
        self.client.get(
            "/api/recommendations?limit=10",
            headers=self._headers,
            name="GET /api/recommendations",
        )

    # Reporte detallado de una sesión individual
    @task(1)
    def get_session_report(self):
        with self.client.get(
            "/api/sessions?limit=1",
            headers=self._headers,
            name="GET /api/sessions [for-report]",
            catch_response=True,
        ) as resp:
            if resp.status_code == 200:
                items = resp.json()
                if isinstance(items, list) and items:
                    session_id = items[0].get("id")
                    resp.success()
                    self.client.get(
                        f"/api/interviews/{session_id}/report",
                        headers=self._headers,
                        name="GET /api/interviews/{id}/report",
                    )
                else:
                    resp.success()

    # Verificar token propio
    @task(1)
    def get_auth_me(self):
        self.client.get("/auth/me", headers=self._headers, name="GET /auth/me")


# ─────────────────────────────────────────────────────────────────────────────
# 3. InterviewUser — crea sesiones, preguntas y calcula matching
# ─────────────────────────────────────────────────────────────────────────────

class InterviewUser(HttpUser):
    """
    Simula un usuario activo que crea sesiones de entrevista y preguntas.
    También dispara el cálculo de matching. No llama a Azure OpenAI.
    """
    weight = 30
    wait_time = between(2, 5)

    def on_start(self):
        user = _pick_user()
        self._headers = auth_headers(user)
        self._session_id: int | None = None
        self._question_id: int | None = None

    @task(3)
    def create_session(self):
        with self.client.post(
            "/api/sessions",
            headers=self._headers,
            name="POST /api/sessions",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                self._session_id = resp.json().get("id")
                self._question_id = None  # Nueva sesión, reset pregunta
            else:
                resp.failure(f"Create session → {resp.status_code}: {resp.text[:120]}")

    @task(2)
    def create_question(self):
        if not self._session_id:
            raise RescheduleTask()

        q = random.choice(SAMPLE_QUESTIONS)
        with self.client.post(
            "/api/questions",
            headers=self._headers,
            json={
                "interview_session_id": self._session_id,
                "question_text": q["text"],
                "category": q["category"],
                "difficulty": q["difficulty"],
                "expected_topics": q["expected_topics"],
            },
            name="POST /api/questions",
            catch_response=True,
        ) as resp:
            if resp.status_code == 201:
                self._question_id = resp.json().get("id")
            elif resp.status_code in (400, 409):
                # La máquina de estados no permite crear pregunta ahora
                # (evaluación pendiente o flujo inválido) → marcar OK y resetear sesión
                resp.success()
                self._session_id = None
            else:
                resp.failure(f"Create question → {resp.status_code}: {resp.text[:120]}")

    @task(2)
    def calculate_matching(self):
        self.client.post(
            "/api/matching/calculate",
            headers=self._headers,
            name="POST /api/matching/calculate",
        )

    @task(1)
    def list_sessions(self):
        self.client.get(
            "/api/sessions?limit=5",
            headers=self._headers,
            name="GET /api/sessions",
        )

    @task(1)
    def create_group_session(self):
        with self.client.post(
            "/api/group-sessions",
            headers=self._headers,
            json={"role_id": random.choice(ROLE_IDS), "difficulty": "medium"},
            name="POST /api/group-sessions",
            catch_response=True,
        ) as resp:
            if resp.status_code in (200, 201):
                pass
            else:
                resp.failure(f"Create group session → {resp.status_code}: {resp.text[:120]}")


# ─────────────────────────────────────────────────────────────────────────────
# 4. AIEvaluationUser — flujo completo con evaluación real de Azure OpenAI
# ─────────────────────────────────────────────────────────────────────────────

class AIEvaluationUser(HttpUser):
    """
    Simula el flujo completo de entrevista individual con evaluación IA:
      sesión → pregunta → respuesta → polling hasta completado.

    Peso bajo (15) para no saturar la cuota de Azure OpenAI.
    Con 50 usuarios totales → ~7-8 usuarios de este tipo concurrentes.
    """
    weight = 15
    wait_time = between(5, 10)

    def on_start(self):
        user = _pick_user()
        self._headers = auth_headers(user)

    @task
    def full_interview_evaluation(self):
        # ── Paso 1: Crear sesión ───────────────────────────────────────────
        resp = self.client.post(
            "/api/sessions",
            headers=self._headers,
            name="POST /api/sessions [AI-setup]",
        )
        if resp.status_code != 201:
            logger.warning("AI eval: create session failed %s", resp.status_code)
            return
        session_id = resp.json().get("id")

        # ── Paso 2: Crear pregunta ─────────────────────────────────────────
        q = random.choice(SAMPLE_QUESTIONS)
        resp = self.client.post(
            "/api/questions",
            headers=self._headers,
            json={
                "interview_session_id": session_id,
                "question_text": q["text"],
                "category": q["category"],
                "difficulty": q["difficulty"],
                "expected_topics": q["expected_topics"],
            },
            name="POST /api/questions [AI-setup]",
        )
        if resp.status_code != 201:
            logger.warning("AI eval: create question failed %s", resp.status_code)
            return
        question_id = resp.json().get("id")

        # ── Paso 3: Enviar respuesta (dispara Azure OpenAI en background) ──
        answer = random.choice(SAMPLE_ANSWERS)
        resp = self.client.post(
            "/evaluations/answer",
            headers=self._headers,
            json={"question_id": question_id, "user_answer_text": answer},
            name="POST /evaluations/answer",
        )
        if resp.status_code != 202:
            logger.warning("AI eval: submit answer failed %s", resp.status_code)
            return
        evaluation_id = resp.json().get("evaluation_id")

        # ── Paso 4: Polling hasta que la evaluación esté lista ─────────────
        for attempt in range(AI_POLL_MAX_RETRIES):
            time.sleep(AI_POLL_INTERVAL_SECONDS)
            resp = self.client.get(
                f"/evaluations/evaluation/{evaluation_id}",
                headers=self._headers,
                name="GET /evaluations/evaluation/{id}",
            )
            if resp.status_code == 200:
                ev_status = resp.json().get("status")
                if ev_status in ("completed", "failed"):
                    logger.info(
                        "AI eval: %s after %d poll(s), status=%s",
                        evaluation_id,
                        attempt + 1,
                        ev_status,
                    )
                    return
            else:
                logger.warning("AI eval: poll failed %s", resp.status_code)
                return

        logger.warning("AI eval: timed out polling evaluation %s", evaluation_id)


# ─────────────────────────────────────────────────────────────────────────────
# 5. WebSocketUser — sala grupal con conexión WebSocket
# ─────────────────────────────────────────────────────────────────────────────

class WebSocketUser(User):
    """
    Simula un participante entrando a una sala grupal de entrevista via WebSocket.
    Flujo: descubrir sala → conectar WS → escuchar eventos → desconectar.
    Usa locust.User (no HttpUser) y reporta métricas con events.request.fire().
    """
    weight = 10
    wait_time = between(8, 15)

    def on_start(self):
        user = _pick_user()
        self._user = user
        self._token = generate_token(user)
        self._http_headers = auth_headers(user)
        self._session_code: str | None = None
        self._http = _requests.Session()
        self._http.headers.update(self._http_headers)
        # Obtener o crear sala en waiting
        self._session_code = self._get_or_create_group_session()

    def _get_or_create_group_session(self) -> str | None:
        host = self.host or "http://localhost:8000"
        try:
            r = self._http.get(f"{host}/api/group-sessions/discover", params={"limit": 20})
            if r.status_code == 200:
                sessions = [s for s in r.json() if s.get("status") == "waiting"]
                if sessions:
                    return random.choice(sessions)["session_code"]
        except Exception:
            logger.exception("WS user: error discovering sessions")

        # Si no hay sala disponible, crear una nueva
        try:
            r = self._http.post(
                f"{host}/api/group-sessions",
                json={"role_id": random.choice(ROLE_IDS), "difficulty": "medium"},
            )
            if r.status_code in (200, 201):
                return r.json().get("session_code")
        except Exception:
            logger.exception("WS user: error creating group session")

        return None

    @task
    def ws_connect_and_listen(self):
        if not self._session_code:
            # Reintentar conseguir sala
            self._session_code = self._get_or_create_group_session()
            if not self._session_code:
                return

        host = self.host or "http://localhost:8000"
        ws_host = host.replace("http://", "ws://").replace("https://", "wss://")
        user_id = self._user["id"]
        url = f"{ws_host}/api/ws/{self._session_code}/{user_id}?token={self._token}"

        # ── Conexión ──────────────────────────────────────────────────────
        t0 = time.perf_counter()
        ws = None
        try:
            ws = create_connection(url, timeout=10)
            elapsed = (time.perf_counter() - t0) * 1000
            _fire_ws_event("WS connect", elapsed)
        except (WebSocketException, ConnectionRefusedError, OSError) as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            _fire_ws_event("WS connect", elapsed, exc=exc)
            self._session_code = None  # Sala inaccesible, buscar otra en el próximo ciclo
            return

        # ── Recibir mensajes durante ~10 segundos ─────────────────────────
        try:
            ws.settimeout(5)
            deadline = time.perf_counter() + 10
            while time.perf_counter() < deadline:
                try:
                    t_recv = time.perf_counter()
                    raw = ws.recv()
                    elapsed = (time.perf_counter() - t_recv) * 1000
                    _fire_ws_event("WS recv", elapsed, length=len(raw) if raw else 0)
                except WebSocketException:
                    break
                except Exception:
                    break
        finally:
            try:
                ws.close()
                _fire_ws_event("WS close", 0)
            except Exception:
                pass
