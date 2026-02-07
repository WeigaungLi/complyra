from __future__ import annotations

import json

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, get_tenant_id
from app.models.schemas import ChatRequest, ChatResponse, RetrievedChunk
from app.services.audit import log_event
from app.services.workflow import run_workflow

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/", response_model=ChatResponse)
def chat(payload: ChatRequest, tenant_id: str = Depends(get_tenant_id), user: dict = Depends(get_current_user)) -> ChatResponse:
    state = run_workflow(payload.question, tenant_id, user["user_id"])
    matches = state.get("retrieved", [])
    approval_required = state.get("approval_required", False)
    approval_id = state.get("approval_id")
    policy_blocked = state.get("policy_blocked", False)
    policy_violations = state.get("policy_violations", [])

    retrieved = [RetrievedChunk(text=text, score=score, source=source) for text, score, source in matches]

    if approval_required:
        answer = "Your request is pending human approval."
        status = "pending_approval"
    else:
        answer = state.get("draft_answer", "")
        status = "completed"

    if policy_blocked:
        action = "chat_blocked_by_policy"
    elif approval_required:
        action = "chat_pending"
    else:
        action = "chat_completed"

    log_event(
        tenant_id=tenant_id,
        user=user["username"],
        action=action,
        input_text=payload.question,
        output_text=answer,
        metadata=json.dumps(
            {
                "approval_id": approval_id or "",
                "policy_blocked": policy_blocked,
                "policy_violations": policy_violations,
            }
        ),
    )

    return ChatResponse(status=status, answer=answer, retrieved=retrieved, approval_id=approval_id)
