-- 01_create_schema.sql

-- Справочник сценариев
CREATE TABLE IF NOT EXISTS scenario (
    scenario_id SMALLINT PRIMARY KEY CHECK (scenario_id BETWEEN 0 AND 6),
    code        TEXT NOT NULL UNIQUE,
    name_ru     TEXT NOT NULL
);

-- Справочник 19 тенор-бакетов (Таблица 1 приложения к 8-МР)
CREATE TABLE IF NOT EXISTS tenor_grid (
    tenor_label   TEXT PRIMARY KEY,
    order_no      SMALLINT NOT NULL UNIQUE,
    interval_name TEXT NOT NULL,
    tenor_years   NUMERIC(8,4) NOT NULL,
    t_mid_years   NUMERIC(8,4) NOT NULL
);

-- Календарь рабочих/торговых дней
CREATE TABLE IF NOT EXISTS calendar (
    calendar_date  DATE PRIMARY KEY,
    is_working_day BOOLEAN NOT NULL,
    is_trading_day BOOLEAN NOT NULL,
    note           TEXT
);

-- История запусков
CREATE TABLE IF NOT EXISTS curve_run (
    run_id        BIGSERIAL PRIMARY KEY,
    report_date   DATE NOT NULL,
    run_type      TEXT NOT NULL CHECK (run_type IN ('manual', 'scheduled')),
    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at   TIMESTAMPTZ,
    status        TEXT NOT NULL CHECK (status IN ('running', 'success', 'error', 'no_data', 'skipped')),
    error_message TEXT,
    started_by    TEXT NOT NULL DEFAULT 'scheduler',
    CHECK (finished_at IS NULL OR finished_at >= started_at)
);

CREATE INDEX IF NOT EXISTS idx_curve_run_report_date ON curve_run(report_date);
CREATE INDEX IF NOT EXISTS idx_curve_run_status ON curve_run(status);

-- Сырые точки MOEX
CREATE TABLE IF NOT EXISTS moex_raw (
    raw_id         BIGSERIAL PRIMARY KEY,
    run_id         BIGINT NOT NULL REFERENCES curve_run(run_id) ON DELETE CASCADE,
    tenor_years    NUMERIC(8,4) NOT NULL,
    rate_pct       NUMERIC(10,4) NOT NULL,
    moex_tradetime TIME,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (run_id, tenor_years)
);

CREATE INDEX IF NOT EXISTS idx_moex_raw_run_id ON moex_raw(run_id);

-- Результат: кривые (19 теноров × 7 сценариев = 133 строки на запуск)
CREATE TABLE IF NOT EXISTS curve_point (
    point_id         BIGSERIAL PRIMARY KEY,
    run_id           BIGINT NOT NULL REFERENCES curve_run(run_id) ON DELETE CASCADE,
    report_date      DATE NOT NULL,
    scenario_id      SMALLINT NOT NULL REFERENCES scenario(scenario_id),
    tenor_label      TEXT NOT NULL REFERENCES tenor_grid(tenor_label),
    tenor_years      NUMERIC(8,4) NOT NULL,
    t_mid_years      NUMERIC(8,4) NOT NULL,
    rate_pct         NUMERIC(10,6) NOT NULL,
    discount_factor  NUMERIC(18,12) NOT NULL,
    method           TEXT NOT NULL CHECK (method IN ('moex', 'nearest', 'interpolation', 'extrapolation')),
    is_interpolated  BOOLEAN NOT NULL DEFAULT FALSE,
    is_extrapolated  BOOLEAN NOT NULL DEFAULT FALSE,
    calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, scenario_id, tenor_label),
    CHECK (is_interpolated = (method = 'interpolation')),
    CHECK (is_extrapolated = (method = 'extrapolation'))
);

CREATE INDEX IF NOT EXISTS idx_curve_point_run_id ON curve_point(run_id);
CREATE INDEX IF NOT EXISTS idx_curve_point_report_date ON curve_point(report_date);
CREATE INDEX IF NOT EXISTS idx_curve_point_scenario ON curve_point(scenario_id);

-- ============================================================
-- Представление 1: curve_latest (длинный вид)
-- Последний успешный запуск за каждую дату
-- ============================================================
CREATE OR REPLACE VIEW curve_latest AS
SELECT
    cp.report_date, 
    cp.run_id, 
    cp.scenario_id, 
    s.code AS scenario_code,
    cp.tenor_label, 
    tg.order_no, 
    cp.tenor_years, 
    cp.t_mid_years,
    cp.rate_pct, 
    cp.discount_factor, 
    cp.method,
    cp.is_interpolated, 
    cp.is_extrapolated, 
    cp.calculated_at
FROM curve_point cp
JOIN scenario s ON cp.scenario_id = s.scenario_id
JOIN tenor_grid tg ON cp.tenor_label = tg.tenor_label
JOIN (
    SELECT report_date, MAX(run_id) AS max_run_id
    FROM curve_run WHERE status = 'success'
    GROUP BY report_date
) latest ON cp.report_date = latest.report_date AND cp.run_id = latest.max_run_id;

-- ============================================================
-- Представление 2: curve_latest_wide (широкий вид)
-- Одна строка = один тенор-бакет, ставки и DF по всем сценариям
-- ============================================================
DROP VIEW IF EXISTS curve_latest_wide;
CREATE VIEW curve_latest_wide AS
WITH latest_runs AS (
    SELECT report_date, MAX(run_id) AS run_id
    FROM curve_run WHERE status = 'success'
    GROUP BY report_date
)
SELECT
    lr.report_date,
    lr.run_id,
    cp.tenor_label,
    tg.order_no,
    cp.t_mid_years,
    MAX(CASE WHEN cp.scenario_id = 0 THEN cp.rate_pct END)        AS rate_base,
    MAX(CASE WHEN cp.scenario_id = 1 THEN cp.rate_pct END)        AS rate_s1,
    MAX(CASE WHEN cp.scenario_id = 2 THEN cp.rate_pct END)        AS rate_s2,
    MAX(CASE WHEN cp.scenario_id = 3 THEN cp.rate_pct END)        AS rate_s3,
    MAX(CASE WHEN cp.scenario_id = 4 THEN cp.rate_pct END)        AS rate_s4,
    MAX(CASE WHEN cp.scenario_id = 5 THEN cp.rate_pct END)        AS rate_s5,
    MAX(CASE WHEN cp.scenario_id = 6 THEN cp.rate_pct END)        AS rate_s6,
    MAX(CASE WHEN cp.scenario_id = 0 THEN cp.discount_factor END) AS df_base,
    MAX(CASE WHEN cp.scenario_id = 1 THEN cp.discount_factor END) AS df_s1,
    MAX(CASE WHEN cp.scenario_id = 2 THEN cp.discount_factor END) AS df_s2,
    MAX(CASE WHEN cp.scenario_id = 3 THEN cp.discount_factor END) AS df_s3,
    MAX(CASE WHEN cp.scenario_id = 4 THEN cp.discount_factor END) AS df_s4,
    MAX(CASE WHEN cp.scenario_id = 5 THEN cp.discount_factor END) AS df_s5,
    MAX(CASE WHEN cp.scenario_id = 6 THEN cp.discount_factor END) AS df_s6,
    MAX(CASE WHEN cp.scenario_id = 0 THEN cp.method END)          AS method,
    BOOL_OR(CASE WHEN cp.scenario_id = 0 THEN cp.is_interpolated END) AS is_interpolated,
    BOOL_OR(CASE WHEN cp.scenario_id = 0 THEN cp.is_extrapolated END) AS is_extrapolated,
    MAX(cp.calculated_at) AS calculated_at
FROM latest_runs lr
JOIN curve_point cp ON lr.run_id = cp.run_id
JOIN tenor_grid tg ON cp.tenor_label = tg.tenor_label
GROUP BY
    lr.report_date, lr.run_id, cp.tenor_label, tg.order_no, cp.t_mid_years;