from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditAction, AuditLog, Client


async def log_action(
    session: AsyncSession,
    *,
    user_id: int | None,
    action: AuditAction,
    entity_type: str,
    entity_id: int | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    session.add(
        AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
        )
    )


async def get_or_create_client(session: AsyncSession, full_name: str) -> Client:
    normalized = full_name.strip()
    result = await session.execute(
        select(Client).where(func.lower(func.trim(Client.full_name)) == normalized.lower())
    )
    client = result.scalar_one_or_none()
    if client is None:
        client = Client(full_name=normalized)
        session.add(client)
        await session.flush()
    return client


async def autocomplete_clients(session: AsyncSession, query: str, limit: int = 10) -> list[Client]:
    q = query.strip()
    if len(q) < 2:
        return []
    result = await session.execute(
        select(Client)
        .where(Client.full_name.ilike(f"%{q}%"))
        .order_by(Client.full_name)
        .limit(limit)
    )
    return list(result.scalars().all())
