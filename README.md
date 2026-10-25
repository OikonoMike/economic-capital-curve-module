# Economic Capital Curve Module

Автоматическая загрузка сырых данных бескупонной кривой доходности ОФЗ с Московской биржи (MOEX ISS API) и сохранение в PostgreSQL.

## Возможности

- Загрузка кривой за одну дату.
- Загрузка за диапазон дат с последовательной обработкой рабочих дней.
- Пропуск дат, успешно загруженных ранее.
- Тайм-ауты, повторные попытки запросов и паузы между запросами.
- Режимы запуска `manual` и `scheduled`.
- Сохранение точек кривой в `moex_raw`.
- Сохранение истории запусков, статусов и ошибок в `curve_run`.
- Разделение результатов на `success`, `no_data` и `error`.

## Технологии

- Python
- PostgreSQL
- SQLAlchemy
- Requests
- pytest
- MOEX ISS API

## Структура проекта

```text
economic-capital-curve-module/
├── data/
├── src/
│   └── moex_loader/
│       ├── __init__.py
│       ├── moex_client.py
│       ├── database.py
│       └── loader.py
├── tests/
│   ├── test_moex_client.py
│   ├── test_database.py
│   └── test_loader.py
├── .env
├── .gitignore
├── init_db.py
├── main.py
├── requirements.txt
└── README.md
```

## Требования

- Python 3.10 или новее.
- PostgreSQL.
- Доступ к MOEX ISS API по HTTPS.

## Установка

Создать и активировать виртуальное окружение:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Установить зависимости:

```bash
pip install -r requirements.txt
```

## Настройка PostgreSQL

Создать базу данных и пользователя PostgreSQL, если они ещё не существуют.

Пример для PostgreSQL:

```sql
CREATE USER curve_user WITH PASSWORD 'your_password';
CREATE DATABASE curve_db OWNER curve_user;
```

Создать в корне проекта файл `.env`:

```dotenv
DATABASE_URL=postgresql+psycopg://curve_user:your_password@localhost:5432/curve_db
```

Заменить `your_password` на настоящий пароль. Если пароль содержит специальные символы, их необходимо корректно URL-кодировать.

Файл `.env` не должен попадать в Git.

Создать таблицы:

```bash
python init_db.py
```

Используются две основные таблицы:

- `moex_raw` — сохранённые точки кривой доходности.
- `curve_run` — история запусков, режим, статус, время выполнения и сообщение об ошибке.

## Запуск

### Загрузка за одну дату

```bash
python main.py --date 2026-10-23
```

### Загрузка диапазона дат

```bash
python main.py --from-date 2026-10-13 --to-date 2026-10-26
```

Начальная и конечная даты включаются в диапазон. Субботы и воскресенья пропускаются. Если MOEX не возвращает данные за рабочую дату, запуск получает статус `no_data`.

### Указать режим запуска

Ручной запуск:

```bash
python main.py --date 2026-10-23 --mode manual
```

Запуск с меткой `scheduled`:

```bash
python main.py --date 2026-10-23 --mode scheduled
```

Параметр `--mode` записывается в историю запусков. Сам по себе он не запускает приложение по расписанию.

### Настроить тайм-аут и повторные попытки

```bash
python main.py \
  --date 2026-10-23 \
  --timeout 20 \
  --retries 3 \
  --retry-pause 2 \
  --request-pause 1
```

Параметры:

| Параметр | Значение по умолчанию | Назначение |
|---|---:|---|
| `--timeout` | 20 секунд | Тайм-аут HTTP-запроса |
| `--retries` | 3 | Число попыток запроса, включая первую |
| `--retry-pause` | 2 секунды | Пауза между повторными попытками |
| `--request-pause` | 1 секунда | Пауза между датами диапазона |
| `--mode` | `manual` | Режим запуска |

Если дата уже успешно загружена, повторный запрос за ней пропускается. Ошибка при загрузке одной даты не должна препятствовать обработке следующих дат диапазона.

## Статусы запусков

| Статус | Значение |
|---|---|
| `running` | Запуск начат и ещё не завершён |
| `success` | Данные получены и сохранены |
| `no_data` | MOEX не вернула данные за указанную дату |
| `error` | Загрузка или сохранение завершились ошибкой |

Отсутствие данных, например в праздничный день, не считается техническим сбоем.

## Проверка тестов

Запустить тесты:

```bash
python -m pytest -v
```

Тесты проверяют клиент MOEX, работу репозитория, сохранение точек, обработку ошибок, повторные попытки и загрузку диапазона дат.

## Проверка истории запусков

Подключиться к PostgreSQL:

```bash
psql -U curve_user -h localhost -d curve_db
```

Посмотреть историю:

```sql
SELECT
    id,
    requested_date,
    mode,
    status,
    started_at,
    finished_at,
    error_message
FROM curve_run
ORDER BY requested_date DESC, id DESC;
```

Посмотреть количество сохранённых точек по датам:

```sql
SELECT
    trade_date,
    COUNT(*) AS points_count,
    MIN(period_years) AS min_period_years,
    MAX(period_years) AS max_period_years
FROM moex_raw
GROUP BY trade_date
ORDER BY trade_date DESC;
```

Посмотреть точки за конкретную дату:

```sql
SELECT
    trade_date,
    trade_time,
    period_years,
    yield_percent,
    run_id,
    fetched_at
FROM moex_raw
WHERE trade_date = DATE '2026-10-23'
ORDER BY period_years;
```

## Источник данных и ограничения

Источник данных — MOEX ISS API, раздел ZCYC (бескупонная кривая доходности).

Используемый endpoint:

`https://iss.moex.com/iss/engines/stock/zcyc.json`

Дата передаётся параметром `date`.

Проверенный формат ответа содержит блок `yearyields` с полями `tradedate`, `tradetime`, `period` и `value`.

В проверенном ответе присутствовали 11 сроков — от 0,25 до 20 лет. Наличие ставок до 30 лет не подтверждено; при обязательном требовании к сроку 30 лет необходимо дополнительно проверить доступность этих данных в другом источнике или endpoint.

## Безопасность

- Не добавлять `.env` в Git.
- Не хранить пароли базы данных в исходном коде.
- Не удалять историю ошибок для улучшения демонстрационных результатов.
- Перед переносом проекта на другую машину настроить подключение к соответствующей базе данных.