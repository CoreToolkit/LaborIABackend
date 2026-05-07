from sqlalchemy.orm import Session

from models.group_interview_round import GroupInterviewRound, GroupInterviewRoundStatus
from repositories.group_interview_round_repository import GroupInterviewRoundRepository
from repositories.group_interview_session_repository import GroupInterviewSessionRepository


class GroupInterviewRoundService:
    def __init__(self, db: Session):
        self.db = db
        self.round_repo = GroupInterviewRoundRepository(db)
        self.group_session_repo = GroupInterviewSessionRepository(db)

    def get_active_round(self, group_session_id: int) -> GroupInterviewRound | None:
        return self.round_repo.get_active_by_session_id(group_session_id)

    def create_next_round(
        self,
        group_session_id: int,
        question_text: str | None = None,
        target_skill: str | None = None,
        difficulty: str | None = None,
        created_by: int | None = None,
        metadata_json: dict | None = None,
    ) -> GroupInterviewRound:
        session = self.group_session_repo.get_by_id(group_session_id)
        if not session:
            raise ValueError("Group interview session not found")

        active_round = self.round_repo.get_active_by_session_id(group_session_id)
        if active_round:
            self.round_repo.close_round(active_round)

        last_round = self.round_repo.get_last_by_session_id(group_session_id)
        next_index = 1 if not last_round else last_round.round_index + 1

        return self.round_repo.create(
            group_interview_session_id=group_session_id,
            round_index=next_index,
            question_text=question_text,
            target_skill=target_skill,
            difficulty=difficulty,
            status=GroupInterviewRoundStatus.ACTIVE,
            created_by=created_by,
            metadata_json=metadata_json,
        )

    def close_active_round(self, group_session_id: int) -> GroupInterviewRound | None:
        active_round = self.round_repo.get_active_by_session_id(group_session_id)
        if not active_round:
            return None
        return self.round_repo.close_round(active_round)