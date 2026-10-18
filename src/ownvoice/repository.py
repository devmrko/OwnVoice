from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    pass


class Record(Base):
    __tablename__ = "records"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    kind: Mapped[str] = mapped_column(String, index=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String, default=lambda: datetime.now(UTC).isoformat())


class Repository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, kind: str, key: str) -> Record | None:
        return self.session.scalar(select(Record).where(Record.kind == kind, Record.id == key))

    def list(self, kind: str) -> list[Record]:
        return list(
            self.session.scalars(select(Record).where(Record.kind == kind).order_by(Record.created_at.desc()))
        )

    def add(self, kind: str, key: str, data: dict[str, Any]) -> None:
        self.session.add(Record(id=key, kind=kind, data=data))
