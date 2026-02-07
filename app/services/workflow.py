from __future__ import annotations

from typing import List, Tuple, TypedDict

from langgraph.graph import END, START, StateGraph

from app.core.config import settings
from app.services.approvals import create_approval_request
from app.services.llm import generate_answer
from app.services.policy import evaluate_output_policy
from app.services.retrieval import search_chunks


class WorkflowState(TypedDict, total=False):
    question: str
    tenant_id: str
    user_id: str
    retrieved: List[Tuple[str, float, str]]
    draft_answer: str
    policy_blocked: bool
    policy_violations: List[str]
    approval_required: bool
    approval_id: str


def retrieve_node(state: WorkflowState) -> WorkflowState:
    matches = search_chunks(state["question"], settings.top_k, state["tenant_id"])
    return {"retrieved": matches}


def draft_node(state: WorkflowState) -> WorkflowState:
    contexts = [text for text, _, _ in state.get("retrieved", [])]
    raw_answer = generate_answer(state["question"], contexts)
    policy_result = evaluate_output_policy(raw_answer)
    return {
        "draft_answer": policy_result.answer,
        "policy_blocked": policy_result.blocked,
        "policy_violations": policy_result.matched_rules,
    }


def approval_node(state: WorkflowState) -> WorkflowState:
    approval_id = create_approval_request(
        user_id=state["user_id"],
        tenant_id=state["tenant_id"],
        question=state["question"],
        draft_answer=state["draft_answer"],
    )
    return {"approval_required": True, "approval_id": approval_id}


def final_node(_: WorkflowState) -> WorkflowState:
    return {"approval_required": False}


def route_after_draft(state: WorkflowState) -> str:
    if state.get("policy_blocked"):
        return "final"
    return "approval" if settings.require_approval else "final"


builder = StateGraph(WorkflowState)
builder.add_node("retrieve", retrieve_node)
builder.add_node("draft", draft_node)
builder.add_node("approval", approval_node)
builder.add_node("final", final_node)
builder.add_edge(START, "retrieve")
builder.add_edge("retrieve", "draft")
builder.add_conditional_edges("draft", route_after_draft, {"approval": "approval", "final": "final"})
builder.add_edge("approval", END)
builder.add_edge("final", END)
workflow_graph = builder.compile()


def run_workflow(question: str, tenant_id: str, user_id: str) -> WorkflowState:
    return workflow_graph.invoke({"question": question, "tenant_id": tenant_id, "user_id": user_id})
