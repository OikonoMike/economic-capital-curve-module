"""Подключение к PostgreSQL и операции с данными кривой MOEX"""

import os
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    """Базовый класс моделей SQLAlchemy"""


class CurveRun(Base):
    """История запусков загрузчика"""

    __tablename__ = "curve_run"
    __table_args__ = (
        CheckConstraint(
            "mode IN ('manual', 'scheduled')",
            name="ck_curve_run_mode",
        ),
        CheckConstraint(
            "status IN ('running', 'success', 'no_data', 'error')",
            name="ck_curve_run_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    requested_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="running"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class MoexRaw(Base):
    """Исходные точки кривой доходности, полученные от MOEX"""

    __tablename__ = "moex_raw"
    __table_args__ = (
        UniqueConstraint(
            "trade_date",
            "trade_time",
            "period_years",
            name="uq_moex_raw_date_time_period",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    trade_time: Mapped[str] = mapped_column(String(8), nullable=False)
    period_years: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), nullable=False
    )
    yield_percent: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False
    )
    run_id: Mapped[int] = mapped_column(
        ForeignKey("curve_run.id"), nullable=False
    )
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


def create_database_url() -> str:
    """Читает URL базы из переменной окружения или файла .env"""
    load_dotenv()
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "Не задан DATABASE_URL. Проверь файл .env в корне проекта."
        )

    return database_url


def create_db_engine(database_url: str | None = None) -> Engine:
    """Создаёт SQLAlchemy Engine для PostgreSQL"""
    url = database_url or create_database_url()
    return create_engine(url, pool_pre_ping=True)


def init_db(engine: Engine) -> None:
    """Создаёт таблицы, если они ещё не существуют"""
    Base.metadata.create_all(engine)


class CurveRepository:
    """Предоставляет операции для сохранения кривой и истории запусков"""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def create_run(self, requested_date: date, mode: str) -> int:
        """Создаёт запись о начале загрузки и возвращает её ID"""
        if mode not in {"manual", "scheduled"}:
            raise ValueError("mode должен быть 'manual' или 'scheduled'.")

        with Session(self.engine) as session:
            run = CurveRun(
                requested_date=requested_date,
                mode=mode,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            session.add(run)
            session.commit()
            session.refresh(run)
            return run.id

    def finish_run(
        self,
        run_id: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Завершает запуск и сохраняет его статус."""
        allowed_statuses = {"success", "no_data", "error"}
        if status not in allowed_statuses:
            raise ValueError(
                f"Недопустимый конечный статус: {status}"
            )

        with Session(self.engine) as session:
            run = session.get(CurveRun, run_id)
            if run is None:
                raise ValueError(f"Запуск с id={run_id} не найден.")

            run.status = status
            run.finished_at = datetime.now(timezone.utc)
            run.error_message = error_message
            session.commit()

    def has_successful_run(self, requested_date: date) -> bool:
        """Проверяет, есть ли успешная загрузка за эту дату"""
        with Session(self.engine) as session:
            statement = (
                select(CurveRun.id)
                .where(CurveRun.requested_date == requested_date)
                .where(CurveRun.status == "success")
                .limit(1)
            )
            return session.scalar(statement) is not None

    def save_curve(
        self,
        run_id: int,
        requested_date: date,
        points: list[dict[str, Any]],
    ) -> int:
        """
        Сохраняет точки кривой

        Возвращает число добавленных строк. Повторная вставка уже
        существующей точки с теми же датой, временем и сроком пропускается
        """
        now = datetime.now(timezone.utc)
        inserted_count = 0

        with Session(self.engine) as session:
            run = session.get(CurveRun, run_id)
            if run is None:
                raise ValueError(f"Запуск с id={run_id} не найден.")

            for point in points:
                point_date = date.fromisoformat(str(point["tradedate"]))
                if point_date != requested_date:
                    raise ValueError(
                        f"Дата точки {point_date} не совпадает "
                        f"с запрошенной {requested_date}."
                    )

                trade_time = str(point["tradetime"])
                period = Decimal(str(point["period"]))
                yield_value = Decimal(str(point["value"]))

                existing = session.scalar(
                    select(MoexRaw.id)
                    .where(MoexRaw.trade_date == point_date)
                    .where(MoexRaw.trade_time == trade_time)
                    .where(MoexRaw.period_years == period)
                    .limit(1)
                )

                if existing is not None:
                    continue

                session.add(
                    MoexRaw(
                        trade_date=point_date,
                        trade_time=trade_time,
                        period_years=period,
                        yield_percent=yield_value,
                        run_id=run_id,
                        fetched_at=now,
                    )
                )
                inserted_count += 1

            session.commit()

        return inserted_count