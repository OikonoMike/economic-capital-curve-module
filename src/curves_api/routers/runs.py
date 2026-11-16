from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.engine import Connection

from src.curves_api.database import get_db

router = APIRouter()


@router.get("/runs")
def get_runs(db: Connection = Depends(get_db)):
    query = """
        SELECT
            run_id,
            report_date,
            run_type,
            status,
            started_at,
            finished_at,
            started_by,
            error_message
        FROM curve_run
        ORDER BY started_at DESC
    """

    result = db.execute(text(query))

    return [dict(row) for row in result.mappings().all()]