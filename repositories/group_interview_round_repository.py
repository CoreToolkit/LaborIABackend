from datetime import datetime, timezone

from sqlalchemy.orm import Session, selectinload

from models.group_interview_round import GroupInterviewRound, GroupInterviewRoundStatus


class GroupInterviewRoundRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        group_interview_session_id: int,
        round_index: int,
        question_text: str | None = None,
        target_skill: str | None = None,
        difficulty: str | None = None,
        status: GroupInterviewRoundStatus = GroupInterviewRoundStatus.ACTIVE,
        created_by: int | None = None,
        metadata_json: dict | None = None,
        assigned_user_id: int | None = None,
    ) -> GroupInterviewRound:
        round_item = GroupInterviewRound(
            group_interview_session_id=group_interview_session_id,
            round_index=round_index,
            question_text=question_text,
            target_skill=target_skill,
            difficulty=difficulty,
            status=status,
            created_by=created_by,
            metadata_json=metadata_json,
            assigned_user_id=assigned_user_id,
        )
        self.db.add(round_item)
        self.db.commit()
        self.db.refresh(round_item)
        return round_item

    def get_by_id(self, round_id: str) -> GroupInterviewRound | None:
        return (
            self.db.query(GroupInterviewRound)
            .options(
                selectinload(GroupInterviewRound.group_interview_session),
                selectinload(GroupInterviewRound.creator),
            )
            .filter(GroupInterviewRound.id == round_id)
            .first()
        )

    def get_active_by_session_id(self, group_interview_session_id: int) -> GroupInterviewRound | None:
        return (
            self.db.query(GroupInterviewRound)
            .filter(
                GroupInterviewRound.group_interview_session_id == group_interview_session_id,
                GroupInterviewRound.status == GroupInterviewRoundStatus.ACTIVE,
            )
            .order_by(GroupInterviewRound.round_index.desc())
            .first()
        )

    def get_last_by_session_id(self, group_interview_session_id: int) -> GroupInterviewRound | None:
        return (
            self.db.query(GroupInterviewRound)
            .filter(GroupInterviewRound.group_interview_session_id == group_interview_session_id)
            .order_by(GroupInterviewRound.round_index.desc())
            .first()
        )

    def list_by_session_id(self, group_interview_session_id: int) -> list[GroupInterviewRound]:
        return (
            self.db.query(GroupInterviewRound)
            .filter(GroupInterviewRound.group_interview_session_id == group_interview_session_id)
            .order_by(GroupInterviewRound.round_index.asc())
            .all()
        )

    def close_round(self, round_item: GroupInterviewRound) -> GroupInterviewRound:
        round_item.status = GroupInterviewRoundStatus.CLOSED
        round_item.closed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(round_item)
        return round_item

    def get_assigned_user_ids_in_session(
        self, group_interview_session_id: int
    ) -> list[int]:
        """
        Retorna la lista ordenada de assigned_user_id de todas las rondas no-intro
        de la sesión (en orden de round_index ascendente).
        Se usa para calcular el turno siguiente en la rotación round-robin.
        """
        rows = (
            self.db.query(GroupInterviewRound.assigned_user_id)
            .filter(
                GroupInterviewRound.group_interview_session_id == group_interview_session_id,
                GroupInterviewRound.assigned_user_id.isnot(None),
            )
            .order_by(GroupInterviewRound.round_index.asc())
            .all()
        )
        return [row[0] for row in rows if row[0] is not None]
