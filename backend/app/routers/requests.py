from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_current_user
from app.db.session import get_session
from app.models import AuditAction, Request, Status, UrgencyLevel, User
from app.schemas import RequestDetail, RequestListItem, RequestUpdate, SortField
from app.services.clients import log_action
from app.services.requests import (
    add_history,
    get_request_detail,
    get_status_by_name,
    list_requests,
    request_to_detail,
    request_to_list_item,
)

router = APIRouter(prefix="/api/requests", tags=["requests"])


@router.get("", response_model=list[RequestListItem])
async def get_requests(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    status_id: int | None = None,
    category_id: int | None = None,
    specialist_id: int | None = None,
    urgency: UrgencyLevel | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: SortField = SortField.created_at,
    sort_desc: bool = True,
):
    requests = await list_requests(
        session,
        search=search,
        status_id=status_id,
        category_id=category_id,
        specialist_id=specialist_id,
        urgency=urgency,
        date_from=date_from,
        date_to=date_to,
        sort_by=sort_by,
        sort_desc=sort_desc,
    )
    return [request_to_list_item(r) for r in requests]


@router.get("/{request_id}", response_model=RequestDetail)
async def get_request(
    request_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_user)],
):
    req = await get_request_detail(session, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")
    return request_to_detail(req)


@router.post("/{request_id}/accept", response_model=RequestDetail)
async def accept_request(
    request_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
):
    req = await get_request_detail(session, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    in_progress = await get_status_by_name(session, "В работе")
    if in_progress is None:
        raise HTTPException(status_code=500, detail="Статус «В работе» не найден")

    old_status_id = req.status_id
    req.status_id = in_progress.id
    req.specialist_id = user.id
    req.accepted_at = datetime.now(UTC)

    await add_history(
        session,
        request_id=req.id,
        changed_by_id=user.id,
        old_status_id=old_status_id,
        new_status_id=in_progress.id,
        comment="Заявка принята в работу",
    )
    await log_action(
        session,
        user_id=user.id,
        action=AuditAction.STATUS_CHANGE,
        entity_type="request",
        entity_id=req.id,
        details={"old_status_id": old_status_id, "new_status_id": in_progress.id},
    )
    await log_action(
        session,
        user_id=user.id,
        action=AuditAction.ASSIGN_SPECIALIST,
        entity_type="request",
        entity_id=req.id,
        details={"specialist_id": user.id},
    )
    await session.commit()
    req = await get_request_detail(session, request_id)
    return request_to_detail(req)


@router.patch("/{request_id}", response_model=RequestDetail)
async def update_request(
    request_id: int,
    payload: RequestUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
):
    req = await get_request_detail(session, request_id)
    if req is None:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    old_status_id = req.status_id

    if payload.status_id is not None:
        new_status = await session.get(Status, payload.status_id)
        if new_status is None or not new_status.is_active:
            raise HTTPException(status_code=400, detail="Неверный статус")
        if new_status.id != req.status_id:
            req.status_id = new_status.id
            completed = await get_status_by_name(session, "Завершена")
            if completed and new_status.id == completed.id:
                req.completed_at = datetime.now(UTC)
            await add_history(
                session,
                request_id=req.id,
                changed_by_id=user.id,
                old_status_id=old_status_id,
                new_status_id=new_status.id,
                comment="Статус изменён",
            )
            await log_action(
                session,
                user_id=user.id,
                action=AuditAction.STATUS_CHANGE,
                entity_type="request",
                entity_id=req.id,
                details={"old_status_id": old_status_id, "new_status_id": new_status.id},
            )

    if payload.specialist_id is not None:
        specialist = await session.get(User, payload.specialist_id)
        if specialist is None:
            raise HTTPException(status_code=400, detail="Специалист не найден")
        req.specialist_id = specialist.id
        await log_action(
            session,
            user_id=user.id,
            action=AuditAction.ASSIGN_SPECIALIST,
            entity_type="request",
            entity_id=req.id,
            details={"specialist_id": specialist.id},
        )

    if payload.specialist_comment is not None:
        req.specialist_comment = payload.specialist_comment.strip() or None
        await log_action(
            session,
            user_id=user.id,
            action=AuditAction.COMMENT_ADDED,
            entity_type="request",
            entity_id=req.id,
        )

    if payload.client_department is not None:
        req.client.department = payload.client_department.strip() or None
        await log_action(
            session,
            user_id=user.id,
            action=AuditAction.CLIENT_DEPARTMENT_UPDATED,
            entity_type="client",
            entity_id=req.client.id,
            details={"department": req.client.department},
        )

    await session.commit()
    req = await get_request_detail(session, request_id)
    return request_to_detail(req)
