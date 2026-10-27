# База данных IRRBB

PostgreSQL в Docker для хранения кривых доходности ОФЗ и истории расчётов.

## Быстрый запуск

```bash
# Запустить базу данных
docker-compose up -d
```
```bash
# Проверить статус
docker-compose ps
```
```bash
# Посмотреть логи
docker-compose logs postgres
```

Статус должен быть `Up (healthy)`. В логах должно быть сообщение:
```
Роли loader_rw и calc_ro успешно созданы.
```

## Подключение

### Через командную строку
```bash
# Суперпользователь (полный доступ)
docker-compose exec postgres psql -U postgres -d irrbb
```
```bash
# Загрузчик (чтение + запись)
docker-compose exec postgres psql -U loader_rw -d irrbb
```
```bash
# Калькулятор (только чтение)
docker-compose exec postgres psql -U calc_ro -d irrbb
```

### Через GUI-клиент (DBeaver, pgAdmin)
- Хост: localhost
- Порт: 5432
- База: irrbb
- Пользователь: postgres / loader_rw / calc_ro
- Пароль: из файла `.env`

## Структура базы данных 
### Таблицы
|Таблица|Описание|
|---|---|
|scenario|Справочник 7 сценариев (0 = база, 1-6 = стресс)|
|tenor_grid|Справочник 19 тенор-бакетов (Таблица 1 8-МР)|
|calendar|Календарь рабочих/торговых дней|
|curve_run|История запусков (ручные и автоматические)|
|moex_raw|Сырые точки MOEX для каждого запуска|
|curve_point|Результат: 133 строки на запуск (19 теноров × 7 сценариев)|

### Представления (для калькулятора)
|Представление|Описание|
|---|---|
|curve_latest|Длинный вид: последний успешный запуск за дату|
|curve_latest_wide|Широкий вид: одна строка = один тенор, ставки по всем сценариям|


## Пользователи и права
| Пользователь | Права |
|---|---|
| `postgres` | Суперпользователь, полный доступ |
| `loader_rw` | Чтение и запись во все таблицы |
| `calc_ro` | Только чтение (представления `curve_latest`, `curve_latest_wide`, а также таблицы `curve_run`, `curve_point`, `scenario`, `tenor_grid`, `calendar`) |


## Примеры SQL-запросов
### Кривая на дату по сценарию 3 (увеличение наклона)
```sql
SELECT tenor_label, t_mid_years, rate_pct, discount_factor
FROM curve_latest
WHERE report_date = '2026-07-31' AND scenario_id = 3
ORDER BY order_no;
```

### Все кривые за дату в широком виде
```sql
SELECT * FROM curve_latest_wide
WHERE report_date = '2026-07-31'
ORDER BY order_no;
```

### История запусков за последние дни
```sql
SELECT run_id, report_date, run_type, status, started_at, error_message
FROM curve_run
ORDER BY run_id DESC
LIMIT 20;
```


## Остановка и сброс
```bash
# Остановить (данные сохранятся)
docker-compose down
```

```bash
# Остановить и удалить данные (полный сброс)
docker-compose down -v
```

## Файлы инициализации
- `init/01_create_schema.sql` — создание таблиц и представлений
- `init/02_roles.sh` — создание пользователей и прав доступа (читает пароли из `.env`)
- `init/03_seed_data.sql` — начальные данные для справочников



**Важно**: Скрипты инициализации (`db/init/`) выполняются только при первом запуске, когда том с данными пуст. Если изменил *схему* или *пароли* — нужно выполнить `docker-compose down -v` и запустить заново.