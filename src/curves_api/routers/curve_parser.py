"""HTTP compatibility with the Factor Lab curve client."""

import logging
import os
from collections import Counter, defaultdict
from datetime import date, timedelta
from functools import lru_cache
from math import isfinite
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator
from sqlalchemy import Date, create_engine, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import SQLAlchemyError

from src.curves_api.database import engine, get_db
from src.curves_api.routers.curves import fetch_curves
from src.interpolate_curve import GRID, SCENARIO_CODES, stress_rates
from src.moex_loader.database import CurveRepository
from src.moex_loader.loader import CurveLoader
from src.moex_loader.moex_client import MoexClient
from src.pipeline.runner import run_for_date

router = APIRouter(prefix="/v1", tags=["Factor Lab"])
logger = logging.getLogger(__name__)
DB = Annotated[Connection, Depends(get_db)]
EXPECTED_ROWS = len(GRID) * (1 + len(SCENARIO_CODES))
INGEST_LOCK = Lock()
MAX_INGEST_DAYS = 11  # The client looks back 10 days, plus the requested date.


class ShockPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenor_years: FiniteFloat = Field(gt=0)
    base_rate: FiniteFloat = Field(gt=-0.95, le=1.0)


class ShockRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenors: list[ShockPoint] = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def unique_tenors(self):
        if len({p.tenor_years for p in self.tenors}) != len(self.tenors):
            raise ValueError("Tenors must be unique")
        return self


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start: date = Field(alias="from")
    end: date = Field(alias="to")
    refresh: Literal[False] = False


def stored_dates(db: Connection, start: date, end: date) -> list[date]:
    stmt = text("""
        SELECT report_date
        FROM curve_latest
        WHERE report_date BETWEEN :start AND :end
        GROUP BY report_date
        HAVING COUNT(*) = :expected_rows
        ORDER BY report_date
    """).columns(report_date=Date())
    return list(db.execute(stmt, {
        "start": start, "end": end, "expected_rows": EXPECTED_ROWS,
    }).scalars())


@router.get("/ready")
def ready():
    try:
        with engine.connect() as db:
            db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("Curve database is unavailable")
        return JSONResponse(
            status_code=503, content={"status": "unavailable", "storage": "unreachable"}
        )
    return {"status": "ok", "storage": "reachable"}


@router.get("/curves")
def dates(start: Annotated[date, Query(alias="from")], end: Annotated[date, Query(alias="to")], db: DB):
    if not 0 <= (end - start).days < 3660:
        raise HTTPException(422, "Invalid date range")
    return {"from": start, "to": end, "dates": stored_dates(db, start, end)}


@router.get("/curves/{trade_date}")
def snapshot(trade_date: date, db: DB):
    rows = fetch_curves(db, trade_date)
    if not rows:
        raise HTTPException(404, "Curve not stored")

    rates = defaultdict(dict)
    for row in rows:
        rates[float(row["t_mid_years"])][row["scenario_code"]] = float(row["rate_pct"]) / 100
    expected_codes = {"base", *SCENARIO_CODES}
    if len(rows) != EXPECTED_ROWS or len(rates) != len(GRID) or any(
        set(values) != expected_codes or not all(map(isfinite, values.values()))
        for values in rates.values()
    ):
        raise HTTPException(503, "Stored curve is incomplete or invalid")
    return {
        "date": trade_date,
        "tenors": [
            {"tenor_years": years, "base_rate": values["base"],
             "scenarios": [
                 {"scenario": code, "rate": values[code],
                  "shock_bp": round((values[code] - values["base"]) * 10000, 6)}
                 for code in SCENARIO_CODES
             ]}
            for years, values in sorted(rates.items())
        ],
    }


@router.post("/curves/shock")
def shock(request: ShockRequest):
    return {
        "tenors": [
            {"tenor_years": point.tenor_years, "base_rate": point.base_rate,
             "scenarios": [
                 {"scenario": code, "rate": round(rate, 4) / 100,
                  "shock_bp": round((round(rate, 4) - point.base_rate * 100) * 100, 6)}
                 for code, rate in zip(SCENARIO_CODES, stress_rates(
                     point.base_rate * 100, point.tenor_years
                 ), strict=True)
             ]}
            for point in request.tenors
        ],
    }


@lru_cache(maxsize=1)
def writer_repository(url: str) -> CurveRepository:
    return CurveRepository(create_engine(url, pool_pre_ping=True))


@router.post("/curves/ingest")
def ingest(request: IngestRequest):
    count = (request.end - request.start).days + 1
    if not 1 <= count <= MAX_INGEST_DAYS:
        raise HTTPException(422, f"Range must contain 1–{MAX_INGEST_DAYS} days")
    url = os.getenv("CURVES_INGEST_DATABASE_URL")
    if not url:
        raise HTTPException(503, "On-demand load is disabled")
    if not INGEST_LOCK.acquire(blocking=False):
        raise HTTPException(503, "Another on-demand load is in progress")
    try:
        repository = writer_repository(url)
        loader = CurveLoader(MoexClient(timeout=5), repository, retries=2,
                             retry_pause=0.5, started_by="factor-lab")
        with repository.engine.connect() as db:
            already_stored = set(stored_dates(db, request.start, request.end))
        results = []
        for offset in range(count):
            day = request.start + timedelta(days=offset)
            row = {"date": day}
            if day in already_stored:
                row["status"] = "unchanged"
            else:
                try:
                    status = run_for_date(day, loader=loader, repository=repository)
                    if status == "success":
                        row["status"] = "stored"
                    elif status == "no_data":
                        row["status"] = "no_data"
                    elif status == "skipped":
                        with repository.engine.connect() as db:
                            stored = bool(stored_dates(db, day, day))
                        if stored:
                            row["status"] = "unchanged"
                        elif not repository.is_trading_day(day):
                            row["status"] = "no_data"
                        else:
                            row.update(status="failed", reason="Successful run has no complete curve")
                    else:
                        row.update(status="failed", reason="Pipeline failed; see run history")
                except (ValueError, SQLAlchemyError):
                    logger.exception("On-demand load failed for %s", day)
                    row.update(status="failed", reason="Pipeline or calendar unavailable")
            results.append(row)
        totals = Counter(row["status"] for row in results)
        return {
            "requested": count,
            **{key: totals[key] for key in ("stored", "no_data", "unchanged", "failed")},
            "dates": results,
        }
    except (ValueError, SQLAlchemyError):
        logger.exception("On-demand load is unavailable")
        raise HTTPException(503, "On-demand load is unavailable") from None
    finally:
        INGEST_LOCK.release()
