"""Создание таблиц проекта в PostgreSQL"""

from src.moex_loader.database import create_db_engine, init_db


def main() -> None:
    engine = create_db_engine()
    init_db(engine)
    print("Таблицы успешно созданы или уже существуют.")


if __name__ == "__main__":
    main()