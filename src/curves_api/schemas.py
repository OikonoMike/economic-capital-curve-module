from datetime import date, datetime

from pydantic import BaseModel


class CurveRow(BaseModel):
    report_date: date
    scenario_id: int
    scenario_code: str
    tenor_label: str
    tenor_years: float
    t_mid_years: float
    rate_pct: float
    discount_factor: float
    method: str
    is_interpolated: bool
    is_extrapolated: bool
    calculated_at: datetime
    run_type: str
    started_by: str | None
    started_at: datetime
