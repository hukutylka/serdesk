from datetime import UTC, datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Category, Client, Request, RequestHistory, Status, UrgencyLevel, User, UserRole
from app.schemas import SortField, URGENCY_LABELS


URGENCY_ORDER = {
    UrgencyLevel.CRITICAL: 0,
    UrgencyLevel.HIGH: 1,
    UrgencyLevel.MEDIUM: 2,
    UrgencyLevel.LOW: 3,
}


async def get_status_by_name(session: AsyncSession, name: str) -> Status | None:
    result = await session.execute(select(Status).where(Status.name == name))
    return result.scalar_one_or_none()


def build_request_query(
    *,
    search: str | None = None,
    status_id: int | None = None,
    category_id: int | None = None,
    specialist_id: int | None = None,
    urgency: UrgencyLevel | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> Select:
    query = (
        select(Request)
        .options(
            selectinload(Request.client),
            selectinload(Request.category),
            selectinload(Request.status),
            selectinload(Request.specialist),
        )
        .join(Request.client)
        .join(Request.category)
        .join(Request.status)
    )

    if search:
        term = f"%{search.strip()}%"
        filters = [
            Client.full_name.ilike(term),
            Request.cabinet.ilike(term),
        ]
        if search.strip().isdigit():
            filters.append(Request.id == int(search.strip()))
        query = query.where(or_(*filters))

    if status_id is not None:
        query = query.where(Request.status_id == status_id)
    if category_id is not None:
        query = query.where(Request.category_id == category_id)
    if specialist_id is not None:
        query = query.where(Request.specialist_id == specialist_id)
    if urgency is not None:
        query = query.where(Request.urgency == urgency)
    if date_from is not None:
        query = query.where(Request.created_at >= date_from)
    if date_to is not None:
        query = query.where(Request.created_at <= date_to)

    return query


async def list_requests(
    session: AsyncSession,
    *,
    search: str | None = None,
    status_id: int | None = None,
    category_id: int | None = None,
    specialist_id: int | None = None,
    urgency: UrgencyLevel | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    sort_by: SortField = SortField.created_at,
    sort_desc: bool = True,
) -> list[Request]:
    query = build_request_query(
        search=search,
        status_id=status_id,
        category_id=category_id,
        specialist_id=specialist_id,
        urgency=urgency,
        date_from=date_from,
        date_to=date_to,
    )

    if sort_by == SortField.created_at:
        query = query.order_by(Request.created_at.desc() if sort_desc else Request.created_at.asc())
    elif sort_by == SortField.urgency:
        query = query.order_by(Request.urgency.asc() if sort_desc else Request.urgency.desc())
    else:
        query = query.order_by(Status.sort_order.asc() if not sort_desc else Status.sort_order.desc())

    result = await session.execute(query)
    requests = list(result.scalars().unique().all())

    if sort_by == SortField.urgency:
        requests.sort(key=lambda r: URGENCY_ORDER[r.urgency], reverse=sort_desc)

    return requests


async def get_request_detail(session: AsyncSession, request_id: int) -> Request | None:
    result = await session.execute(
        select(Request)
        .options(
            selectinload(Request.client),
            selectinload(Request.category),
            selectinload(Request.status),
            selectinload(Request.specialist),
            selectinload(Request.history).selectinload(RequestHistory.old_status),
            selectinload(Request.history).selectinload(RequestHistory.new_status),
            selectinload(Request.history).selectinload(RequestHistory.changed_by),
        )
        .where(Request.id == request_id)
    )
    return result.scalar_one_or_none()


async def add_history(
    session: AsyncSession,
    *,
    request_id: int,
    changed_by_id: int | None,
    old_status_id: int | None,
    new_status_id: int,
    comment: str | None = None,
) -> None:
    session.add(
        RequestHistory(
            request_id=request_id,
            changed_by_id=changed_by_id,
            old_status_id=old_status_id,
            new_status_id=new_status_id,
            comment=comment,
        )
    )


def request_to_list_item(req: Request) -> dict:
    return {
        "id": req.id,
        "created_at": req.created_at,
        "client_name": req.client.full_name,
        "cabinet": req.cabinet,
        "category_name": req.category.name,
        "urgency": req.urgency,
        "urgency_label": URGENCY_LABELS[req.urgency],
        "status_id": req.status_id,
        "status_name": req.status.name,
        "specialist": (
            {"id": req.specialist.id, "full_name": req.specialist.full_name}
            if req.specialist
            else None
        ),
    }


def request_to_detail(req: Request) -> dict:
    return {
        "id": req.id,
        "created_at": req.created_at,
        "client": {
            "id": req.client.id,
            "full_name": req.client.full_name,
            "department": req.client.department,
        },
        "cabinet": req.cabinet,
        "category_id": req.category_id,
        "category_name": req.category.name,
        "urgency": req.urgency,
        "urgency_label": URGENCY_LABELS[req.urgency],
        "description": req.description,
        "preferred_visit_time": req.preferred_visit_time,
        "status_id": req.status_id,
        "status_name": req.status.name,
        "specialist": (
            {"id": req.specialist.id, "full_name": req.specialist.full_name}
            if req.specialist
            else None
        ),
        "accepted_at": req.accepted_at,
        "completed_at": req.completed_at,
        "specialist_comment": req.specialist_comment,
        "history": [
            {
                "id": h.id,
                "changed_at": h.changed_at,
                "old_status_name": h.old_status.name if h.old_status else None,
                "new_status_name": h.new_status.name,
                "changed_by_name": h.changed_by.full_name if h.changed_by else None,
                "comment": h.comment,
            }
            for h in req.history
        ],
    }


async def get_stats(session: AsyncSession) -> dict:
    status_counts = await session.execute(
        select(Status.name, func.count(Request.id))
        .outerjoin(Request, Request.status_id == Status.id)
        .group_by(Status.id, Status.name, Status.sort_order)
        .order_by(Status.sort_order)
    )
    counts = {name: count for name, count in status_counts.all()}

    avg_result = await session.execute(
        select(
            func.avg(
                func.extract("epoch", Request.completed_at - Request.accepted_at) / 3600.0
            )
        ).where(Request.completed_at.is_not(None), Request.accepted_at.is_not(None))
    )
    avg_hours = avg_result.scalar_one()

    by_category = await session.execute(
        select(Category.name, func.count(Request.id))
        .outerjoin(Request, Request.category_id == Category.id)
        .group_by(Category.id, Category.name)
        .order_by(func.count(Request.id).desc())
    )

    by_specialist = await session.execute(
        select(User.full_name, func.count(Request.id))
        .outerjoin(Request, Request.specialist_id == User.id)
        .where(User.role == UserRole.SPECIALIST)
        .group_by(User.id, User.full_name)
        .order_by(func.count(Request.id).desc())
    )

    return {
        "new_count": counts.get("Новая", 0),
        "in_progress_count": counts.get("В работе", 0),
        "completed_count": counts.get("Завершена", 0),
        "avg_processing_hours": round(float(avg_hours), 2) if avg_hours else None,
        "by_category": [{"name": n, "count": c} for n, c in by_category.all()],
        "by_specialist": [{"name": n, "count": c} for n, c in by_specialist.all()],
    }
