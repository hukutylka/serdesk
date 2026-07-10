from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, get_current_user, verify_password
from app.db.session import get_session
from app.models import AccountStatus, AuditAction, User
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.services.clients import log_action

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
):
    result = await session.execute(select(User).where(User.login == payload.login))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    if user.account_status == AccountStatus.BLOCKED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Учётная запись заблокирована")

    token = create_access_token(user.id, user.login, user.role.value)
    await log_action(
        session,
        user_id=user.id,
        action=AuditAction.LOGIN,
        entity_type="user",
        entity_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    await session.commit()
    return TokenResponse(
        access_token=token,
        user=UserOut(id=user.id, login=user.login, full_name=user.full_name, role=user.role),
    )


@router.get("/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return UserOut(id=user.id, login=user.login, full_name=user.full_name, role=user.role)
