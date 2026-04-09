# Sales Aggregator (Django)

Реализация тестового задания на Django + Django REST Framework.

## Что реализовано

- `POST /sales` — добавление одной или нескольких продаж
- `GET /sales` — список продаж с фильтрацией и пагинацией
- `GET /analytics/summary` — агрегированные метрики за период
- `GET /analytics/top-products` — топ продуктов за период
- `GET /analytics/summary-usd` — summary в USD
- `POST /analytics/upload-csv` — загрузка продаж из CSV (Pandas)
- Хранение в SQLite
- Кеш курса USD на 1 час
- JSON-логирование
- Swagger UI

## Запуск

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Swagger UI:

- `http://127.0.0.1:8000/docs/`

## Тесты

```bash
python manage.py test
```

## Метрики

- `total_revenue` и `total_cost` считаются только по `delivered`
- `gross_profit = revenue - cost`
- `margin_percent = gross_profit / revenue * 100`
- `avg_order_value = revenue / total_orders`
- `return_rate = returned / (delivered + returned) * 100`
- Если API курса недоступен, `/analytics/summary-usd` возвращает `503`
