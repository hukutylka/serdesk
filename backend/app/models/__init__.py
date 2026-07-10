import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class UrgencyLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class UserRole(str, enum.Enum):
    SPECIALIST = "specialist"
    ADMIN = "admin"


class AccountStatus(str, enum.Enum):
    ACTIVE = "active"
    BLOCKED = "blocked"


class AuditAction(str, enum.Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    STATUS_CHANGE = "status_change"
    ASSIGN_SPECIALIST = "assign_specialist"
    COMMENT_ADDED = "comment_added"
    CLIENT_DEPARTMENT_UPDATED = "client_department_updated"
    REQUEST_CREATED = "request_created"
    CATEGORY_CREATED = "category_created"
    CATEGORY_UPDATED = "category_updated"
    USER_CREATED = "user_created"
    USER_BLOCKED = "user_blocked"
    USER_UNBLOCKED = "user_unblocked"
    STATUS_CREATED = "status_created"
    STATUS_UPDATED = "status_updated"
    REQUEST_DELETED = "request_deleted"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    requests: Mapped[list["Request"]] = relationship(back_populates="category")


class Status(Base):
    __tablename__ = "statuses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    requests: Mapped[list["Request"]] = relationship(back_populates="status")
    history_old: Mapped[list["RequestHistory"]] = relationship(
        back_populates="old_status",
        foreign_keys="RequestHistory.old_status_id",
    )
    history_new: Mapped[list["RequestHistory"]] = relationship(
        back_populates="new_status",
        foreign_keys="RequestHistory.new_status_id",
    )


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        Index(
            "uq_clients_full_name_normalized",
            text("lower(trim(full_name))"),
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    requests: Mapped[list["Request"]] = relationship(back_populates="client")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    login: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(
            UserRole,
            name="user_role",
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=UserRole.SPECIALIST,
        nullable=False,
    )
    account_status: Mapped[AccountStatus] = mapped_column(
        Enum(
            AccountStatus,
            name="account_status",
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=AccountStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    assigned_requests: Mapped[list["Request"]] = relationship(
        back_populates="specialist",
        foreign_keys="Request.specialist_id",
    )
    history_entries: Mapped[list["RequestHistory"]] = relationship(
        back_populates="changed_by",
    )
    audit_entries: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class Request(Base):
    __tablename__ = "requests"
    __table_args__ = (
        CheckConstraint(
            "completed_at IS NULL OR accepted_at IS NULL OR completed_at >= accepted_at",
            name="chk_requests_completed_after_accepted",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    cabinet: Mapped[str] = mapped_column(String(64), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    urgency: Mapped[UrgencyLevel] = mapped_column(
        Enum(
            UrgencyLevel,
            name="urgency_level",
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        default=UrgencyLevel.MEDIUM,
        nullable=False,
    )
    preferred_visit_time: Mapped[str | None] = mapped_column(String(255))
    status_id: Mapped[int] = mapped_column(ForeignKey("statuses.id"), nullable=False)
    specialist_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    specialist_comment: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    client: Mapped["Client"] = relationship(back_populates="requests")
    category: Mapped["Category"] = relationship(back_populates="requests")
    status: Mapped["Status"] = relationship(back_populates="requests")
    specialist: Mapped["User | None"] = relationship(
        back_populates="assigned_requests",
        foreign_keys=[specialist_id],
    )
    history: Mapped[list["RequestHistory"]] = relationship(
        back_populates="request",
        order_by="RequestHistory.changed_at.desc()",
    )


class RequestHistory(Base):
    __tablename__ = "request_history"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("requests.id", ondelete="CASCADE"))
    changed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    old_status_id: Mapped[int | None] = mapped_column(ForeignKey("statuses.id"))
    new_status_id: Mapped[int] = mapped_column(ForeignKey("statuses.id"), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    request: Mapped["Request"] = relationship(back_populates="history")
    changed_by: Mapped["User | None"] = relationship(back_populates="history_entries")
    old_status: Mapped["Status | None"] = relationship(
        back_populates="history_old",
        foreign_keys=[old_status_id],
    )
    new_status: Mapped["Status"] = relationship(
        back_populates="history_new",
        foreign_keys=[new_status_id],
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[AuditAction] = mapped_column(
        Enum(
            AuditAction,
            name="audit_action",
            create_type=False,
            values_callable=lambda enum_cls: [e.value for e in enum_cls],
        ),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(Integer)
    details: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User | None"] = relationship(back_populates="audit_entries")
