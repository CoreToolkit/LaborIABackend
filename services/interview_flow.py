from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from models.evaluation import EvaluationStatus


InterviewFlowState = Literal[
    "session_created",
    "question_created",
    "evaluation_pending",
    "evaluation_completed",
    "evaluation_failed",
]

FlowEvent = Literal[
    "question_created",
    "evaluation_pending",
    "evaluation_resolved",
    "next_question",
]


SESSION_CREATED: Final[InterviewFlowState] = "session_created"
QUESTION_CREATED: Final[InterviewFlowState] = "question_created"
EVALUATION_PENDING: Final[InterviewFlowState] = "evaluation_pending"
EVALUATION_COMPLETED: Final[InterviewFlowState] = "evaluation_completed"
EVALUATION_FAILED: Final[InterviewFlowState] = "evaluation_failed"

EVENT_QUESTION_CREATED: Final[FlowEvent] = "question_created"
EVENT_EVALUATION_PENDING: Final[FlowEvent] = "evaluation_pending"
EVENT_EVALUATION_RESOLVED: Final[FlowEvent] = "evaluation_resolved"
EVENT_NEXT_QUESTION: Final[FlowEvent] = "next_question"

VALID_STATES: Final[tuple[InterviewFlowState, ...]] = (
    SESSION_CREATED,
    QUESTION_CREATED,
    EVALUATION_PENDING,
    EVALUATION_COMPLETED,
    EVALUATION_FAILED,
)

VALID_TRANSITIONS: Final[dict[InterviewFlowState, set[InterviewFlowState]]] = {
    SESSION_CREATED: {QUESTION_CREATED},
    QUESTION_CREATED: {EVALUATION_PENDING},
    EVALUATION_PENDING: {EVALUATION_COMPLETED, EVALUATION_FAILED},
    EVALUATION_COMPLETED: {QUESTION_CREATED},
    EVALUATION_FAILED: set(),
}


@dataclass(frozen=True)
class InterviewFlowSnapshot:
    state: InterviewFlowState
    session_id: int | None = None
    question_id: int | None = None
    evaluation_id: str | None = None


class InterviewFlowTransitionError(ValueError):
    pass


class InterviewFlowGraphState(TypedDict, total=False):
    session_id: int | None
    question_id: int | None
    evaluation_id: str | None
    logical_state: InterviewFlowState | None
    event: FlowEvent | None
    evaluation_status: EvaluationStatus | str | None
    user_answer_text: str | None


def is_valid_state(state: str) -> bool:
    return state in VALID_STATES


def get_allowed_next_states(state: str) -> tuple[InterviewFlowState, ...]:
    if not is_valid_state(state):
        return ()
    return tuple(VALID_TRANSITIONS[state])  # type: ignore[index]


def can_transition(current_state: str, target_state: str) -> bool:
    if not is_valid_state(current_state) or not is_valid_state(target_state):
        return False
    return target_state in VALID_TRANSITIONS[current_state]  # type: ignore[index]


def ensure_transition(current_state: str, target_state: str) -> None:
    if can_transition(current_state, target_state):
        return
    raise InterviewFlowTransitionError(
        f"Invalid interview flow transition: {current_state} -> {target_state}"
    )


def can_enter_session_created(*, session_id: int | None, user_id: int | None) -> bool:
    return bool(session_id and session_id > 0 and user_id and user_id > 0)


def can_enter_question_created(*, interview_session_id: int | None) -> bool:
    return interview_session_id is not None


def can_enter_evaluation_pending(*, question_id: int | None, user_answer_text: str | None) -> bool:
    if question_id is None:
        return False
    if user_answer_text is None:
        return False
    return bool(user_answer_text.strip())


def normalize_evaluation_status(
    evaluation_status: EvaluationStatus | str | None,
) -> EvaluationStatus | None:
    if isinstance(evaluation_status, EvaluationStatus):
        return evaluation_status
    if evaluation_status is None:
        return None

    raw = str(evaluation_status).strip().lower()
    for status in EvaluationStatus:
        if raw == status.value or raw == status.name.lower():
            return status
    return None


def state_from_evaluation_status(
    evaluation_status: EvaluationStatus | str | None,
) -> InterviewFlowState | None:
    normalized = normalize_evaluation_status(evaluation_status)
    if normalized == EvaluationStatus.PENDING:
        return EVALUATION_PENDING
    if normalized == EvaluationStatus.COMPLETED:
        return EVALUATION_COMPLETED
    if normalized == EvaluationStatus.FAILED:
        return EVALUATION_FAILED
    return None


def to_evaluation_status(flow_state: str) -> EvaluationStatus | None:
    if flow_state == EVALUATION_PENDING:
        return EvaluationStatus.PENDING
    if flow_state == EVALUATION_COMPLETED:
        return EvaluationStatus.COMPLETED
    if flow_state == EVALUATION_FAILED:
        return EvaluationStatus.FAILED
    return None


def resolve_pending_result_state(
    evaluation_status: EvaluationStatus | str | None,
) -> InterviewFlowState | None:
    state = state_from_evaluation_status(evaluation_status)
    if state in {EVALUATION_COMPLETED, EVALUATION_FAILED}:
        return state
    return None


def resolve_session_created_snapshot(
    *,
    session_id: int | None,
    user_id: int | None,
) -> InterviewFlowSnapshot | None:
    if not can_enter_session_created(session_id=session_id, user_id=user_id):
        return None

    flow_state = _invoke_flow_graph(
        current_state=SESSION_CREATED,
        session_id=session_id,
    )
    if flow_state.get("logical_state") != SESSION_CREATED:
        return None

    return InterviewFlowSnapshot(
        state=SESSION_CREATED,
        session_id=session_id,
    )


def resolve_next_state(
    current_state: str,
    *,
    event: str,
    evaluation_status: EvaluationStatus | str | None = None,
    session_id: int | None = None,
    question_id: int | None = None,
    evaluation_id: str | None = None,
    user_answer_text: str | None = None,
) -> InterviewFlowState | None:
    if not is_valid_state(current_state):
        return None

    flow_state = _invoke_flow_graph(
        current_state=current_state,
        event=event,
        session_id=session_id,
        question_id=question_id,
        evaluation_id=evaluation_id,
        evaluation_status=evaluation_status,
        user_answer_text=user_answer_text,
    )

    candidate_state = flow_state.get("logical_state")
    if candidate_state is None or candidate_state == current_state:
        return None
    if candidate_state not in VALID_TRANSITIONS[current_state]:  # type: ignore[index]
        return None
    return candidate_state


def _session_created_node(_: InterviewFlowGraphState) -> InterviewFlowGraphState:
    return {"logical_state": SESSION_CREATED}


def _question_created_node(_: InterviewFlowGraphState) -> InterviewFlowGraphState:
    return {"logical_state": QUESTION_CREATED}


def _evaluation_pending_node(_: InterviewFlowGraphState) -> InterviewFlowGraphState:
    return {"logical_state": EVALUATION_PENDING}


def _evaluation_completed_node(_: InterviewFlowGraphState) -> InterviewFlowGraphState:
    return {"logical_state": EVALUATION_COMPLETED}


def _evaluation_failed_node(_: InterviewFlowGraphState) -> InterviewFlowGraphState:
    return {"logical_state": EVALUATION_FAILED}


def _route_from_start(state: InterviewFlowGraphState) -> InterviewFlowState | str:
    logical_state = state.get("logical_state")
    if logical_state is None or not is_valid_state(logical_state):
        return END
    return logical_state


def _route_from_session_created(state: InterviewFlowGraphState) -> InterviewFlowState | str:
    if state.get("event") != EVENT_QUESTION_CREATED:
        return END
    if not _can_route_to_question_created(state):
        return END
    return QUESTION_CREATED


def _route_from_question_created(state: InterviewFlowGraphState) -> InterviewFlowState | str:
    if state.get("event") != EVENT_EVALUATION_PENDING:
        return END
    if not _can_route_to_evaluation_pending(state):
        return END
    return EVALUATION_PENDING


def _route_from_evaluation_pending(state: InterviewFlowGraphState) -> InterviewFlowState | str:
    if state.get("event") != EVENT_EVALUATION_RESOLVED:
        return END

    resolved_state = resolve_pending_result_state(state.get("evaluation_status"))
    if resolved_state is None:
        return END
    return resolved_state


def _route_from_evaluation_completed(state: InterviewFlowGraphState) -> InterviewFlowState | str:
    if state.get("event") != EVENT_NEXT_QUESTION:
        return END
    if not _can_route_to_question_created(state):
        return END
    return QUESTION_CREATED


def _can_route_to_question_created(state: InterviewFlowGraphState) -> bool:
    interview_session_id = state.get("session_id")
    if interview_session_id is None:
        return True
    return can_enter_question_created(interview_session_id=interview_session_id)


def _can_route_to_evaluation_pending(state: InterviewFlowGraphState) -> bool:
    question_id = state.get("question_id")
    user_answer_text = state.get("user_answer_text")

    # Backward compatible default: if call site does not pass guard data, keep
    # transition resolution behavior from earlier versions.
    if question_id is None and user_answer_text is None:
        return True

    return can_enter_evaluation_pending(
        question_id=question_id,
        user_answer_text=user_answer_text,
    )


def _build_graph_state(
    *,
    current_state: str,
    event: str | None = None,
    session_id: int | None = None,
    question_id: int | None = None,
    evaluation_id: str | None = None,
    evaluation_status: EvaluationStatus | str | None = None,
    user_answer_text: str | None = None,
) -> InterviewFlowGraphState:
    logical_state: InterviewFlowState | None = None
    if is_valid_state(current_state):
        logical_state = current_state  # type: ignore[assignment]

    event_value: FlowEvent | None = None
    if event in {
        EVENT_QUESTION_CREATED,
        EVENT_EVALUATION_PENDING,
        EVENT_EVALUATION_RESOLVED,
        EVENT_NEXT_QUESTION,
    }:
        event_value = event  # type: ignore[assignment]

    return {
        "session_id": session_id,
        "question_id": question_id,
        "evaluation_id": evaluation_id,
        "logical_state": logical_state,
        "event": event_value,
        "evaluation_status": evaluation_status,
        "user_answer_text": user_answer_text,
    }


def _build_interview_flow_graph():
    graph = StateGraph(InterviewFlowGraphState)

    graph.add_node(SESSION_CREATED, _session_created_node)
    graph.add_node(QUESTION_CREATED, _question_created_node)
    graph.add_node(EVALUATION_PENDING, _evaluation_pending_node)
    graph.add_node(EVALUATION_COMPLETED, _evaluation_completed_node)
    graph.add_node(EVALUATION_FAILED, _evaluation_failed_node)

    graph.add_conditional_edges(
        START,
        _route_from_start,
        {
            SESSION_CREATED: SESSION_CREATED,
            QUESTION_CREATED: QUESTION_CREATED,
            EVALUATION_PENDING: EVALUATION_PENDING,
            EVALUATION_COMPLETED: EVALUATION_COMPLETED,
            EVALUATION_FAILED: EVALUATION_FAILED,
            END: END,
        },
    )
    graph.add_conditional_edges(
        SESSION_CREATED,
        _route_from_session_created,
        {
            QUESTION_CREATED: QUESTION_CREATED,
            END: END,
        },
    )
    graph.add_conditional_edges(
        QUESTION_CREATED,
        _route_from_question_created,
        {
            EVALUATION_PENDING: EVALUATION_PENDING,
            END: END,
        },
    )
    graph.add_conditional_edges(
        EVALUATION_PENDING,
        _route_from_evaluation_pending,
        {
            EVALUATION_COMPLETED: EVALUATION_COMPLETED,
            EVALUATION_FAILED: EVALUATION_FAILED,
            END: END,
        },
    )
    graph.add_conditional_edges(
        EVALUATION_COMPLETED,
        _route_from_evaluation_completed,
        {
            QUESTION_CREATED: QUESTION_CREATED,
            END: END,
        },
    )
    graph.add_edge(EVALUATION_FAILED, END)

    return graph.compile()


_INTERVIEW_FLOW_GRAPH = _build_interview_flow_graph()


def _invoke_flow_graph(
    *,
    current_state: str,
    event: str | None = None,
    session_id: int | None = None,
    question_id: int | None = None,
    evaluation_id: str | None = None,
    evaluation_status: EvaluationStatus | str | None = None,
    user_answer_text: str | None = None,
) -> InterviewFlowGraphState:
    initial_state = _build_graph_state(
        current_state=current_state,
        event=event,
        session_id=session_id,
        question_id=question_id,
        evaluation_id=evaluation_id,
        evaluation_status=evaluation_status,
        user_answer_text=user_answer_text,
    )
    result = _INTERVIEW_FLOW_GRAPH.invoke(initial_state)
    return result
