from __future__ import annotations

from sqlalchemy.orm import Session


def get_session_used_skills(db: Session, session_id: int, user_id: int) -> list[str]:
    """
    Returns skill names already covered in a session (Question.category != null),
    ordered by question creation (id asc) to preserve rotation sequence.
    """
    from models.interview_session import InterviewSession
    from models.question import Question

    rows = (
        db.query(Question.category)
        .join(InterviewSession, Question.interview_session_id == InterviewSession.id)
        .filter(
            Question.interview_session_id == session_id,
            InterviewSession.user_id == user_id,
            Question.category.isnot(None),
        )
        .order_by(Question.id.asc())
        .all()
    )
    return [row[0] for row in rows if row[0]]


def select_target_skill(profile_skills: list, used_skills: list[str]) -> str | None:
    """
    Picks the next skill to cover in a session.

    Strategy:
      1. Build the ordered list of skill names from the user's profile.
      2. Return the first profile skill not yet in used_skills (case-insensitive).
      3. If all skills have been covered at least once, restart the rotation using
         len(used_skills) % len(available) so the cycle continues indefinitely.

    Returns None if the profile has no named skills.
    """
    available = [
        str(s.name).strip()
        for s in profile_skills
        if getattr(s, "name", None) and str(s.name).strip()
    ]

    if not available:
        return None

    used_lower = {s.lower() for s in used_skills if s}

    uncovered = [s for s in available if s.lower() not in used_lower]
    if uncovered:
        return uncovered[0]

    return available[len(used_skills) % len(available)]
