from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Category, Request
from app.schemas import (
    CategoryOut,
    ClientAutocomplete,
    PublicRequestCreate,
    PublicRequestResponse,
)
from app.services.clients import autocomplete_clients, get_or_create_client, log_action
from app.models import AuditAction
from app.services.requests import get_status_by_name

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(session: Annotated[AsyncSession, Depends(get_session)]):
    result = await session.execute(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.name)
    )
    return result.scalars().all()


@router.get("/clients/autocomplete", response_model=list[ClientAutocomplete])
async def clients_autocomplete(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: str = Query(min_length=2, max_length=100),
):
    clients = await autocomplete_clients(session, q)
    return clients


@router.post("/requests", response_model=PublicRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_request(
    payload: PublicRequestCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    category = await session.get(Category, payload.category_id)
    if category is None or not category.is_active:
        raise HTTPException(status_code=400, detail="Неверная категория")

    new_status = await get_status_by_name(session, "Новая")
    if new_status is None:
        raise HTTPException(status_code=500, detail="Статус «Новая» не найден в базе")

    client = await get_or_create_client(session, payload.full_name)
    request = Request(
        client_id=client.id,
        cabinet=payload.cabinet.strip(),
        category_id=payload.category_id,
        description=payload.description.strip(),
        urgency=payload.urgency,
        preferred_visit_time=payload.preferred_visit_time,
        status_id=new_status.id,
    )
    session.add(request)
    await session.flush()

    await log_action(
        session,
        user_id=None,
        action=AuditAction.REQUEST_CREATED,
        entity_type="request",
        entity_id=request.id,
        details={"client_id": client.id},
    )
    await session.commit()
    return PublicRequestResponse(id=request.id)
