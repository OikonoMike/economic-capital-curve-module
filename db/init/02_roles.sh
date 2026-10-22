#!/bin/bash
set -e

# Передаём пароли из переменных окружения (.env) в переменные psql
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v loader_pw="$LOADER_PASSWORD" -v calc_pw="$CALC_PASSWORD" <<-'EOSQL'
    
    -- Удаляем роли, если они уже существуют (для безопасности)
    DO $$
    BEGIN
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'loader_rw') THEN DROP ROLE loader_rw; END IF;
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'calc_ro') THEN DROP ROLE calc_ro; END IF;
    END $$;

    -- Создаём роли с паролями из psql-переменных
    CREATE ROLE loader_rw LOGIN PASSWORD :'loader_pw';
    CREATE ROLE calc_ro   LOGIN PASSWORD :'calc_pw';

    -- Даем права на использование схемы public
    GRANT USAGE ON SCHEMA public TO loader_rw, calc_ro;

    -- loader_rw (загрузчик): чтение, запись, удаление + права на последовательности (для BIGSERIAL)
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO loader_rw;
    GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO loader_rw;
    
    -- Чтобы loader_rw мог работать с таблицами, которые создадутся в будущем
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO loader_rw;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO loader_rw;

    -- calc_ro (калькулятор): только чтение представлений и справочников
    GRANT SELECT ON curve_latest, curve_latest_wide, curve_run, curve_point, scenario, tenor_grid, calendar TO calc_ro;

EOSQL

echo "Роли loader_rw и calc_ro успешно созданы."