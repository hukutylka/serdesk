from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_current_user
from app.db.session import get_session
from app.models import AccountStatus, Status, User
from app.schemas import StatsDashboard, StatusOut, UserAdminOut
from app.services.requests import get_stats

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/statuses", response_model=list[StatusOut])
async def list_statuses(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_user)],
):
    result = await session.execute(
        select(Status).where(Status.is_active.is_(True)).order_by(Status.sort_order)
    )
    return result.scalars().all()


@router.get("/stats", response_model=StatsDashboard)
async def dashboard_stats(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_user)],
):
    return await get_stats(session)


@router.get("/specialists", response_model=list[UserAdminOut])
async def list_specialists(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_current_user)],
):
    result = await session.execute(
        select(User)
        .where(User.account_status == AccountStatus.ACTIVE)
        .order_by(User.full_name)
    )
    users = result.scalars().all()
    return [
        UserAdminOut(
            id=u.id,
            login=u.login,
            full_name=u.full_name,
            role=u.role,
            account_status=u.account_status.value,
            created_at=u.created_at,
        )
        for u in users
    ]
