"""Подключение к общей PostgreSQL БД и работа с данными MOEX"""

import os
from contextlib import contextmanager
from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    Text,
    Time,
    URL,
    UniqueConstraint,
    create_engine,
    select,
    text,
    Integer,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


class Base(DeclarativeBase):
    """Базовый класс моделей SQLAlchemy"""


class CurveRun(Base):
    """История запусков загрузчика"""

    __tablename__ = "curve_run"

    run_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    run_type: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by: Mapped[str] = mapped_column(Text, nullable=False)


class MoexRaw(Base):
    """Исходные точки кривой доходности MOEX"""

    __tablename__ = "moex_raw"
    __table_args__ = (
        UniqueConstraint("run_id", "tenor_years", name="uq_moex_raw_run_tenor"),
    )

    raw_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("curve_run.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    tenor_years: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False
    )
    rate_pct: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False
    )
    moex_tradetime: Mapped[time | None] = mapped_column(
        Time, nullable=True
    )
    loaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class DataCheck(Base):
    """Результаты проверок исходных данных MOEX"""

    __tablename__ = "data_check"

    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("curve_run.run_id", ondelete="CASCADE"),
        primary_key=True,
    )
    check_code: Mapped[str] = mapped_column(Text, primary_key=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)


class CalendarDay(Base):
    """Торговый календарь общей БД"""

    __tablename__ = "calendar"

    calendar_date: Mapped[date] = mapped_column(
        Date, primary_key=True
    )
    is_working_day: Mapped[bool] = mapped_column(nullable=False)
    is_trading_day: Mapped[bool] = mapped_column(nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
class Scenario(Base):
    """Справочник сценариев"""

    __tablename__ = "scenario"

    scenario_id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name_ru: Mapped[str] = mapped_column(Text, nullable=False)


class TenorGrid(Base):
    """Справочник тенор-бакетов"""

    __tablename__ = "tenor_grid"

    tenor_label: Mapped[str] = mapped_column(Text, primary_key=True)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    interval_name: Mapped[str] = mapped_column(Text, nullable=False)
    tenor_years: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False
    )
    t_mid_years: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False
    )


class CurvePoint(Base):
    """Рассчитанные точки кривой по сценариям"""

    __tablename__ = "curve_point"
    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "scenario_id",
            "tenor_label",
            name="uq_curve_point_run_scenario_tenor",
        ),
    )

    point_id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    )
    run_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("curve_run.run_id", ondelete="CASCADE"),
        nullable=False,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenario.scenario_id"), nullable=False
    )
    tenor_label: Mapped[str] = mapped_column(
        ForeignKey("tenor_grid.tenor_label"), nullable=False
    )
    tenor_years: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False
    )
    t_mid_years: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False
    )
    rate_pct: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False
    )
    discount_factor: Mapped[Decimal] = mapped_column(
        Numeric(18, 12), nullable=False
    )
    method: Mapped[str] = mapped_column(Text, nullable=False)
    is_interpolated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_extrapolated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


def create_db_engine() -> Engine:
    """Создаёт подключение к существующей БД без создания таблиц"""
    load_dotenv()

    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return create_engine(database_url, pool_pre_ping=True)

    password = os.getenv("LOADER_PASSWORD")
    if not password:
        raise RuntimeError(
            "Не задан DATABASE_URL или LOADER_PASSWORD в файле .env."
        )

    url = URL.create(
        drivername="postgresql+psycopg",
        username=os.getenv("DB_USER", "loader_rw"),
        password=password,
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "irrbb"),
    )
    return create_engine(url, pool_pre_ping=True)


class CurveRepository:
    """Операции с историей запусков, календарём и сырыми точками"""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def lock_pipeline_date(self, requested_date: date):
        """Serialize cron and HTTP loads for the same date in PostgreSQL."""
        if self.engine.dialect.name == "postgresql":
            with self.engine.begin() as connection:
                connection.execute(text("SET LOCAL lock_timeout = '5s'"))
                connection.execute(
                    text("SELECT pg_advisory_xact_lock(1116478338, :day)"),
                    {"day": requested_date.toordinal()},
                )
                yield
        else:
            yield

    def is_trading_day(self, requested_date: date) -> bool:
        """Проверяет торговый календарь; при отсутствии даты сообщает об ошибке."""
        with Session(self.engine) as session:
            calendar_day = session.get(CalendarDay, requested_date)

        if calendar_day is None:
            raise ValueError(
                f"Дата {requested_date} отсутствует в таблице calendar. "
                "Проверьте и заполните торговый календарь."
            )

        return (
            calendar_day.is_working_day
            and calendar_day.is_trading_day
        )

    def create_run(
        self,
        requested_date: date,
        mode: str,
        started_by: str = "scheduler",
        status: str = "running",
        error_message: str | None = None,
    ) -> int:
        """Создаёт запись о запуске и возвращает run_id"""
        if mode not in {"manual", "scheduled"}:
            raise ValueError("mode должен быть 'manual' или 'scheduled'.")

        now = datetime.now(timezone.utc)

        with Session(self.engine) as session:
            run = CurveRun(
                report_date=requested_date,
                run_type=mode,
                started_at=now,
                finished_at=now if status != "running" else None,
                status=status,
                error_message=error_message,
                started_by=started_by,
            )
            session.add(run)
            session.flush()
            run_id = run.run_id
            session.commit()
            return run_id

    def finish_run(
        self,
        run_id: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """Завершает запуск и записывает его результат"""
        allowed_statuses = {"success", "no_data", "error", "skipped"}
        if status not in allowed_statuses:
            raise ValueError(f"Недопустимый конечный статус: {status}")

        with Session(self.engine) as session:
            run = session.get(CurveRun, run_id)
            if run is None:
                raise ValueError(f"Запуск run_id={run_id} не найден.")

            run.status = status
            run.finished_at = datetime.now(timezone.utc)
            run.error_message = error_message
            session.commit()

    def has_successful_run(self, requested_date: date) -> bool:
        """Проверяет, есть ли успешный запуск за дату"""
        with Session(self.engine) as session:
            statement = (
                select(CurveRun.run_id)
                .where(CurveRun.report_date == requested_date)
                .where(CurveRun.status == "success")
                .limit(1)
            )
            return session.scalar(statement) is not None

    def save_data_checks(self, run_id: int, checks: dict) -> None:
        """
        Записывает результаты проверок в data_check.
        checks — результат run_all_checks().
        Использует session.merge() для upsert по PK (run_id, check_code).
        """
        with Session(self.engine) as session:
            for code, value in checks.items():
   	    # Пропускаем служебные ключи ДО распаковки
                if code in ('all_ok', 'error_summary'):
                    continue
                status, details = value
                check = DataCheck(
                    run_id=run_id,
                    check_code=code,
                    status=status,
                    details=details,
                )
                session.merge(check)
            session.commit()

    def save_curve(
        self,
        run_id: int,
        requested_date: date,
        points: list[dict[str, Any]],
    ) -> int:
        """Сохраняет исходные точки MOEX для конкретного запуска"""
        loaded_at = datetime.now(timezone.utc)
        inserted_count = 0

        with Session(self.engine) as session:
            run = session.get(CurveRun, run_id)
            if run is None:
                raise ValueError(f"Запуск run_id={run_id} не найден.")

            if run.report_date != requested_date:
                raise ValueError(
                    "Дата не совпадает с датой запуска."
                )

            for point in points:
                point_date = date.fromisoformat(str(point["tradedate"]))
                if point_date != requested_date:
                    raise ValueError(
                        f"Дата точки {point_date} не совпадает "
                        f"с запрошенной {requested_date}."
                    )

                tenor = Decimal(str(point["period"]))
                rate = Decimal(str(point["value"]))

                existing = session.scalar(
                    select(MoexRaw.raw_id)
                    .where(MoexRaw.run_id == run_id)
                    .where(MoexRaw.tenor_years == tenor)
                    .limit(1)
                )

                if existing is not None:
                    continue

                raw_time = point.get("tradetime")
                moex_time = (
                    time.fromisoformat(str(raw_time))
                    if raw_time
                    else None
                )

                session.add(
                    MoexRaw(
                        run_id=run_id,
                        tenor_years=tenor,
                        rate_pct=rate,
                        moex_tradetime=moex_time,
                        loaded_at=loaded_at,
                    )
                )
                inserted_count += 1

            session.commit()

        return inserted_count
    def get_moex_points(self, run_id: int) -> list[tuple[float, float]]:
        """Возвращает исходные точки MOEX только для указанного запуска."""
        with Session(self.engine) as session:
            statement = (
                select(MoexRaw.tenor_years, MoexRaw.rate_pct)
                .where(MoexRaw.run_id == run_id)
                .order_by(MoexRaw.tenor_years)
            )
            rows = session.execute(statement).all()

        return [
            (float(tenor), float(rate))
            for tenor, rate in rows
        ]

    def save_curve_points(
        self,
        run_id: int,
        requested_date: date,
        long_df: Any,
    ) -> int:
        """Сохраняет рассчитанные точки кривой для конкретного запуска."""
        calculated_at = datetime.now(timezone.utc)
        inserted_count = 0

        with Session(self.engine) as session:
            run = session.get(CurveRun, run_id)

            if run is None:
                raise ValueError(f"Запуск run_id={run_id} не найден.")

            if run.report_date != requested_date:
                raise ValueError("Дата не совпадает с датой запуска.")

            for _, row in long_df.iterrows():
                scenario_id = int(row["scenario_id"])
                tenor_label = str(row["tenor_label"])

                existing = session.scalar(
                    select(CurvePoint)
                    .where(CurvePoint.run_id == run_id)
                    .where(CurvePoint.scenario_id == scenario_id)
                    .where(CurvePoint.tenor_label == tenor_label)
                )

                values = {
                    "report_date": requested_date,
                    "tenor_years": Decimal(str(row["tenor_years"])),
                    "t_mid_years": Decimal(str(row["t_mid_years"])),
                    "rate_pct": Decimal(str(row["rate_pct"])),
                    "discount_factor": Decimal(
                        str(row["discount_factor"])
                    ),
                    "method": str(row["method"]),
                    "is_interpolated": bool(row["is_interpolated"]),
                    "is_extrapolated": bool(row["is_extrapolated"]),
                    "calculated_at": calculated_at,
                }

                if existing is not None:
                    for key, value in values.items():
                        setattr(existing, key, value)
                else:
                    session.add(
                        CurvePoint(
                            run_id=run_id,
                            scenario_id=scenario_id,
                            tenor_label=tenor_label,
                            **values,
                        )
                    )
                    inserted_count += 1

            session.commit()

        return inserted_count
