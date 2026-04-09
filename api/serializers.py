from __future__ import annotations

from datetime import date

from rest_framework import serializers

from api.models import Sale


class SaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = [
            'id',
            'order_id',
            'marketplace',
            'product_name',
            'quantity',
            'price',
            'cost_price',
            'status',
            'sold_at',
        ]
        read_only_fields = ['id']

    def validate_sold_at(self, value: date) -> date:
        if value > date.today():
            raise serializers.ValidationError('sold_at cannot be in the future')
        return value


class SalesQuerySerializer(serializers.Serializer):
    marketplace = serializers.ChoiceField(choices=Sale.Marketplace.choices, required=False)
    status = serializers.ChoiceField(choices=Sale.Status.choices, required=False)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    page = serializers.IntegerField(required=False, default=1, min_value=1)
    page_size = serializers.IntegerField(required=False, default=20, min_value=1, max_value=200)

    def validate(self, attrs: dict) -> dict:
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')
        if date_from and date_to and date_from > date_to:
            raise serializers.ValidationError('date_from must be less or equal to date_to')
        return attrs


class SummaryQuerySerializer(serializers.Serializer):
    GROUP_BY_CHOICES = [
        ('marketplace', 'marketplace'),
        ('date', 'date'),
        ('status', 'status'),
    ]

    date_from = serializers.DateField(required=True)
    date_to = serializers.DateField(required=True)
    marketplace = serializers.ChoiceField(choices=Sale.Marketplace.choices, required=False)
    group_by = serializers.ChoiceField(choices=GROUP_BY_CHOICES, required=False)

    def validate(self, attrs: dict) -> dict:
        if attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError('date_from must be less or equal to date_to')
        return attrs


class TopProductsQuerySerializer(serializers.Serializer):
    SORT_BY_CHOICES = [
        ('revenue', 'revenue'),
        ('quantity', 'quantity'),
        ('profit', 'profit'),
    ]

    date_from = serializers.DateField(required=True)
    date_to = serializers.DateField(required=True)
    sort_by = serializers.ChoiceField(choices=SORT_BY_CHOICES, required=False, default='revenue')
    limit = serializers.IntegerField(required=False, default=10, min_value=1, max_value=200)

    def validate(self, attrs: dict) -> dict:
        if attrs['date_from'] > attrs['date_to']:
            raise serializers.ValidationError('date_from must be less or equal to date_to')
        return attrs


class CsvUploadRequestSerializer(serializers.Serializer):
    file = serializers.FileField(write_only=True, use_url=False)
