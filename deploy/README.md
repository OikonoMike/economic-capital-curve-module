# Развёртывание пайплайна кривых

## Требования

- Ubuntu 22.04/24.04
- Docker и Docker Compose plugin
- Python 3.12
- Git

## Первоначальная настройка

1. Клонировать репозиторий:

   ```bash
   git clone -b develop <repo> economic-capital-curve-module
   cd economic-capital-curve-module
   ```

2. Запустить PostgreSQL:

   ```bash
   docker compose up -d
   ```

3. Настроить переменные окружения:

   ```bash
   cp .env.example .env
   ```

   Заполнить необходимые параметры подключения к БД. Файл `.env` не коммитить.

4. Создать виртуальное окружение и установить зависимости:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

5. Загрузить производственный календарь:

   ```bash
   PYTHONPATH=. python src/load_calendar.py
   ```

## Ручной запуск pipeline

Pipeline выполняет загрузку данных MOEX, проверки, расчёт кривых и сохранение результата в `curve_point` в рамках одного `run_id`.

Запуск за одну дату:

```bash
python main.py --date 2026-10-30 --mode manual
```

Запуск за диапазон дат:

```bash
python main.py --from-date 2026-10-01 --to-date 2026-10-30 --mode manual
```

Дополнительные параметры:

- `--mode manual|scheduled` — режим запуска.
- `--retries` — количество попыток запроса MOEX.
- `--retry-pause` — пауза между повторными запросами.
- `--request-pause` — пауза между датами.
- `--timeout` — тайм-аут запроса MOEX.

Справка по параметрам:

```bash
python main.py --help
```

## Автоматический запуск

Для автоматического запуска используется единый скрипт:

`deploy/run_pipeline.sh`

Скрипт запускает pipeline за текущую дату в режиме `scheduled`.

Сделать скрипт исполняемым:

```bash
chmod +x deploy/run_pipeline.sh
```

Установить cron:

```bash
crontab deploy/crontab.txt
```

Расписание:

- Понедельник–пятница.
- 16:30 UTC.
- Часовой пояс задаётся через `CRON_TZ=UTC`.

Логи записываются в:

```text
/home/ubuntu/pipeline.log
```

## Логика обработки

1. Проверяется торговый календарь.
2. Создаётся запись запуска в `curve_run`.
3. Загружаются исходные точки MOEX.
4. Выполняются проверки исходных данных.
5. При успешной загрузке рассчитываются кривые.
6. Результат сохраняется в `curve_point` под тем же `run_id`.
7. Запуск получает статус `success`.

Если загрузка завершилась ошибкой или данных нет, расчёт не выполняется. В `curve_run` сохраняются соответствующий статус и текст ошибки.