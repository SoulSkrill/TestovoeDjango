from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models


class Sale(models.Model):
    class Marketplace(models.TextChoices):
        OZON = 'ozon', 'Ozon'
        WILDBERRIES = 'wildberries', 'Wildberries'
        YANDEX_MARKET = 'yandex_market', 'Yandex Market'

    class Status(models.TextChoices):
        DELIVERED = 'delivered', 'Delivered'
        RETURNED = 'returned', 'Returned'
        CANCELLED = 'cancelled', 'Cancelled'

    order_id = models.CharField(max_length=64)
    marketplace = models.CharField(max_length=32, choices=Marketplace.choices)
    product_name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    cost_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    status = models.CharField(max_length=16, choices=Status.choices)
    sold_at = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['sold_at']),
            models.Index(fields=['marketplace']),
            models.Index(fields=['status']),
        ]

    def clean(self) -> None:
        super().clean()
        if self.sold_at > date.today():
            raise models.ValidationError({'sold_at': 'sold_at cannot be in the future'})

    def __str__(self) -> str:
        return f'{self.order_id} ({self.marketplace})'
