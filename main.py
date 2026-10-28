"""Командная строка загрузчика бескупонной кривой MOEX"""

import argparse
import logging
from datetime import date

from src.moex_loader.database import CurveRepository, create_db_engine
from src.moex_loader.loader import CurveLoader
from src.moex_loader.moex_client import MoexClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Загрузка бескупонной кривой доходности ОФЗ с MOEX в PostgreSQL"
        )
    )

    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        "--date",
        type=date.fromisoformat,
        help="Дата кривой в формате YYYY-MM-DD.",
    )
    date_group.add_argument(
        "--from-date",
        type=date.fromisoformat,
        help="Начальная дата диапазона YYYY-MM-DD.",
    )

    parser.add_argument(
        "--to-date",
        type=date.fromisoformat,
        help="Конечная дата диапазона YYYY-MM-DD.",
    )
    parser.add_argument(
        "--mode",
        choices=("manual", "scheduled"),
        default="manual",
        help="Режим запуска: manual или scheduled. По умолчанию manual.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Количество попыток запроса, включая первую. По умолчанию 3.",
    )
    parser.add_argument(
        "--retry-pause",
        type=float,
        default=2.0,
        help="Пауза между повторами в секундах. По умолчанию 2.",
    )
    parser.add_argument(
        "--request-pause",
        type=float,
        default=1.0,
        help="Пауза между датами в секундах. По умолчанию 1.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Тайм-аут запроса MOEX в секундах. По умолчанию 20.",
    )

    args = parser.parse_args()

    if args.from_date is not None and args.to_date is None:
        parser.error("При использовании --from-date необходимо указать --to-date.")

    if args.from_date is not None and args.from_date > args.to_date:
        parser.error("--from-date не может быть позже --to-date.")

    if args.retries < 1:
        parser.error("--retries должен быть не меньше 1.")

    if args.retry_pause < 0 or args.request_pause < 0:
        parser.error("Паузы не могут быть отрицательными.")

    if args.timeout <= 0:
        parser.error("--timeout должен быть положительным.")

    return args


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    args = parse_args()

    try:
        engine = create_db_engine()

        repository = CurveRepository(engine)
        client = MoexClient(timeout=args.timeout)
        loader = CurveLoader(
            client=client,
            repository=repository,
            retries=args.retries,
            retry_pause=args.retry_pause,
            request_pause=args.request_pause,
            started_by=(
                "scheduler" if args.mode == "scheduled" else "manual"
            ),
        )

        if args.date is not None:
            status = loader.load_date(args.date, mode=args.mode)
            print(f"{args.date}: {status}")
            return 1 if status == "error" else 0

        results = loader.load_range(
            from_date=args.from_date,
            to_date=args.to_date,
            mode=args.mode,
        )

        print("Результаты загрузки:")
        for status, count in results.items():
            print(f"  {status}: {count}")

        return 1 if results["error"] else 0

    except Exception:
        logging.exception("Не удалось запустить загрузчик.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())