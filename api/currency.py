from __future__ import annotations

import requests
from django.core.cache import cache


class CurrencyServiceError(RuntimeError):
    pass


def get_usd_rate() -> float:
    cache_key = 'usd_rate_cbr'
    cached = cache.get(cache_key)
    if cached is not None:
        return float(cached)

    try:
        response = requests.get('https://www.cbr-xml-daily.ru/daily_json.js', timeout=10)
        response.raise_for_status()
        payload = response.json()
        rate = float(payload['Valute']['USD']['Value'])
    except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
        raise CurrencyServiceError('Currency provider is unavailable') from exc

    if rate <= 0:
        raise CurrencyServiceError('Currency provider returned non-positive USD rate')

    cache.set(cache_key, rate, timeout=3600)
    return rate
