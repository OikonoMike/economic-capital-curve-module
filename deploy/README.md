# Развёртывание пайплайна на ВМ

## Требования
Ubuntu 22.04/24.04, Docker + compose plugin, Python 3.12 + venv.

## Шаги
1. git clone -b develop <repo> && cd repo
2. docker compose up -d   (создаёт БД, роли loader_rw / calc_ro)
3. cp .env.example .env   (заполнить пароли; .env не коммитить)
4. python3 -m venv .venv && source .venv/bin/activate
5. pip install -r requirements.txt
6. PYTHONPATH=. python src/load_calendar.py
7. python main.py --from-date YYYY-MM-DD --to-date YYYY-MM-DD --mode manual
8. python run_calculator.py

## Автозапуск
Скопировать run_loader.sh и run_calculator.sh в /home/ubuntu/,
выдать chmod +x, установить crontab.txt через crontab.
Время в cron — UTC: 16:30 загрузка, 16:40 расчёт (= 19:30 / 19:40 МСК).
