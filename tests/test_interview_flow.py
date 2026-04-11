from models.evaluation import EvaluationStatus
from services.interview_flow import (
    EVALUATION_COMPLETED,
    EVALUATION_FAILED,
    EVALUATION_PENDING,
    QUESTION_CREATED,
    SESSION_CREATED,
    VALID_STATES,
    can_enter_evaluation_pending,
    can_enter_question_created,
    can_enter_session_created,
    can_transition,
    get_allowed_next_states,
    resolve_next_state,
    resolve_pending_result_state,
    resolve_session_created_snapshot,
    state_from_evaluation_status,
    to_evaluation_status,
)


def test_flow_states_are_the_confirmed_states_only():
    assert set(VALID_STATES) == {
        SESSION_CREATED,
        QUESTION_CREATED,
        EVALUATION_PENDING,
        EVALUATION_COMPLETED,
        EVALUATION_FAILED,
    }


def test_confirmed_transitions_are_allowed():
    assert can_transition(SESSION_CREATED, QUESTION_CREATED)
    assert can_transition(QUESTION_CREATED, EVALUATION_PENDING)
    assert can_transition(EVALUATION_PENDING, EVALUATION_COMPLETED)
    assert can_transition(EVALUATION_PENDING, EVALUATION_FAILED)
    assert can_transition(EVALUATION_COMPLETED, QUESTION_CREATED)


def test_non_confirmed_transitions_are_rejected():
    assert not can_transition(SESSION_CREATED, EVALUATION_PENDING)
    assert not can_transition(EVALUATION_FAILED, QUESTION_CREATED)
    assert not can_transition(EVALUATION_COMPLETED, EVALUATION_PENDING)


def test_allowed_next_states_match_minimum_graph():
    assert set(get_allowed_next_states(SESSION_CREATED)) == {QUESTION_CREATED}
    assert set(get_allowed_next_states(QUESTION_CREATED)) == {EVALUATION_PENDING}
    assert set(get_allowed_next_states(EVALUATION_PENDING)) == {
        EVALUATION_COMPLETED,
        EVALUATION_FAILED,
    }
    assert set(get_allowed_next_states(EVALUATION_COMPLETED)) == {QUESTION_CREATED}
    assert get_allowed_next_states(EVALUATION_FAILED) == ()


def test_state_from_evaluation_status_uses_persisted_truth():
    assert state_from_evaluation_status(EvaluationStatus.PENDING) == EVALUATION_PENDING
    assert state_from_evaluation_status(EvaluationStatus.COMPLETED) == EVALUATION_COMPLETED
    assert state_from_evaluation_status(EvaluationStatus.FAILED) == EVALUATION_FAILED
    assert state_from_evaluation_status("PENDING") == EVALUATION_PENDING
    assert state_from_evaluation_status("completed") == EVALUATION_COMPLETED
    assert state_from_evaluation_status("FAILED") == EVALUATION_FAILED


def test_resolve_pending_result_state_only_returns_terminal_outcomes():
    assert resolve_pending_result_state(EvaluationStatus.COMPLETED) == EVALUATION_COMPLETED
    assert resolve_pending_result_state(EvaluationStatus.FAILED) == EVALUATION_FAILED
    assert resolve_pending_result_state(EvaluationStatus.PENDING) is None
    assert resolve_pending_result_state(None) is None


def test_to_evaluation_status_maps_supported_states():
    assert to_evaluation_status(EVALUATION_PENDING) == EvaluationStatus.PENDING
    assert to_evaluation_status(EVALUATION_COMPLETED) == EvaluationStatus.COMPLETED
    assert to_evaluation_status(EVALUATION_FAILED) == EvaluationStatus.FAILED


def test_resolve_next_state_for_confirmed_events():
    assert resolve_next_state(SESSION_CREATED, event="question_created") == QUESTION_CREATED
    assert resolve_next_state(QUESTION_CREATED, event="evaluation_pending") == EVALUATION_PENDING
    assert (
        resolve_next_state(
            EVALUATION_PENDING,
            event="evaluation_resolved",
            evaluation_status=EvaluationStatus.COMPLETED,
        )
        == EVALUATION_COMPLETED
    )
    assert (
        resolve_next_state(
            EVALUATION_PENDING,
            event="evaluation_resolved",
            evaluation_status=EvaluationStatus.FAILED,
        )
        == EVALUATION_FAILED
    )
    assert resolve_next_state(EVALUATION_COMPLETED, event="next_question") == QUESTION_CREATED


def test_guards_for_minimum_flow_requirements():
    assert can_enter_session_created(session_id=10, user_id=9)
    assert not can_enter_session_created(session_id=0, user_id=9)

    assert can_enter_question_created(interview_session_id=5)
    assert not can_enter_question_created(interview_session_id=None)

    assert can_enter_evaluation_pending(question_id=3, user_answer_text="respuesta")
    assert can_enter_evaluation_pending(question_id=-1, user_answer_text="respuesta")
    assert not can_enter_evaluation_pending(question_id=3, user_answer_text="   ")


def test_session_snapshot_uses_session_created_state():
    snapshot = resolve_session_created_snapshot(session_id=2, user_id=7)
    assert snapshot is not None
    assert snapshot.state == SESSION_CREATED
    assert snapshot.session_id == 2


def test_resolve_next_state_uses_guard_data_for_evaluation_pending():
    assert (
        resolve_next_state(
            QUESTION_CREATED,
            event="evaluation_pending",
            question_id=99,
            user_answer_text="respuesta valida",
        )
        == EVALUATION_PENDING
    )
    assert (
        resolve_next_state(
            QUESTION_CREATED,
            event="evaluation_pending",
            question_id=99,
            user_answer_text="   ",
        )
        is None
    )
