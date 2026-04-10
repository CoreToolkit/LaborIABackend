import secrets
import string
from sqlalchemy.orm import Session
from repositories.group_interview_session_repository import GroupInterviewSessionRepository
from exceptions.interview_session_exceptions import InterviewSessionNotFoundError


class GroupInterviewSessionService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = GroupInterviewSessionRepository(db)

    def _generate_unique_session_code(self) -> str:
        """
        Generar un código único y legible para la sesión grupal.
        Formato: 4 letras mayúsculas + 4 números (ej: ABCD1234)
        """
        while True:
            letters = "".join(
                secrets.choice(string.ascii_uppercase) for _ in range(4)
            )
            numbers = "".join(secrets.choice(string.digits) for _ in range(4))
            code = letters + numbers

            # Verificar que no exista en BD
            existing = self.repo.get_by_code(code)
            if not existing:
                return code

    def create_group_session(
        self,
        host_id: int,
        role_id: str,
        difficulty: str | None = None,
    ):
        """
        Crear una nueva sesión grupal de entrevista.
        
        Args:
            host_id: ID del usuario que inicia la sesión
            role_id: ID del rol de trabajo para esta sesión
            difficulty: Nivel de dificultad (opcional)
        
        Returns:
            GroupInterviewSession con código único generado
        """
        session_code = self._generate_unique_session_code()
        return self.repo.create(
            session_code=session_code,
            host_id=host_id,
            role_id=role_id,
            difficulty=difficulty,
        )

    def get_group_session_by_code(self, session_code: str):
        """Obtener sesión grupal por su código único."""
        session = self.repo.get_by_code(session_code)
        if not session:
            raise InterviewSessionNotFoundError(
                f"No se encontró sesión grupal con código: {session_code}"
            )
        return session

    def get_group_session_by_id(self, group_session_id: int):
        """Obtener sesión grupal por ID."""
        session = self.repo.get_by_id(group_session_id)
        if not session:
            raise InterviewSessionNotFoundError(
                f"No se encontró sesión grupal con ID: {group_session_id}"
            )
        return session

    def list_my_group_sessions(self, host_id: int):
        """Listar todas mis sesiones grupales como host."""
        return self.repo.list_by_host_id(host_id)

    def list_active_sessions(self, limit: int = 50):
        """Listar sesiones grupales activas disponibles para unirse."""
        return self.repo.list_active(limit=limit)

    def delete_group_session(self, group_session_id: int, host_id: int) -> bool:
        """
        Eliminar una sesión grupal (solo el host puede hacerlo).
        
        Args:
            group_session_id: ID de la sesión
            host_id: ID del usuario que solicita la eliminación
        
        Returns:
            True si se eliminó exitosamente
        """
        session = self.repo.get_by_id(group_session_id)
        if not session:
            raise InterviewSessionNotFoundError()
        
        if session.host_id != host_id:
            raise PermissionError("Solo el host puede eliminar la sesión grupal")
        
        return self.repo.delete(group_session_id)
