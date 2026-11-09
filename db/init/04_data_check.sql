-- 04_data_check.sql
-- Миграция: добавление таблицы проверок исходных данных MOEX

CREATE TABLE IF NOT EXISTS data_check (
    run_id     BIGINT NOT NULL REFERENCES curve_run(run_id) ON DELETE CASCADE,
    check_code TEXT   NOT NULL CHECK (check_code IN ('tenors', 'rates', 'tradetime', 'report_date')),
    status     TEXT   NOT NULL CHECK (status IN ('ok', 'error')),
    details    TEXT,
    PRIMARY KEY (run_id, check_code)
);

CREATE INDEX IF NOT EXISTS idx_data_check_run_id ON data_check(run_id);
CREATE INDEX IF NOT EXISTS idx_data_check_status ON data_check(status);

COMMENT ON TABLE data_check IS 'Результаты проверок исходных данных MOEX до записи в moex_raw';
COMMENT ON COLUMN data_check.run_id IS 'Внешний ключ на curve_run.run_id';
COMMENT ON COLUMN data_check.check_code IS 'Код правила: tenors, rates, tradetime, report_date';
COMMENT ON COLUMN data_check.status IS 'Результат проверки: ok или error';
COMMENT ON COLUMN data_check.details IS 'Фактический результат или причина ошибки';