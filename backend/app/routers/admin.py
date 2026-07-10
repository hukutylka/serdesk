from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import get_admin_user, get_current_user, hash_password
from app.db.session import get_session
from app.models import AccountStatus, AuditAction, Category, Status, User
from app.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    StatusCreate,
    StatusOut,
    StatusUpdate,
    UserAdminOut,
    UserCreate,
)
from app.services.clients import log_action

router = APIRouter(prefix="/api/admin", tags=["admin"])


# --- Categories ---


@router.get("/categories", response_model=list[CategoryOut])
async def admin_list_categories(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_admin_user)],
):
    result = await session.execute(select(Category).order_by(Category.name))
    return result.scalars().all()


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: CategoryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_admin_user)],
):
    category = Category(name=payload.name.strip())
    session.add(category)
    await session.flush()
    await log_action(
        session,
        user_id=user.id,
        action=AuditAction.CATEGORY_CREATED,
        entity_type="category",
        entity_id=category.id,
    )
    await session.commit()
    await session.refresh(category)
    return category


@router.patch("/categories/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    payload: CategoryUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_admin_user)],
):
    category = await session.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Категория не найдена")
    if payload.name is not None:
        category.name = payload.name.strip()
    if payload.is_active is not None:
        category.is_active = payload.is_active
    await log_action(
        session,
        user_id=user.id,
        action=AuditAction.CATEGORY_UPDATED,
        entity_type="category",
        entity_id=category.id,
    )
    await session.commit()
    await session.refresh(category)
    return category


# --- Statuses ---


@router.get("/statuses", response_model=list[StatusOut])
async def admin_list_statuses(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_admin_user)],
):
    result = await session.execute(select(Status).order_by(Status.sort_order))
    return result.scalars().all()


@router.post("/statuses", response_model=StatusOut, status_code=status.HTTP_201_CREATED)
async def create_status(
    payload: StatusCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_admin_user)],
):
    status_obj = Status(name=payload.name.strip(), sort_order=payload.sort_order)
    session.add(status_obj)
    await session.flush()
    await log_action(
        session,
        user_id=user.id,
        action=AuditAction.STATUS_CREATED,
        entity_type="status",
        entity_id=status_obj.id,
    )
    await session.commit()
    await session.refresh(status_obj)
    return status_obj


@router.patch("/statuses/{status_id}", response_model=StatusOut)
async def update_status(
    status_id: int,
    payload: StatusUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[User, Depends(get_admin_user)],
):
    status_obj = await session.get(Status, status_id)
    if status_obj is None:
        raise HTTPException(status_code=404, detail="Статус не найден")
    if payload.name is not None:
        status_obj.name = payload.name.strip()
    if payload.sort_order is not None:
        status_obj.sort_order = payload.sort_order
    if payload.is_active is not None:
        status_obj.is_active = payload.is_active
    await log_action(
        session,
        user_id=user.id,
        action=AuditAction.STATUS_UPDATED,
        entity_type="status",
        entity_id=status_obj.id,
    )
    await session.commit()
    await session.refresh(status_obj)
    return status_obj


# --- Users ---


@router.get("/users", response_model=list[UserAdminOut])
async def list_users(
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(get_admin_user)],
):
    result = await session.execute(select(User).order_by(User.full_name))
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


@router.post("/users", response_model=UserAdminOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: UserCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(get_admin_user)],
):
    existing = await session.execute(select(User).where(User.login == payload.login))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Логин уже занят")

    new_user = User(
        login=payload.login.strip(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        role=payload.role,
    )
    session.add(new_user)
    await session.flush()
    await log_action(
        session,
        user_id=admin.id,
        action=AuditAction.USER_CREATED,
        entity_type="user",
        entity_id=new_user.id,
    )
    await session.commit()
    await session.refresh(new_user)
    return UserAdminOut(
        id=new_user.id,
        login=new_user.login,
        full_name=new_user.full_name,
        role=new_user.role,
        account_status=new_user.account_status.value,
        created_at=new_user.created_at,
    )


@router.patch("/users/{user_id}/block", response_model=UserAdminOut)
async def block_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(get_admin_user)],
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Нельзя заблокировать себя")
    user.account_status = AccountStatus.BLOCKED
    await log_action(
        session,
        user_id=admin.id,
        action=AuditAction.USER_BLOCKED,
        entity_type="user",
        entity_id=user.id,
    )
    await session.commit()
    await session.refresh(user)
    return UserAdminOut(
        id=user.id,
        login=user.login,
        full_name=user.full_name,
        role=user.role,
        account_status=user.account_status.value,
        created_at=user.created_at,
    )


@router.patch("/users/{user_id}/unblock", response_model=UserAdminOut)
async def unblock_user(
    user_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
    admin: Annotated[User, Depends(get_admin_user)],
):
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.account_status = AccountStatus.ACTIVE
    await log_action(
        session,
        user_id=admin.id,
        action=AuditAction.USER_UNBLOCKED,
        entity_type="user",
        entity_id=user.id,
    )
    await session.commit()
    await session.refresh(user)
    return UserAdminOut(
        id=user.id,
        login=user.login,
        full_name=user.full_name,
        role=user.role,
        account_status=user.account_status.value,
        created_at=user.created_at,
    )
