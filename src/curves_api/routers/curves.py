import re
import csv
from io import StringIO, BytesIO
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.engine import Connection
from openpyxl import Workbook

from src.curves_api.database import get_db
from src.curves_api.schemas import CurveRow

router = APIRouter()


# Общая проверка даты для обоих endpoint
def parse_report_date(date_str: str) -> date:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
        raise HTTPException(
            status_code=400,
            detail="Неверный формат даты. Используйте YYYY-MM-DD",
        )

    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Некорректная дата",
        )

def get_report_date(
    date_str: str = Query(..., alias="date"),
) -> date:
    return parse_report_date(date_str)


# Общий запрос к базе
def fetch_curves(
    db: Connection,
    report_date: date,
    scenario: int | None = None,
):
    query = """
        SELECT
            cl.report_date,
            cl.scenario_id,
            cl.scenario_code,
            cl.tenor_label,
            cl.tenor_years,
            cl.t_mid_years,
            cl.rate_pct,
            cl.discount_factor,
            cl.method,
            cl.is_interpolated,
            cl.is_extrapolated,
            cl.calculated_at,
            cr.run_type,
            cr.started_by,
            cr.started_at
        FROM curve_latest cl
        JOIN curve_run cr ON cr.run_id = cl.run_id
        WHERE cl.report_date = :report_date
    """

    params = {"report_date": report_date}

    if scenario is not None:
        query += " AND cl.scenario_id = :scenario"
        params["scenario"] = scenario

    query += " ORDER BY cl.scenario_id, cl.order_no"

    result = db.execute(text(query), params)
    return [dict(row) for row in result.mappings().all()]


@router.get("/curves", response_model=list[CurveRow])
def get_curves(
    report_date: date = Depends(get_report_date),
    scenario: int | None = Query(None, ge=0, le=6),
    db: Connection = Depends(get_db),
):
    rows = fetch_curves(db, report_date, scenario)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Кривые за дату {report_date.isoformat()} не найдены",
        )

    return rows


@router.get("/curves/export")
def export_curves(
    report_date: date = Depends(get_report_date),
    export_format: str = Query(..., alias="format", pattern="^(csv|xlsx)$"),
    scenario: int | None = Query(None, ge=0, le=6),
    db: Connection = Depends(get_db),
):
    report_date = parse_report_date(date_str)

    rows = fetch_curves(db, report_date, scenario)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Кривые за дату {report_date.isoformat()} не найдены",
        )

    columns = list(rows[0].keys())
    filename = f"curves_{report_date.isoformat()}"

    if export_format == "csv":
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=columns)

        writer.writeheader()
        writer.writerows(rows)

        content = output.getvalue().encode("utf-8-sig")

        return Response(
            content=content,
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}.csv"'
            },
        )

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Curves"

    worksheet.append(columns)

    for row in rows:
        excel_row = []

        for column in columns:
            value = row[column]

            # Excel не поддерживает datetime с часовым поясом
            if hasattr(value, "tzinfo") and value.tzinfo is not None:
                value = value.replace(tzinfo=None)

            excel_row.append(value)

        worksheet.append(excel_row)

    output = BytesIO()
    workbook.save(output)

    return Response(
        content=output.getvalue(),
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.xlsx"'
        },
    )