from sqlalchemy.orm import Session, selectinload
from models.group_interview_session import GroupInterviewSession


class GroupInterviewSessionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        session_code: str,
        host_id: int,
        role_id: str,
        difficulty: str | None = None,
    ) -> GroupInterviewSession:
        """Crear una nueva sesión grupal de entrevista."""
        group_session = GroupInterviewSession(
            session_code=session_code,
            host_id=host_id,
            role_id=role_id,
            difficulty=difficulty,
        )
        self.db.add(group_session)
        self.db.commit()
        self.db.refresh(group_session)
        return group_session

    def get_by_id(self, group_session_id: int) -> GroupInterviewSession | None:
        """Obtener sesión grupal por ID con todas sus relaciones."""
        return (
            self.db.query(GroupInterviewSession)
            .options(
                selectinload(GroupInterviewSession.host),
                selectinload(GroupInterviewSession.role),
                selectinload(GroupInterviewSession.interview_sessions),
            )
            .filter(GroupInterviewSession.id == group_session_id)
            .first()
        )

    def get_by_code(self, session_code: str) -> GroupInterviewSession | None:
        """Obtener sesión grupal por su código único."""
        return (
            self.db.query(GroupInterviewSession)
            .options(
                selectinload(GroupInterviewSession.host),
                selectinload(GroupInterviewSession.role),
                selectinload(GroupInterviewSession.interview_sessions),
            )
            .filter(GroupInterviewSession.session_code == session_code)
            .first()
        )

    def list_by_host_id(self, host_id: int) -> list[GroupInterviewSession]:
        """Listar todas las sesiones grupales creadas por un host."""
        return (
            self.db.query(GroupInterviewSession)
            .filter(GroupInterviewSession.host_id == host_id)
            .order_by(GroupInterviewSession.created_at.desc())
            .all()
        )

    def list_active(self, limit: int = 50) -> list[GroupInterviewSession]:
        """Listar sesiones grupales activas (recientemente creadas)."""
        return (
            self.db.query(GroupInterviewSession)
            .order_by(GroupInterviewSession.created_at.desc())
            .limit(limit)
            .all()
        )

    def delete(self, group_session_id: int) -> bool:
        """Eliminar una sesión grupal."""
        session = self.db.query(GroupInterviewSession).filter(
            GroupInterviewSession.id == group_session_id
        ).first()
        
        if not session:
            return False
        
        self.db.delete(session)
        self.db.commit()
        return True
