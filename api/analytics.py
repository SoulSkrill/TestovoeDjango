from __future__ import annotations

from decimal import Decimal

import pandas as pd

from api.models import Sale


def queryset_to_dataframe(queryset) -> pd.DataFrame:
    rows = list(
        queryset.values(
            'order_id',
            'marketplace',
            'product_name',
            'quantity',
            'price',
            'cost_price',
            'status',
            'sold_at',
        )
    )
    columns = [
        'order_id',
        'marketplace',
        'product_name',
        'quantity',
        'price',
        'cost_price',
        'status',
        'sold_at',
        'revenue',
        'cost',
        'profit',
    ]
    if not rows:
        return pd.DataFrame(columns=columns)

    frame = pd.DataFrame(rows)
    frame['price'] = frame['price'].apply(_to_float)
    frame['cost_price'] = frame['cost_price'].apply(_to_float)
    frame['revenue'] = frame['price'] * frame['quantity']
    frame['cost'] = frame['cost_price'] * frame['quantity']
    frame['profit'] = frame['revenue'] - frame['cost']
    return frame


def build_summary_items(frame: pd.DataFrame, group_by: str | None) -> list[dict]:
    if group_by is None:
        return [{'group': 'all', 'metrics': _compute_metrics(frame)}]

    if frame.empty:
        return []

    group_column = 'sold_at' if group_by == 'date' else group_by
    grouped = frame.sort_values(by=[group_column]).groupby(group_column, dropna=False)

    items: list[dict] = []
    for key, group_frame in grouped:
        label = key.isoformat() if hasattr(key, 'isoformat') else str(key)
        items.append({'group': label, 'metrics': _compute_metrics(group_frame)})
    return items


def build_top_products(frame: pd.DataFrame, sort_by: str, limit: int) -> list[dict]:
    if frame.empty:
        return []

    delivered = frame[frame['status'] == Sale.Status.DELIVERED]
    if delivered.empty:
        return []

    grouped = (
        delivered.groupby('product_name', as_index=False)
        .agg(revenue=('revenue', 'sum'), quantity=('quantity', 'sum'), profit=('profit', 'sum'))
        .sort_values(by=[sort_by, 'product_name'], ascending=[False, True])
        .head(limit)
    )

    return [
        {
            'product_name': row['product_name'],
            'revenue': _round2(row['revenue']),
            'quantity': int(row['quantity']),
            'profit': _round2(row['profit']),
        }
        for _, row in grouped.iterrows()
    ]


def _compute_metrics(frame: pd.DataFrame) -> dict:
    delivered = frame[frame['status'] == Sale.Status.DELIVERED]
    revenue = float(delivered['revenue'].sum()) if not delivered.empty else 0.0
    cost = float(delivered['cost'].sum()) if not delivered.empty else 0.0
    gross_profit = revenue - cost

    total_orders = int(frame['order_id'].nunique()) if not frame.empty else 0

    returned_count = int((frame['status'] == Sale.Status.RETURNED).sum())
    delivered_count = int((frame['status'] == Sale.Status.DELIVERED).sum())
    return_base = delivered_count + returned_count

    margin_percent = _safe_div(gross_profit, revenue) * 100
    avg_order_value = _safe_div(revenue, total_orders)
    return_rate = _safe_div(returned_count, return_base) * 100

    return {
        'total_revenue': _round2(revenue),
        'total_cost': _round2(cost),
        'gross_profit': _round2(gross_profit),
        'margin_percent': _round2(margin_percent),
        'total_orders': total_orders,
        'avg_order_value': _round2(avg_order_value),
        'return_rate': _round2(return_rate),
    }


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _round2(value: float) -> float:
    return round(float(value), 2)


def _to_float(value: Decimal | float) -> float:
    return float(value)
